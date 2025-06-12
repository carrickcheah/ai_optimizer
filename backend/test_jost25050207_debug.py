#!/usr/bin/env python3
"""
Debug specific job JOST25050207_CP08-560-1/2 that's still failing.
"""

import logging
from datetime import datetime, timedelta
import pytz

# Setup logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def test_jost25050207_debug():
    """Test the specific failing job JOST25050207_CP08-560-1/2."""
    try:
        from app.data_ingestion.mariadb_parser import load_jobs_planning_data
        from app.scheduling.greedy_solver import (
            GreedyConfigManager, JobValidator, MachineManager, 
            SchedulingConstraints, GreedyScheduler
        )
        from app.scheduling.time_availability import get_next_available_slot, is_time_available_for_scheduling
        from app.utils.time_utils import datetime_to_epoch, epoch_to_datetime
        
        print("=== DEBUGGING JOST25050207_CP08-560-1/2 ===")
        
        # Load data
        jobs, machines, setup_times = load_jobs_planning_data()
        config = GreedyConfigManager.load_config()
        valid_jobs = JobValidator.validate_and_prepare_jobs(jobs)
        machine_names = MachineManager.prepare_machines(machines)
        
        # Find the specific job
        target_job = None
        for job in valid_jobs:
            if job['job_id'] == 'JOST25050207_CP08-560-1/2':
                target_job = job
                break
        
        if not target_job:
            print("❌ Job JOST25050207_CP08-560-1/2 not found!")
            print("Available jobs with similar ID:")
            for job in valid_jobs:
                if 'CP08-560' in job['job_id']:
                    print(f"  - {job['job_id']}")
            return
        
        print(f"Found target job: {target_job['job_id']}")
        print(f"Machine: {target_job.get('MachineName_v')}")
        print(f"Processing time: {target_job.get('processing_time')} seconds = {target_job.get('processing_time')/3600:.1f} hours")
        print(f"Priority: {target_job.get('priority')}")
        print(f"LCD date: {target_job.get('lcd_date_epoch')}")
        
        # Check deadline constraints
        if target_job.get('lcd_date_epoch'):
            deadline_dt = epoch_to_datetime(target_job['lcd_date_epoch'])
            print(f"Deadline: {deadline_dt}")
            current_time = datetime.now(pytz.timezone('Asia/Singapore'))
            print(f"Current time: {current_time}")
            is_overdue = target_job['lcd_date_epoch'] < datetime_to_epoch(current_time)
            print(f"Is overdue: {is_overdue}")
            if is_overdue:
                days_overdue = (datetime_to_epoch(current_time) - target_job['lcd_date_epoch']) / 86400
                print(f"Days overdue: {days_overdue:.1f}")
        
        # Find best machine
        current_time = datetime_to_epoch(datetime.now())
        machine_id = MachineManager.find_best_machine(
            target_job, machine_names, 
            {m: current_time for m in machine_names}
        )
        print(f"Best machine: {machine_id}")
        
        # Test get_next_available_slot for this specific job
        duration_hours = target_job.get('processing_time', 3600) / 3600
        print(f"\nTesting get_next_available_slot for {duration_hours} hour job...")
        
        next_slot = get_next_available_slot(current_time, duration_hours)
        if next_slot:
            next_datetime = epoch_to_datetime(next_slot)
            end_datetime = epoch_to_datetime(next_slot + target_job['processing_time'])
            print(f"✅ Found next slot: {next_datetime}")
            print(f"Job would end at: {end_datetime}")
            print(f"Start time is available: {is_time_available_for_scheduling(next_datetime)}")
            
            # Check if this would meet deadline
            if target_job.get('lcd_date_epoch'):
                deadline_met = next_slot + target_job['processing_time'] <= target_job['lcd_date_epoch']
                print(f"Would meet original deadline: {deadline_met}")
                if not deadline_met:
                    grace_period = config.grace_period_hours * 3600
                    extended_deadline = datetime_to_epoch(datetime.now()) + grace_period
                    grace_met = next_slot + target_job['processing_time'] <= extended_deadline
                    print(f"Would meet grace period deadline: {grace_met}")
                    if not grace_met:
                        print(f"Grace period: {config.grace_period_hours} hours")
                        print(f"Extended deadline: {epoch_to_datetime(extended_deadline)}")
        else:
            print(f"❌ No slot found by get_next_available_slot!")
        
        # Test constraints manually
        constraints = SchedulingConstraints(config)
        test_schedule = {machine: [] for machine in machine_names}
        
        # Test at current time
        print(f"\n=== TESTING CONSTRAINTS AT CURRENT TIME ===")
        can_schedule_now = constraints.can_schedule_job(
            target_job, machine_id, current_time, test_schedule, {}, 0
        )
        print(f"Can schedule at current time: {can_schedule_now}")
        
        if not can_schedule_now:
            end_time = current_time + target_job['processing_time']
            
            # Test individual constraints
            machine_avail = constraints._check_machine_availability(
                machine_id, current_time, end_time, test_schedule
            )
            print(f"  Machine available: {machine_avail}")
            
            deadline_ok = constraints._check_deadline_constraints(target_job, end_time)
            print(f"  Deadline OK: {deadline_ok}")
            
            time_avail = constraints._check_time_availability(current_time, end_time, target_job)
            print(f"  Time available: {time_avail}")
            
            current_dt = epoch_to_datetime(current_time)
            end_dt = epoch_to_datetime(end_time)
            print(f"  Would start at: {current_dt}")
            print(f"  Would end at: {end_dt}")
        
        # Test at next available slot if found
        if next_slot:
            print(f"\n=== TESTING CONSTRAINTS AT NEXT AVAILABLE SLOT ===")
            can_schedule_next = constraints.can_schedule_job(
                target_job, machine_id, next_slot, test_schedule, {}, 0
            )
            print(f"Can schedule at next slot: {can_schedule_next}")
            
            if not can_schedule_next:
                end_time = next_slot + target_job['processing_time']
                
                # Test individual constraints
                machine_avail = constraints._check_machine_availability(
                    machine_id, next_slot, end_time, test_schedule
                )
                print(f"  Machine available: {machine_avail}")
                
                deadline_ok = constraints._check_deadline_constraints(target_job, end_time)
                print(f"  Deadline OK: {deadline_ok}")
                
                time_avail = constraints._check_time_availability(next_slot, end_time, target_job)
                print(f"  Time available: {time_avail}")
                
                if not deadline_ok:
                    print(f"  Job would end: {epoch_to_datetime(end_time)}")
                    print(f"  Deadline is: {epoch_to_datetime(target_job.get('lcd_date_epoch', 0))}")
        
        # Check if this is part of a dependency chain
        from app.scheduling.scheduler_utils import extract_job_family, extract_process_number
        family = extract_job_family(target_job['job_id'])
        process_num = extract_process_number(target_job['job_id'])
        print(f"\nJob family: {family}")
        print(f"Process number: {process_num}")
        
        if process_num > 1:
            print("This job has dependencies - may need previous process to complete first")
            
        # Try to find all jobs in the same family
        family_jobs = []
        for job in valid_jobs:
            if extract_job_family(job['job_id']) == family:
                family_jobs.append((extract_process_number(job['job_id']), job['job_id'], job))
        
        family_jobs.sort()
        print(f"\nJobs in family '{family}':")
        for proc_num, job_id, job_data in family_jobs:
            duration = job_data.get('processing_time', 0) / 3600
            machine = job_data.get('MachineName_v', 'Unknown')
            deadline = job_data.get('lcd_date_epoch')
            deadline_str = epoch_to_datetime(deadline).strftime('%m-%d') if deadline else 'None'
            print(f"  Process {proc_num}: {job_id} ({duration:.1f}h on {machine}, deadline: {deadline_str})")
            
        # Test different start times to see if there's any valid slot
        print(f"\n=== TESTING VARIOUS START TIMES ===")
        singapore_tz = pytz.timezone('Asia/Singapore')
        base_time = datetime.now(tz=singapore_tz).replace(hour=6, minute=30, second=0, microsecond=0)
        
        for day_offset in range(5):  # Test next 5 days
            test_time = base_time + timedelta(days=day_offset)
            test_epoch = datetime_to_epoch(test_time)
            
            can_schedule = constraints.can_schedule_job(
                target_job, machine_id, test_epoch, test_schedule, {}, 0
            )
            
            print(f"Day +{day_offset} ({test_time.strftime('%m-%d %H:%M')}): {can_schedule}")
            
            if not can_schedule:
                end_time = test_epoch + target_job['processing_time']
                deadline_ok = constraints._check_deadline_constraints(target_job, end_time)
                time_avail = constraints._check_time_availability(test_epoch, end_time, target_job)
                print(f"    Deadline OK: {deadline_ok}, Time available: {time_avail}")
            
            if can_schedule:
                break
                
    except Exception as e:
        logger.error(f"Error in test: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_jost25050207_debug()