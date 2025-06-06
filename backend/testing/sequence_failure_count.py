#!/usr/bin/env python3

import sys
sys.path.append('.')
from app.data_ingestion.mariadb_parser import load_jobs_planning_data
import logging

logging.basicConfig(level=logging.WARNING)

print('=== JOB SEQUENCE FAILURE COUNT (Full 1000 Jobs) ===')

# Load full dataset
jobs, machines, setup = load_jobs_planning_data(max_jobs=1000, planning_horizon_days=60)
print(f'Loaded {len(jobs)} jobs')

# Analyze job families and sequences
families = {}

for job in jobs:
    job_id = job.get('job_id', '')
    
    if '_CP' in job_id:
        parts = job_id.split('_CP')
        if len(parts) == 2:
            family = parts[0]
            process_part = parts[1]
            
            if '-' in process_part:
                process_info = process_part.split('-')[-1]  # "1/4"
                if '/' in process_info:
                    current_process = process_info.split('/')[0]  # "1"
                    
                    if family not in families:
                        families[family] = {}
                    families[family][current_process] = job_id

# Count sequence failures
complete_sequences = 0
broken_sequences = 0
jobs_in_complete = 0
jobs_in_broken = 0
cascade_failures = 0

for family, processes in families.items():
    if len(processes) > 1:
        process_numbers = sorted([int(p) for p in processes.keys() if p.isdigit()])
        expected = list(range(1, max(process_numbers) + 1))
        
        if process_numbers == expected:
            complete_sequences += 1
            jobs_in_complete += len(processes)
        else:
            broken_sequences += 1
            jobs_in_broken += len(processes)
            
            # Calculate cascade failures
            missing = set(expected) - set(process_numbers)
            for missing_proc in missing:
                # All processes after the missing one are cascade failures
                cascade_failures += len([p for p in process_numbers if p > missing_proc])

print(f'\nSEQUENCE FAILURE ANALYSIS:')
print(f'Total job families analyzed: {len(families)}')
total_multi_process = len([f for f in families.values() if len(f) > 1])
print(f'Multi-process families: {total_multi_process}')
print(f'Complete sequences: {complete_sequences}')
print(f'Broken sequences: {broken_sequences}')

if total_multi_process > 0:
    print(f'Sequence failure rate: {broken_sequences/total_multi_process*100:.1f}%')

print(f'\nJOB IMPACT:')
print(f'Jobs in complete sequences: {jobs_in_complete}')
print(f'Jobs in broken sequences: {jobs_in_broken}')
print(f'Additional cascade failures: {cascade_failures}')

print(f'\n=== FINAL SEQUENCE FAILURE COUNT ===')
print(f'Direct sequence failures: {jobs_in_broken} jobs')
print(f'Cascade failures from missing predecessors: {cascade_failures} jobs')
print(f'Total jobs affected by sequence failures: {jobs_in_broken + cascade_failures} jobs')
print(f'Percentage of total jobs affected: {(jobs_in_broken + cascade_failures)/len(jobs)*100:.1f}%')

# Detailed breakdown
print(f'\nDETAILED BREAKDOWN:')
print(f'1. Jobs in broken dependency chains: {jobs_in_broken}')
print(f'2. Additional jobs failing due to missing predecessors: {cascade_failures}')
print(f'3. Total sequence-related failures: {jobs_in_broken + cascade_failures}')
print(f'4. This represents {(jobs_in_broken + cascade_failures)/859*100:.1f}% of the 859 unscheduled jobs')