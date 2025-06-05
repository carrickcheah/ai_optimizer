# cpsat_solver.py | dont edit this line
# Constraint Programming (CP-SAT) solver for production scheduling
'''
1. schedule_jobs - Main CP-SAT constraint programming solver for production scheduling optimization
2. _create_error_result - Creates standardized error result dictionary with metadata
3. _calculate_horizon - Calculates solver time horizon based on maximum job durations
4. _calculate_total_job_hours - Calculates total job hours including setup, break, and non-productive time
5. _add_sequence_constraints - Adds precedence constraints between processes of same job family
6. _add_operator_constraints - Adds cumulative operator resource constraints using CP-SAT Cumulative
7. _add_start_date_constraints - Adds hard START_DATE constraints with priority-based conflict resolution
8. _create_objective_function - Creates multi-objective function minimizing priority penalties, tardiness, and makespan
9. _solve_model - Configures and runs CP-SAT solver with time limits and workers
10. _process_solver_results - Processes solver results and converts to final schedule format
11. _validate_sequence_constraints - Validates sequence constraints are satisfied in final schedule
12. main execution block - CLI example usage with data loading and result display
'''

from ortools.sat.python import cp_model
from datetime import datetime
import logging
import time
import os
import math
from collections import defaultdict
from typing import List, Dict, Any, Optional

from app.utils.time_utils import (
    epoch_to_relative_hours,
    relative_hours_to_epoch,
    epoch_to_datetime,
    datetime_to_epoch,
    format_datetime_for_display
)
from app.scheduling.setup_buffer import get_start_date_epoch
from app.scheduling.scheduler_utils import extract_process_number, extract_job_family, normalize_job_fields, validate_job_data
from app.scheduling.time_availability import is_time_available, get_next_available_slot

# Get module-specific logger without configuring at module level
logger = logging.getLogger(__name__)

# Suppress OR-Tools logging output
ortools_logger = logging.getLogger('ortools')
ortools_logger.setLevel(logging.ERROR)  # Set to ERROR to hide all but errors

def schedule_jobs(
    jobs: List[Dict[str, Any]], 
    machines: List[str], 
    setup_times: Optional[Dict] = None, 
    enforce_sequence: bool = True, 
    time_limit_seconds: int = 120,  # Reduced from 300 to 30 seconds
    max_operators: Optional[int] = None,
    max_jobs_limit: int = 1000,  # New parameter to limit problem size
    planning_horizon_days: int = 60,  # New parameter to limit planning horizon
    enforce_deadlines: bool = True  # New parameter to enable/disable deadline constraints
) -> Dict[str, Any]:
    """
    Schedule jobs using Google's CP-SAT solver with performance optimizations.
    
    Args:
        jobs: List of job dictionaries with job_id, rsc_code, hours_need, etc.
        machines: List of machine names or machine dictionaries with MachineName_v key
        setup_times: Optional setup times (not used in CP-SAT)
        enforce_sequence: Whether to enforce job sequence constraints
        time_limit_seconds: Solver time limit in seconds (default: 30s for performance)
        max_operators: Maximum number of operators (optional)
        max_jobs_limit: Maximum number of jobs to process for performance (default: 1000)
        planning_horizon_days: Planning horizon in days (default: 60 days)
        enforce_deadlines: Whether to enforce deadline constraints (default: True)
        
    Returns:
        Schedule dictionary with results and metadata
    """
    logger.info(f"Using CP-SAT solver to schedule {len(jobs)} jobs on {len(machines)} machines")
    start_time = time.time()
    
    # Performance optimization: Filter and limit jobs
    current_time_epoch = datetime_to_epoch(datetime.now())
    horizon_cutoff_epoch = current_time_epoch + (planning_horizon_days * 24 * 3600)  # Convert days to seconds
    
    # Filter jobs by planning horizon and priority
    filtered_jobs = []
    for job in jobs:
        # Include job if it's within planning horizon or high priority
        lcd_date_epoch = job.get('lcd_date_epoch')
        priority = job.get('priority', 5)  # Default to low priority
        
        include_job = True
        
        # Apply horizon filter for non-critical jobs
        if lcd_date_epoch and priority > 2:  # Only filter low/medium priority jobs
            if lcd_date_epoch > horizon_cutoff_epoch:
                include_job = False
                
        if include_job:
            filtered_jobs.append(job)
    
    # Limit total jobs for performance
    if len(filtered_jobs) > max_jobs_limit:
        # Prioritize by urgency and priority
        filtered_jobs = sorted(filtered_jobs, key=lambda x: (
            x.get('priority', 5),  # Lower priority number = higher priority
            x.get('lcd_date_epoch', current_time_epoch + 999999)  # Earlier due date = higher priority
        ))[:max_jobs_limit]
        logger.warning(f"Limited to {max_jobs_limit} jobs for performance (from {len(jobs)} total)")
    
    logger.info(f"Performance filtering: {len(jobs)} → {len(filtered_jobs)} jobs (horizon: {planning_horizon_days} days, limit: {max_jobs_limit})")
    
    # Normalize machines list - handle both string and dictionary formats
    if machines and isinstance(machines[0], dict):
        machine_names = [m.get('MachineName_v', m.get('machine_name', str(m))) for m in machines]
        logger.debug(f"Converted machine dictionaries to names: {machine_names}")
    else:
        machine_names = machines
    
    # Initialize the CP-SAT model
    model = cp_model.CpModel()
    
    # Filter valid jobs from the already filtered set
    valid_jobs = [
        job for job in filtered_jobs 
        if isinstance(job, dict) and job.get('job_id') and job.get('rsc_code')
    ]
    
    if not valid_jobs:
        logger.error("No valid jobs found")
        return _create_error_result("No valid jobs found")
        
    logger.info(f"Processing {len(valid_jobs)} valid jobs (filtered from {len(jobs)})")
    
    # Calculate horizon efficiently
    horizon = _calculate_horizon(valid_jobs)
    logger.info(f"Solver horizon set to {horizon} relative hours")

    # Create job variables and intervals
    all_tasks = {}
    all_starts = []
    all_ends = []
    all_intervals = []
    
    # Dictionary to cache job intervals on machines
    jobs_on_machine = defaultdict(list)
    
    # Separate dictionary to store sequence constraints for visualization
    job_dependencies = defaultdict(list)
    
    # Track jobs with constraints for visualization
    start_date_processes = {}
    jobs_with_due_dates = {}
    start_time_preferences = {}
    
    # Process all jobs to create variables and constraints
    for job_item in valid_jobs:
        job_id = job_item['job_id']
        
        # Check if the job has a machine assignment
        if not job_item.get('rsc_code') or job_item['rsc_code'] not in machine_names:
            logger.warning(f"Job {job_id} has no valid machine assignment, skipping: {job_item.get('rsc_code')}")
            continue
            
        machine = job_item['rsc_code']
        
        # Calculate total hours needed including non-working time components
        total_hours = _calculate_total_job_hours(job_item)
        if total_hours <= 0:
            logger.warning(f"Job {job_id} has zero or negative duration, setting to 1 hour")
            total_hours = 1

        # Convert hours to integer for solver (round up to ensure we don't underestimate)
        hours_need = int(math.ceil(total_hours))
        logger.debug(f"Job {job_id}: Total hours with non-working time={total_hours:.2f}, solver hours={hours_need}")
        
        # Handle due dates
        if 'lcd_date_epoch' in job_item and job_item['lcd_date_epoch']:
            due_date_rel = epoch_to_relative_hours(job_item['lcd_date_epoch'])
            due_date_rel_int = int(due_date_rel)
            jobs_with_due_dates[job_id] = due_date_rel_int
            logger.debug(f"Added due date for job {job_id}: {due_date_rel_int} relative hours")
        
        # Handle START_DATE constraints
        job_start_date_epoch_val = get_start_date_epoch(job_item)
        if job_start_date_epoch_val:
            start_date_rel = epoch_to_relative_hours(job_start_date_epoch_val)
            start_date_rel_int = int(start_date_rel)
            start_time_preferences[job_id] = start_date_rel_int
            start_date_processes[job_id] = job_start_date_epoch_val
            logger.debug(f"Added start time preference for job {job_id}: {start_date_rel_int} relative hours")
        
        # Create start and end variables
        start_var = model.NewIntVar(0, horizon, f'start_{job_id}')
        end_var = model.NewIntVar(0, horizon + hours_need, f'end_{job_id}')
        
        # Record all start and end variables
        all_starts.append(start_var)
        all_ends.append(end_var)
        
        # Create interval variable
        interval_var = model.NewIntervalVar(
            start_var, hours_need, end_var, f'interval_{job_id}'
        )
        
        # Record the interval
        all_intervals.append(interval_var)
        
        # Store task info
        all_tasks[job_id] = {
            'start': start_var,
            'end': end_var,
            'interval': interval_var,
            'machine': machine,
            'hours': hours_need,
            'job': job_item
        }
        
        # Add to machine-specific list
        jobs_on_machine[machine].append(interval_var)
        
    if not all_tasks:
        logger.warning("No valid tasks created after processing")
        return _create_error_result("No valid tasks created after processing constraints")

    # Add NoOverlap constraint for each machine
    for machine_key in machine_names:
        if jobs_on_machine[machine_key]:
            model.AddNoOverlap(jobs_on_machine[machine_key])
            logger.debug(f"Added NoOverlap constraint for machine {machine_key} with {len(jobs_on_machine[machine_key])} jobs")

    # Add sequence constraints (precedences)
    if enforce_sequence:
        _add_sequence_constraints(model, all_tasks, job_dependencies, logger)

    # Add operator constraints using Cumulative
    if max_operators is not None and max_operators > 0:
        _add_operator_constraints(model, all_tasks, max_operators, logger)

    # Add hard START_DATE constraints with priority-based conflict resolution
    _add_start_date_constraints(model, all_tasks, start_time_preferences, logger)
    
    # Add HARD LCD_DATE (deadline) constraints - jobs MUST complete before deadline
    _add_deadline_constraints(model, all_tasks, jobs_with_due_dates, logger, enforce_deadlines)
    
    # Add working hours constraints to prevent midnight scheduling
    _add_working_hours_constraints(model, all_tasks, logger)

    # Define objective function
    objective_terms = _create_objective_function(
        model, all_ends, jobs_with_due_dates, start_time_preferences, 
        all_tasks, horizon, logger
    )
    
    if objective_terms:
        model.Minimize(sum(objective_terms))
        logger.info("Objective function set to minimize sum of makespan, weighted tardiness, and start time deviations")
    else:
        logger.warning("No objective function created")

    # Solve the model
    solver_result = _solve_model(model, time_limit_seconds, logger)
    
    # Process results
    return _process_solver_results(
        solver_result, all_tasks, datetime_to_epoch(datetime.now()), job_dependencies,
        start_date_processes, jobs_with_due_dates, enforce_sequence, logger
    )

def _create_error_result(message: str) -> Dict[str, Any]:
    """Create a standardized error result dictionary."""
    return {
        '_metadata': {
            'status': 'ERROR',
            'solver_time': 0,
            'objective_value': None,
            'reference_time_epoch': datetime_to_epoch(datetime.now()),
            'message': message
        }
    }

def _calculate_horizon(jobs: List[Dict[str, Any]]) -> int:
    """Calculate the solver horizon based on job durations.
    
    Considers both DAY_NEED (priority) and HOURS_NEED for duration calculation.
    """
    max_hours_need = 0
    for job_item in jobs:
        # Use the same priority logic as _calculate_total_job_hours
        day_need = job_item.get('day_need') or job_item.get('DAY_NEED')
        
        if day_need is not None:
            try:
                day_need_val = float(day_need)
                if day_need_val > 0:
                    hours_val = day_need_val * 24  # Convert days to hours
                else:
                    hours_val = job_item.get('hours_need', 1)
            except (ValueError, TypeError):
                hours_val = job_item.get('hours_need', 1)
        else:
            hours_val = job_item.get('hours_need', 1)
        
        try:
            hours_val = float(hours_val)
            if hours_val > max_hours_need:
                max_hours_need = hours_val
        except (ValueError, TypeError):
            logger.warning(f"Job {job_item.get('job_id')} has invalid duration values")
    
    if max_hours_need == 0:
        max_hours_need = 1
        
    horizon = int(max_hours_need * len(jobs) * 1.5) + 24
    return max(horizon, 24*7)  # Minimum one week

def _calculate_total_job_hours(job_item: Dict[str, Any]) -> float:
    """Calculate total hours needed including non-working time components.
    
    Priority logic:
    1. If DAY_NEED has a value, use that (convert days to hours by * 24)
    2. If DAY_NEED is empty/null, fall back to HOURS_NEED
    """
    # Priority 1: Check for DAY_NEED first
    day_need = job_item.get('day_need') or job_item.get('DAY_NEED')
    if day_need is not None:
        try:
            day_need_val = float(day_need)
            if day_need_val > 0:
                total_hours = day_need_val * 24  # Convert days to hours
                logger.debug(f"Using DAY_NEED for job {job_item.get('job_id')}: {day_need_val} days = {total_hours} hours")
            else:
                # DAY_NEED is 0 or negative, fall back to HOURS_NEED
                total_hours = job_item.get('hours_need', 1)
                try:
                    total_hours = float(total_hours)
                except (ValueError, TypeError):
                    total_hours = 1.0
                logger.debug(f"DAY_NEED is 0/negative, using HOURS_NEED for job {job_item.get('job_id')}: {total_hours} hours")
        except (ValueError, TypeError):
            # DAY_NEED is invalid, fall back to HOURS_NEED
            total_hours = job_item.get('hours_need', 1)
            try:
                total_hours = float(total_hours)
            except (ValueError, TypeError):
                total_hours = 1.0
            logger.debug(f"DAY_NEED is invalid, using HOURS_NEED for job {job_item.get('job_id')}: {total_hours} hours")
    else:
        # Priority 2: No DAY_NEED, use HOURS_NEED
        total_hours = job_item.get('hours_need', 1)
        try:
            total_hours = float(total_hours)
        except (ValueError, TypeError):
            total_hours = 1.0
        logger.debug(f"No DAY_NEED, using HOURS_NEED for job {job_item.get('job_id')}: {total_hours} hours")
    
    # Add setup time if available (convert from seconds to hours)
    setup_time = job_item.get('setup_time') or job_item.get('setting_hours', 0)
    if setup_time:
        try:
            if 'setup_time' in job_item:
                total_hours += float(setup_time) / 3600  # Convert seconds to hours
            else:
                total_hours += float(setup_time)  # Already in hours
        except (ValueError, TypeError):
            pass
            
    # Add break time if available
    break_time = job_item.get('break_time') or job_item.get('break_hours', 0)
    if break_time:
        try:
            if 'break_time' in job_item:
                total_hours += float(break_time) / 3600
            else:
                total_hours += float(break_time)
        except (ValueError, TypeError):
            pass
            
    # Add no_prod time if available
    no_prod_time = job_item.get('no_prod_time') or job_item.get('no_prod', 0)
    if no_prod_time:
        try:
            if 'no_prod_time' in job_item:
                total_hours += float(no_prod_time) / 3600
            else:
                total_hours += float(no_prod_time)
        except (ValueError, TypeError):
            pass
    
    return total_hours

def _add_sequence_constraints(model, all_tasks, job_dependencies, logger):
    """Add sequence constraints between processes of the same family."""
    logger.info("Enforcing sequence constraints between processes of the same family")
    
    # Group jobs by family to apply sequence constraints
    job_families = defaultdict(list)
    for job_id, task_info in all_tasks.items():
        original_job_id_for_family = task_info['job'].get('job')
        family = extract_job_family(job_id, job_id_suffix=original_job_id_for_family) 
        process_num = extract_process_number(job_id)
        if process_num != 999:
            job_families[family].append((process_num, job_id))
        else:
            logger.warning(f"Job {job_id} has invalid process number, cannot enforce sequence")

    for family_key, processes in job_families.items():
        processes.sort()  # Sort by process number
        for i in range(len(processes) - 1):
            pred_job_id = processes[i][1]
            succ_job_id = processes[i+1][1]
            
            if pred_job_id in all_tasks and succ_job_id in all_tasks:
                pred_end = all_tasks[pred_job_id]['end']
                succ_start = all_tasks[succ_job_id]['start']
                model.Add(pred_end <= succ_start)
                job_dependencies[succ_job_id].append(pred_job_id)
                logger.debug(f"Added sequence constraint: {pred_job_id} before {succ_job_id}")
            else:
                logger.warning(f"Skipping sequence constraint for family {family_key} due to missing tasks")

def _add_operator_constraints(model, all_tasks, max_operators, logger):
    """Add cumulative operator constraints."""
    logger.info(f"Adding cumulative operator constraint with capacity {max_operators}")
    
    operator_demands = []
    operator_intervals = []
    
    for job_id, task_info in all_tasks.items():
        num_ops = task_info['job'].get('operators') or task_info['job'].get('number_operator', 1)
        try:
            num_ops = int(num_ops) if num_ops is not None else 1
            if num_ops > 0:
                operator_intervals.append(task_info['interval'])
                operator_demands.append(num_ops)
        except (ValueError, TypeError):
            logger.warning(f"Invalid operator count for job {job_id}: {num_ops}")
        
    if operator_intervals:
        model.AddCumulative(operator_intervals, operator_demands, max_operators)
        logger.info(f"Added Cumulative constraint for {len(operator_intervals)} tasks requiring operators")
    else:
        logger.info("No jobs require operators, skipping cumulative operator constraint")

def _add_start_date_constraints(model, all_tasks, start_time_preferences, logger):
    """Add hard START_DATE constraints with priority-based conflict resolution."""
    logger.info("Adding hard START_DATE constraints with priority-based conflict resolution")
    
    # Group P01 jobs by machine to detect TIME conflicts (not just machine conflicts)
    p01_by_machine = defaultdict(list)
    for job_id, task_info in all_tasks.items():
        if job_id in start_time_preferences:
            process_num = extract_process_number(job_id)
            if process_num == 1:  # P01 process
                machine = task_info['machine']
                priority = task_info['job'].get('priority', 3)
                try:
                    priority = int(priority)
                except (ValueError, TypeError):
                    priority = 3
                p01_by_machine[machine].append({
                    'job_id': job_id,
                    'priority': priority,
                    'start_date_rel_int': start_time_preferences[job_id],
                    'duration': task_info['hours'],
                    'task_info': task_info
                })
    
    # For each machine, detect actual TIME conflicts and resolve by priority
    for machine, jobs_list in p01_by_machine.items():
        if len(jobs_list) > 1:
            # Check for actual time overlaps
            conflicts = []
            for i, job1 in enumerate(jobs_list):
                for j, job2 in enumerate(jobs_list[i+1:], i+1):
                    job1_start = job1['start_date_rel_int']
                    job1_end = job1_start + job1['duration']
                    job2_start = job2['start_date_rel_int']
                    job2_end = job2_start + job2['duration']
                    
                    # Check if time windows overlap
                    if not (job1_end <= job2_start or job2_end <= job1_start):
                        # Time conflict detected
                        conflict_pair = [job1, job2]
                        conflict_pair.sort(key=lambda x: x['priority'])  # Sort by priority
                        conflicts.append(conflict_pair)
                        logger.info(f"Time conflict on {machine}: {job1['job_id']} vs {job2['job_id']}")
            
            if conflicts:
                # Handle conflicts by priority
                resolved_jobs = set()
                for conflict_pair in conflicts:
                    higher_priority_job, lower_priority_job = conflict_pair
                    if higher_priority_job['job_id'] not in resolved_jobs:
                        # Make highest priority job exact
                        start_var = higher_priority_job['task_info']['start']
                        model.Add(start_var == higher_priority_job['start_date_rel_int'])
                        logger.debug(f"Added EXACT START_DATE for priority job {higher_priority_job['job_id']}")
                        resolved_jobs.add(higher_priority_job['job_id'])
                    
                    if lower_priority_job['job_id'] not in resolved_jobs:
                        # Make lower priority job flexible
                        start_var = lower_priority_job['task_info']['start']
                        model.Add(start_var >= lower_priority_job['start_date_rel_int'])
                        logger.debug(f"Added flexible START_DATE for {lower_priority_job['job_id']}")
                        resolved_jobs.add(lower_priority_job['job_id'])
                
                # Make non-conflicting jobs exact
                for job_data in jobs_list:
                    if job_data['job_id'] not in resolved_jobs:
                        start_var = job_data['task_info']['start']
                        model.Add(start_var == job_data['start_date_rel_int'])
                        logger.debug(f"Added EXACT START_DATE for non-conflicting job {job_data['job_id']}")
            else:
                # No time conflicts, make all jobs exact
                for job_data in jobs_list:
                    start_var = job_data['task_info']['start']
                    model.Add(start_var == job_data['start_date_rel_int'])
                    logger.debug(f"Added EXACT START_DATE for single P01 job {job_data['job_id']}")
        else:
            # Single job on machine, make it exact
            job_data = jobs_list[0]
            start_var = job_data['task_info']['start']
            model.Add(start_var == job_data['start_date_rel_int'])
            logger.debug(f"Added EXACT START_DATE for single P01 job {job_data['job_id']}")
    
    # Handle non-P01 jobs with START_DATE (minimum bound)
    for job_id, task_info in all_tasks.items():
        if job_id in start_time_preferences:
            process_num = extract_process_number(job_id)
            if process_num != 1:  # Not P01
                start_date_rel_int = start_time_preferences[job_id]
                start_var = task_info['start']
                model.Add(start_var >= start_date_rel_int)
                logger.debug(f"Added minimum START_DATE constraint for non-P01 job {job_id}")

def _add_working_hours_constraints(model, all_tasks, logger):
    """Add SIMPLE working hours constraints: jobs can only start between 8am-6pm each day."""
    logger.info("Adding SIMPLE working hours constraints (8am-6pm daily)")
    
    # SIMPLE approach: For each job, constrain start time to working hours
    # Working hours: 8am-6pm = hours 8-18 each day
    constraints_added = 0
    
    for job_id, task_info in all_tasks.items():
        start_var = task_info['start']
        job_duration = task_info['hours']
        
        # Simple constraint: For any day, job can only start between 8am-6pm
        # and must finish by 6pm (so start <= 18 - duration)
        
        # Create constraint for each possible day (up to 7 days)
        valid_slots = []
        
        for day in range(7):  # Look at first 7 days only
            # Calculate working hours for this day
            day_start = day * 24 + 8   # 8am on day N
            day_end = day * 24 + 18    # 6pm on day N
            
            # Latest possible start time (job must finish by 6pm)
            latest_start = day_end - job_duration
            
            if latest_start >= day_start:
                # Valid time slot exists for this day
                valid_slots.append((day_start, latest_start))
                logger.debug(f"Job {job_id} Day {day}: Can start between {day_start}-{latest_start} hours")
        
        if valid_slots:
            # Create constraint: start_var must be in one of the valid slots
            slot_bools = []
            
            for slot_start, slot_end in valid_slots:
                if slot_start <= slot_end:
                    # Create boolean for this time slot
                    day_num = slot_start // 24
                    slot_bool = model.NewBoolVar(f'work_slot_{job_id}_day{day_num}')
                    
                    # If this slot is chosen, constrain start time
                    model.Add(start_var >= slot_start).OnlyEnforceIf(slot_bool)
                    model.Add(start_var <= slot_end).OnlyEnforceIf(slot_bool)
                    
                    slot_bools.append(slot_bool)
            
            if slot_bools:
                # Exactly one time slot must be chosen
                model.AddExactlyOne(slot_bools)
                constraints_added += 1
                logger.debug(f"Added working hours constraint for {job_id}: {len(slot_bools)} valid slots")
            else:
                logger.warning(f"No valid time slots for job {job_id} (duration {job_duration}h too long)")
        else:
            logger.warning(f"Job {job_id} cannot fit in any working day (duration: {job_duration}h)")
    
    logger.info(f"Added SIMPLE working hours constraints for {constraints_added} jobs")


def _add_deadline_constraints(model, all_tasks, jobs_with_due_dates, logger, enforce_deadlines):
    """Add hard LCD_DATE (deadline) constraints - jobs MUST complete before deadline."""
    if not enforce_deadlines:
        logger.info("Deadline constraints disabled - skipping LCD_DATE constraints")
        return
        
    logger.info("Adding hard LCD_DATE (deadline) constraints - jobs MUST complete before deadline")
    
    current_time_rel = epoch_to_relative_hours(datetime_to_epoch(datetime.now()))
    grace_period_hours = 24  # 24-hour grace period for already late jobs
    
    for job_id, due_date_rel_int in jobs_with_due_dates.items():
        if job_id in all_tasks:
            end_var = all_tasks[job_id]['end']
            
            # If the job's deadline is already in the past, give it a grace period
            if due_date_rel_int < current_time_rel:
                adjusted_deadline = current_time_rel + grace_period_hours
                model.Add(end_var <= int(adjusted_deadline))
                logger.debug(f"Added grace period LCD_DATE constraint for late job {job_id}: end <= {int(adjusted_deadline)} (original: {due_date_rel_int})")
            else:
                model.Add(end_var <= due_date_rel_int)
                logger.debug(f"Added hard LCD_DATE constraint for job {job_id}: end <= {due_date_rel_int}")
        else:
            logger.warning(f"Job {job_id} has a due date but was not found in all_tasks")

def _create_objective_function(model, all_ends, jobs_with_due_dates, start_time_preferences, all_tasks, horizon, logger):
    """Create the objective function for the model."""
    objective_terms = []
    
    if not all_ends:
        return objective_terms
    
    # 1. PRIORITY: Higher priority jobs (lower priority numbers) should start earlier
    priority_penalty_vars = []
    for job_id, task_info in all_tasks.items():
        priority = task_info['job'].get('priority', 3)  # Default to medium priority
        try:
            priority = int(priority)
        except (ValueError, TypeError):
            priority = 3
            
        if priority > 0:  # Only penalize jobs with priority > 0
            start_var = task_info['start']
            # Create penalty variable: priority * start_time
            # Higher priority (lower number) jobs get less penalty for starting late
            priority_penalty = model.NewIntVar(0, horizon * priority * 10, f'priority_penalty_{job_id}')
            model.Add(priority_penalty == start_var * priority)
            priority_penalty_vars.append(priority_penalty)
    
    if priority_penalty_vars:
        priority_weight = 100  # High weight to prioritize this constraint
        total_priority_penalty = model.NewIntVar(0, horizon * len(priority_penalty_vars) * 30, 'total_priority_penalty')
        model.Add(total_priority_penalty == sum(priority_penalty_vars))
        objective_terms.append(total_priority_penalty * priority_weight)
        logger.debug(f"Added priority optimization for {len(priority_penalty_vars)} jobs with weight {priority_weight}")
    
    # 2. Makespan (overall completion time)
    makespan = model.NewIntVar(0, horizon * 2, 'makespan')
    model.AddMaxEquality(makespan, all_ends)
    objective_terms.append(makespan)
    
    # Note: LCD_DATE constraints are now HARD constraints (jobs MUST complete before deadline)
    # START_DATE constraints are EXACT equality constraints (hard)
    # Constraint priority order: LCD_DATE (hard) → START_DATE (hard) → Priority (weight 100) → Makespan (weight 1)
    
    return objective_terms

def _solve_model(model, time_limit_seconds, logger):
    """Solve the CP-SAT model with performance optimizations."""
    solver = cp_model.CpSolver()
    
    # Performance optimizations for faster solving
    solver.parameters.max_time_in_seconds = float(time_limit_seconds)
    
    # CRITICAL: Disable verbose logging that was causing the flood
    solver.parameters.log_search_progress = False
    solver.parameters.log_to_stdout = False
    
    # Advanced solver parameters for better performance
    solver.parameters.num_search_workers = min(os.cpu_count() or 4, 8)  # Cap workers at 8
    solver.parameters.search_branching = cp_model.PORTFOLIO_SEARCH  # Better search strategy
    solver.parameters.cp_model_presolve = True  # Enable preprocessing
    solver.parameters.linearization_level = 2  # More aggressive linearization
    
    # Gap limits for early termination when solution is good enough
    solver.parameters.relative_gap_limit = 0.02  # Stop at 2% gap
    solver.parameters.absolute_gap_limit = 1000  # Or absolute gap of 1000
    
    # Performance monitoring
    solver.parameters.cp_model_probing_level = 0  # Disable probing for speed
    solver.parameters.symmetry_level = 1  # Reduce symmetry breaking overhead
    
    logger.info(f"Solver configured: time_limit={time_limit_seconds}s, workers={solver.parameters.num_search_workers}, "
                f"gap_limits=[rel:2%, abs:1000], logging=disabled")
    
    start_solve_time = time.time()
    status = solver.Solve(model)
    solve_time = time.time() - start_solve_time
    
    # Enhanced logging with performance metrics
    if status == cp_model.OPTIMAL:
        logger.info(f"✅ OPTIMAL solution found in {solve_time:.2f}s, objective: {solver.ObjectiveValue()}")
    elif status == cp_model.FEASIBLE:
        logger.info(f"✅ FEASIBLE solution found in {solve_time:.2f}s, objective: {solver.ObjectiveValue()}")
    elif status == cp_model.UNKNOWN:
        logger.warning(f"⏱️  Solver timed out after {solve_time:.2f}s - may need problem size reduction")
    elif status == cp_model.INFEASIBLE:
        logger.error(f"❌ INFEASIBLE problem in {solve_time:.2f}s - constraints cannot be satisfied")
    else:
        logger.error(f"❌ Solver failed with status: {solver.StatusName(status)} in {solve_time:.2f}s")
    
    # Performance warnings
    if solve_time > 25:
        logger.warning(f"⚠️  Solver took {solve_time:.1f}s (>25s) - consider reducing problem size")
    
    # Log solver statistics for performance tuning
    try:
        stats = solver.ResponseStats()
        logger.debug(f"Solver stats: {stats}")
    except Exception as e:
        logger.debug(f"Could not get solver stats: {e}")
    
    return {
        'solver': solver,
        'status': status,
        'solve_time': solve_time,
        'model': model,
        'performance_warning': solve_time > 25
    }

def _process_solver_results(solver_result, all_tasks, reference_time_epoch, job_dependencies, 
                          start_date_processes, jobs_with_due_dates, enforce_sequence, logger):
    """Process the solver results and create the final schedule with performance metrics."""
    solver = solver_result['solver']
    status = solver_result['status']
    solve_time = solver_result['solve_time']
    performance_warning = solver_result.get('performance_warning', False)
    
    # Enhanced metadata with performance tracking
    metadata = {
        'status': solver.StatusName(status),
        'solver_time': solve_time,
        'objective_value': solver.ObjectiveValue() if status in [cp_model.OPTIMAL, cp_model.FEASIBLE] else None,
        'reference_time_epoch': reference_time_epoch,
        'job_dependencies': job_dependencies,
        'start_date_constraints': start_date_processes,
        'due_dates_considered': jobs_with_due_dates,
        'solver_stats': solver.ResponseStats(),
        'performance_metrics': {
            'solve_time_seconds': solve_time,
            'is_optimal': status == cp_model.OPTIMAL,
            'is_feasible': status in [cp_model.OPTIMAL, cp_model.FEASIBLE],
            'timed_out': status == cp_model.UNKNOWN,
            'performance_warning': performance_warning,
            'num_jobs_processed': len(all_tasks),
            'solver_efficiency': 'FAST' if solve_time < 10 else 'MEDIUM' if solve_time < 25 else 'SLOW'
        }
    }
    
    # Add performance recommendations
    recommendations = []
    if performance_warning:
        recommendations.append("Consider reducing planning horizon or job limit for faster solving")
    if status == cp_model.UNKNOWN:
        recommendations.append("Solver timed out - try smaller problem size or longer time limit")
    if solve_time < 5 and len(all_tasks) < 50:
        recommendations.append("Problem size is small - could increase planning horizon")
        
    metadata['recommendations'] = recommendations
    
    # Prepare results
    results = {'_metadata': metadata}
    time_adjusted_jobs = 0

    if status == cp_model.OPTIMAL or status == cp_model.FEASIBLE:
        logger.info(f"Solution found. Objective value: {solver.ObjectiveValue()}")

        for job_id, task_info in all_tasks.items():
            start_val_rel = solver.Value(task_info['start'])
            end_val_rel = solver.Value(task_info['end'])
            
            # Convert relative start/end times back to epoch timestamps
            start_epoch = relative_hours_to_epoch(start_val_rel)
            end_epoch = relative_hours_to_epoch(end_val_rel)
            
            # Check time availability and adjust if necessary
            if not is_time_available(start_epoch, end_epoch):
                logger.debug(f"Job {job_id} scheduled outside working hours: {format_datetime_for_display(epoch_to_datetime(start_epoch))} to {format_datetime_for_display(epoch_to_datetime(end_epoch))}")
                
                # Calculate job duration in hours
                duration_hours = (end_epoch - start_epoch) / 3600
                
                # Find next available slot
                next_available_start = get_next_available_slot(start_epoch, duration_hours)
                
                if next_available_start:
                    new_start_epoch = next_available_start
                    new_end_epoch = new_start_epoch + (end_epoch - start_epoch)  # Keep same duration
                    
                    logger.info(f"Moved job {job_id} from {format_datetime_for_display(epoch_to_datetime(start_epoch))} to {format_datetime_for_display(epoch_to_datetime(new_start_epoch))} (working hours adjustment)")
                    
                    start_epoch = new_start_epoch
                    end_epoch = new_end_epoch
                    time_adjusted_jobs += 1
                else:
                    logger.warning(f"Could not find available time slot for job {job_id} - keeping original schedule")
            
            machine_val = task_info['machine']
            priority = task_info['job'].get('priority', 3)
            
            job_result = {
                'job_id': job_id,
                'machine': machine_val,
                'start': int(start_epoch),
                'end': int(end_epoch),
                'priority': priority,
                'duration_hours': task_info['hours'],
                'original_job_data': task_info['job']
            }
            results[job_id] = job_result
            
            logger.debug(f"Scheduled {job_id} on {machine_val}: "
                        f"Start={format_datetime_for_display(epoch_to_datetime(start_epoch))}, "
                        f"End={format_datetime_for_display(epoch_to_datetime(end_epoch))}")

        # Add time adjustment info to metadata
        if time_adjusted_jobs > 0:
            logger.info(f"Adjusted {time_adjusted_jobs} jobs to comply with working hours, holidays, and break times")
            metadata['time_adjustments'] = {
                'jobs_moved': time_adjusted_jobs,
                'reason': 'Working hours, holidays, and break time compliance'
            }

        # Validate sequence if enforced
        if enforce_sequence:
            _validate_sequence_constraints(results, job_dependencies, logger)

    elif status == cp_model.INFEASIBLE:
        logger.error("No solution found: The problem is infeasible")
        results['_metadata']['message'] = "The scheduling problem is infeasible with the given constraints"

    elif status == cp_model.MODEL_INVALID:
        logger.error("No solution found: The model is invalid")
        results['_metadata']['message'] = "The CP-SAT model is invalid"
        
    else:
        logger.warning(f"No optimal or feasible solution found. Status: {solver.StatusName(status)}")
        results['_metadata']['message'] = f"Solver did not find an optimal/feasible solution. Status: {solver.StatusName(status)}"

    return results

def _validate_sequence_constraints(results, job_dependencies, logger):
    """Validate that sequence constraints are satisfied in the final schedule."""
    logger.info("Validating sequence constraints in the final schedule")
    violations = 0
    
    for succ_job_id, pred_job_ids in job_dependencies.items():
        if succ_job_id not in results:
            continue
            
        succ_start_epoch = results[succ_job_id]['start']
        for pred_job_id in pred_job_ids:
            if pred_job_id not in results:
                continue
                
            pred_end_epoch = results[pred_job_id]['end']
            if pred_end_epoch > succ_start_epoch:
                violations += 1
                logger.error(f"SEQUENCE VIOLATION: {pred_job_id} (ends {format_datetime_for_display(epoch_to_datetime(pred_end_epoch))}) "
                           f"should end before {succ_job_id} (starts {format_datetime_for_display(epoch_to_datetime(succ_start_epoch))})")
    
    if violations > 0:
        logger.error(f"Found {violations} sequence violations in the CP-SAT schedule!")
        results['_metadata']['sequence_violations'] = violations
    else:
        logger.info("All sequence constraints are satisfied")

if __name__ == '__main__':
    # Example usage
    start_time = time.time()
    results = None
    
    # Import locally just for the CLI example
    from app.data_ingestion.mariadb_parser import load_jobs_planning_data
    
    try:
        # Run with test data
        jobs, machines, setup_times = load_jobs_planning_data()
        if jobs and machines:
            results = schedule_jobs(jobs, machines, setup_times)
        else:
            logger.error("No jobs or machines loaded")
            results = _create_error_result("No jobs or machines loaded")
    except Exception as e:
        logger.error(f"Error loading jobs: {e}")
        results = _create_error_result(f"Error loading jobs: {e}")
    finally:
        logger.info(f"Total execution time: {time.time() - start_time:.2f} seconds")

    if results and results.get('_metadata', {}).get('status') in ['OPTIMAL', 'FEASIBLE']:
        print("\nCP-SAT Schedule Output (First 5 tasks per machine):")
        
        # Create a temporary machine-grouped schedule for printing
        machine_grouped = defaultdict(list)
        for job_id_key, details in results.items():
            if job_id_key == '_metadata':
                continue
            machine_grouped[details['machine']].append(
                (details['job_id'], details['start'], details['end'], details['priority'], {})
            )

        for machine_key in machine_grouped:
            machine_grouped[machine_key].sort(key=lambda x: x[1])

        for machine_print_key, tasks_to_print in machine_grouped.items():
            if tasks_to_print:
                print(f"  Machine: {machine_print_key}")
                for i, task_tuple in enumerate(tasks_to_print[:5]):
                    job_id_p, start_epoch_p, end_epoch_p, priority_p, *_ = task_tuple
                    start_dt_p = format_datetime_for_display(epoch_to_datetime(start_epoch_p))
                    end_dt_p = format_datetime_for_display(epoch_to_datetime(end_epoch_p))
                    print(f"    Task {i+1}: Job={job_id_p}, Start={start_dt_p}, End={end_dt_p}, Priority={priority_p}")
        
        print(f"\nObjective Value: {results['_metadata']['objective_value']}")
        print(f"Solver Time: {results['_metadata']['solver_time']:.2f}s")
    else:
        print("No schedule generated or solution was not optimal/feasible")
        if results and '_metadata' in results:
            print(f"  Status: {results['_metadata'].get('status')}")
            print(f"  Message: {results['_metadata'].get('message')}") 