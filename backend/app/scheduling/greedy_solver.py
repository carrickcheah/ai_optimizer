# greedy_solver.py | dont edit this line
import logging
from datetime import datetime
from collections import defaultdict
from typing import List, Dict, Any, Tuple, Optional
import time
import os
import math
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

from ortools.sat.python import cp_model

from app.utils.time_utils import (
    epoch_to_datetime, 
    datetime_to_epoch,
    format_datetime_for_display,
    epoch_to_relative_hours,
    relative_hours_to_epoch
)
from app.scheduling.setup_buffer import get_start_date_epoch
from app.scheduling.scheduler_utils import (
    extract_process_number, 
    extract_job_family, 
    normalize_job_fields, 
    validate_job_data,
    group_jobs_by_family
)
from app.scheduling.time_availability import is_time_available, get_next_available_slot

# Get module-specific logger without configuring at module level
logger = logging.getLogger(__name__)

# Get normal working hours from environment, default to 17.5
NORMAL_WORKING_HOURS = float(os.getenv('NORMAL_WORKING_HOURS', '17.5'))

def find_best_machine(job: Dict[str, Any], machines: List[str], machine_available_time: Dict[str, float]) -> Optional[str]:
    """Helper function to find the best machine for a job"""
    # Find least loaded compatible machine for job assignment
    # First check if job has a specific machine requirement
    required_machine = job.get('MachineName_v')
    if required_machine:
        if required_machine == "NOT_ASSIGN":
            logger.debug(f"Job {job.get('job_id', 'Unknown')} has NOT_ASSIGN machine - assigning to 'Subcon'")
            return 'Subcon'
        elif required_machine in machines:
            return required_machine
        
    # If no specific machine required, find least loaded compatible machine
    compatible_machines = []
    for machine in machines:
        # Check if machine is compatible with job requirements
        # You can add more compatibility checks here
        compatible_machines.append(machine)
    
    if not compatible_machines:
        logger.warning(f"No compatible machines found for job {job.get('job_id')}")
        return None
        
    # Return least loaded compatible machine
    return min(compatible_machines, key=lambda m: machine_available_time[m])

def greedy_schedule(
    jobs: List[Dict[str, Any]], 
    machines: List[str], 
    setup_times: Optional[Dict] = None, 
    enforce_sequence: bool = True, 
    max_operators: int = 0
) -> Dict[str, List[Tuple]]:
    """
    Create a schedule using a greedy algorithm.
    
    Args:
        jobs: List of job dictionaries
        machines: List of machine IDs
        setup_times: Dictionary of setup times between processes
        enforce_sequence: Whether to enforce process sequence dependencies
        max_operators: Maximum number of operators available at any time
        
    Returns:
        Dictionary with machine IDs as keys and lists of scheduled jobs as values
    """
    # Main greedy scheduling algorithm - assigns jobs to least loaded machines
    start_time = time.time()
    logger.info(f"Creating schedule using greedy algorithm for {len(jobs)} jobs on {len(machines)} machines")
    logger.info(f"Using max_operators={max_operators}")
    
    # Handle case where machines is a list of dictionaries
    if machines and isinstance(machines[0], dict):
        # Extract machine names from dictionary format
        machine_names = [m.get('MachineName_v', str(m)) for m in machines if m.get('MachineName_v')]
        machines = machine_names
        logger.info(f"Extracted {len(machines)} machine names from dictionary format")
    
    # Add 'Subcon' to machines if not present, for handling unassigned jobs
    if 'Subcon' not in machines:
        machines.append('Subcon')
        logger.info("Added 'Subcon' to machine list for unassigned jobs.")
    
    # Input validation
    if not isinstance(jobs, list) or not jobs:
        logger.error("Jobs must be a non-empty list")
        return {}
        
    if not isinstance(machines, list) or not machines:
        logger.error("Machines must be a non-empty list")
        return {}
    
    # Normalize and validate job data
    valid_jobs = []
    for job in jobs:
        normalized_job = normalize_job_fields(job)
        if validate_job_data(normalized_job):
            valid_jobs.append(normalized_job)
        else:
            logger.warning(f"Skipping invalid job: {job.get('job_id', 'unknown')}")
    
    if not valid_jobs:
        logger.warning("No valid jobs after validation")
        return {}
    
    logger.info(f"Processing {len(valid_jobs)} valid jobs (filtered from {len(jobs)})")

    # Use current time as reference
    current_time = datetime_to_epoch(datetime.now())
    
    # Create a dictionary to track machine availability
    machine_available_time = {machine: current_time for machine in machines}
    
    # Track operator usage over time
    operators_in_use = defaultdict(int)  # time_point -> number of operators
    
    # Create schedule dictionary and tracking sets
    schedule = {machine: [] for machine in machines}
    scheduled_jobs = set()
    unscheduled_jobs_list = []
    
    # Track family end times to enforce dependencies properly
    family_end_times = defaultdict(lambda: current_time)
    process_end_times = {}

    # Improved dependency handling - separate jobs by dependency status
    dependency_jobs = []  # Jobs with dependencies
    independent_jobs = []  # Jobs without dependencies
    not_assign_jobs = []  # NOT_ASSIGN jobs

    # Categorize jobs by dependency status
    for job in valid_jobs:
        if job.get('MachineName_v') == 'NOT_ASSIGN':
            not_assign_jobs.append(job)
        else:
            family = extract_job_family(job['job_id'])
            process_num = extract_process_number(job['job_id'])
            
            if family and process_num > 1:
                dependency_jobs.append(job)
            else:
                independent_jobs.append(job)

    logger.info(f"Job categorization: {len(not_assign_jobs)} NOT_ASSIGN, {len(independent_jobs)} independent, {len(dependency_jobs)} with dependencies")

    # --- Pre-schedule NOT_ASSIGN jobs on 'Subcon' ---
    logger.info(f"Scheduling {len(not_assign_jobs)} NOT_ASSIGN jobs on 'Subcon'")
    for job_item in sorted(not_assign_jobs, key=lambda j: j.get('priority', 99)):
        job_id = job_item['job_id']
        machine_id = 'Subcon'
        
        # Calculate processing time if missing
        if not job_item.get('processing_time'):
            lead_time_d = job_item.get('LeadTime_d')
            if lead_time_d is not None and float(lead_time_d) > 0:
                job_item['processing_time'] = float(lead_time_d) * NORMAL_WORKING_HOURS * 3600
            else:
                job_item['processing_time'] = 3600
        
        start_search_time = machine_available_time.get(machine_id, current_time)
        
        if not _find_next_available_slot(
            job_item, machine_id, start_search_time, schedule, scheduled_jobs,
            machine_available_time, operators_in_use, family_end_times,
            process_end_times, 'NOT_ASSIGN_FAMILY', 99, max_operators,
            unscheduled_jobs_list):
            logger.warning(f"Could not find a slot for NOT_ASSIGN job {job_id} on 'Subcon'")

    # --- Schedule independent jobs first (no dependencies) ---
    logger.info(f"Scheduling {len(independent_jobs)} independent jobs")
    for job_item in sorted(independent_jobs, key=lambda j: j.get('priority', 99)):
        job_id = job_item['job_id']
        if job_id in scheduled_jobs:
            continue

        machine_id = find_best_machine(job_item, machines, machine_available_time)
        if not machine_id:
            unscheduled_jobs_list.append(job_item)
            continue

        if not job_item.get('processing_time'):
            lead_time_d = job_item.get('LeadTime_d')
            if lead_time_d is not None and float(lead_time_d) > 0:
                job_item['processing_time'] = float(lead_time_d) * NORMAL_WORKING_HOURS * 3600
            else:
                job_item['processing_time'] = 3600

        start_search_time = machine_available_time.get(machine_id, current_time)
        family = extract_job_family(job_id) or 'INDEPENDENT'
        process_num = extract_process_number(job_id) or 1

        if not _find_next_available_slot(
            job_item, machine_id, start_search_time, schedule, scheduled_jobs,
            machine_available_time, operators_in_use, family_end_times,
            process_end_times, family, process_num, max_operators,
            unscheduled_jobs_list):
            logger.warning(f"Could not find a slot for independent job {job_id}")

    # --- Schedule dependency jobs by family and process order ---
    logger.info(f"Scheduling {len(dependency_jobs)} jobs with dependencies")
    job_families = group_jobs_by_family([job for job in dependency_jobs if job['job_id'] not in scheduled_jobs])
    
    # Process families in order, ensuring dependencies are met
    for family, family_jobs in job_families.items():
        if not family_jobs:
            continue
            
        logger.info(f"Processing family '{family}' with {len(family_jobs)} jobs")
        
        # family_jobs is already sorted by process number in group_jobs_by_family
        # Extract the job data from the tuple (process_number, job_id, job_data)
        for process_num, job_id, job_item in family_jobs:
            if job_id in scheduled_jobs:
                continue
            
            # Check dependency - can only schedule if previous process is done
            if enforce_sequence and process_num > 1:
                prev_process_key = (family, process_num - 1)
                if prev_process_key not in process_end_times:
                    logger.warning(f"Job {job_id} cannot be scheduled due to unmet dependencies")
                    unscheduled_jobs_list.append(job_item)
                    continue
                    
                # Start no earlier than when previous process finished
                earliest_start = process_end_times[prev_process_key]
            else:
                earliest_start = current_time
            
            # Find best machine for this job
            machine_id = find_best_machine(job_item, machines, machine_available_time)
            if not machine_id:
                logger.warning(f"No machine for job {job_id}")
                unscheduled_jobs_list.append(job_item)
                continue
            
            # Calculate processing time if missing
            if not job_item.get('processing_time'):
                lead_time_d = job_item.get('LeadTime_d')
                if lead_time_d is not None and float(lead_time_d) > 0:
                    job_item['processing_time'] = float(lead_time_d) * NORMAL_WORKING_HOURS * 3600
                else:
                    job_item['processing_time'] = 3600
            
            # Start search from the later of machine availability or dependency requirement
            start_search_time = max(machine_available_time.get(machine_id, current_time), earliest_start)
            
            if not _find_next_available_slot(
                job_item, machine_id, start_search_time, schedule, scheduled_jobs,
                machine_available_time, operators_in_use, family_end_times,
                process_end_times, family, process_num, max_operators,
                unscheduled_jobs_list):
                logger.warning(f"Could not find a slot for dependent job {job_id}")

    # Clean up schedule: sort tasks by start time for each machine
    for machine in schedule:
        schedule[machine].sort(key=lambda x: x[1])
        
    end_time_algo = time.time()
    logger.info(f"Greedy scheduling completed in {end_time_algo - start_time:.2f} seconds")
    
    # Calculate and log detailed statistics
    total_input_jobs = len(valid_jobs)
    total_scheduled = len(scheduled_jobs)
    total_unscheduled = len(unscheduled_jobs_list)
    success_rate = (total_scheduled / total_input_jobs * 100) if total_input_jobs > 0 else 0
    
    logger.info(f"Scheduling Results:")
    logger.info(f"  Total jobs processed: {total_input_jobs}")
    logger.info(f"  Successfully scheduled: {total_scheduled} ({success_rate:.1f}%)")
    logger.info(f"  Failed to schedule: {total_unscheduled} ({100-success_rate:.1f}%)")
    
    # Log machine utilization
    machine_task_counts = {machine: len(tasks) for machine, tasks in schedule.items() if tasks}
    if machine_task_counts:
        logger.info(f"Machine utilization:")
        for machine, count in sorted(machine_task_counts.items(), key=lambda x: x[1], reverse=True)[:10]:
            logger.info(f"  {machine}: {count} tasks")
    
    if unscheduled_jobs_list:
        logger.warning(f"Unscheduled jobs breakdown:")
        # Group unscheduled jobs by reason (if we can determine it)
        not_assign_unscheduled = [job for job in unscheduled_jobs_list if job.get('MachineName_v') == 'NOT_ASSIGN']
        dependency_unscheduled = [job for job in unscheduled_jobs_list if extract_process_number(job['job_id']) > 1]
        other_unscheduled = [job for job in unscheduled_jobs_list if job not in not_assign_unscheduled and job not in dependency_unscheduled]
        
        if not_assign_unscheduled:
            logger.warning(f"  NOT_ASSIGN jobs: {len(not_assign_unscheduled)}")
        if dependency_unscheduled:
            logger.warning(f"  Dependency failures: {len(dependency_unscheduled)}")
        if other_unscheduled:
            logger.warning(f"  Other scheduling failures: {len(other_unscheduled)}")
            
        # Log first few unscheduled jobs for debugging
        for i, job_item in enumerate(unscheduled_jobs_list[:10]):
            logger.warning(f"  Unscheduled: {job_item['job_id']}")
            
        if len(unscheduled_jobs_list) > 10:
            logger.warning(f"  ... and {len(unscheduled_jobs_list) - 10} more")
            
    return schedule

def _schedule_job_at_time(job_item, machine_id, start_time, schedule, scheduled_jobs, 
                         machine_available_time, operators_in_use, family_end_times, 
                         process_end_times, family, process_num, max_operators):
    """Helper to schedule a job at a specific time."""
    # Place job in schedule and update all tracking structures
    job_id = job_item['job_id']
    end_time = start_time + job_item['processing_time']
    
    additional_params = {
        'greedy_scheduled_at': datetime_to_epoch(datetime.now()),
        'original_priority': job_item.get('priority')
    }
    schedule[machine_id].append((job_id, start_time, end_time, job_item.get('priority', 0), additional_params))
    scheduled_jobs.add(job_id)
    machine_available_time[machine_id] = end_time
    
    # Update operator usage
    if max_operators > 0:
        start_rel = epoch_to_relative_hours(start_time)
        end_rel = epoch_to_relative_hours(end_time)
        for hour in range(int(start_rel), int(end_rel) + 1):
            operators_in_use[hour] += 1
            
    # Update end times for dependency tracking
    family_end_times[family] = max(family_end_times[family], end_time)
    process_end_times[(family, process_num)] = end_time
    
    logger.info(f"Scheduled job {job_id} (P{process_num:02d}) on {machine_id}: "
               f"{format_datetime_for_display(epoch_to_datetime(start_time))} to "
               f"{format_datetime_for_display(epoch_to_datetime(end_time))}")

def _find_next_available_slot(job_item, machine_id, start_search_time, schedule, scheduled_jobs, 
                            machine_available_time, operators_in_use, family_end_times, 
                            process_end_times, family, process_num, max_operators, 
                            unscheduled_jobs_list):
    """Helper to find the next available slot for a job."""
    # Search for available time slot within extended horizon window
    job_id = job_item['job_id']
    search_limit_hours = 8760  # Extended search window to 8760 hours (~365 days)
    current_search_time = start_search_time
    max_search_time = current_search_time + search_limit_hours * 3600

    def can_schedule_job_internal(start_time_val):
        """Internal version of can_schedule_job for this search."""
        end_time_val = start_time_val + job_item['processing_time']
        
        # Check machine availability
        for scheduled_item in schedule[machine_id]:
            scheduled_start = scheduled_item[1]
            scheduled_end = scheduled_item[2]
            
            if not (end_time_val <= scheduled_start or start_time_val >= scheduled_end):
                return False
                
        # Check operator constraints
        if max_operators > 0:
            start_rel = epoch_to_relative_hours(start_time_val)
            end_rel = epoch_to_relative_hours(end_time_val)
            
            for hour in range(int(start_rel), int(end_rel) + 1):
                if operators_in_use[hour] >= max_operators:
                    return False
        
        # Check LCD date deadline constraints - job must complete before its deadline
        if 'lcd_date_epoch' in job_item and job_item['lcd_date_epoch']:
            lcd_deadline = job_item['lcd_date_epoch']
            current_time = datetime_to_epoch(datetime.now())
            grace_period_hours = int(os.getenv('GRACE_PERIOD_HOURS', '72'))  # Default 72 hours grace
            grace_period_seconds = grace_period_hours * 3600
            
            # If job is already late, give it a grace period based on priority
            if lcd_deadline < current_time:
                priority = job_item.get('priority', 3)
                # High priority jobs get more grace time
                if priority <= 2:
                    extended_grace = grace_period_seconds * 2  # Double grace for high priority
                else:
                    extended_grace = grace_period_seconds
                
                adjusted_deadline = current_time + extended_grace
                if end_time_val > adjusted_deadline:
                    return False
            else:
                # For future deadlines, allow small buffer for scheduling flexibility
                buffer_seconds = 24 * 3600  # 24 hour buffer
                if end_time_val > (lcd_deadline + buffer_seconds):
                    return False
        
        # Check time availability (working hours, holidays, break times)
        if not is_time_available(start_time_val, end_time_val):
            logger.debug(f"Job {job_id} conflicts with non-working hours, holidays, or break times: "
                       f"{format_datetime_for_display(epoch_to_datetime(start_time_val))} to "
                       f"{format_datetime_for_display(epoch_to_datetime(end_time_val))}")
            return False
        
        return True

    # Use smarter search increments - start with fine granularity, increase if needed
    increment = 3600  # Start with 1 hour
    attempts = 0
    max_attempts_per_increment = 48  # Try 48 times (2 days) before increasing increment
    
    while current_search_time < max_search_time:
        if can_schedule_job_internal(current_search_time):
            _schedule_job_at_time(job_item, machine_id, current_search_time, schedule, scheduled_jobs,
                                machine_available_time, operators_in_use, family_end_times,
                                process_end_times, family, process_num, max_operators)
            return True
            
        current_search_time += increment
        attempts += 1
        
        # Adaptive search: increase increment size after many failed attempts
        if attempts >= max_attempts_per_increment:
            if increment < 86400:  # Less than 24 hours
                increment = min(increment * 2, 86400)  # Double increment, max 24 hours
                logger.debug(f"Job {job_id}: Increasing search increment to {increment/3600:.1f} hours")
            attempts = 0

    unscheduled_jobs_list.append(job_item)
    return False

if __name__ == "__main__":
    # Example usage when running this file directly
    import time
    from app.data_ingestion.mariadb_parser import load_jobs_planning_data
    
    # Test with production data
    start_time = time.time()
    try:
        jobs, machines, setup_times = load_jobs_planning_data()
        
        if jobs:
            test_jobs = jobs
            
            print(f"Running greedy scheduler on {len(test_jobs)} jobs and {len(machines)} machines")
            schedule = greedy_schedule(test_jobs, machines, setup_times, enforce_sequence=True)
            
            # Print sample of the results
            print("\nGreedy Schedule (Sample):")
            task_count = 0
            for machine, tasks in sorted(schedule.items())[:5]:  # First 5 machines
                if tasks:
                    print(f"\nMachine: {machine} - {len(tasks)} tasks")
                    for i, task in enumerate(tasks[:3]):  # First 3 tasks per machine
                        job_id, start, end, priority = task[:4]
                        print(f"  Task {i+1}: {job_id} (Start: {start}, End: {end}, Priority: {priority})")
                        task_count += 1
                if task_count >= 15:  # Show at most 15 tasks
                    break
            
            total_jobs = sum(len(tasks) for tasks in schedule.values())
            print(f"\nScheduled {total_jobs} of {len(test_jobs)} jobs")
            print(f"Done in {time.time() - start_time:.2f} seconds")
        else:
            print("No jobs loaded. Check your database connection and query.")
    except Exception as e:
        print(f"Error: {e}") 