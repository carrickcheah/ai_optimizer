#!/usr/bin/env python3
"""
Test the overloaded machine fix to confirm it's working.
"""

import logging
from datetime import datetime
import pytz

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def test_overload_fix():
    """Test that the overloaded machine fix works."""
    try:
        from app.data_ingestion.mariadb_parser import load_jobs_planning_data
        from app.scheduling.greedy_solver import greedy_schedule
        
        print("=== TESTING OVERLOADED MACHINE FIX ===")
        
        # Load data and run greedy scheduling
        jobs, machines, setup_times = load_jobs_planning_data()
        
        print(f"Loaded {len(jobs)} jobs and {len(machines)} machines")
        
        # Run greedy scheduling
        print("Running greedy scheduling with overload fix...")
        schedule = greedy_schedule(jobs, machines, setup_times, enforce_sequence=True, max_operators=0)
        
        # Count scheduled vs unscheduled jobs
        total_scheduled = sum(len(tasks) for tasks in schedule.values())
        total_jobs = len(jobs)
        success_rate = (total_scheduled / total_jobs * 100) if total_jobs > 0 else 0
        
        print(f"\n=== RESULTS ===")
        print(f"Total jobs: {total_jobs}")
        print(f"Successfully scheduled: {total_scheduled}")
        print(f"Failed to schedule: {total_jobs - total_scheduled}")
        print(f"Success rate: {success_rate:.1f}%")
        
        # Look specifically for the jobs that were previously failing
        target_jobs = ['JOST25050169_CP08-384-1/3', 'JOST25050207_CP08-560-1/2']
        
        print(f"\n=== CHECKING TARGET JOBS ===")
        for target_job in target_jobs:
            found = False
            for machine, tasks in schedule.items():
                for task in tasks:
                    if task[0] == target_job:  # task[0] is job_id
                        print(f"✅ {target_job} scheduled on {machine}")
                        found = True
                        break
                if found:
                    break
            
            if not found:
                print(f"❌ {target_job} still not scheduled")
        
        # Show machine utilization for overloaded machines
        print(f"\n=== MACHINE UTILIZATION ===")
        machine_task_counts = {
            machine: len(tasks) for machine, tasks in schedule.items() if len(tasks) > 15
        }
        
        for machine, count in sorted(machine_task_counts.items(), key=lambda x: x[1], reverse=True)[:10]:
            print(f"{machine}: {count} tasks")
            
        return success_rate > 90  # Consider it successful if >90% jobs scheduled
        
    except Exception as e:
        logger.error(f"Error in test: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_overload_fix()
    if success:
        print("\n🎉 OVERLOAD FIX TEST PASSED!")
    else:
        print("\n❌ OVERLOAD FIX TEST FAILED!")