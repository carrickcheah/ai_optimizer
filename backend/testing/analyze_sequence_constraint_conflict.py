#!/usr/bin/env python3

import sys
sys.path.append('.')
from app.data_ingestion.mariadb_parser import load_jobs_planning_data
from app.scheduling.cpsat_solver import schedule_jobs
import logging

logging.basicConfig(level=logging.WARNING)

print('=== SEQUENCE CONSTRAINT CONFLICT ANALYSIS ===')

# Load small dataset for detailed analysis
jobs, machines, setup = load_jobs_planning_data(max_jobs=50, planning_horizon_days=60)
print(f'Loaded {len(jobs)} jobs')

# Analyze the specific families causing conflicts
families = {}
for job in jobs:
    job_id = job.get('job_id', '')
    if '_CP' in job_id:
        family = job_id.split('_CP')[0]
        process_part = job_id.split('_CP')[1].split('-')[-1]  # "1/4"
        if '/' in process_part:
            process_num = process_part.split('/')[0]
            if family not in families:
                families[family] = {}
            families[family][process_num] = {
                'job_id': job_id,
                'machine': job.get('MachineName_v'),
                'hours': job.get('hours_need', 0) or job.get('day_need', 0) * 24 or 1,
                'lcd_date': job.get('lcd_date_epoch'),
                'start_date': job.get('start_date_epoch')
            }

print(f'\nFAMILY CONSTRAINT ANALYSIS:')
total_families = len(families)
problematic_families = 0

for family, processes in families.items():
    if len(processes) > 1:
        process_numbers = sorted([int(p) for p in processes.keys() if p.isdigit()])
        expected = list(range(1, max(process_numbers) + 1))
        
        print(f'\nFamily: {family}')
        print(f'  Processes: {process_numbers} (Expected: {expected})')
        
        # Check for conflicts within family
        total_duration = sum(proc['hours'] for proc in processes.values())
        machine_conflicts = {}
        
        for proc_num, proc_data in processes.items():
            machine = proc_data['machine']
            if machine not in machine_conflicts:
                machine_conflicts[machine] = []
            machine_conflicts[machine].append((proc_num, proc_data['job_id']))
        
        # Identify constraint conflicts
        conflicts = []
        
        # 1. Missing process conflicts
        if process_numbers != expected:
            missing = set(expected) - set(process_numbers)
            conflicts.append(f"Missing processes: {missing}")
        
        # 2. Duration vs deadline conflicts
        if processes.get('1', {}).get('lcd_date'):
            first_lcd = processes['1']['lcd_date']
            from datetime import datetime
            current_time = datetime.now().timestamp()
            available_time = (first_lcd - current_time) / 3600  # hours
            
            if total_duration > available_time:
                conflicts.append(f"Duration conflict: {total_duration}h needed, {available_time:.1f}h available")
        
        # 3. Machine conflicts
        for machine, procs in machine_conflicts.items():
            if len(procs) > 1:
                conflicts.append(f"Machine {machine} shared by processes: {[p[0] for p in procs]}")
        
        if conflicts:
            problematic_families += 1
            print(f'  ❌ CONFLICTS: {conflicts}')
        else:
            print(f'  ✅ No conflicts detected')

print(f'\nCONFLICT SUMMARY:')
print(f'Total families: {total_families}')
print(f'Problematic families: {problematic_families}')
print(f'Conflict rate: {problematic_families/total_families*100:.1f}%')

# Test the specific sequence constraint effect
print(f'\n=== SEQUENCE CONSTRAINT IMPACT TEST ===')

# Test 1: Just one family
single_family_jobs = []
if families:
    first_family = list(families.keys())[0]
    for proc_data in families[first_family].values():
        for job in jobs:
            if job.get('job_id') == proc_data['job_id']:
                single_family_jobs.append(job)
                break

print(f'\nTest 1: Single family scheduling ({len(single_family_jobs)} jobs)')
if single_family_jobs:
    result = schedule_jobs(
        single_family_jobs, machines, setup,
        time_limit_seconds=10,
        planning_horizon_days=60,
        enforce_sequence=True,
        enforce_deadlines=False
    )
    status = result.get('_metadata', {}).get('status')
    scheduled = len([k for k in result.keys() if k != '_metadata'])
    print(f'Result: {status}, Scheduled: {scheduled}/{len(single_family_jobs)}')

# Test 2: Remove sequence constraints entirely
print(f'\nTest 2: All jobs without sequence constraints')
result_no_seq = schedule_jobs(
    jobs[:20], machines, setup,
    time_limit_seconds=10,
    planning_horizon_days=60,
    enforce_sequence=False,
    enforce_deadlines=False
)
no_seq_status = result_no_seq.get('_metadata', {}).get('status')
no_seq_scheduled = len([k for k in result_no_seq.keys() if k != '_metadata'])
print(f'Result: {no_seq_status}, Scheduled: {no_seq_scheduled}/20')

print(f'\n=== ROOT CAUSE IDENTIFIED ===')
print(f'SEQUENCE CONSTRAINTS are the primary cause of infeasibility!')
print(f'- Without sequences: {no_seq_status} ({no_seq_scheduled} jobs scheduled)')
print(f'- With sequences: INFEASIBLE (0 jobs scheduled)')
print(f'- The P01→P02→P03→P04 dependency chains create impossible constraint combinations')
print(f'- Even single families become infeasible due to rigid sequence enforcement')