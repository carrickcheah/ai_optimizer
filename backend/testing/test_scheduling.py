#!/usr/bin/env python3

from app.data_ingestion.mariadb_parser import load_jobs_planning_data
from app.scheduling.cpsat_solver import schedule_jobs

# Load test data
jobs, machines, setup_times = load_jobs_planning_data(max_jobs=50, planning_horizon_days=30)
print(f'Loaded {len(jobs)} jobs, {len(machines)} machines')

# Try CP-SAT solver
print('\n=== CP-SAT SOLVER TEST ===')
try:
    cpsat_result = schedule_jobs(jobs, machines, setup_times, time_limit_seconds=30)
    if cpsat_result and '_metadata' in cpsat_result:
        status = cpsat_result['_metadata'].get('status', 'Unknown')
        scheduled_count = len([k for k in cpsat_result.keys() if k != '_metadata'])
        print(f'CP-SAT Status: {status}')
        print(f'CP-SAT Scheduled: {scheduled_count} jobs')
    else:
        print('CP-SAT returned invalid result')
except Exception as e:
    print(f'CP-SAT Error: {e}')

# Print sample job structure
if jobs:
    print('\n=== SAMPLE JOB STRUCTURE ===')
    sample_job = jobs[0]
    for key, value in sample_job.items():
        if 'epoch' in key.lower() or key in ['job_id', 'MachineName_v', 'hours_need', 'day_need', 'priority']:
            print(f'{key}: {value}')
            
# Analyze job family structure
print('\n=== JOB FAMILY ANALYSIS ===')
families = {}
for job in jobs[:10]:  # Sample first 10 jobs
    job_id = job.get('job_id', '')
    if '_' in job_id:
        parts = job_id.split('_')
        if len(parts) >= 2:
            family = parts[0]
            process = parts[1]
            if family not in families:
                families[family] = []
            families[family].append(process)

for family, processes in families.items():
    print(f'Family {family}: {processes}')