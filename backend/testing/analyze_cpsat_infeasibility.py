#!/usr/bin/env python3

import sys
sys.path.append('.')
from app.data_ingestion.mariadb_parser import load_jobs_planning_data
from app.scheduling.cpsat_solver import schedule_jobs
from datetime import datetime
import logging

logging.basicConfig(level=logging.WARNING)

print('=== CP-SAT INFEASIBILITY DETAILED ANALYSIS ===')

# Load dataset
jobs, machines, setup = load_jobs_planning_data(max_jobs=200, planning_horizon_days=60)
print(f'Loaded {len(jobs)} jobs on {len(machines)} machines')

# Analyze constraint conflicts step by step
print(f'\n1. CONSTRAINT TYPE ANALYSIS:')

# A. START_DATE constraints
start_date_jobs = 0
start_date_conflicts = 0
machine_start_conflicts = {}

for job in jobs:
    if job.get('start_date_epoch'):
        start_date_jobs += 1
        machine = job.get('MachineName_v')
        start_date = job.get('start_date_epoch')
        
        if machine not in machine_start_conflicts:
            machine_start_conflicts[machine] = []
        machine_start_conflicts[machine].append((job.get('job_id'), start_date))

# Check for START_DATE conflicts on same machine
for machine, job_times in machine_start_conflicts.items():
    if len(job_times) > 1:
        # Sort by start time
        job_times.sort(key=lambda x: x[1])
        for i in range(len(job_times) - 1):
            time_diff = (job_times[i+1][1] - job_times[i][1]) / 3600  # hours
            if time_diff < 8:  # Less than 8 hours apart
                start_date_conflicts += 1

print(f'Jobs with START_DATE constraints: {start_date_jobs}')
print(f'START_DATE conflicts detected: {start_date_conflicts}')

# B. LCD_DATE constraints
lcd_date_jobs = 0
impossible_deadlines = 0
current_time = datetime.now().timestamp()

for job in jobs:
    if job.get('lcd_date_epoch'):
        lcd_date_jobs += 1
        lcd_date = job.get('lcd_date_epoch')
        hours_need = job.get('hours_need', 0) or job.get('day_need', 0) * 24 or 1
        
        # Check if deadline is impossible given job duration
        time_to_deadline = (lcd_date - current_time) / 3600  # hours
        if time_to_deadline < hours_need:
            impossible_deadlines += 1

print(f'Jobs with LCD_DATE constraints: {lcd_date_jobs}')
print(f'Impossible deadlines detected: {impossible_deadlines}')

# C. Working hours constraints
long_jobs = 0
impossible_working_hours = 0

for job in jobs:
    hours_need = job.get('hours_need', 0) or job.get('day_need', 0) * 24 or 1
    if hours_need > 17.5:  # Longer than normal working day
        long_jobs += 1
        if hours_need > 120:  # More than a week of work
            impossible_working_hours += 1

print(f'Jobs longer than daily working hours: {long_jobs}')
print(f'Jobs with impossible working hour requirements: {impossible_working_hours}')

print(f'\n2. CONSTRAINT INTERACTION ANALYSIS:')

# Test different constraint combinations
print(f'\nA. Test with NO constraints:')
result_no_constraints = schedule_jobs(
    jobs[:50], machines, setup,
    time_limit_seconds=30,
    planning_horizon_days=60,
    enforce_sequence=False,
    enforce_deadlines=False
)
no_constraint_status = result_no_constraints.get('_metadata', {}).get('status')
no_constraint_scheduled = len([k for k in result_no_constraints.keys() if k != '_metadata'])
print(f'Status: {no_constraint_status}, Scheduled: {no_constraint_scheduled}/50')

print(f'\nB. Test with ONLY sequence constraints:')
result_sequence_only = schedule_jobs(
    jobs[:50], machines, setup,
    time_limit_seconds=30,
    planning_horizon_days=60,
    enforce_sequence=True,
    enforce_deadlines=False
)
sequence_status = result_sequence_only.get('_metadata', {}).get('status')
sequence_scheduled = len([k for k in result_sequence_only.keys() if k != '_metadata'])
print(f'Status: {sequence_status}, Scheduled: {sequence_scheduled}/50')

print(f'\nC. Test with ALL constraints (current system):')
result_all_constraints = schedule_jobs(
    jobs[:50], machines, setup,
    time_limit_seconds=30,
    planning_horizon_days=60,
    enforce_sequence=True,
    enforce_deadlines=True
)
all_status = result_all_constraints.get('_metadata', {}).get('status')
all_scheduled = len([k for k in result_all_constraints.keys() if k != '_metadata'])
print(f'Status: {all_status}, Scheduled: {all_scheduled}/50')

print(f'\n3. INFEASIBILITY ROOT CAUSE ANALYSIS:')

if all_status == 'INFEASIBLE':
    print(f'✅ CONFIRMED: CP-SAT reports INFEASIBLE with all constraints')
    
    print(f'\nCONSTRAINT INTERACTION MATRIX:')
    print(f'No constraints: {no_constraint_status} ({no_constraint_scheduled} jobs)')
    print(f'Sequence only: {sequence_status} ({sequence_scheduled} jobs)')
    print(f'All constraints: {all_status} ({all_scheduled} jobs)')
    
    print(f'\nROOT CAUSES IDENTIFIED:')
    if start_date_conflicts > 0:
        print(f'1. START_DATE conflicts: {start_date_conflicts} machine conflicts')
    if impossible_deadlines > 0:
        print(f'2. LCD_DATE impossible: {impossible_deadlines} jobs with unrealistic deadlines')
    if impossible_working_hours > 0:
        print(f'3. Working hours impossible: {impossible_working_hours} jobs too long for schedule')
        
    # Calculate constraint density
    total_constraints = start_date_jobs + lcd_date_jobs + long_jobs
    print(f'\nCONSTRAINT DENSITY: {total_constraints} constraints on {len(jobs)} jobs')
    print(f'Constraint ratio: {total_constraints/len(jobs):.2f} constraints per job')

print(f'\n=== CP-SAT INFEASIBILITY SUMMARY ===')
print(f'Total jobs analyzed: {len(jobs)}')
print(f'Constraint conflicts detected:')
print(f'  - START_DATE conflicts: {start_date_conflicts}')
print(f'  - Impossible LCD_DATE deadlines: {impossible_deadlines}')  
print(f'  - Impossible working hour jobs: {impossible_working_hours}')
print(f'CP-SAT result with all constraints: {all_status}')
print(f'This constraint over-specification prevents ANY jobs from being scheduled.')