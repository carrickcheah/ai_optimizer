#!/usr/bin/env python3

import logging
from app.data_ingestion.mariadb_parser import load_jobs_planning_data
from app.scheduling.cpsat_solver import schedule_jobs
from datetime import datetime

# Configure logging to reduce verbosity
logging.basicConfig(
    level=logging.WARNING,  # Only show warnings and errors
    format='%(levelname)s:%(name)s:%(message)s'
)

# Enable INFO only for our specific modules we care about
logging.getLogger('app.scheduling.cpsat_solver').setLevel(logging.INFO)
logging.getLogger('__main__').setLevel(logging.INFO)

def epoch_to_dt(epoch):
    return datetime.fromtimestamp(epoch).strftime('%Y-%m-%d %H:%M:%S')

def main():
    print("Testing improved constraint handling with optimized parameters...")
    
    print("Loading jobs data...")
    jobs, machines, setup = load_jobs_planning_data(max_jobs=50)  # Reduced to 50 for faster testing
    print(f"Loaded {len(jobs)} jobs on {len(machines)} machines")
    
    print("Running CP-SAT solver...")
    result = schedule_jobs(
        jobs, 
        machines, 
        setup, 
        time_limit_seconds=30,  # Reduced from 60 for faster testing
        max_jobs_limit=50,      # Limit for test performance
        planning_horizon_days=7  # Short horizon for testing
    )
    
    print(f"Status: {result.get('_metadata', {}).get('status')}")
    print(f"Objective: {result.get('_metadata', {}).get('objective_value')}")
    
    # Check START_DATE constraint adherence
    print('\n=== START_DATE Constraint Violations ===')
    start_violations = 0
    for job_id, job_data in result.items():
        if job_id == '_metadata':
            continue
        original_data = job_data.get('original_job_data', {})
        if 'start_date_epoch' in original_data and original_data['start_date_epoch']:
            required_start = original_data['start_date_epoch']
            actual_start = job_data['start']
            delay_hours = (actual_start - required_start) / 3600
            if delay_hours > 1:  # More than 1 hour delay
                start_violations += 1
                print(f'  {job_id}: Required={epoch_to_dt(required_start)}, Actual={epoch_to_dt(actual_start)}, Delay={delay_hours:.1f}h')
    
    if start_violations == 0:
        print("  ✅ No significant START_DATE violations!")
    else:
        print(f"  ❌ Found {start_violations} START_DATE violations")
    
    # Check LCD_DATE constraint adherence  
    print('\n=== LCD_DATE (Due Date) Violations ===')
    due_violations = 0
    for job_id, job_data in result.items():
        if job_id == '_metadata':
            continue
        original_data = job_data.get('original_job_data', {})
        if 'lcd_date_epoch' in original_data and original_data['lcd_date_epoch']:
            due_date = original_data['lcd_date_epoch']
            actual_end = job_data['end']
            tardiness_hours = (actual_end - due_date) / 3600
            if tardiness_hours > 1:  # More than 1 hour late
                due_violations += 1
                print(f'  {job_id}: Due={epoch_to_dt(due_date)}, Actual={epoch_to_dt(actual_end)}, Late={tardiness_hours:.1f}h')
    
    if due_violations == 0:
        print("  ✅ No significant LCD_DATE violations!")
    else:
        print(f"  ❌ Found {due_violations} LCD_DATE violations")
    
    # Show first few scheduled jobs
    print('\n=== Sample Schedule (CD02 Family) ===')
    cd02_jobs = [(k, v) for k, v in result.items() if k != '_metadata' and 'CD02' in k]
    cd02_jobs.sort(key=lambda x: x[1]['start'])
    
    for job_id, job_data in cd02_jobs[:8]:
        start_time = epoch_to_dt(job_data['start'])
        end_time = epoch_to_dt(job_data['end'])
        machine = job_data['machine']
        print(f'  {job_id}: {start_time} → {end_time} on {machine}')

if __name__ == '__main__':
    main() 