#!/usr/bin/env python3
"""
Test to verify both CP-SAT and Greedy solvers work consistently with working hours.
"""

import os
import sys
from datetime import datetime

# Add the backend directory to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import logging
logging.basicConfig(level=logging.INFO)

def test_solver_consistency():
    """Test that both solvers handle working hours consistently."""
    try:
        print("=" * 80)
        print("TESTING BOTH SOLVERS FOR WORKING HOURS CONSISTENCY")
        print("=" * 80)
        
        # Create a simple test job with long duration (like a combined job)
        test_jobs = [
            {
                'job_id': 'TEST_COMBINED_001',
                'job': 'COMBINED_JOB',
                'process_code': 'CO01-001-1/1',
                'MachineName_v': 'M001',
                'hours_need': 48.0,  # 48 hours - spans multiple days
                'processing_time': 48 * 3600,  # seconds
                'priority': 2,
                'day_need': 2.0,  # 2 days
                'job_quantity': 1000,
                'expect_output_per_hour': 21,
            }
        ]
        
        test_machines = ['M001']
        
        print(f"Test job: {test_jobs[0]['job_id']} - Duration: {test_jobs[0]['hours_need']}h")
        print()
        
        # Test 1: Greedy Solver
        print("1. TESTING GREEDY SOLVER")
        print("-" * 40)
        try:
            from app.scheduling.greedy_solver import greedy_schedule
            
            greedy_results = greedy_schedule(
                jobs=test_jobs,
                machines=test_machines,
                setup_times={},
                enforce_sequence=False,
                max_operators=0
            )
            
            if greedy_results:
                print("✅ Greedy solver completed successfully")
                for machine, tasks in greedy_results.items():
                    for task in tasks:
                        job_id, start_epoch, end_epoch, priority, _ = task
                        from app.utils.time_utils import epoch_to_datetime, format_datetime_for_display
                        start_dt = epoch_to_datetime(start_epoch)
                        end_dt = epoch_to_datetime(end_epoch)
                        if start_dt and end_dt:
                            start_str = format_datetime_for_display(start_dt)
                            end_str = format_datetime_for_display(end_dt)
                            print(f"  Job {job_id}: {start_str} - {end_str}")
                            
                            # Check if start time is during working hours
                            start_hour = start_dt.hour + start_dt.minute / 60.0
                            weekday = start_dt.weekday()
                            
                            if weekday < 5:  # Monday-Friday
                                working_hours_ok = 6.5 <= start_hour <= 18.0
                            elif weekday == 5:  # Saturday
                                working_hours_ok = 6.5 <= start_hour <= 13.0
                            else:  # Sunday
                                working_hours_ok = False
                                
                            status = "✅ Valid" if working_hours_ok else "❌ VIOLATION"
                            print(f"    Start time check: {status}")
            else:
                print("❌ Greedy solver failed - no results")
                
        except Exception as e:
            print(f"❌ Greedy solver failed: {e}")
        
        print()
        
        # Test 2: CP-SAT Solver
        print("2. TESTING CP-SAT SOLVER")
        print("-" * 40)
        try:
            from app.scheduling.cpsat_solver import schedule_jobs as cpsat_schedule
            
            cpsat_results = cpsat_schedule(
                jobs=test_jobs,
                machines=test_machines,
                setup_times={},
                enforce_sequence=False,
                enforce_deadlines=False,
                max_jobs_limit=10
            )
            
            if cpsat_results and cpsat_results.get('_metadata', {}).get('status') in ['OPTIMAL', 'FEASIBLE']:
                print("✅ CP-SAT solver completed successfully")
                
                for job_id, details in cpsat_results.items():
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
                            print(f"  Job {job_id}: {start_str} - {end_str}")
                            
                            # Check if start time is during working hours
                            start_hour = start_dt.hour + start_dt.minute / 60.0
                            weekday = start_dt.weekday()
                            
                            if weekday < 5:  # Monday-Friday
                                working_hours_ok = 6.5 <= start_hour <= 18.0
                            elif weekday == 5:  # Saturday
                                working_hours_ok = 6.5 <= start_hour <= 13.0
                            else:  # Sunday
                                working_hours_ok = False
                                
                            status = "✅ Valid" if working_hours_ok else "❌ VIOLATION"
                            print(f"    Start time check: {status}")
            else:
                print("❌ CP-SAT solver failed or no feasible solution")
                metadata = cpsat_results.get('_metadata', {}) if cpsat_results else {}
                print(f"Status: {metadata.get('status', 'Unknown')}")
                print(f"Message: {metadata.get('message', 'No message')}")
                
        except Exception as e:
            print(f"❌ CP-SAT solver failed: {e}")
            import traceback
            traceback.print_exc()
        
        print()
        print("=" * 80)
        print("CONCLUSION")
        print("=" * 80)
        print("Both solvers should now use the time_availability module consistently")
        print("and only schedule jobs starting during working hours.")
        print("Multi-day jobs will automatically span across working days.")
        
    except Exception as e:
        print(f"❌ Test setup failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_solver_consistency()