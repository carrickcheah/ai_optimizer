#!/usr/bin/env python3
"""
Debug script to analyze dependency chain issues.
Focuses on JOTP25050215_CP08-563A sequence
"""

import logging
import time
from datetime import datetime
from typing import Dict, List, Any

# Setup logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def debug_dependency_chain():
    """Debug why dependency chain is failing."""
    try:
        # Import necessary modules
        from app.data_ingestion.mariadb_parser import load_jobs_planning_data
        from app.scheduling.greedy_solver import (
            GreedyConfigManager, JobValidator, MachineManager, 
            SchedulingConstraints, GreedyScheduler
        )
        from app.utils.time_utils import datetime_to_epoch, epoch_to_datetime
        
        print("=== DEBUGGING DEPENDENCY CHAIN ===")
        
        # Target job family
        target_family = "JOTP25050215_CP08-563A"
        
        # Load data
        print("Loading jobs and machines data...")
        jobs, machines, setup_times = load_jobs_planning_data()
        print(f"Loaded {len(jobs)} jobs and {len(machines)} machines")
        
        # Load configuration
        config = GreedyConfigManager.load_config()
        
        # Find all jobs in the family
        family_jobs = []
        for job in jobs:
            job_id = job.get('job_id', '')
            if target_family in job_id:
                family_jobs.append(job)
                
        print(f"\n=== FOUND {len(family_jobs)} JOBS IN FAMILY ===")
        for job in sorted(family_jobs, key=lambda x: x.get('job_id', '')):
            job_id = job.get('job_id', '')
            print(f"Job: {job_id}")
            print(f"  Machine: {job.get('MachineName_v', 'Unknown')}")
            print(f"  Priority: {job.get('priority', 'Unknown')}")
            print(f"  Processing Time: {job.get('processing_time', 'Unknown')} seconds")
            if job.get('processing_time'):
                hours = job.get('processing_time') / 3600
                print(f"  Processing Hours: {hours:.1f} hours")
            print(f"  LCD Date: {job.get('lcd_date', 'Unknown')}")
            print()
        
        # Validate and prepare jobs
        print("=== VALIDATING JOBS ===")
        valid_jobs = JobValidator.validate_and_prepare_jobs(jobs)
        machine_names = MachineManager.prepare_machines(machines)
        
        # Find family jobs in valid set
        valid_family_jobs = []
        valid_job_ids = {job['job_id'] for job in valid_jobs}
        for job in family_jobs:
            if job['job_id'] in valid_job_ids:
                valid_family_jobs.append(next(j for j in valid_jobs if j['job_id'] == job['job_id']))
                print(f"✅ {job['job_id']} passed validation")
            else:
                print(f"❌ {job['job_id']} FAILED validation")
        
        if not valid_family_jobs:
            print("No valid family jobs found!")
            return
            
        # Initialize scheduler components
        constraints = SchedulingConstraints(config)
        current_time = datetime_to_epoch(datetime.now())
        
        print(f"\n=== SEQUENTIAL SCHEDULING TEST ===")
        print(f"Current time: {datetime.now()}")
        
        # Create a minimal schedule to test dependencies
        test_schedule = {machine: [] for machine in machine_names}
        family_end_times = {}
        process_end_times = {}
        
        # Sort jobs by process number
        sorted_jobs = sorted(valid_family_jobs, key=lambda x: x.get('job_id', ''))
        
        for i, job in enumerate(sorted_jobs):
            job_id = job['job_id']
            process_num = i + 1  # Assume sequential processes
            
            print(f"\n--- TESTING {job_id} (Process {process_num}) ---")
            
            # Find best machine
            machine_id = MachineManager.find_best_machine(
                job, machine_names, 
                {m: current_time for m in machine_names}
            )
            print(f"Best machine: {machine_id}")
            
            # Determine earliest start time
            if process_num > 1:
                # This job depends on previous process
                prev_key = (target_family, process_num - 1)
                if prev_key in process_end_times:
                    earliest_start = process_end_times[prev_key]
                    print(f"Dependency: Must start after {epoch_to_datetime(earliest_start)}")
                else:
                    print(f"❌ DEPENDENCY MISSING: Process {process_num-1} not completed")
                    continue
            else:
                earliest_start = current_time
                print(f"No dependencies - can start at current time")
            
            # Test scheduling at different times
            machine_available_time = max(
                test_schedule.get(machine_id, [])[-1][2] if test_schedule.get(machine_id) else current_time,
                earliest_start
            )
            
            print(f"Machine {machine_id} available at: {epoch_to_datetime(machine_available_time)}")
            
            # Test at machine available time
            can_schedule = constraints.can_schedule_job(
                job, machine_id, machine_available_time, 
                test_schedule, {}, 0  # No operator constraints
            )
            
            print(f"Can schedule at machine available time: {can_schedule}")
            
            if can_schedule:
                # Schedule the job
                end_time = machine_available_time + job['processing_time']
                test_schedule[machine_id].append((job_id, machine_available_time, end_time, 0))
                process_end_times[(target_family, process_num)] = end_time
                
                print(f"✅ Scheduled: {epoch_to_datetime(machine_available_time)} to {epoch_to_datetime(end_time)}")
            else:
                # Test individual constraints
                end_time = machine_available_time + job['processing_time']
                
                # Machine availability
                machine_avail = constraints._check_machine_availability(
                    machine_id, machine_available_time, end_time, test_schedule
                )
                print(f"  Machine available: {machine_avail}")
                
                # Deadline constraints
                deadline_ok = constraints._check_deadline_constraints(job, end_time)
                print(f"  Deadline OK: {deadline_ok}")
                
                # Time availability
                time_avail = constraints._check_time_availability(machine_available_time, end_time, job)
                print(f"  Time available: {time_avail}")
                
                print(f"❌ Cannot schedule - blocking dependency chain")
                break
    
    except Exception as e:
        logger.error(f"Error in dependency chain analysis: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    debug_dependency_chain()