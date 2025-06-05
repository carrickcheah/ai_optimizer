# greedy_solver.py | dont edit this line
import logging
from datetime import datetime
from collections import defaultdict
from typing import List, Dict, Any, Tuple, Optional
import time
import os
import math

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

def find_best_machine(job: Dict[str, Any], machines: List[str], machine_available_time: Dict[str, float]) -> Optional[str]:
    """Helper function to find the best machine for a job"""
    # First check if job has a specific machine requirement
    required_machine = job.get('rsc_code')
    if required_machine and required_machine in machines:
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
    start_time = time.time()
    logger.info(f"Creating schedule using greedy algorithm for {len(jobs)} jobs on {len(machines)} machines")
    logger.info(f"Using max_operators={max_operators}")
    
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
    
    # Group jobs by family and sort by process number
    job_families = group_jobs_by_family(valid_jobs)
    unassigned_jobs = []
    start_date_jobs = []
    
    # First pass: Separate jobs by type
    for job in valid_jobs:
        if not job.get('job_id'):
            continue
            
        # Handle START_DATE jobs first
        job_start_date_epoch = get_start_date_epoch(job)
        if job_start_date_epoch is not None and job_start_date_epoch > current_time:
            start_date_jobs.append(job)
            continue
            
        family = extract_job_family(job['job_id'])
        process_num = extract_process_number(job['job_id'])
        
        # Jobs that couldn't be grouped by family go to unassigned
        if family and process_num != 999:
            # Already handled in group_jobs_by_family
            pass
        else:
            unassigned_jobs.append(job)
    
    # Create schedule dictionary and tracking sets
    schedule = {machine: [] for machine in machines}
    scheduled_jobs = set()
    unscheduled_jobs_list = []
    
    # Track family end times to enforce dependencies properly
    family_end_times = defaultdict(lambda: current_time)
    process_end_times = {}  # Track (family, process_num) end times for sequence enforcement
    
    def can_schedule_job(job: Dict[str, Any], machine_id: str, start_time_epoch_val: float) -> bool:
        """Check if a job can be scheduled at the given time"""
        processing_time = job.get('processing_time')
        if not processing_time:
            # Priority logic: DAY_NEED takes precedence over HOURS_NEED
            day_need = job.get('day_need') or job.get('DAY_NEED')
            
            if day_need is not None:
                try:
                    day_need_val = float(day_need)
                    if day_need_val > 0:
                        # Convert days to hours, then to seconds
                        job['processing_time'] = day_need_val * 24 * 3600
                        logger.debug(f"Using DAY_NEED for job {job.get('job_id')}: {day_need_val} days = {job['processing_time']} seconds")
                    else:
                        # DAY_NEED is 0/negative, fall back to HOURS_NEED
                        if 'hours_need' in job and job['hours_need'] is not None:
                            try:
                                job['processing_time'] = float(job['hours_need']) * 3600
                                logger.debug(f"DAY_NEED is 0/negative, using HOURS_NEED for job {job.get('job_id')}: {job['hours_need']} hours")
                            except (ValueError, TypeError):
                                job['processing_time'] = 3600
                        else:
                            job['processing_time'] = 3600
                except (ValueError, TypeError):
                    # DAY_NEED is invalid, fall back to HOURS_NEED
                    if 'hours_need' in job and job['hours_need'] is not None:
                        try:
                            job['processing_time'] = float(job['hours_need']) * 3600
                            logger.debug(f"DAY_NEED is invalid, using HOURS_NEED for job {job.get('job_id')}: {job['hours_need']} hours")
                        except (ValueError, TypeError):
                            job['processing_time'] = 3600
                    else:
                        job['processing_time'] = 3600
            else:
                # No DAY_NEED, use HOURS_NEED directly
                if 'hours_need' in job and job['hours_need'] is not None:
                    try:
                        job['processing_time'] = float(job['hours_need']) * 3600
                        logger.debug(f"No DAY_NEED, using HOURS_NEED for job {job.get('job_id')}: {job['hours_need']} hours")
                    except (ValueError, TypeError):
                        job['processing_time'] = 3600
                else:
                    job['processing_time'] = 3600
        
        # Validate start_time_epoch_val is a reasonable timestamp
        if not isinstance(start_time_epoch_val, (int, float)) or start_time_epoch_val < 1000:
            logger.error(f"Invalid start time detected: {start_time_epoch_val} for job {job.get('job_id')} on machine {machine_id}")
            return False
        
        end_time_epoch_val = start_time_epoch_val + job['processing_time']
        
        # Check machine availability
        for scheduled_item in schedule[machine_id]:
            scheduled_start = scheduled_item[1]
            scheduled_end = scheduled_item[2]
            
            if not (end_time_epoch_val <= scheduled_start or start_time_epoch_val >= scheduled_end):
                return False
                
        # Check operator constraints
        if max_operators > 0:
            start_rel = epoch_to_relative_hours(start_time_epoch_val)
            end_rel = epoch_to_relative_hours(end_time_epoch_val)
            
            for hour in range(int(start_rel), int(end_rel) + 1):
                if operators_in_use[hour] >= max_operators:
                    return False
        
        # Check LCD date deadline constraints - job must complete before its deadline
        if 'lcd_date_epoch' in job and job['lcd_date_epoch']:
            lcd_deadline = job['lcd_date_epoch']
            current_time = datetime_to_epoch(datetime.now())
            grace_period_seconds = 12 * 3600  # 12-hour grace period for already late jobs
            
            # If job is already late, give it a grace period
            if lcd_deadline < current_time:
                adjusted_deadline = current_time + grace_period_seconds
                if end_time_epoch_val > adjusted_deadline:
                    logger.debug(f"Job {job.get('job_id')} would finish after grace period deadline: "
                               f"end={format_datetime_for_display(epoch_to_datetime(end_time_epoch_val))}, "
                               f"adjusted_deadline={format_datetime_for_display(epoch_to_datetime(adjusted_deadline))}")
                    return False
            else:
                if end_time_epoch_val > lcd_deadline:
                    logger.debug(f"Job {job.get('job_id')} would finish after LCD date deadline: "
                               f"end={format_datetime_for_display(epoch_to_datetime(end_time_epoch_val))}, "
                               f"deadline={format_datetime_for_display(epoch_to_datetime(lcd_deadline))}")
                    return False
        
        # Check time availability (working hours, holidays, break times)
        if not is_time_available(start_time_epoch_val, end_time_epoch_val):
            logger.debug(f"Job {job.get('job_id')} conflicts with non-working hours, holidays, or break times: "
                       f"{format_datetime_for_display(epoch_to_datetime(start_time_epoch_val))} to "
                       f"{format_datetime_for_display(epoch_to_datetime(end_time_epoch_val))}")
            return False
        
        return True
    
    # First schedule START_DATE jobs since they have fixed start times
    for job_item in start_date_jobs:
        job_id = job_item['job_id']
        start_time_epoch_val = get_start_date_epoch(job_item)
        
        # Validate timestamp
        if not start_time_epoch_val or not isinstance(start_time_epoch_val, (int, float)) or start_time_epoch_val < 1000:
            logger.error(f"Invalid START_DATE value detected: {start_time_epoch_val} for job {job_id}")
            unscheduled_jobs_list.append(job_item)
            continue
            
        machine_id = find_best_machine(job_item, machines, machine_available_time)
        if not machine_id:
            logger.warning(f"No compatible machine found for START_DATE job {job_id}")
            unscheduled_jobs_list.append(job_item)
            continue
            
        if can_schedule_job(job_item, machine_id, start_time_epoch_val):
            end_time_epoch_val = start_time_epoch_val + job_item['processing_time']
            
            # Add to schedule with 5-tuple format for consistency
            additional_params = {
                'start_date_fixed': True,
                'original_priority': job_item.get('priority')
            }
            schedule[machine_id].append((job_id, start_time_epoch_val, end_time_epoch_val, job_item.get('priority', 0), additional_params))
            
            scheduled_jobs.add(job_id)
            machine_available_time[machine_id] = max(machine_available_time[machine_id], end_time_epoch_val)
            
            # Update operator usage
            if max_operators > 0:
                start_rel = epoch_to_relative_hours(start_time_epoch_val)
                end_rel = epoch_to_relative_hours(end_time_epoch_val)
                for hour in range(int(start_rel), int(end_rel) + 1):
                    operators_in_use[hour] += 1
            
            # Update family end time for dependency tracking
            family = extract_job_family(job_id)
            process_num = extract_process_number(job_id)
            family_end_times[family] = max(family_end_times[family], end_time_epoch_val)
            process_end_times[(family, process_num)] = end_time_epoch_val
            
            logger.info(f"Scheduled START_DATE job {job_id} on {machine_id}: "
                       f"{format_datetime_for_display(epoch_to_datetime(start_time_epoch_val))} to "
                       f"{format_datetime_for_display(epoch_to_datetime(end_time_epoch_val))}")
        else:
            unscheduled_jobs_list.append(job_item)
            logger.warning(f"Could not schedule START_DATE job {job_id} at required time "
                          f"{format_datetime_for_display(epoch_to_datetime(start_time_epoch_val))}")
    
    # Collect all jobs into a single list to schedule by priority
    all_remaining_jobs = []
    for family, jobs_in_family in job_families.items():
        all_remaining_jobs.extend([(family, process_num, job_data) for process_num, job_id, job_data in jobs_in_family])
    
    # Sort all jobs by LCD date deadline (urgency) first, then priority, then process number
    def get_sort_key(job_tuple):
        family, process_num, job_data = job_tuple
        # Get LCD date for urgency sorting - jobs with earlier deadlines go first
        lcd_date_epoch = job_data.get('lcd_date_epoch', float('inf'))  # No deadline = lowest priority
        priority = job_data.get('priority', 3)  # Default to medium priority
        return (lcd_date_epoch, priority, process_num)
    
    all_remaining_jobs.sort(key=get_sort_key)
    logger.info(f"Processing {len(all_remaining_jobs)} jobs sorted by deadline urgency, then priority")
    
    # Process all jobs in priority order
    for family, process_num, job_item in all_remaining_jobs:
        job_id = job_item['job_id'] 
        if job_id in scheduled_jobs:
            continue
        
        # Check family dependencies
        min_start_time = current_time
        dependencies_met = True
        
        # Define special process rules
        special_processes = {
            5: {"allow_cross_family": True, "can_skip_dependencies": True}
        }
        
        # Enforce process sequence - ensure previous processes in the family are completed
        if enforce_sequence and process_num > 1:
            can_skip = special_processes.get(process_num, {}).get('can_skip_dependencies', False)
            
            if not can_skip:
                prev_process_num = process_num - 1
                if (family, prev_process_num) in process_end_times:
                    min_start_time = max(min_start_time, process_end_times[(family, prev_process_num)])
                else:
                    dependencies_met = False
                    logger.debug(f"Job {job_id} (P{process_num:02d}) depends on P{prev_process_num:02d} of family {family}, which is not yet scheduled")
            
        if not dependencies_met:
            logger.warning(f"Job {job_id} cannot be scheduled due to unmet dependencies")
            unscheduled_jobs_list.append(job_item)
            continue

        # Find the best machine for this job
        machine_id = find_best_machine(job_item, machines, machine_available_time)
        if not machine_id:
            logger.warning(f"No compatible machine found for job {job_id}")
            unscheduled_jobs_list.append(job_item)
            continue

        # Calculate the earliest possible start time for this job on the chosen machine
        possible_start_time = max(machine_available_time[machine_id], min_start_time)
        
        # Ensure processing_time is available
        if not job_item.get('processing_time'):
            # Priority logic: DAY_NEED takes precedence over HOURS_NEED
            day_need = job_item.get('day_need') or job_item.get('DAY_NEED')
            
            if day_need is not None:
                try:
                    day_need_val = float(day_need)
                    if day_need_val > 0:
                        # Convert days to hours, then to seconds
                        job_item['processing_time'] = day_need_val * 24 * 3600
                    else:
                        # DAY_NEED is 0/negative, fall back to HOURS_NEED
                        if 'hours_need' in job_item and job_item['hours_need'] is not None:
                            try:
                                job_item['processing_time'] = float(job_item['hours_need']) * 3600
                            except (ValueError, TypeError):
                                job_item['processing_time'] = 3600
                        else:
                            job_item['processing_time'] = 3600
                except (ValueError, TypeError):
                    # DAY_NEED is invalid, fall back to HOURS_NEED
                    if 'hours_need' in job_item and job_item['hours_need'] is not None:
                        try:
                            job_item['processing_time'] = float(job_item['hours_need']) * 3600
                        except (ValueError, TypeError):
                            job_item['processing_time'] = 3600
                    else:
                        job_item['processing_time'] = 3600
            else:
                # No DAY_NEED, use HOURS_NEED directly
                if 'hours_need' in job_item and job_item['hours_need'] is not None:
                    try:
                        job_item['processing_time'] = float(job_item['hours_need']) * 3600
                    except (ValueError, TypeError):
                        job_item['processing_time'] = 3600
                else:
                    job_item['processing_time'] = 3600

        # Attempt to schedule the job at the earliest possible time
        if can_schedule_job(job_item, machine_id, possible_start_time):
            _schedule_job_at_time(job_item, machine_id, possible_start_time, schedule, scheduled_jobs, 
                                machine_available_time, operators_in_use, family_end_times, 
                                process_end_times, family, process_num, max_operators)
        else:
            # Try to find next available slot using time availability checker
            duration_hours = job_item['processing_time'] / 3600  # Convert seconds to hours
            next_available = get_next_available_slot(possible_start_time, duration_hours)
            
            if next_available:
                # Check if this slot works with other constraints
                if can_schedule_job(job_item, machine_id, next_available):
                    _schedule_job_at_time(job_item, machine_id, next_available, schedule, scheduled_jobs, 
                                        machine_available_time, operators_in_use, family_end_times, 
                                        process_end_times, family, process_num, max_operators)
                else:
                    # Fall back to original slot finding if time available slot doesn't work
                    found_slot = _find_next_available_slot(job_item, machine_id, possible_start_time, schedule, 
                                                         scheduled_jobs, machine_available_time, operators_in_use, 
                                                         family_end_times, process_end_times, family, process_num,
                                                         max_operators, unscheduled_jobs_list)
                    if not found_slot:
                        logger.warning(f"Could not find a slot for job {job_id} on machine {machine_id}")
            else:
                logger.warning(f"No available time slots found for job {job_id} within search window")
    
    # Handle jobs that couldn't be assigned to families
    if unassigned_jobs:
        logger.info(f"Processing {len(unassigned_jobs)} unassigned jobs (no family or process number)")
        unassigned_jobs.sort(key=lambda x: x['priority'])
        
        for job_item in unassigned_jobs:
            job_id = job_item['job_id']
            if job_id in scheduled_jobs:
                continue

            machine_id = find_best_machine(job_item, machines, machine_available_time)
            if not machine_id:
                logger.warning(f"No machine for unassigned job {job_id}")
                unscheduled_jobs_list.append(job_item)
                continue

            start_actual = machine_available_time[machine_id]
            if not job_item.get('processing_time'):
                job_item['processing_time'] = 3600
            end_actual = start_actual + job_item['processing_time']
            
            additional_params = {
                'greedy_scheduled_at': datetime_to_epoch(datetime.now()),
                'original_priority': job_item.get('priority')
            }
            schedule[machine_id].append((job_id, start_actual, end_actual, job_item.get('priority', 0), additional_params))
            scheduled_jobs.add(job_id)
            machine_available_time[machine_id] = end_actual
            logger.info(f"Scheduled unassigned job {job_id} on {machine_id}")

    # Clean up schedule: sort tasks by start time for each machine
    for machine in schedule:
        schedule[machine].sort(key=lambda x: x[1])
        
    end_time_algo = time.time()
    logger.info(f"Greedy scheduling completed in {end_time_algo - start_time:.2f} seconds")
    logger.info(f"Total jobs scheduled: {len(scheduled_jobs)}")
    
    if unscheduled_jobs_list:
        logger.warning(f"Total jobs unscheduled: {len(unscheduled_jobs_list)}")
        for job_item in unscheduled_jobs_list:
            logger.warning(f"  Unscheduled: {job_item['job_id']}")
            
    return schedule

def _schedule_job_at_time(job_item, machine_id, start_time, schedule, scheduled_jobs, 
                         machine_available_time, operators_in_use, family_end_times, 
                         process_end_times, family, process_num, max_operators):
    """Helper to schedule a job at a specific time."""
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
    job_id = job_item['job_id']
    search_limit_hours = 24 
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
            grace_period_seconds = 12 * 3600  # 12-hour grace period for already late jobs
            
            # If job is already late, give it a grace period
            if lcd_deadline < current_time:
                adjusted_deadline = current_time + grace_period_seconds
                if end_time_val > adjusted_deadline:
                    return False
            else:
                if end_time_val > lcd_deadline:
                    return False
        
        # Check time availability (working hours, holidays, break times)
        if not is_time_available(start_time_val, end_time_val):
            logger.debug(f"Job {job_id} conflicts with non-working hours, holidays, or break times: "
                       f"{format_datetime_for_display(epoch_to_datetime(start_time_val))} to "
                       f"{format_datetime_for_display(epoch_to_datetime(end_time_val))}")
            return False
        
        return True

    while current_search_time < max_search_time:
        if can_schedule_job_internal(current_search_time):
            _schedule_job_at_time(job_item, machine_id, current_search_time, schedule, scheduled_jobs,
                                machine_available_time, operators_in_use, family_end_times,
                                process_end_times, family, process_num, max_operators)
            return True
        current_search_time += 3600  # Increment by 1 hour

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