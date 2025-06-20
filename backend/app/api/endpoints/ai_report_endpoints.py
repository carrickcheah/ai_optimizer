from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from typing import Dict, Any
import logging
import json
import asyncio
import httpx
from datetime import datetime
from pydantic import BaseModel

# Configure logging
logger = logging.getLogger(__name__)

# Create router
router = APIRouter(tags=["ai_report"])

class CachedDataInput(BaseModel):
    """Input model for cached data from frontend."""
    systemLogs: list
    detailedSchedule: list
    ganttPriorityView: list
    ganttResourceView: list
    scheduleOverview: dict

@router.post("/ai-report")
async def generate_ai_report(cached_data: CachedDataInput) -> Dict[str, Any]:
    """
    Generate AI-powered report from cached scheduling data.
    
    Args:
        cached_data: The cached data from the frontend DataCacheContext
    
    Returns:
        Dictionary containing the AI-generated report
    """
    try:
        # Import here to avoid circular imports
        try:
            from app.llm_integration.llm import get_report_generator
        except ImportError as e:
            logger.error(f"Import error: {e}")
            return _generate_fallback_report(str(e))
        
        logger.info("Generating AI report from cached data...")
        
        # Convert the cached data to the format expected by the LLM
        all_data = {
            'systemLogs': cached_data.systemLogs,
            'detailedSchedule': cached_data.detailedSchedule,
            'ganttPriorityView': cached_data.ganttPriorityView,
            'ganttResourceView': cached_data.ganttResourceView,
            'scheduleOverview': cached_data.scheduleOverview
        }
        
        # Try to generate AI report
        try:
            report_generator = get_report_generator()
            ai_report = await report_generator.generate_comprehensive_report(all_data)
            logger.info("✅ Successfully generated AI report from cached data")
            return ai_report
            
        except Exception as llm_error:
            logger.warning(f"LLM generation failed, using fallback: {llm_error}")
            report_generator = get_report_generator()
            fallback_report = report_generator.generate_fallback_report(all_data)
            return fallback_report
            
    except Exception as e:
        logger.error(f"❌ Error generating AI report: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error generating AI report: {str(e)}")

@router.post("/ai-report-stream")
async def generate_ai_report_stream(cached_data: CachedDataInput):
    """
    Generate AI-powered report with streaming response (Server-Sent Events).
    
    Args:
        cached_data: The cached data from the frontend DataCacheContext
    
    Returns:
        Streaming response with real-time AI generation
    """
    async def generate_stream():
        try:
            # Import here to avoid circular imports
            try:
                from app.llm_integration.llm import DeepSeekClient
            except ImportError as e:
                logger.error(f"Import error: {e}")
                yield f"data: {json.dumps({'error': str(e)})}\n\n"
                return
            
            logger.info("Starting streaming AI report generation...")
            
            # Send initial status
            yield f"data: {json.dumps({'status': 'starting', 'message': 'Initializing AI analysis...'})}\n\n"
            await asyncio.sleep(0.1)
            
            # Convert the cached data to the format expected by the LLM
            all_data = {
                'systemLogs': cached_data.systemLogs,
                'detailedSchedule': cached_data.detailedSchedule,
                'ganttPriorityView': cached_data.ganttPriorityView,
                'ganttResourceView': cached_data.ganttResourceView,
                'scheduleOverview': cached_data.scheduleOverview
            }
            
            yield f"data: {json.dumps({'status': 'analyzing', 'message': 'Analyzing production data...'})}\n\n"
            await asyncio.sleep(0.1)
            
            # Initialize the client and generate report with streaming
            try:
                client = DeepSeekClient()
                
                yield f"data: {json.dumps({'status': 'generating', 'message': 'Generating AI insights...'})}\n\n"
                await asyncio.sleep(0.1)
                
                # Create the analysis prompt
                prompt = client._create_analysis_prompt(
                    all_data.get('systemLogs', []),
                    {'jobs': all_data.get('detailedSchedule', [])},
                    {
                        'priority_view': all_data.get('ganttPriorityView', []),
                        'resource_view': all_data.get('ganttResourceView', [])
                    },
                    all_data.get('scheduleOverview', {})
                )
                
                # Make streaming API request
                async with httpx.AsyncClient() as http_client:
                    async with http_client.stream(
                        "POST",
                        f"{client.base_url}/chat/completions",
                        headers=client.headers,
                        json={
                            "model": client.model,
                            "messages": [
                                {
                                    "role": "system",
                                    "content": """You are an AI scheduling analyst. Analyze production scheduling data and generate a comprehensive report with:
1. Executive Summary (key findings, system health)
2. Performance Metrics (completion rates, efficiency)
3. Issues & Bottlenecks (problems detected)
4. Recommendations (actionable improvements)
5. Detailed Analysis (in-depth findings)

Format the report in clear sections with bullet points. Be specific with numbers and percentages."""
                                },
                                {
                                    "role": "user",
                                    "content": prompt
                                }
                            ],
                            "temperature": 0.7,
                            "max_tokens": 4000,
                            "stream": True
                        },
                        timeout=120.0
                    ) as response:
                        
                        if response.status_code != 200:
                            yield f"data: {json.dumps({'error': f'API request failed with status {response.status_code}'})}\n\n"
                            return
                        
                        # Stream the response word by word
                        async for line in response.aiter_lines():
                            if line.startswith("data: "):
                                data_str = line[6:]  # Remove "data: " prefix
                                if data_str.strip() == "[DONE]":
                                    yield f"data: {json.dumps({'status': 'completed', 'message': 'Report generation completed!'})}\n\n"
                                    break
                                try:
                                    data = json.loads(data_str)
                                    if 'choices' in data and len(data['choices']) > 0:
                                        delta = data['choices'][0].get('delta', {})
                                        if 'content' in delta:
                                            # Send each chunk of content
                                            yield f"data: {json.dumps({'content': delta['content']})}\n\n"
                                except json.JSONDecodeError:
                                    continue
                        
                logger.info("✅ Successfully completed streaming AI report")
                
            except Exception as llm_error:
                logger.warning(f"LLM generation failed: {llm_error}")
                yield f"data: {json.dumps({'error': f'AI generation failed: {str(llm_error)}'})}\n\n"
                
        except Exception as e:
            logger.error(f"❌ Error in streaming AI report: {str(e)}")
            yield f"data: {json.dumps({'error': str(e)})}\n\n"
    
    return StreamingResponse(
        generate_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "*"
        }
    )

def _generate_fallback_report(error_message: str) -> Dict[str, Any]:
    """Generate a basic fallback report when AI generation fails."""
    return {
        "status": "fallback",
        "report": {
            "executive_summary": f"""AI Report Generation Status
            
Status: Service temporarily unavailable
Error: {error_message}
Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

This is a fallback report. Please ensure:
1. DeepSeek API key is configured
2. All dependencies are installed
3. Database connection is working""",
            
            "performance_metrics": "Metrics unavailable - AI analysis required",
            "issues_bottlenecks": "Issue analysis unavailable - AI analysis required", 
            "recommendations": "Recommendations unavailable - AI analysis required",
            "detailed_analysis": "Detailed analysis unavailable - AI analysis required",
            "generated_at": datetime.now().isoformat()
        },
        "metadata": {
            "generated_at": datetime.now().isoformat(),
            "error": error_message
        }
    }

@router.get("/health")
async def ai_report_health() -> Dict[str, str]:
    """Health check endpoint for AI report service."""
    try:
        from app.llm_integration.llm import get_report_generator
        # Try to initialize the report generator
        get_report_generator()
        return {
            "status": "healthy",
            "service": "ai_report_endpoints",
            "llm_status": "available"
        }
    except Exception as e:
        return {
            "status": "degraded",
            "service": "ai_report_endpoints",
            "llm_status": "unavailable",
            "error": str(e)
        }