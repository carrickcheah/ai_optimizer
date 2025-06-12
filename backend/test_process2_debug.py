#!/usr/bin/env python3
"""
Debug Process 2 specifically to see why it can't be scheduled.
"""

import logging
from datetime import datetime, timedelta
import pytz

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def test_process2_scheduling():
    """Test Process 2 scheduling specifically."""
    try:
        from app.data_ingestion.mariadb_parser import load_jobs_planning_data
        from app.scheduling.greedy_solver import (
            GreedyConfigManager, JobValidator, MachineManager, 
            SchedulingConstraints, GreedyScheduler
        )
        from app.scheduling.time_availability import get_next_available_slot
        from app.utils.time_utils import datetime_to_epoch, epoch_to_datetime
        
        print("=== DEBUGGING PROCESS 2 SPECIFICALLY ===")
        
        # Load data
        jobs, machines, setup_times = load_jobs_planning_data()
        config = GreedyConfigManager.load_config()
        valid_jobs = JobValidator.validate_and_prepare_jobs(jobs)
        machine_names = MachineManager.prepare_machines(machines)
        
        # Find Process 2 job
        process2_job = None
        for job in valid_jobs:
            if job['job_id'] == 'JOTP25050215_CP08-563A-2/3':
                process2_job = job
                break
        
        if not process2_job:
            print("❌ Process 2 job not found!")
            return
        
        print(f"Found Process 2 job: {process2_job['job_id']}")
        print(f"Machine: {process2_job.get('MachineName_v')}")
        print(f"Processing time: {process2_job.get('processing_time')} seconds = {process2_job.get('processing_time')/3600:.1f} hours")
        
        # Find best machine
        current_time = datetime_to_epoch(datetime.now())
        machine_id = MachineManager.find_best_machine(
            process2_job, machine_names, 
            {m: current_time for m in machine_names}
        )
        print(f"Best machine: {machine_id}")
        
        # Test get_next_available_slot for this specific job
        duration_hours = process2_job.get('processing_time', 3600) / 3600
        print(f"\nTesting get_next_available_slot for {duration_hours} hour job...")
        
        next_slot = get_next_available_slot(current_time, duration_hours)
        if next_slot:
            next_datetime = epoch_to_datetime(next_slot)
            print(f"✅ Found next slot: {next_datetime}")
        else:
            print(f"❌ No slot found!")
        
        # Test constraints manually
        constraints = SchedulingConstraints(config)
        test_schedule = {machine: [] for machine in machine_names}
        
        # Simulate Process 1 being scheduled first (ends after 12 hours)
        singapore_tz = pytz.timezone('Asia/Singapore')
        tomorrow_630 = datetime.now(tz=singapore_tz).replace(hour=6, minute=30, second=0, microsecond=0)
        tomorrow_630 += timedelta(days=1)
        process1_start = datetime_to_epoch(tomorrow_630)
        process1_end = process1_start + 12 * 3600  # 12 hours
        
        # Add Process 1 to schedule (simulating it was scheduled)
        test_schedule['TM03-017T'].append(('JOTP25050215_CP08-563A-1/3', process1_start, process1_end, 0))
        
        print(f"\nSimulated Process 1 scheduled:")
        print(f"  Start: {epoch_to_datetime(process1_start)}")
        print(f"  End: {epoch_to_datetime(process1_end)}")
        
        # Now test Process 2 scheduling after Process 1
        print(f"\nTesting Process 2 after Process 1...")
        
        # Process 2 should start after Process 1 ends
        earliest_start = process1_end
        print(f"Earliest start for Process 2: {epoch_to_datetime(earliest_start)}")
        
        # Check if machine is available then
        machine_available_time = max(
            test_schedule.get(machine_id, [])[-1][2] if test_schedule.get(machine_id) else current_time,
            earliest_start
        )
        print(f"Machine {machine_id} available at: {epoch_to_datetime(machine_available_time)}")
        
        # Test constraints at that time
        can_schedule = constraints.can_schedule_job(
            process2_job, machine_id, machine_available_time, 
            test_schedule, {}, 0
        )
        print(f"Can schedule Process 2 at machine available time: {can_schedule}")
        
        if not can_schedule:
            end_time = machine_available_time + process2_job['processing_time']
            
            # Test individual constraints
            machine_avail = constraints._check_machine_availability(
                machine_id, machine_available_time, end_time, test_schedule
            )
            print(f"  Machine available: {machine_avail}")
            
            deadline_ok = constraints._check_deadline_constraints(process2_job, end_time)
            print(f"  Deadline OK: {deadline_ok}")
            
            time_avail = constraints._check_time_availability(machine_available_time, end_time, process2_job)
            print(f"  Time available: {time_avail}")
            
            print(f"  Machine available time: {epoch_to_datetime(machine_available_time)}")
            print(f"  Job would end at: {epoch_to_datetime(end_time)}")
        
        # Test get_next_available_slot from the dependency time
        print(f"\nTesting get_next_available_slot from dependency end time...")
        next_slot_from_dep = get_next_available_slot(earliest_start, duration_hours)
        if next_slot_from_dep:
            next_datetime_dep = epoch_to_datetime(next_slot_from_dep)
            print(f"✅ Found slot from dependency time: {next_datetime_dep}")
        else:
            print(f"❌ No slot found from dependency time!")
            
    except Exception as e:
        logger.error(f"Error in test: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_process2_scheduling()