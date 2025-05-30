#!/usr/bin/env python3
"""Test script to demonstrate the LCD date deadline fix"""

import sys
sys.path.append('services/backend')

from app.scheduling.cpsat_solver import schedule_jobs
from app.utils.time_utils import datetime_to_epoch, epoch_to_datetime
from datetime import datetime, timedelta

def create_test_jobs():
    """Create test jobs with various deadline scenarios"""
    current_time = datetime.now()
    
    # Job 1: Normal deadline (future)
    future_deadline = current_time + timedelta(days=2)
    
    # Job 2: Late deadline (past)
    past_deadline = current_time - timedelta(days=1)
    
    # Job 3: Very late deadline
    very_past_deadline = current_time - timedelta(days=5)
    
    jobs = [
        {
            'job_id': 'TEST_JOB_01_P01',
            'rsc_code': 'MACHINE_A',
            'hours_need': 4,
            'priority': 1,
            'lcd_date_epoch': datetime_to_epoch(future_deadline),
        },
        {
            'job_id': 'TEST_JOB_02_P01', 
            'rsc_code': 'MACHINE_A',
            'hours_need': 6,
            'priority': 2,
            'lcd_date_epoch': datetime_to_epoch(past_deadline),
        },
        {
            'job_id': 'TEST_JOB_03_P01',
            'rsc_code': 'MACHINE_B', 
            'hours_need': 8,
            'priority': 3,
            'lcd_date_epoch': datetime_to_epoch(very_past_deadline),
        }
    ]
    
    machines = ['MACHINE_A', 'MACHINE_B']
    
    return jobs, machines

def test_deadline_constraints():
    """Test that LCD date constraints work correctly"""
    print("=== Testing LCD Date Deadline Constraints ===\n")
    
    jobs, machines = create_test_jobs()
    
    print("Test Jobs:")
    for job in jobs:
        lcd_date = epoch_to_datetime(job['lcd_date_epoch'])
        print(f"  {job['job_id']}: LCD Date = {lcd_date}, Hours = {job['hours_need']}")
    
    print(f"\nCurrent time: {datetime.now()}")
    print("\n--- Testing with Deadline Constraints ENABLED ---")
    
    # Test with deadline constraints enabled
    result_with_deadlines = schedule_jobs(
        jobs=jobs,
        machines=machines, 
        enforce_deadlines=True,
        time_limit_seconds=10,
        max_jobs_limit=10
    )
    
    status = result_with_deadlines.get('_metadata', {}).get('status', 'UNKNOWN')
    print(f"Result: {status}")
    
    if status in ['OPTIMAL', 'FEASIBLE']:
        print("✅ Jobs scheduled successfully with deadline constraints!")
        for job_id, job_data in result_with_deadlines.items():
            if job_id != '_metadata':
                start_time = epoch_to_datetime(job_data['start'])
                end_time = epoch_to_datetime(job_data['end'])
                print(f"  {job_id}: {start_time} → {end_time} on {job_data['machine']}")
    else:
        print("❌ Jobs could not be scheduled with deadline constraints")
        message = result_with_deadlines.get('_metadata', {}).get('message', 'No message')
        print(f"   Reason: {message}")
    
    print("\n--- Testing with Deadline Constraints DISABLED ---")
    
    # Test with deadline constraints disabled
    result_without_deadlines = schedule_jobs(
        jobs=jobs,
        machines=machines,
        enforce_deadlines=False,
        time_limit_seconds=10, 
        max_jobs_limit=10
    )
    
    status = result_without_deadlines.get('_metadata', {}).get('status', 'UNKNOWN')
    print(f"Result: {status}")
    
    if status in ['OPTIMAL', 'FEASIBLE']:
        print("✅ Jobs scheduled successfully without deadline constraints!")
        for job_id, job_data in result_without_deadlines.items():
            if job_id != '_metadata':
                start_time = epoch_to_datetime(job_data['start'])
                end_time = epoch_to_datetime(job_data['end'])
                print(f"  {job_id}: {start_time} → {end_time} on {job_data['machine']}")
    else:
        print("❌ Jobs could not be scheduled even without deadline constraints")
        message = result_without_deadlines.get('_metadata', {}).get('message', 'No message')
        print(f"   Reason: {message}")

    print("\n=== Summary ===")
    print("Before fix: LCD dates were ignored, jobs could start on their deadline")
    print("After fix: LCD dates are hard constraints, jobs MUST complete before deadline")
    print("Grace period: Jobs already past deadline get 24-hour extension")

if __name__ == '__main__':
    test_deadline_constraints() 