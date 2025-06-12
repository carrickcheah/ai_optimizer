#!/usr/bin/env python3
"""
Debug script to analyze specific constraints preventing job JOST25050207_CP08-560-1/2 from scheduling.
"""

import os
import sys
import logging
import time
from datetime import datetime, timedelta

# Add the project root to the Python path
sys.path.append('/Users/carrickcheah/Project/ai_optimizer/backend')

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def debug_specific_constraints():
    """Debug specific constraints for the target job."""
    print("🔍 Debugging Specific Constraints for JOST25050207_CP08-560-1/2")
    print("=" * 80)
    
    try:
        # Import required modules
        from app.data_ingestion.mariadb_parser import load_jobs_planning_data
        from app.scheduling.greedy_solver import GreedyConfigManager, SchedulingConstraints
        from app.scheduling.time_availability import is_time_available_for_scheduling, get_next_available_slot
        from app.utils.time_utils import epoch_to_datetime, format_datetime_for_display
        import pytz
        
        print("✅ Successfully imported required modules")
        
        # Load configuration and data
        config = GreedyConfigManager.load_config()
        jobs, machines, setup_times = load_jobs_planning_data()
        
        # Find the target job
        target_job_id = "JOST25050207_CP08-560-1/2"
        target_job = None
        
        for job in jobs:
            if job.get('job_id') == target_job_id:
                target_job = job
                break
        
        if not target_job:
            print(f"❌ Job {target_job_id} not found")
            return
        
        print(f"✅ Found target job: {target_job_id}")
        print("Job details:")
        for key, value in target_job.items():
            if key in ['job_id', 'MachineName_v', 'hours_need', 'day_need', 'priority', 
                      'lcd_date_epoch', 'processing_time', 'job_quantity', 'expect_output_per_hour']:
                print(f"   - {key}: {value}")
        
        # Extract machine names
        if machines and isinstance(machines[0], dict):
            machine_names = [m.get('MachineName_v', str(m)) for m in machines if m.get('MachineName_v')]
        else:
            machine_names = machines
        
        # Add Subcon if not present
        if 'Subcon' not in machine_names:
            machine_names.append('Subcon')
        
        required_machine = target_job.get('MachineName_v')
        print(f"\n🔧 Machine Requirements:")
        print(f"   - Required machine: {required_machine}")
        print(f"   - Machine available: {required_machine in machine_names}")
        
        # Initialize constraint checker
        constraints = SchedulingConstraints(config)
        
        # Test current time
        current_time = time.time()
        current_dt = datetime.fromtimestamp(current_time, tz=pytz.timezone('Asia/Singapore'))
        processing_time = target_job.get('processing_time', 8100.0)
        end_time = current_time + processing_time
        end_dt = datetime.fromtimestamp(end_time, tz=pytz.timezone('Asia/Singapore'))
        
        print(f"\n⏰ Time Analysis:")
        print(f"   - Current time: {format_datetime_for_display(current_dt)}")
        print(f"   - Processing time: {processing_time} seconds ({processing_time/3600:.2f} hours)")
        print(f"   - Job would end at: {format_datetime_for_display(end_dt)}")
        
        # Test time availability
        print(f"\n🕐 Time Availability Tests:")
        is_current_available = is_time_available_for_scheduling(current_dt)
        print(f"   - Current time available for scheduling: {is_current_available}")
        
        # Test next available slot
        duration_hours = processing_time / 3600
        next_slot = get_next_available_slot(current_time, duration_hours)
        if next_slot:
            next_dt = epoch_to_datetime(next_slot)
            print(f"   - Next available slot: {format_datetime_for_display(next_dt)}")
            
            # Calculate how far in the future this is
            hours_ahead = (next_slot - current_time) / 3600
            print(f"   - Hours ahead: {hours_ahead:.1f}")
        else:
            print(f"   - ❌ No available slot found within search period!")
        
        # Test individual constraint components
        print(f"\n🔍 Individual Constraint Analysis:")
        
        # Empty schedule for testing
        empty_schedule = {machine: [] for machine in machine_names}
        empty_operators = {}
        
        # 1. Machine availability
        machine_available = constraints._check_machine_availability(
            required_machine, current_time, end_time, empty_schedule
        )
        print(f"   1. Machine availability: {machine_available}")
        
        # 2. Operator availability  
        operator_available = constraints._check_operator_availability(
            current_time, end_time, empty_operators, 0  # max_operators = 0 means no limit
        )
        print(f"   2. Operator availability: {operator_available}")
        
        # 3. Deadline constraints
        deadline_ok = constraints._check_deadline_constraints(target_job, end_time)
        print(f"   3. Deadline constraints: {deadline_ok}")
        
        if not deadline_ok:
            lcd_date = target_job.get('lcd_date_epoch')
            if lcd_date:
                lcd_dt = epoch_to_datetime(lcd_date)
                print(f"      - LCD Date: {format_datetime_for_display(lcd_dt)}")
                print(f"      - Job is overdue by: {(current_time - lcd_date)/3600:.1f} hours")
                
                # Check grace period calculation
                grace_period_seconds = config.grace_period_hours * 3600
                priority = target_job.get('priority', 3)
                if priority <= 2:
                    extended_grace = grace_period_seconds * 2
                else:
                    extended_grace = grace_period_seconds
                
                adjusted_deadline = current_time + extended_grace
                print(f"      - Grace period: {extended_grace/3600:.1f} hours")
                print(f"      - Adjusted deadline: {format_datetime_for_display(epoch_to_datetime(adjusted_deadline))}")
                print(f"      - Job end vs adjusted deadline: {end_time <= adjusted_deadline}")
        
        # 4. Time availability (working hours, breaks, holidays)
        time_available = constraints._check_time_availability(
            current_time, end_time, target_job
        )
        print(f"   4. Time availability: {time_available}")
        
        # Test different starting times
        print(f"\n🕒 Testing Different Start Times:")
        test_times = []
        
        # Test immediate start
        test_times.append(("Now", current_time))
        
        # Test start of next working day
        next_day = datetime.now().replace(hour=8, minute=0, second=0, microsecond=0) + timedelta(days=1)
        test_times.append(("Tomorrow 8 AM", next_day.timestamp()))
        
        # Test start of next week
        next_week = datetime.now().replace(hour=8, minute=0, second=0, microsecond=0) + timedelta(days=7)
        test_times.append(("Next week", next_week.timestamp()))
        
        for label, test_start in test_times:
            test_end = test_start + processing_time
            can_schedule = constraints.can_schedule_job(
                target_job, required_machine, test_start, empty_schedule, empty_operators, 0
            )
            
            test_start_dt = epoch_to_datetime(test_start)
            print(f"   - {label} ({format_datetime_for_display(test_start_dt)}): {can_schedule}")
            
            if not can_schedule:
                # Check which constraint fails
                machine_ok = constraints._check_machine_availability(
                    required_machine, test_start, test_end, empty_schedule
                )
                operator_ok = constraints._check_operator_availability(
                    test_start, test_end, empty_operators, 0
                )
                deadline_ok = constraints._check_deadline_constraints(target_job, test_end)
                time_ok = constraints._check_time_availability(test_start, test_end, target_job)
                
                print(f"     Failures: Machine={not machine_ok}, Operator={not operator_ok}, Deadline={not deadline_ok}, Time={not time_ok}")
        
        # Test with realistic machine loading
        print(f"\n🏭 Testing with Machine Loading:")
        
        # Create a more realistic schedule with some jobs already scheduled
        realistic_schedule = {machine: [] for machine in machine_names}
        
        # Add some dummy jobs to the required machine to simulate loading
        dummy_start = current_time - 3600  # 1 hour ago
        dummy_end = current_time + 7200    # 2 hours from now
        realistic_schedule[required_machine] = [
            ("DUMMY_JOB_1", dummy_start, dummy_end, 3, {})
        ]
        
        # Test if job can be scheduled with this loading
        earliest_free_time = dummy_end + 300  # 5 minutes buffer
        can_schedule_loaded = constraints.can_schedule_job(
            target_job, required_machine, earliest_free_time, realistic_schedule, empty_operators, 0
        )
        
        earliest_dt = epoch_to_datetime(earliest_free_time)
        print(f"   - With machine loaded until {format_datetime_for_display(epoch_to_datetime(dummy_end))}")
        print(f"   - Can schedule at {format_datetime_for_display(earliest_dt)}: {can_schedule_loaded}")
        
        # Final summary
        print(f"\n📋 CONSTRAINT ANALYSIS SUMMARY:")
        print(f"=" * 50)
        
        overall_can_schedule = constraints.can_schedule_job(
            target_job, required_machine, current_time, empty_schedule, empty_operators, 0
        )
        
        if overall_can_schedule:
            print(f"✅ Job CAN be scheduled now - issue may be in full dataset complexity")
        else:
            print(f"❌ Job CANNOT be scheduled now due to constraints:")
            
            machine_ok = constraints._check_machine_availability(
                required_machine, current_time, end_time, empty_schedule
            )
            operator_ok = constraints._check_operator_availability(
                current_time, end_time, empty_operators, 0
            )
            deadline_ok = constraints._check_deadline_constraints(target_job, end_time)
            time_ok = constraints._check_time_availability(current_time, end_time, target_job)
            
            if not machine_ok:
                print(f"   - ❌ Machine constraint failure")
            if not operator_ok:
                print(f"   - ❌ Operator constraint failure")  
            if not deadline_ok:
                print(f"   - ❌ Deadline constraint failure (overdue job)")
            if not time_ok:
                print(f"   - ❌ Time availability constraint failure (working hours/breaks/holidays)")
        
        print(f"\nPossible solutions:")
        print(f"1. Adjust grace period for overdue jobs")
        print(f"2. Review working hours and break time restrictions")
        print(f"3. Consider machine capacity and loading")
        print(f"4. Check holiday calendar for restrictive dates")
        print(f"5. Examine process sequence dependencies in full dataset")
            
    except Exception as e:
        print(f"❌ Error during constraint debugging: {e}")
        logger.exception("Constraint debugging error details:")

if __name__ == "__main__":
    debug_specific_constraints()