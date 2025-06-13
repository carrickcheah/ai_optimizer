#!/usr/bin/env python3
"""
Quick test to verify the working hours fix is working.
"""

import os
import sys
from datetime import datetime

# Add the backend directory to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import logging
logging.basicConfig(level=logging.DEBUG)

def test_working_hours_fix():
    """Test that jobs are properly constrained to working hours."""
    try:
        # Import the CP-SAT scheduler
        from app.scheduling.cpsat_solver import schedule_jobs
        from app.data_ingestion.mariadb_parser import load_jobs_planning_data
        
        print("Loading test data...")
        jobs, machines, setup_times = load_jobs_planning_data(max_jobs=3)
        
        if not jobs:
            print("❌ No jobs loaded for testing")
            return
        
        print(f"✅ Loaded {len(jobs)} jobs for testing")
        
        # Run scheduling with working hours constraints
        print("\nRunning CP-SAT scheduling with working hours constraints...")
        results = schedule_jobs(
            jobs=jobs,
            machines=machines,
            setup_times=setup_times,
            enforce_sequence=True,
            enforce_deadlines=True,
            max_jobs_limit=3
        )
        
        # Check results
        if '_metadata' not in results:
            print("❌ No metadata in results")
            return
            
        metadata = results['_metadata']
        print(f"\nScheduling Status: {metadata.get('status')}")
        print(f"Solver Time: {metadata.get('solver_time', 0):.2f}s")
        
        if metadata.get('status') not in ['OPTIMAL', 'FEASIBLE']:
            print(f"❌ Scheduling failed: {metadata.get('message', 'Unknown error')}")
            return
        
        # Check scheduled times
        print("\nScheduled Jobs:")
        working_hours_violations = 0
        
        for job_id, details in results.items():
            if job_id == '_metadata':
                continue
                
            start_epoch = details.get('start')
            end_epoch = details.get('end')
            machine = details.get('machine')
            
            if start_epoch and end_epoch:
                from app.utils.time_utils import epoch_to_datetime, format_datetime_for_display
                start_dt = epoch_to_datetime(start_epoch)
                end_dt = epoch_to_datetime(end_epoch)
                
                if start_dt and end_dt:
                    start_str = format_datetime_for_display(start_dt)
                    end_str = format_datetime_for_display(end_dt)
                    print(f"  {job_id} on {machine}: {start_str} - {end_str}")
                    
                    # Check if scheduled outside working hours (after 6 PM or before 6:30 AM)
                    start_hour = start_dt.hour + start_dt.minute / 60.0
                    end_hour = end_dt.hour + end_dt.minute / 60.0
                    
                    # Working hours: 6:30 AM (6.5) to 6:00 PM (18.0) on weekdays
                    # Saturday: 6:30 AM to 1:00 PM (13.0)
                    weekday = start_dt.weekday()  # 0=Monday, 6=Sunday
                    
                    if weekday < 5:  # Monday-Friday
                        if start_hour < 6.5 or start_hour > 18.0 or end_hour > 18.0:
                            print(f"    ❌ VIOLATION: Outside weekday working hours (6:30-18:00)")
                            working_hours_violations += 1
                    elif weekday == 5:  # Saturday
                        if start_hour < 6.5 or start_hour > 13.0 or end_hour > 13.0:
                            print(f"    ❌ VIOLATION: Outside Saturday working hours (6:30-13:00)")
                            working_hours_violations += 1
                    elif weekday == 6:  # Sunday
                        print(f"    ❌ VIOLATION: Scheduled on Sunday (non-working day)")
                        working_hours_violations += 1
                    else:
                        print(f"    ✅ Within working hours")
        
        if working_hours_violations == 0:
            print(f"\n✅ SUCCESS: All jobs scheduled within working hours!")
        else:
            print(f"\n❌ FAILED: {working_hours_violations} working hours violations found!")
            
    except Exception as e:
        print(f"❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_working_hours_fix()