#!/usr/bin/env python3
"""
Debug script for investigating scheduling issues with the full dataset.
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
    level=logging.WARNING,  # Reduce noise
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def debug_full_scheduling():
    """Debug scheduling with full dataset to identify patterns."""
    print("🔍 Debugging Full Dataset Scheduling Issues")
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
        
        # Load data
        print("\n📊 Loading jobs and machines data...")
        jobs, machines, setup_times = load_jobs_planning_data()
        print(f"✅ Loaded {len(jobs)} jobs and {len(machines)} machines")
        
        # Find the target job and related CP08 jobs
        target_job_id = "JOST25050207_CP08-560-1/2"
        target_job = None
        cp08_jobs = []
        overdue_jobs = []
        current_time = time.time()
        
        for job in jobs:
            if job.get('job_id') == target_job_id:
                target_job = job
            
            # Collect CP08 family jobs
            family = extract_job_family(job.get('job_id', ''))
            if 'CP08' in family:
                cp08_jobs.append(job)
            
            # Check for overdue jobs
            lcd_date = job.get('lcd_date_epoch')
            if lcd_date and lcd_date < current_time:
                overdue_jobs.append(job)
        
        print(f"\n📋 Dataset Analysis:")
        print(f"   - Total CP08 family jobs: {len(cp08_jobs)}")
        print(f"   - Total overdue jobs: {len(overdue_jobs)}")
        
        # Check machine availability for CP08 jobs
        print(f"\n🔧 Machine Analysis:")
        required_machines = set()
        
        # Extract machine names from the machines list
        if machines and isinstance(machines[0], dict):
            available_machines = set(m.get('MachineName_v', str(m)) for m in machines if m.get('MachineName_v'))
        else:
            available_machines = set(machines)
        
        for job in cp08_jobs:
            machine = job.get('MachineName_v')
            if machine and machine != 'NOT_ASSIGN':
                required_machines.add(machine)
        
        missing_machines = required_machines - available_machines
        print(f"   - Required machines for CP08 jobs: {len(required_machines)}")
        print(f"   - Available machines: {len(available_machines)}")
        print(f"   - Missing machines: {len(missing_machines)}")
        
        if missing_machines:
            print(f"   - Missing machine examples: {list(missing_machines)[:5]}")
        
        # Check target job specifically
        if target_job:
            print(f"\n🎯 Target job analysis:")
            required_machine = target_job.get('MachineName_v')
            print(f"   - Required machine: {required_machine}")
            print(f"   - Machine available: {required_machine in available_machines}")
            
            lcd_date = target_job.get('lcd_date_epoch')
            if lcd_date:
                lcd_dt = epoch_to_datetime(lcd_date)
                print(f"   - LCD Date: {format_datetime_for_display(lcd_dt)}")
                print(f"   - Is overdue: {lcd_date < current_time}")
        
        # Try scheduling with full dataset
        print(f"\n🧪 Testing full dataset scheduling...")
        
        try:
            start_time = time.time()
            result = greedy_schedule(jobs, machines, setup_times, enforce_sequence=True, max_operators=0)
            elapsed = time.time() - start_time
            
            scheduled_count = sum(len(tasks) for tasks in result.values())
            unscheduled_count = len(jobs) - scheduled_count
            success_rate = (scheduled_count / len(jobs)) * 100
            
            print(f"   - Processing time: {elapsed:.2f} seconds")
            print(f"   - Scheduled jobs: {scheduled_count}")
            print(f"   - Unscheduled jobs: {unscheduled_count}")
            print(f"   - Success rate: {success_rate:.1f}%")
            
            # Check if target job was scheduled
            target_scheduled = False
            target_machine = None
            target_start = None
            target_end = None
            
            for machine, tasks in result.items():
                for task in tasks:
                    job_id = task[0]
                    if job_id == target_job_id:
                        target_scheduled = True
                        target_machine = machine
                        target_start = epoch_to_datetime(task[1])
                        target_end = epoch_to_datetime(task[2])
                        break
                if target_scheduled:
                    break
            
            if target_scheduled:
                print(f"   - ✅ Target job scheduled on {target_machine}")
                print(f"     Time: {format_datetime_for_display(target_start)} to {format_datetime_for_display(target_end)}")
            else:
                print(f"   - ❌ Target job NOT scheduled in full dataset")
            
            # Analyze unscheduled jobs
            if unscheduled_count > 0:
                print(f"\n📊 Unscheduled jobs analysis:")
                
                # Find which jobs are unscheduled
                scheduled_job_ids = set()
                for machine, tasks in result.items():
                    for task in tasks:
                        scheduled_job_ids.add(task[0])
                
                unscheduled_jobs = [job for job in jobs if job['job_id'] not in scheduled_job_ids]
                
                # Categorize unscheduled jobs
                unscheduled_cp08 = [job for job in unscheduled_jobs if 'CP08' in extract_job_family(job.get('job_id', ''))]
                unscheduled_overdue = [job for job in unscheduled_jobs if job.get('lcd_date_epoch', float('inf')) < current_time]
                unscheduled_missing_machines = [job for job in unscheduled_jobs if job.get('MachineName_v') not in available_machines]
                
                print(f"   - Unscheduled CP08 jobs: {len(unscheduled_cp08)}")
                print(f"   - Unscheduled overdue jobs: {len(unscheduled_overdue)}")
                print(f"   - Unscheduled due to missing machines: {len(unscheduled_missing_machines)}")
                
                # Show examples
                if unscheduled_cp08:
                    print(f"   - Unscheduled CP08 examples: {[job['job_id'] for job in unscheduled_cp08[:3]]}")
                
                if unscheduled_missing_machines:
                    print(f"   - Missing machine examples:")
                    for job in unscheduled_missing_machines[:3]:
                        print(f"     - {job['job_id']}: needs {job.get('MachineName_v')}")
        
        except Exception as e:
            print(f"   - ❌ Scheduling failed with error: {e}")
            logger.exception("Scheduling error details:")
        
        # Test constraints specifically
        print(f"\n🕐 Testing constraints...")
        try:
            from app.scheduling.time_availability import is_time_available_for_scheduling
            from app.scheduling.greedy_solver import SchedulingConstraints
            
            # Test time availability
            current_dt = datetime.fromtimestamp(current_time)
            is_available_now = is_time_available_for_scheduling(current_dt)
            print(f"   - Current time scheduling available: {is_available_now}")
            
            # Test constraints for target job if found
            if target_job:
                constraints = SchedulingConstraints(config)
                test_start_time = current_time
                test_machine = target_job.get('MachineName_v')
                
                # Empty schedule for testing
                empty_schedule = {machine: [] for machine in machines}
                empty_operators = {}
                
                can_schedule = constraints.can_schedule_job(
                    target_job, test_machine, test_start_time, 
                    empty_schedule, empty_operators, 0
                )
                print(f"   - Target job can be scheduled now: {can_schedule}")
                
                # Test individual constraint components
                processing_time = target_job.get('processing_time', 3600)
                end_time = test_start_time + processing_time
                
                machine_available = constraints._check_machine_availability(
                    test_machine, test_start_time, end_time, empty_schedule
                )
                print(f"   - Machine availability: {machine_available}")
                
                deadline_ok = constraints._check_deadline_constraints(target_job, end_time)
                print(f"   - Deadline constraints: {deadline_ok}")
                
                time_available = constraints._check_time_availability(
                    test_start_time, end_time, target_job
                )
                print(f"   - Time availability: {time_available}")
                
        except Exception as e:
            print(f"   - ❌ Constraint testing failed: {e}")
            logger.exception("Constraint testing error:")
        
        print(f"\n📋 Key Findings:")
        print("Potential issues causing scheduling failures:")
        print("1. Machine availability - some required machines may not exist in system")
        print("2. Overdue jobs may have complex deadline handling")
        print("3. Working hour constraints may be too restrictive")
        print("4. Process sequence dependencies may create bottlenecks")
        print("5. Time availability database may have restrictive break/holiday rules")
        
    except Exception as e:
        print(f"❌ Error during debugging: {e}")
        logger.exception("Debugging error details:")

if __name__ == "__main__":
    debug_full_scheduling()