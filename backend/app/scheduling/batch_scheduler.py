#!/usr/bin/env python3

from typing import List, Dict, Any
import time
import logging
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

try:
    from .cpsat_solver import schedule_jobs
except ImportError:
    try:
        from app.scheduling.cpsat_solver import schedule_jobs
    except ImportError:
        from backend.app.scheduling.cpsat_solver import schedule_jobs

logger = logging.getLogger(__name__)

def batch_schedule_jobs(jobs: List[Dict], machines: List[str], setup_times: Dict, 
                       batch_size: int = None) -> Dict[str, Any]:
    """
    PRODUCTION: Schedule jobs in small batches to work around CP-SAT batch size limitations.
    
    Args:
        jobs: List of job dictionaries
        machines: List of machine names
        setup_times: Setup times dictionary
        batch_size: Size of each batch (from .env CPSAT_BATCH_SIZE)
    
    Returns:
        Combined results from all batches
    """
    # Get batch size from environment
    if batch_size is None:
        batch_size_env = os.getenv('CPSAT_BATCH_SIZE')
        if not batch_size_env:
            logger.error("❌ MISSING CPSAT_BATCH_SIZE: CPSAT_BATCH_SIZE not set in .env - cannot determine batch size")
            return {"_metadata": {"total_scheduled": 0, "message": "Missing CPSAT_BATCH_SIZE configuration"}}
        
        try:
            batch_size = int(batch_size_env)
            if batch_size <= 0:
                raise ValueError("CPSAT_BATCH_SIZE must be positive")
        except ValueError as e:
            logger.error(f"❌ INVALID CPSAT_BATCH_SIZE: {e}")
            return {"_metadata": {"total_scheduled": 0, "message": f"Invalid CPSAT_BATCH_SIZE configuration: {e}"}}
    
    # Split large job sets into smaller batches for CP-SAT solver
    logger.info(f"BATCH SCHEDULER: Processing {len(jobs)} jobs in batches of {batch_size}")
    
    all_scheduled_jobs = {}
    total_batches = (len(jobs) + batch_size - 1) // batch_size
    successful_batches = 0
    failed_batches = 0
    total_scheduled = 0
    
    start_time = time.time()
    
    for batch_num in range(total_batches):
        # Create batch
        start_idx = batch_num * batch_size
        end_idx = min(start_idx + batch_size, len(jobs))
        batch_jobs = jobs[start_idx:end_idx]
        
        logger.debug(f"Processing batch {batch_num + 1}/{total_batches}: Jobs {start_idx+1}-{end_idx}")
        
        # Schedule batch with proper error handling
        try:
            # Get environment variables with validation
            solver_time_limit = os.getenv('SOLVER_TIME_LIMIT_SECONDS')
            planning_horizon = os.getenv('PLANNING_HORIZON_DAYS')
            
            if not solver_time_limit:
                logger.error("❌ MISSING SOLVER_TIME_LIMIT_SECONDS in .env")
                continue
            if not planning_horizon:
                logger.error("❌ MISSING PLANNING_HORIZON_DAYS in .env")
                continue
                
            batch_result = schedule_jobs(
                batch_jobs,
                machines,
                setup_times,
                time_limit_seconds=int(solver_time_limit),
                planning_horizon_days=int(planning_horizon)
            )
            
            scheduled_in_batch = 0
            
            if batch_result and isinstance(batch_result, dict):
                # Handle new CP-SAT format: job_id -> {machine, start, end, ...}
                for job_id, job_data in batch_result.items():
                    if job_id == '_metadata':
                        continue
                        
                    if isinstance(job_data, dict) and 'machine' in job_data:
                        # New format: direct job data
                        original_job = next((j for j in batch_jobs if j.get('job_id') == job_id), None)
                        if original_job:
                            all_scheduled_jobs[job_id] = {
                                'machine': job_data['machine'],
                                'start': job_data['start'],
                                'end': job_data['end'],
                                'original_job': original_job
                            }
                            scheduled_in_batch += 1
                    elif isinstance(job_data, list):
                        # Old format: machine -> [(job_id, start, end), ...]
                        for job_tuple in job_data:
                            if len(job_tuple) >= 3:
                                tuple_job_id = job_tuple[0]
                                start_time_epoch = job_tuple[1]
                                end_time_epoch = job_tuple[2]
                                
                                original_job = next((j for j in batch_jobs if j.get('job_id') == tuple_job_id), None)
                                if original_job:
                                    all_scheduled_jobs[tuple_job_id] = {
                                        'machine': job_id,  # job_id is actually machine name in old format
                                        'start': start_time_epoch,
                                        'end': end_time_epoch,
                                        'original_job': original_job
                                    }
                                    scheduled_in_batch += 1
                
                if scheduled_in_batch > 0:
                    successful_batches += 1
                    total_scheduled += scheduled_in_batch
                    logger.debug(f"Batch {batch_num + 1} SUCCESS: {scheduled_in_batch}/{len(batch_jobs)} jobs scheduled")
                else:
                    failed_batches += 1
                    logger.debug(f"Batch {batch_num + 1} FAILED: No jobs scheduled")
            else:
                failed_batches += 1
                logger.debug(f"Batch {batch_num + 1} FAILED: Invalid result")
                
        except Exception as e:
            failed_batches += 1
            logger.warning(f"Batch {batch_num + 1} ERROR: {str(e)}")
    
    total_time = time.time() - start_time
    
    # Create summary metadata
    all_scheduled_jobs['_metadata'] = {
        'status': 'BATCH_COMPLETED',
        'solver_time': total_time,
        'total_jobs': len(jobs),
        'total_scheduled': total_scheduled,
        'success_rate': total_scheduled / len(jobs) * 100 if len(jobs) > 0 else 0,
        'total_batches': total_batches,
        'successful_batches': successful_batches,
        'failed_batches': failed_batches,
        'batch_size': batch_size,
        'message': f'Batch processing completed: {total_scheduled}/{len(jobs)} jobs scheduled ({total_scheduled/len(jobs)*100 if len(jobs) > 0 else 0:.1f}%)'
    }
    
    logger.info(f"BATCH RESULTS: {total_scheduled}/{len(jobs)} jobs scheduled ({total_scheduled/len(jobs)*100 if len(jobs) > 0 else 0:.1f}%) in {total_time:.2f}s")
    
    return all_scheduled_jobs

def smart_batch_schedule_jobs(jobs: List[Dict], machines: List[str], setup_times: Dict) -> Dict[str, Any]:
    """
    Advanced batch scheduler with multiple strategies for maximum job scheduling.
    
    Uses intelligent batching to work around CP-SAT limitations while maximizing
    the number of successfully scheduled jobs.
    
    Returns:
        Dict with job_id -> {machine, start, end, original_job} mapping
        Plus _metadata with statistics
    """
    # Multi-strategy scheduler: batch processing + single job fallback
    logger.info("SMART BATCH SCHEDULER: Starting multi-strategy scheduling")
    
    all_scheduled_jobs = {}
    total_scheduled = 0
    start_time = time.time()

    # Strategy 1: Regular batch processing with smaller batches  
    logger.info("Strategy 1: Regular batch processing")
    
    # FIXED: Use CPSAT_BATCH_SIZE instead of BATCH_SIZE
    batch_size_env = os.getenv('CPSAT_BATCH_SIZE')
    if not batch_size_env:
        logger.error("❌ MISSING CPSAT_BATCH_SIZE: CPSAT_BATCH_SIZE not set in .env")
        return {"_metadata": {"total_scheduled": 0, "message": "Missing CPSAT_BATCH_SIZE configuration"}}
    
    try:
        batch_size = int(batch_size_env)
        if batch_size <= 0:
            raise ValueError("CPSAT_BATCH_SIZE must be positive")
    except ValueError as e:
        logger.error(f"❌ INVALID CPSAT_BATCH_SIZE: {e}")
        return {"_metadata": {"total_scheduled": 0, "message": f"Invalid CPSAT_BATCH_SIZE configuration: {e}"}}
    
    batch_result = batch_schedule_jobs(jobs, machines, setup_times, batch_size=batch_size)
    
    # Extract scheduled jobs from batch result
    for job_id, job_data in batch_result.items():
        if job_id != '_metadata':
            all_scheduled_jobs[job_id] = job_data
            total_scheduled += 1
    
    logger.info(f"Strategy 1 completed: {total_scheduled} jobs scheduled from batch processing")
    
    # Strategy 2: DISABLED - Single job scheduling causes too many INFEASIBLE results
    # Individual job scheduling is too restrictive and causes jobs to fail when scheduled in isolation
    logger.info("Strategy 2: DISABLED - Skipping single job fallback to avoid INFEASIBLE results")
    unscheduled_jobs = []
    
    # Get environment variables with validation for Strategy 2
    solver_time_limit_env = os.getenv('SOLVER_TIME_LIMIT_SECONDS')
    planning_horizon_env = os.getenv('PLANNING_HORIZON_DAYS')
    
    if not solver_time_limit_env:
        logger.error("❌ MISSING SOLVER_TIME_LIMIT_SECONDS for Strategy 2")
    elif not planning_horizon_env:
        logger.error("❌ MISSING PLANNING_HORIZON_DAYS for Strategy 2")
    else:
        try:
            solver_time_limit = int(solver_time_limit_env)
            planning_horizon = int(planning_horizon_env)
            
            for i, job in enumerate(unscheduled_jobs[:100]):  # Limit to prevent infinite processing
                try:
                    # Use CP-SAT for single job scheduling with working hours constraints
                    single_job_result = schedule_jobs([job], machines, setup_times, 
                                                    time_limit_seconds=solver_time_limit,
                                                    planning_horizon_days=planning_horizon)
                    
                    if single_job_result and isinstance(single_job_result, dict):
                        # Handle new CP-SAT format: job_id -> {machine, start, end, ...}
                        for result_job_id, job_data in single_job_result.items():
                            if result_job_id == '_metadata':
                                continue
                                
                            if isinstance(job_data, dict) and 'machine' in job_data:
                                # New format: direct job data
                                if result_job_id not in all_scheduled_jobs:
                                    all_scheduled_jobs[result_job_id] = {
                                        'machine': job_data['machine'],
                                        'start': job_data['start'],
                                        'end': job_data['end'],
                                        'original_job': job
                                    }
                                    total_scheduled += 1
                                    break
                            elif isinstance(job_data, list):
                                # Old format: machine -> [(job_id, start, end), ...]
                                for job_tuple in job_data:
                                    if len(job_tuple) >= 3:
                                        tuple_job_id = job_tuple[0]
                                        start_time_epoch = job_tuple[1]
                                        end_time_epoch = job_tuple[2]
                                        
                                        if tuple_job_id not in all_scheduled_jobs:
                                            all_scheduled_jobs[tuple_job_id] = {
                                                'machine': result_job_id,  # result_job_id is machine name in old format
                                                'start': start_time_epoch,
                                                'end': end_time_epoch,
                                                'original_job': job
                                            }
                                            total_scheduled += 1
                                            break
                    
                except Exception as e:
                    logger.debug(f"Single job scheduling failed for {job.get('job_id', 'unknown')}: {e}")
                    continue
                    
        except ValueError as e:
            logger.error(f"❌ INVALID environment variables for Strategy 2: {e}")
    
    # Strategy 2 is disabled, no additional jobs scheduled
    
    end_time = time.time()
    elapsed_time = end_time - start_time
    success_rate = (total_scheduled / len(jobs)) * 100 if jobs else 0
    
    logger.info(f"SMART BATCH RESULTS: {total_scheduled}/{len(jobs)} jobs scheduled ({success_rate:.1f}%) in {elapsed_time:.2f}s")
    
    # Add metadata
    all_scheduled_jobs['_metadata'] = {
        'total_scheduled': total_scheduled,
        'total_jobs': len(jobs),
        'success_rate': success_rate,
        'elapsed_time': elapsed_time,
        'message': f"Successfully scheduled {total_scheduled} out of {len(jobs)} jobs using multi-strategy approach"
    }
    
    return all_scheduled_jobs