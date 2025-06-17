#!/usr/bin/env python3

from typing import List, Dict, Any
import time
import logging
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

try:
    from .greedy_solver import greedy_schedule
except ImportError:
    try:
        from app.scheduling.greedy_solver import greedy_schedule
    except ImportError:
        from backend.app.scheduling.greedy_solver import greedy_schedule

logger = logging.getLogger(__name__)

def batch_schedule_jobs(jobs: List[Dict], machines: List[str], setup_times: Dict, 
                       batch_size: int = None) -> Dict[str, Any]:
    """
    PRODUCTION: Schedule jobs using greedy solver (batching no longer needed).
    
    Args:
        jobs: List of job dictionaries
        machines: List of machine names
        setup_times: Setup times dictionary
        batch_size: Ignored (greedy solver can handle any number of jobs)
    
    Returns:
        Results from greedy scheduler
    """
    # Greedy solver can handle any number of jobs efficiently, no batching needed
    logger.info(f"🔄 Scheduling {len(jobs)} jobs using greedy solver (no batching required)")
    
    try:
        return greedy_schedule(jobs, machines, setup_times, enforce_sequence=True, max_operators=0)
    except Exception as e:
        logger.error(f"❌ GREEDY SCHEDULING FAILED: {e}")
        return {"_metadata": {"total_scheduled": 0, "message": f"Greedy scheduling failed: {e}"}}

def smart_batch_schedule_jobs(jobs: List[Dict], machines: List[str], setup_times: Dict) -> Dict[str, Any]:
    """
    Advanced scheduler using greedy solver (no batching needed).
    
    Args:
        jobs: List of job dictionaries
        machines: List of machine names
        setup_times: Setup times dictionary
    
    Returns:
        Results from greedy scheduler with metadata
    """
    logger.info(f"🔄 Smart scheduling {len(jobs)} jobs using greedy solver")
    
    start_time = time.time()
    
    try:
        # Use greedy solver directly
        schedule_result = greedy_schedule(jobs, machines, setup_times, enforce_sequence=True, max_operators=0)
        
        # Count scheduled jobs
        total_scheduled = sum(len(tasks) for tasks in schedule_result.values() if isinstance(tasks, list))
        
        end_time = time.time()
        elapsed_time = end_time - start_time
        success_rate = (total_scheduled / len(jobs)) * 100 if jobs else 0
        
        logger.info(f"✅ Smart scheduling results: {total_scheduled}/{len(jobs)} jobs scheduled ({success_rate:.1f}%) in {elapsed_time:.2f}s")
        
        # Add metadata to match expected format
        if '_metadata' not in schedule_result:
            schedule_result['_metadata'] = {
                'total_scheduled': total_scheduled,
                'total_jobs': len(jobs),
                'success_rate': success_rate,
                'elapsed_time': elapsed_time,
                'solver_type': 'greedy',
                'message': f"Successfully scheduled {total_scheduled} out of {len(jobs)} jobs using greedy solver"
            }
        
        return schedule_result
        
    except Exception as e:
        logger.error(f"❌ SMART SCHEDULING FAILED: {e}")
        return {
            "_metadata": {
                "total_scheduled": 0,
                "total_jobs": len(jobs),
                "success_rate": 0.0,
                "elapsed_time": time.time() - start_time,
                "solver_type": "greedy",
                "message": f"Smart scheduling failed: {e}"
            }
        }