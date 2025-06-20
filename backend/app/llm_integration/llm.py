import os
import json
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime
import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

# Configure logging
logger = logging.getLogger(__name__)

class DeepSeekClient:
    """Client for interacting with DeepSeek API for AI report generation."""
    
    def __init__(self):
        self.api_key = os.getenv('DEEPSEEK_API_KEY')
        if not self.api_key:
            raise ValueError("DEEPSEEK_API_KEY environment variable is not set")
        
        self.base_url = "https://api.deepseek.com/v1"
        self.model = os.getenv('DEEPSEEK_MODEL', 'deepseek-chat')
        self.headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }
        logger.info(f"DeepSeek client initialized with model: {self.model}")
    
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
    async def generate_report(self, 
                            logs_data: List[Dict], 
                            schedule_data: Dict,
                            gantt_data: Dict,
                            overview_data: Dict) -> Dict[str, Any]:
        """
        Generate comprehensive AI report from scheduling data.
        
        Args:
            logs_data: System logs
            schedule_data: Detailed schedule information
            gantt_data: Gantt chart data (priority and resource views)
            overview_data: Schedule overview statistics
            
        Returns:
            Generated report with sections
        """
        try:
            # Prepare the analysis prompt
            prompt = self._create_analysis_prompt(logs_data, schedule_data, gantt_data, overview_data)
            
            # Make API request
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.base_url}/chat/completions",
                    headers=self.headers,
                    json={
                        "model": self.model,
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
                    timeout=60.0
                )
                
                if response.status_code != 200:
                    logger.error(f"DeepSeek API error: {response.status_code} - {response.text}")
                    raise Exception(f"API request failed with status {response.status_code}")
                
                # Handle streaming response
                report_content = ""
                async for line in response.aiter_lines():
                    if line.startswith("data: "):
                        data_str = line[6:]  # Remove "data: " prefix
                        if data_str.strip() == "[DONE]":
                            break
                        try:
                            data = json.loads(data_str)
                            if 'choices' in data and len(data['choices']) > 0:
                                delta = data['choices'][0].get('delta', {})
                                if 'content' in delta:
                                    report_content += delta['content']
                        except json.JSONDecodeError:
                            continue
                
                # Parse and structure the report
                structured_report = self._structure_report(report_content)
                
                logger.info("Successfully generated AI report with streaming")
                return structured_report
                
        except Exception as e:
            logger.error(f"Error generating AI report: {str(e)}")
            raise
    
    def _create_analysis_prompt(self, logs_data: List[Dict], schedule_data: Dict, 
                              gantt_data: Dict, overview_data: Dict) -> str:
        """Create a comprehensive prompt for analysis."""
        
        # Extract key metrics
        total_jobs = len(schedule_data.get('jobs', []))
        error_logs = [log for log in logs_data if log.get('level') == 'ERROR']
        warning_logs = [log for log in logs_data if log.get('level') == 'WARNING']
        
        # Calculate completion metrics
        completed_jobs = sum(1 for job in schedule_data.get('jobs', []) 
                           if job.get('status') == 'completed')
        completion_rate = (completed_jobs / total_jobs * 100) if total_jobs > 0 else 0
        
        prompt = f"""Analyze the following production scheduling data:

SYSTEM OVERVIEW:
- Total Jobs: {total_jobs}
- Completed Jobs: {completed_jobs}
- Completion Rate: {completion_rate:.1f}%
- Total Errors: {len(error_logs)}
- Total Warnings: {len(warning_logs)}

SCHEDULE SUMMARY:
{json.dumps(overview_data, indent=2) if overview_data else 'No overview data available'}

RECENT SYSTEM LOGS (Last 10 entries):
{self._format_logs_for_prompt(logs_data[-10:])}

ERROR SUMMARY:
{self._format_logs_for_prompt(error_logs[-5:])}

Please analyze this data and generate a comprehensive report covering:
1. System health and performance
2. Scheduling efficiency
3. Resource utilization
4. Identified issues and bottlenecks
5. Specific recommendations for improvement

Focus on actionable insights and be specific with metrics."""
        
        return prompt
    
    def _format_logs_for_prompt(self, logs: List[Dict]) -> str:
        """Format logs for inclusion in prompt."""
        if not logs:
            return "No logs available"
        
        formatted = []
        for log in logs:
            timestamp = log.get('timestamp', 'N/A')
            level = log.get('level', 'INFO')
            message = log.get('message', '')
            formatted.append(f"[{timestamp}] {level}: {message}")
        
        return "\n".join(formatted)
    
    def _structure_report(self, report_content: str) -> Dict[str, Any]:
        """Structure the AI-generated report into sections."""
        
        # Default sections
        sections = {
            "executive_summary": "",
            "performance_metrics": "",
            "issues_bottlenecks": "",
            "recommendations": "",
            "detailed_analysis": "",
            "raw_content": report_content,
            "generated_at": datetime.now().isoformat()
        }
        
        # Try to parse sections from the content
        current_section = None
        current_content = []
        
        for line in report_content.split('\n'):
            line = line.strip()
            
            # Detect section headers
            if "executive summary" in line.lower():
                if current_section:
                    sections[current_section] = '\n'.join(current_content)
                current_section = "executive_summary"
                current_content = []
            elif "performance metric" in line.lower():
                if current_section:
                    sections[current_section] = '\n'.join(current_content)
                current_section = "performance_metrics"
                current_content = []
            elif "issue" in line.lower() and "bottleneck" in line.lower():
                if current_section:
                    sections[current_section] = '\n'.join(current_content)
                current_section = "issues_bottlenecks"
                current_content = []
            elif "recommendation" in line.lower():
                if current_section:
                    sections[current_section] = '\n'.join(current_content)
                current_section = "recommendations"
                current_content = []
            elif "detailed analysis" in line.lower():
                if current_section:
                    sections[current_section] = '\n'.join(current_content)
                current_section = "detailed_analysis"
                current_content = []
            elif current_section and line:
                current_content.append(line)
        
        # Save the last section
        if current_section and current_content:
            sections[current_section] = '\n'.join(current_content)
        
        return sections


class SchedulingReportGenerator:
    """Generate various types of reports for scheduling system."""
    
    def __init__(self):
        self.client = DeepSeekClient()
    
    async def generate_comprehensive_report(self, all_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate a comprehensive scheduling report.
        
        Args:
            all_data: Dictionary containing all scheduling data
            
        Returns:
            Structured report dictionary
        """
        try:
            # Extract data components
            logs_data = all_data.get('systemLogs', [])
            schedule_data = {
                'jobs': all_data.get('detailedSchedule', [])
            }
            gantt_data = {
                'priority_view': all_data.get('ganttPriorityView', []),
                'resource_view': all_data.get('ganttResourceView', [])
            }
            overview_data = all_data.get('scheduleOverview', {})
            
            # Generate the report
            report = await self.client.generate_report(
                logs_data=logs_data,
                schedule_data=schedule_data,
                gantt_data=gantt_data,
                overview_data=overview_data
            )
            
            return {
                "status": "success",
                "report": report,
                "metadata": {
                    "generated_at": datetime.now().isoformat(),
                    "data_points_analyzed": {
                        "logs": len(logs_data),
                        "jobs": len(schedule_data.get('jobs', [])),
                        "gantt_priority_items": len(gantt_data.get('priority_view', [])),
                        "gantt_resource_items": len(gantt_data.get('resource_view', []))
                    }
                }
            }
            
        except Exception as e:
            logger.error(f"Failed to generate comprehensive report: {str(e)}")
            return {
                "status": "error",
                "error": str(e),
                "report": {
                    "executive_summary": "Failed to generate report due to an error.",
                    "raw_content": f"Error: {str(e)}"
                }
            }
    
    def generate_fallback_report(self, all_data: Dict[str, Any]) -> Dict[str, Any]:
        """Generate a basic report without LLM when API is unavailable."""
        
        logs_data = all_data.get('systemLogs', [])
        jobs_data = all_data.get('detailedSchedule', [])
        
        # Basic analysis
        total_jobs = len(jobs_data)
        error_count = sum(1 for log in logs_data if log.get('level') == 'ERROR')
        warning_count = sum(1 for log in logs_data if log.get('level') == 'WARNING')
        
        return {
            "status": "fallback",
            "report": {
                "executive_summary": f"""System Status Report (Automated Analysis)
                
Total Jobs Scheduled: {total_jobs}
System Errors: {error_count}
System Warnings: {warning_count}

This is an automated report generated without AI analysis.""",
                
                "performance_metrics": f"""Performance Metrics:
- Total Jobs: {total_jobs}
- Error Rate: {(error_count / len(logs_data) * 100) if logs_data else 0:.1f}%
- Warning Rate: {(warning_count / len(logs_data) * 100) if logs_data else 0:.1f}%""",
                
                "issues_bottlenecks": "AI analysis unavailable. Please check system logs manually.",
                
                "recommendations": "Enable AI analysis for detailed recommendations.",
                
                "detailed_analysis": "Detailed AI analysis requires DeepSeek API access.",
                
                "generated_at": datetime.now().isoformat()
            }
        }


# Singleton instance
_report_generator = None

def get_report_generator() -> SchedulingReportGenerator:
    """Get or create the singleton report generator instance."""
    global _report_generator
    if _report_generator is None:
        _report_generator = SchedulingReportGenerator()
    return _report_generator