from fastapi import APIRouter, HTTPException, Query
from typing import Dict, Any, List, Optional
import os
import logging
from datetime import datetime

# Configure logging
logger = logging.getLogger(__name__)

# Create router without prefix (will be added in main.py)
router = APIRouter(tags=["logs"])

def parse_log_line(line: str) -> Optional[Dict[str, str]]:
    """Parse a single log line into structured data."""
    try:
        # Expected format: TIMESTAMP - MODULE - LEVEL - MESSAGE
        parts = line.split(' - ', 3)
        if len(parts) >= 4:
            return {
                "timestamp": parts[0].strip(),
                "module": parts[1].strip(),
                "level": parts[2].strip(),
                "message": parts[3].strip()
            }
        return None
    except Exception:
        return None

@router.get("/recent")
async def get_recent_logs(
    lines: int = Query(default=100, ge=1, le=1000, description="Number of recent log lines to fetch")
) -> Dict[str, Any]:
    """
    Fetch recent logs from the application log file.
    
    Args:
        lines: Number of recent log lines to return (default: 100, max: 1000)
    
    Returns:
        Dictionary containing log entries and metadata
    """
    try:
        log_file_path = os.path.join(os.path.dirname(__file__), '../../../app.log')
        
        if not os.path.exists(log_file_path):
            logger.warning(f"Log file not found at {log_file_path}")
            return {
                "logs": [],
                "total_lines": 0,
                "message": "Log file not found"
            }
        
        # Read the last N lines from the log file
        with open(log_file_path, 'r', encoding='utf-8') as f:
            all_lines = f.readlines()
        
        # Get the last N lines
        recent_lines = all_lines[-lines:] if len(all_lines) > lines else all_lines
        
        # Parse log lines
        parsed_logs = []
        for line in recent_lines:
            line = line.strip()
            if line:  # Skip empty lines
                parsed = parse_log_line(line)
                if parsed:
                    parsed_logs.append(parsed)
                else:
                    # If parsing fails, include as raw message
                    parsed_logs.append({
                        "timestamp": "",
                        "module": "",
                        "level": "INFO",
                        "message": line
                    })
        
        logger.info(f"✅ Retrieved {len(parsed_logs)} log entries")
        
        return {
            "logs": parsed_logs,
            "total_lines": len(parsed_logs),
            "fetch_time": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"❌ Error fetching logs: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error fetching logs: {str(e)}")

@router.get("/health")
async def logs_health() -> Dict[str, str]:
    """Health check endpoint for logs service."""
    return {
        "status": "healthy",
        "service": "logs_endpoints"
    }