#!/usr/bin/env python3

import sys
sys.path.append('.')
from app.data_ingestion.mariadb_parser import load_jobs_planning_data
import logging

logging.basicConfig(level=logging.WARNING)

print('=== JOB SEQUENCE FAILURE ANALYSIS ===')

# Load full dataset
jobs, machines, setup = load_jobs_planning_data(max_jobs=1000, planning_horizon_days=60)
print(f'Loaded {len(jobs)} jobs')

# Analyze job families and sequences
families = {}
total_jobs = 0
jobs_in_sequences = 0

for job in jobs:
    job_id = job.get('job_id', '')
    total_jobs += 1
    
    if 'P0' in job_id:
        jobs_in_sequences += 1
        family = job_id.split('P0')[0]
        process_part = job_id.split('P0')[1]
        process = process_part[0] if process_part else '?'
        
        if family not in families:
            families[family] = {}
        families[family][process] = job_id

print(f'\nSEQUENCE STRUCTURE ANALYSIS:')
print(f'Total jobs: {total_jobs}')
print(f'Jobs in process sequences: {jobs_in_sequences}')
print(f'Jobs NOT in sequences: {total_jobs - jobs_in_sequences}')

# Analyze dependency chains
single_process_families = 0
multi_process_families = 0
complete_chains = 0
broken_chains = 0
jobs_in_complete_chains = 0
jobs_in_broken_chains = 0

print(f'\nDETAILED SEQUENCE ANALYSIS:')

for family, processes in families.items():
    if len(processes) == 1:
        single_process_families += 1
    else:
        multi_process_families += 1
        process_numbers = sorted([int(p) for p in processes.keys() if p.isdigit()])
        expected_sequence = list(range(1, max(process_numbers) + 1))
        
        if process_numbers == expected_sequence:
            complete_chains += 1
            jobs_in_complete_chains += len(processes)
            print(f'COMPLETE: {family} has processes {process_numbers} ({len(processes)} jobs)')
        else:
            broken_chains += 1
            jobs_in_broken_chains += len(processes)
            missing = set(expected_sequence) - set(process_numbers)
            print(f'BROKEN: {family} has {process_numbers}, missing {missing} ({len(processes)} jobs affected)')

print(f'\nSEQUENCE FAILURE SUMMARY:')
print(f'Single-process families: {single_process_families}')
print(f'Multi-process families: {multi_process_families}')
print(f'Complete dependency chains: {complete_chains}')
print(f'Broken dependency chains: {broken_chains}')

print(f'\nJOB IMPACT ANALYSIS:')
print(f'Jobs in complete chains: {jobs_in_complete_chains}')
print(f'Jobs in broken chains: {jobs_in_broken_chains}')
print(f'Jobs affected by sequence failures: {jobs_in_broken_chains}')

# Calculate cascade failure impact
cascade_failures = 0
for family, processes in families.items():
    if len(processes) > 1:
        process_numbers = sorted([int(p) for p in processes.keys() if p.isdigit()])
        # If P01 is missing, all other processes fail
        if 1 not in process_numbers and len(process_numbers) > 0:
            cascade_failures += len(process_numbers)
        # If any intermediate process is missing, later processes fail
        for i in range(2, max(process_numbers) + 1):
            if i not in process_numbers:
                # Count how many later processes are affected
                later_processes = [p for p in process_numbers if p > i]
                cascade_failures += len(later_processes)

print(f'\nCASCADE FAILURE ANALYSIS:')
print(f'Total cascade failures: {cascade_failures}')
print(f'Dependency failure rate: {broken_chains/(broken_chains+complete_chains)*100:.1f}%')
print(f'Jobs affected by dependency failures: {jobs_in_broken_chains}/{jobs_in_sequences} ({jobs_in_broken_chains/jobs_in_sequences*100:.1f}%)')

print(f'\nFINAL SEQUENCE FAILURE COUNT:')
print(f'Direct sequence failures (broken chains): {jobs_in_broken_chains} jobs')
print(f'Cascade failures (dependent processes): {cascade_failures} jobs')
print(f'Total jobs affected by sequence issues: {jobs_in_broken_chains + cascade_failures} jobs')