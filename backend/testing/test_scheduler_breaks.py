#!/usr/bin/env python3
"""
Test how schedulers handle jobs that span across break times
"""

import os
import sys
from datetime import datetime, timedelta
import pytz

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.data_ingestion.mariadb_parser import load_jobs_planning_data
from app.scheduling.greedy_solver import greedy_schedule
from app.scheduling.cpsat_solver import schedule_jobs as cpsat_schedule
from app.utils.time_utils import epoch_to_datetime, format_datetime_for_display

def analyze_scheduled_job(job_id, start_epoch, end_epoch, machine):
    """Analyze if a scheduled job properly respects breaks"""
    from app.scheduling.time_availability import TimeAvailabilityManager
    
    malaysia_tz = pytz.timezone('Asia/Kuala_Lumpur')
    checker = TimeAvailabilityManager.get_instance()
    
    start_dt = epoch_to_datetime(start_epoch)
    end_dt = epoch_to_datetime(end_epoch)
    duration_hours = (end_epoch - start_epoch) / 3600
    
    print(f"\nJob {job_id} on {machine}:")
    print(f"  Start: {format_datetime_for_display(start_dt)}")
    print(f"  End: {format_datetime_for_display(end_dt)}")
    print(f"  Duration: {duration_hours:.1f} hours")
    
    # Check if job spans across breaks
    current = start_dt
    breaks_during_job = []
    
    while current < end_dt:
        if checker.is_break_time(current):
            break_info = None
            for brk in checker.cache._breaktimes_cache:
                start_time = brk['start_time']
                end_time = brk['end_time']
                current_time = current.time()
                
                if start_time <= current_time <= end_time:
                    break_info = brk
                    break
            
            if break_info and break_info not in breaks_during_job:
                breaks_during_job.append(break_info)
        
        current += timedelta(minutes=15)
    
    if breaks_during_job:
        print(f"  ❌ Job runs through {len(breaks_during_job)} break(s):")
        for brk in breaks_during_job:
            print(f"     - {brk['name']}: {brk['start_time']} to {brk['end_time']}")
    else:
        print(f"  ✅ Job does not run through any breaks")
    
    return len(breaks_during_job) > 0

def test_scheduler_break_handling():
    """Test how greedy and CP-SAT schedulers handle breaks"""
    
    print("=== LOADING TEST DATA ===")
    jobs, machines, setup_times = load_jobs_planning_data()
    
    # Take first 10 jobs for testing
    test_jobs = jobs[:10]
    print(f"Testing with {len(test_jobs)} jobs")
    
    print("\n=== TESTING GREEDY SCHEDULER ===")
    greedy_result = greedy_schedule(test_jobs, machines, setup_times)
    
    jobs_with_break_violations = 0
    jobs_analyzed = 0
    
    for machine, scheduled_jobs in greedy_result.items():
        if machine == '_metadata':
            continue
            
        for job_tuple in scheduled_jobs:
            if len(job_tuple) >= 3:
                job_id = job_tuple[0]
                start_epoch = job_tuple[1]
                end_epoch = job_tuple[2]
                
                has_violation = analyze_scheduled_job(job_id, start_epoch, end_epoch, machine)
                if has_violation:
                    jobs_with_break_violations += 1
                jobs_analyzed += 1
                
                if jobs_analyzed >= 5:  # Analyze first 5 jobs
                    break
        
        if jobs_analyzed >= 5:
            break
    
    print(f"\n=== GREEDY SCHEDULER SUMMARY ===")
    print(f"Jobs with break violations: {jobs_with_break_violations}/{jobs_analyzed}")
    
    print("\n=== TESTING CP-SAT SCHEDULER ===")
    cpsat_result = cpsat_schedule(test_jobs, machines, setup_times)
    
    jobs_with_break_violations = 0
    jobs_analyzed = 0
    
    for job_id, job_data in cpsat_result.items():
        if job_id == '_metadata':
            continue
            
        if isinstance(job_data, dict) and 'machine' in job_data:
            has_violation = analyze_scheduled_job(
                job_id, 
                job_data['start'], 
                job_data['end'], 
                job_data['machine']
            )
            if has_violation:
                jobs_with_break_violations += 1
            jobs_analyzed += 1
            
            if jobs_analyzed >= 5:
                break
    
    print(f"\n=== CP-SAT SCHEDULER SUMMARY ===")
    print(f"Jobs with break violations: {jobs_with_break_violations}/{jobs_analyzed}")

if __name__ == "__main__":
    test_scheduler_break_handling()