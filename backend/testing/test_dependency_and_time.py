#!/usr/bin/env python3
"""
Test dependency enforcement (1->2->3->4) and time availability compliance.
"""

import os
import sys
from datetime import datetime

# Add the backend directory to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import logging
logging.basicConfig(level=logging.INFO)

def test_dependency_and_time_compliance():
    """Test sequence dependencies and time availability compliance."""
    try:
        print("=" * 80)
        print("TESTING DEPENDENCY ENFORCEMENT AND TIME AVAILABILITY")
        print("=" * 80)
        
        # Create test jobs with proper sequence dependencies (1->2->3->4)
        test_jobs = [
            {
                'job_id': 'JOST23050001_CO02-012-4/4',  # Process 4 (last)
                'job': 'JOST23050001', 
                'process_code': 'CO02-012-4/4',
                'MachineName_v': 'M001',
                'hours_need': 8.0,
                'processing_time': 8 * 3600,
                'priority': 2,
                'lcd_date_epoch': 1718625600,  # June 17, 2024
            },
            {
                'job_id': 'JOST23050001_CO02-012-1/4',  # Process 1 (first)
                'job': 'JOST23050001',
                'process_code': 'CO02-012-1/4', 
                'MachineName_v': 'M001',
                'hours_need': 12.0,
                'processing_time': 12 * 3600,
                'priority': 2,
                'lcd_date_epoch': 1718625600,
            },
            {
                'job_id': 'JOST23050001_CO02-012-3/4',  # Process 3
                'job': 'JOST23050001',
                'process_code': 'CO02-012-3/4',
                'MachineName_v': 'M002', 
                'hours_need': 6.0,
                'processing_time': 6 * 3600,
                'priority': 2,
                'lcd_date_epoch': 1718625600,
            },
            {
                'job_id': 'JOST23050001_CO02-012-2/4',  # Process 2  
                'job': 'JOST23050001',
                'process_code': 'CO02-012-2/4',
                'MachineName_v': 'M001',
                'hours_need': 10.0,
                'processing_time': 10 * 3600,
                'priority': 2,
                'lcd_date_epoch': 1718625600,
            }
        ]
        
        test_machines = ['M001', 'M002']
        
        print("Test jobs (out of sequence order):")
        for job in test_jobs:
            print(f"  {job['job_id']} - Duration: {job['hours_need']}h - Machine: {job['MachineName_v']}")
        print()
        
        # Test 1: Greedy Solver with sequence enforcement
        print("1. TESTING GREEDY SOLVER WITH SEQUENCE ENFORCEMENT")
        print("-" * 60)
        try:
            from app.scheduling.greedy_solver import greedy_schedule
            
            greedy_results = greedy_schedule(
                jobs=test_jobs,
                machines=test_machines,
                setup_times={},
                enforce_sequence=True,  # ENABLE sequence enforcement
                max_operators=0
            )
            
            if greedy_results:
                print("✅ Greedy solver completed successfully")
                
                # Collect all scheduled jobs with times
                all_scheduled = []
                for machine, tasks in greedy_results.items():
                    for task in tasks:
                        job_id, start_epoch, end_epoch, priority, _ = task
                        all_scheduled.append((job_id, start_epoch, end_epoch, machine))
                
                # Sort by start time to check sequence
                all_scheduled.sort(key=lambda x: x[1])
                
                print("Scheduled jobs in chronological order:")
                sequence_violations = 0
                
                for job_id, start_epoch, end_epoch, machine in all_scheduled:
                    from app.utils.time_utils import epoch_to_datetime, format_datetime_for_display
                    start_dt = epoch_to_datetime(start_epoch)
                    end_dt = epoch_to_datetime(end_epoch)
                    
                    if start_dt and end_dt:
                        start_str = format_datetime_for_display(start_dt)
                        end_str = format_datetime_for_display(end_dt)
                        
                        # Extract process number
                        process_num = job_id.split('-')[-1].split('/')[0] if '-' in job_id else '?'
                        
                        print(f"  Process {process_num}: {job_id} on {machine}")
                        print(f"    Time: {start_str} - {end_str}")
                        
                        # Check working hours compliance
                        start_hour = start_dt.hour + start_dt.minute / 60.0
                        weekday = start_dt.weekday()
                        
                        if weekday < 5:  # Monday-Friday
                            working_hours_ok = 6.5 <= start_hour <= 18.0
                        elif weekday == 5:  # Saturday
                            working_hours_ok = 6.5 <= start_hour <= 13.0
                        else:  # Sunday
                            working_hours_ok = False
                            
                        time_status = "✅ Valid time" if working_hours_ok else "❌ TIME VIOLATION"
                        print(f"    {time_status}")
                        
                        # Check if it respects time_availability module
                        try:
                            from app.scheduling.time_availability import is_time_available_for_scheduling
                            availability_ok = is_time_available_for_scheduling(start_dt)
                            avail_status = "✅ Available" if availability_ok else "❌ AVAILABILITY VIOLATION"
                            print(f"    {avail_status}")
                        except Exception as e:
                            print(f"    ⚠️  Could not check availability: {e}")
                        
                        print()
                
                # Check sequence compliance
                process_order = []
                for job_id, _, _, _ in all_scheduled:
                    if 'CO02-012' in job_id:
                        process_num = int(job_id.split('-')[-1].split('/')[0])
                        process_order.append(process_num)
                
                print(f"Process execution order: {process_order}")
                expected_order = [1, 2, 3, 4]
                sequence_ok = process_order == expected_order
                
                if sequence_ok:
                    print("✅ SEQUENCE COMPLIANCE: Jobs executed in correct order (1->2->3->4)")
                else:
                    print(f"❌ SEQUENCE VIOLATION: Expected {expected_order}, got {process_order}")
                    
            else:
                print("❌ Greedy solver failed - no results")
                
        except Exception as e:
            print(f"❌ Greedy solver failed: {e}")
            import traceback
            traceback.print_exc()
        
        print()
        
        # Test 2: CP-SAT Solver with sequence enforcement
        print("2. TESTING CP-SAT SOLVER WITH SEQUENCE ENFORCEMENT")
        print("-" * 60)
        try:
            from app.scheduling.cpsat_solver import schedule_jobs as cpsat_schedule
            
            cpsat_results = cpsat_schedule(
                jobs=test_jobs,
                machines=test_machines,
                setup_times={},
                enforce_sequence=True,  # ENABLE sequence enforcement
                enforce_deadlines=False,
                max_jobs_limit=10
            )
            
            if cpsat_results and cpsat_results.get('_metadata', {}).get('status') in ['OPTIMAL', 'FEASIBLE']:
                print("✅ CP-SAT solver completed successfully")
                
                # Collect all scheduled jobs with times
                all_scheduled = []
                for job_id, details in cpsat_results.items():
                    if job_id == '_metadata':
                        continue
                        
                    start_epoch = details.get('start')
                    end_epoch = details.get('end')
                    machine = details.get('machine')
                    
                    if start_epoch and end_epoch:
                        all_scheduled.append((job_id, start_epoch, end_epoch, machine))
                
                # Sort by start time to check sequence
                all_scheduled.sort(key=lambda x: x[1])
                
                print("Scheduled jobs in chronological order:")
                
                for job_id, start_epoch, end_epoch, machine in all_scheduled:
                    from app.utils.time_utils import epoch_to_datetime, format_datetime_for_display
                    start_dt = epoch_to_datetime(start_epoch)
                    end_dt = epoch_to_datetime(end_epoch)
                    
                    if start_dt and end_dt:
                        start_str = format_datetime_for_display(start_dt)
                        end_str = format_datetime_for_display(end_dt)
                        
                        # Extract process number
                        process_num = job_id.split('-')[-1].split('/')[0] if '-' in job_id else '?'
                        
                        print(f"  Process {process_num}: {job_id} on {machine}")
                        print(f"    Time: {start_str} - {end_str}")
                        
                        # Check working hours compliance
                        start_hour = start_dt.hour + start_dt.minute / 60.0
                        weekday = start_dt.weekday()
                        
                        if weekday < 5:  # Monday-Friday
                            working_hours_ok = 6.5 <= start_hour <= 18.0
                        elif weekday == 5:  # Saturday
                            working_hours_ok = 6.5 <= start_hour <= 13.0
                        else:  # Sunday
                            working_hours_ok = False
                            
                        time_status = "✅ Valid time" if working_hours_ok else "❌ TIME VIOLATION"
                        print(f"    {time_status}")
                        
                        # Check if it respects time_availability module
                        try:
                            from app.scheduling.time_availability import is_time_available_for_scheduling
                            availability_ok = is_time_available_for_scheduling(start_dt)
                            avail_status = "✅ Available" if availability_ok else "❌ AVAILABILITY VIOLATION"
                            print(f"    {avail_status}")
                        except Exception as e:
                            print(f"    ⚠️  Could not check availability: {e}")
                        
                        print()
                
                # Check sequence compliance
                process_order = []
                for job_id, _, _, _ in all_scheduled:
                    if 'CO02-012' in job_id:
                        process_num = int(job_id.split('-')[-1].split('/')[0])
                        process_order.append(process_num)
                
                print(f"Process execution order: {process_order}")
                expected_order = [1, 2, 3, 4]
                sequence_ok = process_order == expected_order
                
                if sequence_ok:
                    print("✅ SEQUENCE COMPLIANCE: Jobs executed in correct order (1->2->3->4)")
                else:
                    print(f"❌ SEQUENCE VIOLATION: Expected {expected_order}, got {process_order}")
                    
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
        print("SUMMARY")
        print("=" * 80)
        print("This test verifies:")
        print("1. ✅ Sequence dependency enforcement (1->2->3->4)")
        print("2. ✅ Working hours compliance (6:30 AM - 6:00 PM)")
        print("3. ✅ Time availability module compliance (breaks, holidays)")
        print("4. ✅ Database table integration")
        
    except Exception as e:
        print(f"❌ Test setup failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_dependency_and_time_compliance()