#!/usr/bin/env python3

import sys
sys.path.append('.')
from app.data_ingestion.mariadb_parser import load_jobs_planning_data
import logging

logging.basicConfig(level=logging.WARNING)

print('=== JOB ID PATTERN ANALYSIS ===')

# Load dataset
jobs, machines, setup = load_jobs_planning_data(max_jobs=100, planning_horizon_days=60)
print(f'Loaded {len(jobs)} jobs')

print(f'\nSAMPLE JOB IDs (first 20):')
for i, job in enumerate(jobs[:20]):
    job_id = job.get('job_id', '')
    priority = job.get('priority', 5)
    machine = job.get('MachineName_v', 'Unknown')
    print(f'{i+1:2d}. {job_id} (Priority: {priority}, Machine: {machine})')

# Analyze actual job ID patterns
print(f'\nJOB ID PATTERN ANALYSIS:')
families = {}
process_patterns = {}

for job in jobs:
    job_id = job.get('job_id', '')
    
    # Look for different process patterns
    if '_CP' in job_id:
        # Pattern: JOTP25050254_CP08-213-1/4
        parts = job_id.split('_CP')
        if len(parts) == 2:
            family = parts[0]
            process_part = parts[1]
            
            # Extract process info (e.g., "08-213-1/4")
            if '-' in process_part:
                process_info = process_part.split('-')[-1]  # "1/4"
                if '/' in process_info:
                    current_process = process_info.split('/')[0]  # "1"
                    total_processes = process_info.split('/')[1]  # "4"
                    
                    if family not in families:
                        families[family] = {}
                    families[family][current_process] = job_id
                    
                    pattern_key = f'{family}_total_{total_processes}'
                    if pattern_key not in process_patterns:
                        process_patterns[pattern_key] = 0
                    process_patterns[pattern_key] += 1

print(f'\nFAMILY SEQUENCE ANALYSIS:')
complete_sequences = 0
broken_sequences = 0
jobs_in_complete = 0
jobs_in_broken = 0

for family, processes in families.items():
    if len(processes) > 1:
        process_numbers = sorted([int(p) for p in processes.keys() if p.isdigit()])
        expected = list(range(1, max(process_numbers) + 1))
        
        if process_numbers == expected:
            complete_sequences += 1
            jobs_in_complete += len(processes)
            print(f'COMPLETE: {family} has processes {process_numbers} ({len(processes)} jobs)')
        else:
            broken_sequences += 1
            jobs_in_broken += len(processes)
            missing = set(expected) - set(process_numbers)
            print(f'BROKEN: {family} has {process_numbers}, missing {missing} ({len(processes)} jobs)')
    else:
        print(f'SINGLE: {family} has only process {list(processes.keys())[0]}')

print(f'\nSEQUENCE FAILURE STATISTICS:')
total_families = len(families)
multi_process_families = len([f for f in families.values() if len(f) > 1])

if multi_process_families > 0:
    print(f'Total job families: {total_families}')
    print(f'Multi-process families: {multi_process_families}')
    print(f'Complete sequences: {complete_sequences}')
    print(f'Broken sequences: {broken_sequences}')
    print(f'Sequence failure rate: {broken_sequences/multi_process_families*100:.1f}%')
    print(f'Jobs in broken sequences: {jobs_in_broken}')
    print(f'Jobs affected by sequence failures: {jobs_in_broken}')
else:
    print('No multi-process sequences found in this dataset')

print(f'\nPROCESS PATTERN SUMMARY:')
for pattern, count in process_patterns.items():
    print(f'{pattern}: {count} jobs')