# Helper functions for scheduling 

import logging
import re
from typing import Dict, List, Tuple, Any, Optional, Union
from collections import defaultdict

logger = logging.getLogger(__name__)

def extract_process_number(job_id: str) -> int:
    """
    Extract the process sequence number from the new format (e.g., 1 from '1/4' in 'CP08-342-1/4') or return 999 if not found.
    job_id is in the format job_process_code where process_code ends with 'number/total'.
    
    Args:
        job_id: The job identifier string
        
    Returns:
        Process sequence number or 999 if parsing fails
    """
    if not isinstance(job_id, str):
        logger.warning(f"job_id must be string, got {type(job_id)}: {job_id}")
        return 999
        
    try:
        process_code = job_id.split('_', 1)[1]  # Split on first underscore to get PROCESS_CODE
    except IndexError:
        logger.warning(f"Could not extract PROCESS_CODE from job_id {job_id}")
        return 999

    # Look for pattern "number/total" at the end (e.g., "1/4", "2/3")
    match = re.search(r'(\d+)/\d+$', str(process_code))
    if match:
        seq = int(match.group(1))
        return seq
        
    return 999  # Default if parsing fails

def extract_total_processes(job_id: str) -> int:
    """
    Extract the total number of processes from the new format (e.g., 4 from '1/4' in 'CP08-342-1/4') or return 1 if not found.
    This is useful for understanding the full sequence length for a job family.
    
    Args:
        job_id: The job identifier string
        
    Returns:
        Total number of processes or 1 if parsing fails
    """
    if not isinstance(job_id, str):
        logger.warning(f"job_id must be string, got {type(job_id)}: {job_id}")
        return 1
        
    try:
        process_code = job_id.split('_', 1)[1]  # Split on first underscore to get PROCESS_CODE
    except IndexError:
        logger.warning(f"Could not extract PROCESS_CODE from job_id {job_id}")
        return 1

    # Look for pattern "number/total" at the end (e.g., "1/4", "2/3")
    match = re.search(r'\d+/(\d+)$', str(process_code))
    if match:
        total = int(match.group(1))
        return total
        
    return 1  # Default if parsing fails

def extract_job_family(job_id: str, job_id_suffix: Optional[str] = None) -> str:
    """
    Extract the job family from the job_id using the new format (e.g., 'CP33-333' from 'JOST333333_CP33-333-1/4').
    If job_id_suffix is provided, it will be included in the family to distinguish between
    different jobs that share the same process code pattern.
    job_id is in the format PREFIX_FAMILY-PROCESS where PROCESS is 'number/total'.
    
    Args:
        job_id: The job identifier string
        job_id_suffix: Optional suffix to append to family name
        
    Returns:
        Job family string
    """
    if not isinstance(job_id, str):
        logger.warning(f"job_id must be string, got {type(job_id)}: {job_id}")
        if job_id_suffix:
            return f"{job_id}_{job_id_suffix}"
        return str(job_id)
        
    try:
        # Split on first underscore to get the part after the prefix
        process_code = job_id.split('_', 1)[1] if '_' in job_id else job_id
    except IndexError:
        logger.warning(f"Could not extract process_code from job_id {job_id}")
        if job_id_suffix:
            return f"{job_id}_{job_id_suffix}"
        return job_id

    process_code = str(process_code).upper()
    
    # Match everything up to the new format "-number/total"
    match = re.search(r'(.*?)-\d+/\d+$', process_code)
    if match:
        family = match.group(1)
        logger.debug(f"Extracted family {family} from {job_id}")
        if job_id_suffix:
            return f"{family}_{job_id_suffix}"
        return family
    
    # If regex fails, try splitting on the new format pattern
    if re.search(r'-\d+/\d+$', process_code):
        parts = re.split(r'-\d+/\d+$', process_code)
        if len(parts) >= 1:
            family = parts[0]
            logger.debug(f"Extracted family {family} from {job_id} (using split)")
            if job_id_suffix:
                return f"{family}_{job_id_suffix}"
            return family
    
    logger.warning(f"Could not extract family from {job_id}, using full code")
    if job_id_suffix:
        return f"{process_code}_{job_id_suffix}"
    return process_code

def validate_job_data(job: Dict[str, Any]) -> bool:
    """
    Validate that a job dictionary has required fields and valid data types.
    
    Args:
        job: Job dictionary to validate
        
    Returns:
        True if job is valid, False otherwise
    """
    if not isinstance(job, dict):
        logger.error(f"Job must be a dictionary, got {type(job)}")
        return False
        
    # Check required fields
    required_fields = ['job_id']
    for field in required_fields:
        if field not in job or job[field] is None:
            logger.error(f"Job missing required field '{field}': {job}")
            return False
            
    # Validate job_id
    if not isinstance(job['job_id'], str) or not job['job_id'].strip():
        logger.error(f"Invalid job_id: {job.get('job_id')}")
        return False
        
    # Validate numeric fields if present
    numeric_fields = ['hours_need', 'priority', 'processing_time', 'setup_time', 'break_time']
    for field in numeric_fields:
        if field in job and job[field] is not None:
            try:
                float(job[field])
            except (ValueError, TypeError):
                logger.warning(f"Invalid numeric value for {field} in job {job['job_id']}: {job[field]}")
                # Don't fail validation, just warn and let caller handle
                
    return True

def normalize_job_fields(job: Dict[str, Any]) -> Dict[str, Any]:
    """
    Normalize job field names and data types for consistent processing.
    
    Args:
        job: Job dictionary to normalize
        
    Returns:
        Normalized job dictionary
    """
    if not isinstance(job, dict):
        logger.error("Job must be a dictionary")
        return {}
        
    # Create a copy to avoid modifying original
    normalized_job = job.copy()
    
    # Map uppercase fields to lowercase for consistency
    field_mappings = {
        'JOB_ID': 'job_id',
        'RSC_CODE': 'rsc_code',
        'HOURS_NEED': 'hours_need',
        'DAY_NEED': 'day_need',
        'PRIORITY': 'priority',
        'PROCESSING_TIME': 'processing_time',
        'SETUP_TIME': 'setup_time',
        'BREAK_TIME': 'break_time',
        'NO_PROD': 'no_prod'
    }
    
    # Copy uppercase fields to lowercase if they exist and lowercase doesn't
    for upper_field, lower_field in field_mappings.items():
        if upper_field in normalized_job and lower_field not in normalized_job:
            normalized_job[lower_field] = normalized_job[upper_field]
            
    # Normalize numeric fields
    numeric_fields = ['hours_need', 'day_need', 'priority', 'processing_time', 'setup_time', 'break_time', 'no_prod']
    for field in numeric_fields:
        if field in normalized_job and normalized_job[field] is not None:
            try:
                normalized_job[field] = float(normalized_job[field])
            except (ValueError, TypeError):
                logger.warning(f"Could not convert {field} to float for job {normalized_job.get('job_id')}: {normalized_job[field]}")
                
    # Set default values for missing fields
    defaults = {
        'priority': 3,
        'hours_need': 1.0,
        'day_need': None,  # Default to None so HOURS_NEED takes precedence
        'processing_time': 3600,  # 1 hour in seconds
        'setup_time': 0,
        'break_time': 0,
        'no_prod': 0
    }
    
    for field, default_value in defaults.items():
        if field not in normalized_job or normalized_job[field] is None:
            normalized_job[field] = default_value
            
    return normalized_job

def convert_cpsat_to_greedy_format(cpsat_schedule: Dict[str, Any]) -> Dict[str, List[Tuple]]:
    """
    Convert the CP-SAT solver schedule format to the greedy scheduler format.
    The format should be: {machine: [(job_id, start, end, priority, additional_params), ...]}
    
    Args:
        cpsat_schedule: Either CP-SAT format {job_id: {'machine': str, 'start': int, 'end': int, ...}, '_metadata': {...}}
                              or greedy format {machine: [(job_id, start, end, priority), ...]}
    
    Returns:
        Schedule in format {machine: [(job_id, start, end, priority, additional_params), ...]}
    """
    logger.info("Converting CP-SAT schedule format to greedy format")
    
    if not isinstance(cpsat_schedule, dict):
        logger.error(f"Schedule must be a dictionary, got {type(cpsat_schedule)}")
        return {}
    
    # If it's already in the right format (no _metadata), convert tuples to 5-tuples if needed
    if '_metadata' not in cpsat_schedule:
        greedy_format = {}
        for machine, tasks in cpsat_schedule.items():
            if not isinstance(tasks, list):
                logger.warning(f"Tasks for machine {machine} must be a list, got {type(tasks)}")
                continue
                
            greedy_format[machine] = []
            for task in tasks:
                if not isinstance(task, (tuple, list)) or len(task) < 3:
                    logger.warning(f"Invalid task format for machine {machine}: {task}")
                    continue
                    
                # Handle both 4-tuple and 5-tuple formats
                if len(task) == 4:
                    job_id, start, end, priority = task
                    # Validate timestamps
                    if not _is_valid_timestamp(start, job_id, machine, "start"):
                        continue
                    if not _is_valid_timestamp(end, job_id, machine, "end"):
                        continue
                    greedy_format[machine].append((job_id, start, end, priority, {}))
                elif len(task) == 5:
                    job_id, start, end, priority, params = task
                    # Validate timestamps before appending
                    if not _is_valid_timestamp(start, job_id, machine, "start"):
                        continue
                    if not _is_valid_timestamp(end, job_id, machine, "end"):
                        continue
                    greedy_format[machine].append(task)  # Already in correct format
                else:
                    logger.warning(f"Unexpected task format for machine {machine}: {task}")
                    if len(task) >= 3:
                        job_id, start, end = task[:3]
                        priority = task[3] if len(task) > 3 else 3  # Default priority
                        # Validate timestamps
                        if not _is_valid_timestamp(start, job_id, machine, "start"):
                            continue
                        if not _is_valid_timestamp(end, job_id, machine, "end"):
                            continue
                        greedy_format[machine].append((job_id, start, end, priority, {}))
                    else:
                        continue
        return greedy_format
    
    # Create a new schedule without the _metadata
    greedy_format = {}
    
    # Process each job in the CP-SAT schedule
    for job_id, details in cpsat_schedule.items():
        if job_id == '_metadata':
            continue
            
        if not isinstance(details, dict):
            logger.warning(f"Invalid details format for job {job_id}: {details}")
            continue
            
        # Extract required fields
        machine = details.get('machine')
        start = details.get('start')
        end = details.get('end')
        priority = details.get('priority', 3)  # Default to medium priority
        
        if not all(x is not None for x in [machine, start, end]):
            logger.warning(f"Missing required fields for job {job_id}: machine={machine}, start={start}, end={end}")
            continue
            
        # Validate timestamps
        if not _is_valid_timestamp(start, job_id, machine, "start"):
            continue
        if not _is_valid_timestamp(end, job_id, machine, "end"):
            continue
            
        # Initialize machine list if needed
        if machine not in greedy_format:
            greedy_format[machine] = []
            
        # Add the job as a 5-tuple with empty additional params
        greedy_format[machine].append((job_id, start, end, priority, {}))
    
    # Log conversion stats
    total_tasks = sum(len(tasks) for tasks in greedy_format.values())
    logger.info(f"Converted CP-SAT schedule: {total_tasks} tasks scheduled")
    
    return greedy_format

def _is_valid_timestamp(timestamp: Any, job_id: str, machine: str, field_name: str) -> bool:
    """
    Internal helper to validate timestamps and prevent using small integers as timestamps.
    
    Args:
        timestamp: Value to validate
        job_id: Job ID for logging
        machine: Machine name for logging
        field_name: Field name for logging
        
    Returns:
        True if timestamp is valid, False otherwise
    """
    if not isinstance(timestamp, (int, float)):
        logger.error(f"Invalid {field_name} time type for job {job_id} on machine {machine}: {type(timestamp)}")
        return False
        
    if timestamp < 1000:
        logger.error(f"Invalid {field_name} time detected: {timestamp} for job {job_id} on machine {machine}. "
                    "Value too small to be a timestamp.")
        return False
        
    return True

def build_schedule_from_logs(cpsat_schedule: Dict[str, Any]) -> Dict[str, List[Tuple]]:
    """
    Build a schedule directly from the logging messages if the standard conversion fails.
    This is a last resort when the CP-SAT solver returns a format we can't process directly.
    
    Args:
        cpsat_schedule: CP-SAT schedule dictionary
    
    Returns:
        The schedule in greedy scheduler format {machine: [(job_id, start, end, priority, additional_params), ...]}
    """
    logger.info("Building schedule from solver log messages")
    greedy_format = {}
    
    if not isinstance(cpsat_schedule, dict):
        logger.error("Schedule must be a dictionary")
        return {}
    
    # Create a list of dictionaries for all scheduled jobs
    # Format should match what we see in the logs:
    # "Scheduled JOST111111_CP11-111-P01-08 on PAINTING: start=34, end=54"
    for job_id, details in cpsat_schedule.items():
        if job_id == '_metadata':
            continue
            
        if isinstance(details, dict) and 'machine' in details and 'start' in details and 'end' in details:
            machine = details['machine']
            start = details['start']
            end = details['end']
            priority = details.get('priority', 3)  # Default to medium priority
            
            # Validate timestamps
            if not _is_valid_timestamp(start, job_id, machine, "start"):
                continue
            if not _is_valid_timestamp(end, job_id, machine, "end"):
                continue
            
            if machine not in greedy_format:
                greedy_format[machine] = []
                
            greedy_format[machine].append((job_id, start, end, priority, {}))  # Use 5-tuple with empty additional params
    
    # Count how many jobs we scheduled this way
    total_after = sum(len(tasks) for machine, tasks in greedy_format.items())
    logger.info(f"Built schedule from logs: {total_after} tasks scheduled")
    
    return greedy_format 

def group_jobs_by_family(jobs: List[Dict[str, Any]]) -> Dict[str, List[Tuple[int, str, Dict[str, Any]]]]:
    """
    Group jobs by family and sort by process number within each family.
    
    Args:
        jobs: List of job dictionaries
        
    Returns:
        Dictionary mapping family names to lists of (process_number, job_id, job_data) tuples
    """
    job_families = defaultdict(list)
    
    for job in jobs:
        if not validate_job_data(job):
            continue
            
        job_id = job['job_id']
        family = extract_job_family(job_id)
        process_num = extract_process_number(job_id)
        
        job_families[family].append((process_num, job_id, job))
    
    # Sort jobs within each family by process number
    for family in job_families:
        job_families[family].sort(key=lambda x: x[0])
        
    return dict(job_families)

def calculate_schedule_metrics(schedule: Dict[str, List[Tuple]]) -> Dict[str, Any]:
    """
    Calculate basic metrics about a schedule.
    
    Args:
        schedule: Schedule in format {machine: [(job_id, start, end, priority, params), ...]}
        
    Returns:
        Dictionary with schedule metrics
    """
    if not isinstance(schedule, dict):
        return {}
        
    total_jobs = 0
    total_machines = len(schedule)
    machine_utilization = {}
    earliest_start = float('inf')
    latest_end = 0
    
    for machine, tasks in schedule.items():
        if not isinstance(tasks, list):
            continue
            
        machine_jobs = len(tasks)
        total_jobs += machine_jobs
        
        if tasks:
            machine_start = min(task[1] for task in tasks if len(task) >= 2)
            machine_end = max(task[2] for task in tasks if len(task) >= 3)
            
            earliest_start = min(earliest_start, machine_start)
            latest_end = max(latest_end, machine_end)
            
            # Calculate machine utilization (total task time / total available time)
            total_task_time = sum(task[2] - task[1] for task in tasks if len(task) >= 3)
            if latest_end > earliest_start:
                utilization = total_task_time / (latest_end - earliest_start)
                machine_utilization[machine] = min(utilization, 1.0)  # Cap at 100%
            else:
                machine_utilization[machine] = 0
    
    makespan = latest_end - earliest_start if earliest_start != float('inf') else 0
    avg_utilization = sum(machine_utilization.values()) / len(machine_utilization) if machine_utilization else 0
    
    return {
        'total_jobs': total_jobs,
        'total_machines': total_machines,
        'makespan_hours': makespan / 3600,  # Convert from seconds to hours
        'average_utilization': avg_utilization,
        'machine_utilization': machine_utilization,
        'earliest_start': earliest_start,
    } 
