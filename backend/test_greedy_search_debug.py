#!/usr/bin/env python3
"""
Test the greedy search mechanism for JOST25050169_CP08-384-1/3.
"""

import logging
from datetime import datetime
import pytz

# Setup logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def test_greedy_search():
    """Test the greedy search mechanism."""
    try:
        from app.data_ingestion.mariadb_parser import load_jobs_planning_data
        from app.scheduling.greedy_solver import (
            GreedyConfigManager, JobValidator, MachineManager, 
            SchedulingConstraints, GreedyScheduler
        )
        from app.scheduling.time_availability import get_next_available_slot
        from app.utils.time_utils import datetime_to_epoch, epoch_to_datetime
        
        print("=== TESTING GREEDY SEARCH FOR JOST25050169_CP08-384-1/3 ===")
        
        # Load data
        jobs, machines, setup_times = load_jobs_planning_data()
        config = GreedyConfigManager.load_config()
        valid_jobs = JobValidator.validate_and_prepare_jobs(jobs)
        machine_names = MachineManager.prepare_machines(machines)
        
        # Find the target job
        target_job = None
        for job in valid_jobs:
            if job['job_id'] == 'JOST25050169_CP08-384-1/3':
                target_job = job
                break
        
        if not target_job:
            print("❌ Job not found!")
            return
        
        print(f"Found job: {target_job['job_id']} ({target_job.get('processing_time', 0)/3600:.1f}h)")
        
        # Simulate the greedy search mechanism
        current_time = datetime_to_epoch(datetime.now())
        machine_id = 'SM01'  # From previous test
        constraints = SchedulingConstraints(config)
        test_schedule = {machine: [] for machine in machine_names}
        
        # Simulate the search logic from _find_and_schedule_job
        search_limit_hours = config.scheduler_search_days * 24
        max_search_time = current_time + search_limit_hours * 3600
        
        current_search_time = current_time
        increment = 3600  # 1 hour
        attempts = 0
        max_attempts_per_increment = 48
        
        print(f"\nStarting search from: {epoch_to_datetime(current_search_time)}")
        print(f"Search limit: {search_limit_hours} hours")
        
        found_slot = False
        search_iterations = 0
        
        while current_search_time < max_search_time and search_iterations < 10:  # Limit iterations for demo
            search_iterations += 1
            print(f"\nIteration {search_iterations}:")
            print(f"  Checking time: {epoch_to_datetime(current_search_time)}")
            
            # Test if we can schedule at this time
            can_schedule = constraints.can_schedule_job(
                target_job, machine_id, current_search_time, test_schedule, {}, 0
            )
            
            print(f"  Can schedule: {can_schedule}")
            
            if can_schedule:
                print(f"✅ Found valid slot at: {epoch_to_datetime(current_search_time)}")
                found_slot = True
                break
            
            # Try using get_next_available_slot (as the greedy algorithm does)
            try:
                processing_time_hours = target_job.get('processing_time', 3600) / 3600
                next_available = get_next_available_slot(current_search_time, processing_time_hours)
                
                if next_available and next_available > current_search_time:
                    print(f"  get_next_available_slot suggests: {epoch_to_datetime(next_available)}")
                    current_search_time = next_available
                    continue
                else:
                    print(f"  get_next_available_slot returned: {next_available}")
            except Exception as e:
                print(f"  get_next_available_slot failed: {e}")
            
            # Fallback to incremental search
            current_search_time += increment
            attempts += 1
            print(f"  Incremental search, next time: {epoch_to_datetime(current_search_time)}")
            
            # Adaptive search
            if attempts >= max_attempts_per_increment:
                if increment < 86400:
                    increment = min(increment * 2, 86400)
                    print(f"  Increasing increment to {increment/3600:.1f} hours")
                attempts = 0
        
        if not found_slot:
            print(f"❌ No slot found after {search_iterations} iterations")
            
            # Test what get_next_available_slot returns from current time
            print(f"\nDirect test of get_next_available_slot:")
            processing_time_hours = target_job.get('processing_time', 3600) / 3600
            next_slot = get_next_available_slot(current_time, processing_time_hours)
            if next_slot:
                print(f"  Returns: {epoch_to_datetime(next_slot)}")
                
                # Test if we can schedule at that slot
                can_schedule_there = constraints.can_schedule_job(
                    target_job, machine_id, next_slot, test_schedule, {}, 0
                )
                print(f"  Can schedule there: {can_schedule_there}")
            else:
                print(f"  Returns: None")
                
    except Exception as e:
        logger.error(f"Error in test: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_greedy_search()