# urgent_handling.py
import logging
from datetime import datetime
from typing import List, Dict, Any
from app.utils.time_utils import epoch_to_datetime, format_datetime_for_display

# Get module-specific logger without configuring at module level
logger = logging.getLogger(__name__)

def reduce_non_productive_time(
    jobs: List[Dict[str, Any]], 
    buffer_threshold: float = 8, 
    reduction_factor: float = 0.5
) -> List[Dict[str, Any]]:
    """
    Reduce setting and break hours for urgent jobs below buffer threshold.
    
    Args:
        jobs: List of job dictionaries
        buffer_threshold: Threshold in hours below which a job is considered urgent
        reduction_factor: Factor by which to reduce non-productive time (0-1)
        
    Returns:
        Updated jobs list with reduced non-productive time for urgent jobs
        
    Raises:
        ValueError: If reduction_factor is not between 0 and 1
    """
    if not isinstance(jobs, list):
        logger.error("Jobs input must be a list")
        return []
        
    if not 0 <= reduction_factor <= 1:
        raise ValueError(f"reduction_factor must be between 0 and 1, got {reduction_factor}")
        
    if buffer_threshold < 0:
        logger.warning(f"buffer_threshold is negative ({buffer_threshold}), using absolute value")
        buffer_threshold = abs(buffer_threshold)
    
    urgent_jobs_count = 0
    total_time_saved = 0.0
    
    for job in jobs:
        if not isinstance(job, dict):
            logger.warning("Skipping non-dict job entry")
            continue
            
        # Skip jobs without buffer_hours
        buffer_hours = job.get('buffer_hours')
        if buffer_hours is None:
            continue
            
        try:
            buffer_hours = float(buffer_hours)
        except (ValueError, TypeError):
            logger.warning(f"Invalid buffer_hours for job {job.get('job_id', 'unknown')}: {buffer_hours}")
            continue
            
        # Check if the job is urgent based on buffer threshold
        if buffer_hours < buffer_threshold:
            # Get current non-productive time components
            setting_hours = job.get('setting_hours', 0)
            break_hours = job.get('break_hours', 0)
            no_prod = job.get('no_prod', 0)
            
            # Validate and convert to float
            try:
                setting_hours = float(setting_hours) if setting_hours is not None else 0
                break_hours = float(break_hours) if break_hours is not None else 0
                no_prod = float(no_prod) if no_prod is not None else 0
            except (ValueError, TypeError):
                logger.warning(f"Invalid non-productive time values for job {job.get('job_id', 'unknown')}")
                continue
            
            # Calculate total non-productive time
            total_non_prod = setting_hours + break_hours + no_prod
            
            if total_non_prod > 0:
                # Calculate time saved by applying reduction factor
                reduced_non_prod = total_non_prod * reduction_factor
                time_saved = total_non_prod - reduced_non_prod
                
                # Distribute the reduction proportionally across components
                if setting_hours > 0:
                    job['setting_hours'] = setting_hours * reduction_factor
                
                if break_hours > 0:
                    job['break_hours'] = break_hours * reduction_factor
            
                if no_prod > 0:
                    job['no_prod'] = no_prod * reduction_factor
                
                # Update the hours_need if it exists by reducing it
                current_hours_need = job.get('hours_need')
                if current_hours_need is not None:
                    try:
                        current_hours_need = float(current_hours_need)
                        job['hours_need'] = max(0, current_hours_need - time_saved)
                    except (ValueError, TypeError):
                        logger.warning(f"Invalid hours_need for job {job.get('job_id', 'unknown')}: {current_hours_need}")
            
                # Update statistics
                urgent_jobs_count += 1
                total_time_saved += time_saved
                
                # Add a flag to indicate this job was expedited
                job['expedited'] = True
                
                # Log the reduction
                logger.info(f"Reduced non-productive time for job {job.get('job_id', 'unknown')}: " 
                           f"saved {time_saved:.1f} hours, buffer: {buffer_hours:.1f} hours")
    
    logger.info(f"Expedited {urgent_jobs_count} urgent jobs, saving {total_time_saved:.1f} total hours")
    return jobs

def should_reschedule(jobs: List[Dict[str, Any]], reduction_percent: int) -> bool:
    """
    Determine if rescheduling is necessary based on how many jobs were modified
    and how significant the reduction is.
    
    Args:
        jobs: List of job dictionaries
        reduction_percent: Percentage used for reduction
        
    Returns:
        True if rescheduling is recommended
    """
    if not isinstance(jobs, list) or not jobs:
        return False
        
    if not isinstance(reduction_percent, (int, float)):
        logger.warning(f"Invalid reduction_percent: {reduction_percent}, using 0")
        reduction_percent = 0
    
    # Count late jobs using multiple criteria
    late_jobs = []
    for job in jobs:
        if not isinstance(job, dict):
            continue
            
        # Check various indicators of lateness
        bal_hr = job.get('bal_hr', 0)
        buffer_status = job.get('buffer_status', '')
        buffer_hours = job.get('buffer_hours', float('inf'))
        
        try:
            bal_hr = float(bal_hr) if bal_hr is not None else 0
            buffer_hours = float(buffer_hours) if buffer_hours is not None else float('inf')
        except (ValueError, TypeError):
            continue
            
        if (bal_hr < 0 or 
            buffer_status == 'Late' or 
            (buffer_hours != float('inf') and buffer_hours < 0)):
            late_jobs.append(job)
    
    total_jobs = len(jobs)
    late_ratio = len(late_jobs) / total_jobs if total_jobs > 0 else 0
    
    # If more than 10% of jobs are late and reduction is significant, recommend rescheduling
    if late_ratio > 0.1 and reduction_percent >= 50:
        logger.info(f"Recommending reschedule: {len(late_jobs)}/{total_jobs} jobs late ({late_ratio:.1%}), "
                   f"reduction: {reduction_percent}%")
        return True
    
    # If any job has significant non-productive time (>20% of total), recommend rescheduling
    for job in late_jobs:
        try:
            processing_time = job.get('processing_time', 0)
            processing_time = float(processing_time) if processing_time is not None else 0
            
            if processing_time <= 0:
            continue
            
            setup_time = float(job.get('setup_time', 0) or 0)
            break_time = float(job.get('break_time', 0) or 0)
            no_prod_time = float(job.get('no_prod_time', 0) or 0)
            
            nonprod_time = setup_time + break_time + no_prod_time
            nonprod_ratio = nonprod_time / processing_time
            
            if nonprod_ratio > 0.2:
                logger.info(f"Recommending reschedule: job {job.get('job_id', 'unknown')} has "
                           f"{nonprod_ratio:.1%} non-productive time")
            return True
        except (ValueError, TypeError, ZeroDivisionError):
            continue
    
    return False 