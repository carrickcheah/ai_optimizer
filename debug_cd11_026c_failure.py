#!/usr/bin/env python3

import sys
import os
sys.path.append('/Users/carrickcheah/Project/ai_optimizer/backend')

from app.data_processing.main_data_processor import ProductionDataProcessor
from app.scheduling.greedy_solver import GreedyConfigManager, SchedulingConstraints
from app.utils.time_utils import datetime_to_epoch, epoch_to_datetime
from datetime import datetime
import logging

# Set up logging
logging.basicConfig(level=logging.DEBUG)

def debug_cd11_026c_failure():
    """Debug why JOAW25060047_CD11-026C-1/2 fails to schedule"""
    print("=== Debugging CD11-026C-1/2 Scheduling Failure ===")
    
    # Load data and config
    processor = ProductionDataProcessor()
    jobs = processor.load_jobs()
    machines = processor.load_machines()
    config = GreedyConfigManager.load_config()
    constraints = SchedulingConstraints(config=config)
    
    # Find the specific job
    target_job = None
    for job in jobs:
        if job.get('job_id') == 'JOAW25060047_CD11-026C-1/2':
            target_job = job
            break
    
    if not target_job:
        print("❌ Job JOAW25060047_CD11-026C-1/2 not found in loaded jobs!")
        return
    
    print(f"✅ Found job: {target_job.get('job_id')}")
    print(f"   Machine: {target_job.get('machine_id')}")
    print(f"   LCD Date: {target_job.get('lcd_date_str')} (epoch: {target_job.get('lcd_date')})")
    print(f"   Process Time: {target_job.get('process_time_hours'):.2f} hours")
    print(f"   Family: {target_job.get('family_name')}")
    print(f"   Process Order: {target_job.get('process_order')}")
    print(f"   Dependencies: {target_job.get('dependencies', [])}")
    
    # Check machine availability
    machine_id = target_job.get('machine_id')
    machine_data = None
    for machine in machines:
        if machine.get('machine_id') == machine_id:
            machine_data = machine
            break
    
    if not machine_data:
        print(f"❌ Machine {machine_id} not found!")
        return
    
    print(f"✅ Machine {machine_id} found")
    print(f"   Working hours: {machine_data.get('working_hours_per_day', 'N/A')}")
    print(f"   Setup time: {machine_data.get('setup_time_hours', 'N/A')}")
    
    # Check if it's a valid first process
    process_order = target_job.get('process_order', 0)
    dependencies = target_job.get('dependencies', [])
    
    print(f"\n=== Process Analysis ===")
    print(f"Process order: {process_order}")
    print(f"Dependencies: {dependencies}")
    print(f"Is first process: {process_order == 1}")
    print(f"Has dependencies: {len(dependencies) > 0}")
    
    if process_order == 1 and len(dependencies) == 0:
        print("✅ This should be independently schedulable (Process 1 with no dependencies)")
    else:
        print("❌ This job has dependencies or is not Process 1")
        return
    
    # Test scheduling constraints
    print(f"\n=== Testing Scheduling Constraints ===")
    
    # Get current time and try to find a slot
    current_time = datetime.now()
    current_epoch = datetime_to_epoch(current_time)
    
    # Test different time slots
    test_times = []
    for day_offset in range(7):  # Test next 7 days
        test_time = current_epoch + (day_offset * 24 * 3600) + (8 * 3600)  # 8 AM each day
        test_times.append(test_time)
    
    for i, test_time in enumerate(test_times):
        test_datetime = epoch_to_datetime(test_time)
        print(f"\nTesting slot {i+1}: {test_datetime}")
        
        # Check deadline constraint
        lcd_epoch = target_job.get('lcd_date')
        if test_time > lcd_epoch:
            print(f"  ❌ Deadline failed: {test_datetime} > {epoch_to_datetime(lcd_epoch)}")
            continue
        
        # Check machine constraint (simulate empty schedule)
        duration_hours = target_job.get('process_time_hours', 0)
        duration_seconds = duration_hours * 3600
        
        print(f"  ✅ Duration: {duration_hours:.2f} hours")
        print(f"  ✅ End time: {epoch_to_datetime(test_time + duration_seconds)}")
        
        # This would be a valid slot if no other constraints fail
        print(f"  ✅ Slot {i+1} appears valid for scheduling")
        break
    else:
        print("❌ No valid slots found in next 7 days")
    
    # Check if job is actually being processed by scheduler
    print(f"\n=== Job Processing Status ===")
    print(f"Job loaded: Yes")
    print(f"Machine mapped: {machine_data is not None}")
    print(f"LCD date valid: {target_job.get('lcd_date') > current_epoch}")
    
    # Check for any special processing logic
    job_id = target_job.get('job_id', '')
    family_name = target_job.get('family_name', '')
    
    print(f"\n=== Special Cases Check ===")
    print(f"Job ID format: {job_id}")
    print(f"Family name: {family_name}")
    
    # Look for patterns that might cause issues
    if 'JOAW' in job_id:
        print(f"📋 Note: This is an JOAW (Assembly Welding) job")
    
    if '026C' in job_id:
        print(f"📋 Note: This contains '026C' in the task code")

if __name__ == "__main__":
    debug_cd11_026c_failure() 