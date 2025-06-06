#!/usr/bin/env python3

import logging
from app.data_ingestion.mariadb_parser import load_jobs_planning_data
from app.scheduling.cpsat_solver import schedule_jobs

logging.basicConfig(level=logging.WARNING)

print('=== SCHEDULING CONSTRAINT ANALYSIS ===')

jobs, machines, setup = load_jobs_planning_data(max_jobs=100, planning_horizon_days=60)
print(f'Loaded {len(jobs)} jobs')

# Analyze data quality
missing_machines = 0
no_hours = 0
no_lcd_date = 0
families = {}

for job in jobs:
    job_id = job.get('job_id', '')
    
    if not job.get('MachineName_v') or job.get('MachineName_v') == 'NOT_ASSIGN':
        missing_machines += 1
        
    if not job.get('hours_need') and not job.get('day_need'):
        no_hours += 1
        
    if not job.get('lcd_date_epoch'):
        no_lcd_date += 1
    
    if 'P0' in job_id:
        family = job_id.split('P0')[0]
        process = job_id.split('P0')[1][0] if 'P0' in job_id else '?'
        if family not in families:
            families[family] = {}
        families[family][process] = job_id

print(f'\nDATA QUALITY ISSUES:')
print(f'Jobs with missing/unassigned machines: {missing_machines}')
print(f'Jobs without duration: {no_hours}')
print(f'Jobs without LCD dates: {no_lcd_date}')

print(f'\nDEPENDENCY CHAIN ANALYSIS:')
incomplete_chains = 0
complete_chains = 0

for family, processes in families.items():
    if len(processes) > 1:
        process_numbers = sorted([int(p) for p in processes.keys() if p.isdigit()])
        expected = list(range(1, len(process_numbers) + 1))
        if process_numbers != expected:
            incomplete_chains += 1
            missing = set(range(1, max(process_numbers)+1)) - set(process_numbers)
            print(f'BROKEN: {family} has {process_numbers}, missing {missing}')
        else:
            complete_chains += 1

print(f'Complete chains: {complete_chains}')
print(f'Broken chains: {incomplete_chains}')

# Test CP-SAT with small subset
print(f'\nCP-SAT CONSTRAINT ANALYSIS:')
result = schedule_jobs(
    jobs[:20],
    machines,
    setup,
    time_limit_seconds=30,
    planning_horizon_days=7
)

scheduled_count = len([k for k in result.keys() if k != '_metadata'])
status = result.get('_metadata', {}).get('status', 'Unknown')
message = result.get('_metadata', {}).get('message', 'No message')

print(f'CP-SAT Status: {status}')
print(f'Scheduled jobs: {scheduled_count} out of 20')
print(f'Message: {message}')

if status == 'INFEASIBLE':
    print('\nINFEASIBILITY CAUSES:')
    print('1. Conflicting START_DATE constraints (multiple P01 jobs same machine/time)')
    print('2. Impossible deadline constraints (LCD_DATE before completion)')
    print('3. Broken dependency chains (P02 requires P01 but P01 missing)')
    print('4. Working hours constraints (jobs too long for time slots)')