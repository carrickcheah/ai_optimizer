"""
Functions for handling setup times and schedule time adjustments.

This module manages the critical timing aspects of the production planning system:
1. Standardized field access for start date epochs (handling name inconsistencies)  
2. Schedule time calculations and adjustments based on constraints
3. Buffer time calculations between job completion and deadlines
4. Schedule visualization preparation

The overall workflow is:
- Extract scheduled times from the optimized solution
- Group jobs by family and process sequence
- Apply time shifts based on START_DATE constraints
- Calculate buffer hours between job completion and deadline
- Categorize buffer status for visualization
"""
import pandas as pd
from datetime import datetime
import logging
from typing import List, Dict, Any, Optional, Union
from collections import defaultdict

from app.utils.time_utils import (
    epoch_to_datetime, 
    datetime_to_epoch, 
    format_datetime_for_display, 
    validate_timestamp
)
from app.scheduling.scheduler_utils import extract_job_family, extract_process_number

# Get module-specific logger without configuring at module level
logger = logging.getLogger(__name__)

def get_start_date_epoch(job: Dict[str, Any]) -> Optional[Union[int, float]]:
    """
    Standardized accessor for START_DATE_EPOCH field that handles both naming variants.
    Always use this function instead of accessing START_DATE_EPOCH or START_DATE _EPOCH directly.
    
    Args:
        job: Job dictionary
        
    Returns:
        The start date epoch value or None if not present/valid
    """
    if not isinstance(job, dict):
        logger.warning(f"Job must be a dictionary, got {type(job)}")
        return None
        
    # Check all possible field naming variations
    possible_field_names = [
        'START_DATE_EPOCH', 
        'START_DATE _EPOCH', 
        'start_date_epoch', 
        'start_date _epoch',
        'start_date_input_epoch'
    ]
    
    for field_name in possible_field_names:
        if field_name in job and job[field_name] is not None and not pd.isna(job[field_name]):
            value = job[field_name]
            # Validate the timestamp to ensure it's not a small value like a job ID
            if validate_timestamp(value):
                return value
            else:
                logger.warning(f"Rejected invalid {field_name} value: {value} for job ID {job.get('job_id', 'unknown')}")
    
    return None

def is_valid_timestamp(timestamp: Any) -> bool:
    """
    Check if a timestamp is valid for calculations.
    
    Args:
        timestamp: Value to check
        
    Returns:
        True if timestamp is valid, False otherwise
    """
    return (timestamp is not None and 
            not pd.isna(timestamp) and 
            isinstance(timestamp, (int, float)))

def get_buffer_status(buffer_hours: float) -> str:
    """Get status category based on buffer hours.
    
    Args:
        buffer_hours: The buffer time in hours between job completion and deadline.
            Negative values indicate the job will be late by that many hours.
    
    Returns:
        Status category for visualization:
            "Late" - Job will be late (negative buffer)
            "Critical" - Less than 8 hours buffer
            "Warning" - Less than 24 hours buffer
            "Caution" - Less than 72 hours buffer
            "OK" - 72 hours or more buffer
    """
    if not isinstance(buffer_hours, (int, float)):
        try:
            buffer_hours = float(buffer_hours)
        except (ValueError, TypeError):
            logger.warning(f"Invalid buffer_hours value: {buffer_hours}")
            return "Unknown"
    
    if buffer_hours < 0:
        return "Late"
    elif buffer_hours < 8:
        return "Critical"
    elif buffer_hours < 24:
        return "Warning"
    elif buffer_hours < 72:
        return "Caution"
    else:
        return "OK"

def add_schedule_times_and_buffer(jobs: List[Dict[str, Any]], schedule: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Add schedule times (START_TIME and END_TIME) to job dictionaries and
    calculate the buffer time (BAL_HR) between job completion and deadline.
    Also adjusts times for dependent processes to maintain proper sequence.
    
    This is a central function in the production planning workflow that:
    1. Extracts the scheduled start/end times for each job from the optimizer solution
    2. Groups jobs by family to handle related processes
    3. Applies time shift adjustments based on START_DATE constraints
    4. Calculates buffer hours between job completion and deadline
    5. Adds status indicators for buffer visualization
    
    Each job's job_id follows a pattern that includes process number information,
    which is used to identify related jobs that must be processed in sequence.
    
    Args:
        jobs: List of job dictionaries, each with job_id
        schedule: Schedule as {machine: [(job_id, start, end, priority), ...]}
        
    Returns:
        Updated jobs list with START_TIME, END_TIME, and BAL_HR added
    """
    if not isinstance(jobs, list):
        logger.error("Jobs must be a list")
        return []
        
    if not isinstance(schedule, dict):
        logger.error("Schedule must be a dictionary")
        return jobs
    
    logger.info(f"Processing schedule times and buffer calculations for {len(jobs)} jobs")
    
    # STEP 1: Extract job start/end times from the scheduling solution and store in a dictionary
    times = {}
    for machine, tasks in schedule.items():
        if not isinstance(tasks, list):
            logger.warning(f"Tasks for machine {machine} must be a list, got {type(tasks)}")
            continue
            
        for task in tasks:
            if not isinstance(task, (tuple, list)) or len(task) < 3:
                logger.warning(f"Invalid task format for machine {machine}: {task}")
                continue
                
            # Handle both old format (4-tuple) and new format (5-tuple with additional params)
            job_id = task[0]
            start = task[1]
            end = task[2]
            
            if not job_id or not isinstance(start, (int, float)) or not isinstance(end, (int, float)):
                logger.warning(f"Invalid task data: job_id={job_id}, start={start}, end={end}")
                continue
                
            # Store the start and end times for each job
            times[job_id] = (start, end)
            
            # Store additional timing information if available
            if len(task) >= 5 and isinstance(task[4], dict):
                additional_params = task[4]
                for job in jobs:
                    if job.get('job_id') == job_id:
                        # Store actual timing values from scheduler
                        for param_key, param_value in additional_params.items():
                            if param_key.endswith('_time') and isinstance(param_value, (int, float)) and param_value > 0:
                                job[f'actual_{param_key}'] = param_value
                
    # STEP 2: Group jobs by family and sequence number
    family_processes = defaultdict(list)
    for job in jobs:
        if not isinstance(job, dict) or 'job_id' not in job:
            logger.warning("Skipping invalid job entry")
            continue
            
        job_id = job['job_id']
        family = extract_job_family(job_id)
        seq_num = extract_process_number(job_id)
        
        family_processes[family].append((seq_num, job_id, job))
    
    # Sort jobs within each family by their sequence number to maintain proper order
    for family in family_processes:
        family_processes[family].sort(key=lambda x: x[0])
    
    # STEP 3: Calculate time shifts needed to honor START_DATE constraints
    family_time_shifts = {}
    
    for family, processes in family_processes.items():
        for seq_num, job_id, job in processes:
            start_date_epoch = get_start_date_epoch(job)
            
            if start_date_epoch is not None and job_id in times:
                scheduled_start = times[job_id][0]
                requested_start = start_date_epoch
                        
                time_shift = None
                if requested_start is not None:
                    time_shift = scheduled_start - requested_start
                    
                # For each family, we keep track of the largest shift needed
                if family not in family_time_shifts or abs(time_shift) > abs(family_time_shifts[family]):
                    family_time_shifts[family] = time_shift
                
                if time_shift is not None:
                    logger.debug(f"Family {family} has START_DATE constraint for {job_id}: "
                              f"shift={time_shift/3600:.1f} hours")
    
    # STEP 4: Apply time shifts to jobs to meet fixed start date constraints
    job_adjustments = {}
    
    for family, time_shift in family_time_shifts.items():
        # Skip negligible time shifts (less than 1 minute)
        if abs(time_shift) < 60:
            continue
            
        logger.info(f"Applying time shift of {time_shift/3600:.1f} hours to family {family} for visualization")
        
        # Process all jobs in this family
        for seq_num, job_id, job_data in family_processes[family]:
            if job_id in times:
                original_start, original_end = times[job_id]
                
                new_start = original_start - time_shift 
                new_end = original_end - time_shift
                
                job_adjustments[job_id] = (new_start, new_end)
                logger.debug(f"  Adjusted {job_id} from {original_start}-{original_end} to {new_start}-{new_end}")

    # STEP 5: Add final scheduled times and calculate buffer
    for job in jobs:
        if not isinstance(job, dict) or 'job_id' not in job:
            continue
            
        job_id = job['job_id']
        
        # Use adjusted times if they exist, otherwise use original scheduled times
        if job_id in job_adjustments:
            job['start_time'], job['end_time'] = job_adjustments[job_id]
        elif job_id in times:
            job['start_time'], job['end_time'] = times[job_id]
        else:
            # If job was not scheduled, set times to None
            job['start_time'] = None
            job['end_time'] = None
            logger.debug(f"Job {job_id} not found in schedule, times set to None")

        # Calculate buffer time (bal_hr) between scheduled end and due date
        if is_valid_timestamp(job.get('end_time')) and is_valid_timestamp(job.get('lcd_date_epoch')):
            try:
                buffer_seconds = job['lcd_date_epoch'] - job['end_time']
                job['buffer_hours'] = buffer_seconds / 3600
                
                # Log buffer calculation for debugging
                original_lcd = job.get('lcd_date_original', job.get('lcd_date_epoch'))
                lcd_dt_str = format_datetime_for_display(epoch_to_datetime(original_lcd)) if original_lcd else "N/A"
                end_dt_str = format_datetime_for_display(epoch_to_datetime(job['end_time']))
                
                logger.debug(f"Job {job_id}: end_time={end_dt_str}, lcd_date={lcd_dt_str}, "
                           f"Buffer={job['buffer_hours']:.1f} hrs")
            except (TypeError, ValueError) as e:
                logger.warning(f"Error calculating buffer for job {job_id}: {e}")
                job['buffer_hours'] = float('inf')
        else:
            job['buffer_hours'] = float('inf')
            logger.debug(f"Job {job_id}: Missing end_time or lcd_date, buffer set to infinity")
            
        # Add buffer status for visualization
        job['buffer_status'] = get_buffer_status(job['buffer_hours'])

        # Add formatted dates for display purposes
        try:
            if job.get('start_time') is not None:
                job['start_time_str'] = format_datetime_for_display(epoch_to_datetime(job['start_time']))
            if job.get('end_time') is not None:
                job['end_time_str'] = format_datetime_for_display(epoch_to_datetime(job['end_time']))
            if job.get('lcd_date_epoch') is not None:
                job['lcd_date_str'] = format_datetime_for_display(epoch_to_datetime(job['lcd_date_epoch']))
        except Exception as e:
            logger.warning(f"Error formatting display dates for job {job_id}: {e}")

    logger.info("Finished adding schedule times and calculating buffer hours for all jobs")
    return jobs

def apply_sequence_constraints(jobs: List[Dict[str, Any]], schedule: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Apply sequence constraints based on job family and process numbering.
    
    This function ensures that jobs within the same family are scheduled in 
    the order specified by their process numbers. If a job in a sequence needs
    to be rescheduled, all subsequent jobs in the sequence are also adjusted.
    
    Args:
        jobs: List of job dictionaries, each with job_id
        schedule: Schedule as {machine: [(job_id, start, end, priority), ...]}
        
    Returns:
        Updated job list with adjusted times based on sequence constraints
    """
    logger.info("Applying sequence constraints based on job family and process numbers")
    
    if not isinstance(jobs, list) or not isinstance(schedule, dict):
        logger.error("Invalid input types for apply_sequence_constraints")
        return jobs if isinstance(jobs, list) else []
    
    # Extract start/end times from schedule
    times = {}
    for machine, scheduled_jobs in schedule.items():
        if not isinstance(scheduled_jobs, list):
            continue
            
        for job_tuple in scheduled_jobs:
            if isinstance(job_tuple, (tuple, list)) and len(job_tuple) >= 3:
                job_id, start_time, end_time = job_tuple[0:3]
                if job_id and isinstance(start_time, (int, float)) and isinstance(end_time, (int, float)):
                    times[job_id] = (start_time, end_time)
    
    # Group jobs by family and sort by process number
    family_processes = defaultdict(list)
    job_adjustments = {}
    
    for job in jobs:
        if not isinstance(job, dict) or 'job_id' not in job:
            continue
            
        job_id = job.get('job_id')
        if not job_id or job_id not in times:
            continue
            
        if job.get('job_dependency') != 1:
            # Skip jobs with no dependency flag
            continue
            
        family = extract_job_family(job_id)
        seq_num = extract_process_number(job_id)
        
        if seq_num == 999:
            # Skip jobs where we couldn't determine the sequence
            continue
            
        family_processes[family].append((seq_num, job_id, job))
    
    # Process each family
    for family in family_processes:
        processes = sorted(family_processes[family], key=lambda x: x[0])
        
        # Check for START_DATE constraints first
        start_date_constraint = None
        for seq_num, job_id, job_data_item in processes: # Renamed job to job_data_item to avoid conflict
            start_date_epoch = get_start_date_epoch(job_data_item) # Use job_data_item
            
            if start_date_epoch is not None and job_id in times:
                scheduled_start = times[job_id][0]
                
                if scheduled_start < start_date_epoch:
                    time_shift = start_date_epoch - scheduled_start
                    if time_shift > 0:
                        start_date_constraint = {
                            'job_id': job_id,
                            'time_shift': time_shift
                        }
                        logger.info(f"Family {family} has START_DATE constraint for {job_id}: "
                                  f"scheduled_start={scheduled_start}, constraint={start_date_epoch}, "
                                  f"shift={time_shift}")
                        break 
        
        # Apply the time shift to all jobs in the family if needed
        if start_date_constraint:
            time_shift = start_date_constraint['time_shift']
            start_job_id = start_date_constraint['job_id']
            start_index = next((i for i, (_, jid, _) in enumerate(processes) if jid == start_job_id), None)
            
            if start_index is not None:
                for seq_num, job_id, job_data_item_again in processes[start_index:]: # Renamed job to job_data_item_again
                    if job_id in times:
                        original_start, original_end = times[job_id]
                        new_start = original_start + time_shift
                        new_end = original_end + time_shift
                        
                        job_adjustments[job_id] = (new_start, new_end)
                        logger.debug(f"  Adjusted {job_id} from {original_start}-{original_end} to {new_start}-{new_end}")
    
    # Apply adjustments to jobs list
    for job_item_final in jobs: # Renamed job to job_item_final
        if not isinstance(job_item_final, dict) or 'job_id' not in job_item_final:
            continue
            
        job_id = job_item_final['job_id']
        
        if job_id in job_adjustments:
            job_item_final['start_time'], job_item_final['end_time'] = job_adjustments[job_id]
        elif job_id in times:
            job_item_final['start_time'], job_item_final['end_time'] = times[job_id]
            
        # Add buffer_hours if lcd_date and end_time are available
        if 'lcd_date_epoch' in job_item_final and 'end_time' in job_item_final and job_item_final['end_time'] is not None:
            try:
                end_dt = datetime.fromtimestamp(job_item_final['end_time'])
                lcd_dt = datetime.fromtimestamp(job_item_final['lcd_date_epoch'])
                end_dt_str = end_dt.strftime('%Y-%m-%d %H:%M')
                lcd_dt_str = lcd_dt.strftime('%Y-%m-%d %H:%M')
                
                job_item_final['buffer_hours'] = max(0, (job_item_final['lcd_date_epoch'] - job_item_final['end_time']) / 3600)
                logger.debug(f"Job {job_id}: end_time={end_dt_str}, lcd_date={lcd_dt_str}, "
                           f"Buffer={job_item_final['buffer_hours']:.1f} hrs")
            except (ValueError, TypeError, OSError) as e:
                logger.warning(f"Error calculating buffer for job {job_id}: {e}")
                job_item_final['buffer_hours'] = float('inf')
        else:
            job_item_final['buffer_hours'] = float('inf')
            logger.debug(f"Job {job_id}: Missing end_time or lcd_date, buffer set to infinity")
    
    return jobs

if __name__ == '__main__':
    pass 