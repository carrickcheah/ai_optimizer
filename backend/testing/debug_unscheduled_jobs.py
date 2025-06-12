#!/usr/bin/env python3
"""
Debug script to analyze why specific jobs cannot be scheduled.
Focuses on JOPRD25050232_VPSB-SAMP-1/2 and JOTP25050215_CP08-563A-1/3
"""

import logging
import time
from datetime import datetime
from typing import Dict, List, Any

# Setup logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def debug_job_scheduling():
    """Debug why specific jobs cannot be scheduled."""
    try:
        # Import necessary modules
        from app.data_ingestion.mariadb_parser import load_jobs_planning_data
        from app.scheduling.greedy_solver import (
            GreedyConfigManager, JobValidator, MachineManager, 
            SchedulingConstraints, GreedyScheduler
        )
        from app.utils.time_utils import datetime_to_epoch, epoch_to_datetime
        
        print("=== DEBUGGING UNSCHEDULED JOBS ===")
        
        # Target jobs to analyze
        target_jobs = [
            "JOPRD25050232_VPSB-SAMP-1/2",
            "JOTP25050215_CP08-563A-1/3"
        ]
        
        # Load data
        print("Loading jobs and machines data...")
        jobs, machines, setup_times = load_jobs_planning_data()
        print(f"Loaded {len(jobs)} jobs and {len(machines)} machines")
        
        # Load configuration
        config = GreedyConfigManager.load_config()
        print(f"Configuration loaded: {config.scheduler_search_days} search days")
        
        # Find target jobs in the dataset
        target_job_data = {}
        for job in jobs:
            job_id = job.get('job_id', '')
            if job_id in target_jobs:
                target_job_data[job_id] = job
                print(f"\n=== FOUND TARGET JOB: {job_id} ===")
                print(f"Machine: {job.get('MachineName_v', 'Unknown')}")
                print(f"Priority: {job.get('priority', 'Unknown')}")
                print(f"LCD Date: {job.get('lcd_date', 'Unknown')}")
                print(f"Processing Time: {job.get('processing_time', 'Unknown')} seconds")
                print(f"Hours Need: {job.get('hours_need', 'Unknown')}")
                print(f"Day Need: {job.get('day_need', 'Unknown')}")
                print(f"Job Quantity: {job.get('job_quantity', 'Unknown')}")
                print(f"Output Per Hour: {job.get('expect_output_per_hour', 'Unknown')}")
        
        if not target_job_data:
            print("❌ Target jobs not found in dataset!")
            return
        
        # Validate and prepare jobs
        print("\n=== VALIDATING JOBS ===")
        valid_jobs = JobValidator.validate_and_prepare_jobs(jobs)
        machine_names = MachineManager.prepare_machines(machines)
        
        # Check if target jobs are in valid jobs
        valid_job_ids = {job['job_id'] for job in valid_jobs}
        for job_id in target_jobs:
            if job_id in valid_job_ids:
                print(f"✅ {job_id} passed validation")
            else:
                print(f"❌ {job_id} FAILED validation - this is why it's unscheduled!")
        
        # Initialize scheduler components
        constraints = SchedulingConstraints(config)
        current_time = datetime_to_epoch(datetime.now())
        
        print(f"\n=== SCHEDULING ANALYSIS ===")
        print(f"Current time: {datetime.now()}")
        print(f"Search window: {config.scheduler_search_days} days")
        
        # For each target job, analyze why it can't be scheduled
        for job_id, job_data in target_job_data.items():
            if job_id not in valid_job_ids:
                continue
                
            print(f"\n--- ANALYZING {job_id} ---")
            
            # Get validated job data
            validated_job = next((j for j in valid_jobs if j['job_id'] == job_id), None)
            if not validated_job:
                continue
            
            # Find best machine
            machine_id = MachineManager.find_best_machine(
                validated_job, machine_names, 
                {m: current_time for m in machine_names}
            )
            print(f"Best machine: {machine_id}")
            
            # Test scheduling constraints
            print("\n--- CONSTRAINT TESTING ---")
            
            # Create minimal schedule for testing
            test_schedule = {machine: [] for machine in machine_names}
            test_operators = {}
            
            # Test different start times
            search_times = [
                current_time,
                current_time + 3600,  # +1 hour
                current_time + 86400,  # +1 day
                current_time + 2*86400,  # +2 days
            ]
            
            for i, start_time in enumerate(search_times):
                print(f"Test {i+1}: Start time {epoch_to_datetime(start_time)}")
                can_schedule = constraints.can_schedule_job(
                    validated_job, machine_id, start_time, 
                    test_schedule, test_operators, 0  # max_operators=0
                )
                print(f"  Can schedule: {can_schedule}")
                
                if not can_schedule:
                    # Test individual constraints
                    end_time = start_time + validated_job['processing_time']
                    
                    # Machine availability
                    machine_avail = constraints._check_machine_availability(
                        machine_id, start_time, end_time, test_schedule
                    )
                    print(f"  Machine available: {machine_avail}")
                    
                    # Deadline constraints
                    deadline_ok = constraints._check_deadline_constraints(validated_job, end_time)
                    print(f"  Deadline OK: {deadline_ok}")
                    
                    # Time availability
                    time_avail = constraints._check_time_availability(start_time, end_time, validated_job)
                    print(f"  Time available: {time_avail}")
            
            # Check LCD deadline details
            if 'lcd_date_epoch' in validated_job and validated_job['lcd_date_epoch']:
                lcd_deadline = validated_job['lcd_date_epoch']
                deadline_dt = epoch_to_datetime(lcd_deadline)
                is_overdue = lcd_deadline < current_time
                
                print(f"\n--- DEADLINE ANALYSIS ---")
                print(f"LCD Deadline: {deadline_dt}")
                print(f"Is overdue: {is_overdue}")
                
                if is_overdue:
                    grace_seconds = config.grace_period_hours * 3600
                    priority = validated_job.get('priority', 3)
                    if priority <= 2:
                        grace_seconds *= 2
                    
                    grace_deadline = current_time + grace_seconds
                    grace_dt = epoch_to_datetime(grace_deadline)
                    print(f"Grace deadline: {grace_dt}")
                    print(f"Grace period: {grace_seconds/3600:.1f} hours")
    
    except Exception as e:
        logger.error(f"Error in debug analysis: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    debug_job_scheduling()