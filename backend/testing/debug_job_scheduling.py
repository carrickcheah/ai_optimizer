#!/usr/bin/env python3
"""
Debug script for investigating why job JOST25050207_CP08-560-1/2 cannot find an available slot.
"""

import os
import sys
import logging
import time
from datetime import datetime

# Add the project root to the Python path
sys.path.append('/Users/carrickcheah/Project/ai_optimizer/backend')

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def debug_job_scheduling():
    """Debug the specific job scheduling issue."""
    print("🔍 Debugging Job JOST25050207_CP08-560-1/2 Scheduling Issue")
    print("=" * 60)
    
    try:
        # Import required modules
        from app.data_ingestion.mariadb_parser import load_jobs_planning_data
        from app.scheduling.greedy_solver import greedy_schedule, GreedyConfigManager
        from app.scheduling.scheduler_utils import extract_job_family, extract_process_number
        from app.utils.time_utils import epoch_to_datetime, format_datetime_for_display
        
        print("✅ Successfully imported required modules")
        
        # Load configuration
        config = GreedyConfigManager.load_config()
        print(f"✅ Configuration loaded:")
        print(f"   - SCHEDULER_SEARCH_DAYS: {config.scheduler_search_days}")
        print(f"   - GRACE_PERIOD_HOURS: {config.grace_period_hours}")
        print(f"   - NORMAL_WORKING_HOURS: {config.normal_working_hours}")
        print(f"   - OT_WORKING_HOURS: {config.ot_working_hours}")
        
        # Load data
        print("\n📊 Loading jobs and machines data...")
        jobs, machines, setup_times = load_jobs_planning_data()
        print(f"✅ Loaded {len(jobs)} jobs and {len(machines)} machines")
        
        # Find the specific job
        target_job_id = "JOST25050207_CP08-560-1/2"
        target_job = None
        
        for job in jobs:
            if job.get('job_id') == target_job_id:
                target_job = job
                break
        
        if not target_job:
            print(f"❌ Job {target_job_id} not found in data")
            return
        
        print(f"\n🎯 Found target job: {target_job_id}")
        print("Job details:")
        for key, value in target_job.items():
            if key in ['job_id', 'MachineName_v', 'hours_need', 'day_need', 'priority', 
                      'lcd_date_epoch', 'processing_time', 'job_quantity', 'expect_output_per_hour']:
                print(f"   - {key}: {value}")
        
        # Extract job family and process info
        family = extract_job_family(target_job_id)
        process_num = extract_process_number(target_job_id)
        print(f"   - Family: {family}")
        print(f"   - Process Number: {process_num}")
        
        # Check if job has valid processing time
        processing_time = target_job.get('processing_time')
        hours_need = target_job.get('hours_need')
        day_need = target_job.get('day_need')
        
        print(f"\n⏱️ Processing time analysis:")
        print(f"   - processing_time: {processing_time}")
        print(f"   - hours_need: {hours_need}")
        print(f"   - day_need: {day_need}")
        
        if not processing_time and not hours_need and not day_need:
            print("❌ Job has no valid duration information!")
            return
        
        # Check machine assignment
        required_machine = target_job.get('MachineName_v')
        print(f"\n🔧 Machine analysis:")
        print(f"   - Required machine: {required_machine}")
        
        if required_machine == "NOT_ASSIGN":
            print("   - Job is marked as NOT_ASSIGN - should go to Subcon")
        elif required_machine and required_machine not in machines:
            print(f"   - ❌ Required machine '{required_machine}' not found in available machines!")
            print(f"   - Available machines with 'CP08': {[m for m in machines if 'CP08' in str(m)]}")
        else:
            print(f"   - ✅ Machine '{required_machine}' is available")
        
        # Check deadline constraints
        lcd_date = target_job.get('lcd_date_epoch')
        if lcd_date:
            lcd_dt = epoch_to_datetime(lcd_date)
            if lcd_dt:
                print(f"\n📅 Deadline analysis:")
                print(f"   - LCD Date: {format_datetime_for_display(lcd_dt)}")
                current_time = datetime.now()
                if lcd_dt.replace(tzinfo=None) < current_time:
                    print(f"   - ❌ Job is overdue! (Due: {lcd_dt}, Now: {current_time})")
                else:
                    days_remaining = (lcd_dt.replace(tzinfo=None) - current_time).days
                    print(f"   - ✅ Job has {days_remaining} days remaining")
        
        # Try scheduling just this job to see what happens
        print(f"\n🧪 Testing single job scheduling...")
        test_jobs = [target_job]
        test_machines = machines.copy()
        
        try:
            result = greedy_schedule(test_jobs, test_machines, setup_times, enforce_sequence=True, max_operators=0)
            
            scheduled_count = sum(len(tasks) for tasks in result.values())
            print(f"   - Scheduled tasks: {scheduled_count}")
            
            if scheduled_count == 0:
                print("   - ❌ Job could not be scheduled!")
            else:
                print("   - ✅ Job was successfully scheduled!")
                for machine, tasks in result.items():
                    if tasks:
                        for task in tasks:
                            job_id, start, end, priority = task[:4]
                            start_dt = epoch_to_datetime(start)
                            end_dt = epoch_to_datetime(end)
                            print(f"     - {job_id} on {machine}: {format_datetime_for_display(start_dt)} to {format_datetime_for_display(end_dt)}")
        
        except Exception as e:
            print(f"   - ❌ Scheduling failed with error: {e}")
            logger.exception("Scheduling error details:")
        
        # Test time availability for this job
        print(f"\n🕐 Testing time availability...")
        try:
            from app.scheduling.time_availability import is_time_available_for_scheduling, get_next_available_slot
            
            current_time = time.time()
            
            # Test if current time is available
            current_dt = datetime.fromtimestamp(current_time)
            is_available_now = is_time_available_for_scheduling(current_dt)
            print(f"   - Current time available: {is_available_now}")
            
            # Test finding next available slot
            duration = 8.0  # 8 hours default
            if hours_need:
                duration = float(hours_need)
            elif day_need:
                duration = float(day_need) * 24
            
            next_slot = get_next_available_slot(current_time, duration)
            if next_slot:
                next_dt = epoch_to_datetime(next_slot)
                print(f"   - Next available slot: {format_datetime_for_display(next_dt)}")
            else:
                print(f"   - ❌ No available slot found within search period!")
                
        except Exception as e:
            print(f"   - ❌ Time availability check failed: {e}")
            logger.exception("Time availability error details:")
        
        print(f"\n📋 Summary for job {target_job_id}:")
        print("Check the following potential issues:")
        print("1. ❓ Missing or invalid processing time data")
        print("2. ❓ Machine constraints (CP08 availability)")
        print("3. ❓ Time availability constraints (working hours, holidays, breaks)")
        print("4. ❓ Deadline constraints (overdue jobs)")
        print("5. ❓ Process sequence dependencies")
        print("6. ❓ Operator availability constraints")
        
    except Exception as e:
        print(f"❌ Error during debugging: {e}")
        logger.exception("Debugging error details:")

if __name__ == "__main__":
    debug_job_scheduling()