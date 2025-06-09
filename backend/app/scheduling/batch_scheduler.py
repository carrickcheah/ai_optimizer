#!/usr/bin/env python3

from typing import List, Dict, Any
import time
import logging

try:
    from .cpsat_solver import schedule_jobs
except ImportError:
    try:
        from app.scheduling.cpsat_solver import schedule_jobs
    except ImportError:
        from backend.app.scheduling.cpsat_solver import schedule_jobs

logger = logging.getLogger(__name__)

def batch_schedule_jobs(jobs: List[Dict], machines: List[str], setup_times: Dict, 
                       batch_size: int = 50) -> Dict[str, Any]:
    """
    PRODUCTION: Schedule jobs in small batches to work around CP-SAT batch size limitations.
    
    Args:
        jobs: List of job dictionaries
        machines: List of machine names
        setup_times: Setup times dictionary
        batch_size: Size of each batch (default 5 based on testing)
    
    Returns:
        Combined results from all batches
    """
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
        
        # Schedule batch
        try:
            batch_result = schedule_jobs(
                batch_jobs,
                machines,
                setup_times,
                time_limit_seconds=60,
                max_jobs=len(batch_jobs),
                planning_horizon_days=60
            )
            
            scheduled_in_batch = 0
            
            if batch_result and isinstance(batch_result, dict):
                # Convert CP-SAT format to our format
                for machine, job_tuples in batch_result.items():
                    for job_tuple in job_tuples:
                        if len(job_tuple) >= 3:
                            job_id = job_tuple[0]
                            start_time_epoch = job_tuple[1]
                            end_time_epoch = job_tuple[2]
                            
                            # Find original job data
                            original_job = next((j for j in batch_jobs if j.get('job_id') == job_id), None)
                            if original_job:
                                all_scheduled_jobs[job_id] = {
                                    'machine': machine,
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
    batch_result = batch_schedule_jobs(jobs, machines, setup_times, batch_size=3)  # Smaller batches for better success
    
    # Extract scheduled jobs from batch result
    for job_id, job_data in batch_result.items():
        if job_id != '_metadata':
            all_scheduled_jobs[job_id] = job_data
            total_scheduled += 1
    
    logger.info(f"Strategy 1 completed: {total_scheduled} jobs scheduled from batch processing")
    
    # Strategy 2: Single job fallback for remaining jobs with better constraint handling
    unscheduled_jobs = [job for job in jobs if job.get('job_id', '') not in all_scheduled_jobs]
    logger.info(f"Strategy 2: Single job fallback for {len(unscheduled_jobs)} remaining jobs")
    
    for i, job in enumerate(unscheduled_jobs[:100]):  # Limit to prevent infinite processing
        try:
            # Use CP-SAT for single job scheduling with working hours constraints
            single_job_result = schedule_jobs([job], machines, setup_times, 
                                            time_limit_seconds=30,  # Reduced time limit for single jobs
                                            max_jobs=1, 
                                            planning_horizon_days=30)
            
            if single_job_result and isinstance(single_job_result, dict):
                # Convert CP-SAT format to our format
                for machine, job_tuples in single_job_result.items():
                    for job_tuple in job_tuples:
                        if len(job_tuple) >= 3:
                            job_id = job_tuple[0]
                            start_time_epoch = job_tuple[1]
                            end_time_epoch = job_tuple[2]
                            
                            if job_id not in all_scheduled_jobs:
                                all_scheduled_jobs[job_id] = {
                                    'machine': machine,
                                    'start': start_time_epoch,
                                    'end': end_time_epoch,
                                    'original_job': job
                                }
                                total_scheduled += 1
                                break
            
        except Exception as e:
            logger.debug(f"Single job scheduling failed for {job.get('job_id', 'unknown')}: {e}")
            continue
    
    logger.info(f"Strategy 2 completed: {total_scheduled} total jobs scheduled")
    
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