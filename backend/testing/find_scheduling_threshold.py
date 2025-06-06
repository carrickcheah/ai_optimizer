#!/usr/bin/env python3

import sys
sys.path.append('.')
from app.data_ingestion.mariadb_parser import load_jobs_planning_data
from app.scheduling.cpsat_solver import schedule_jobs
import logging

logging.basicConfig(level=logging.WARNING)

print('=== FINDING CP-SAT SCHEDULING THRESHOLD ===')

# Load dataset
jobs, machines, setup = load_jobs_planning_data(max_jobs=50, planning_horizon_days=60)
print(f'Loaded {len(jobs)} jobs')

print(f'\nTESTING DIFFERENT JOB BATCH SIZES TO FIND THRESHOLD:')

# Test different batch sizes to find where it breaks
test_sizes = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 12, 15, 20]
results = {}

for size in test_sizes:
    print(f'\nTesting {size} jobs:')
    result = schedule_jobs(
        jobs[:size], machines, setup,
        time_limit_seconds=300,  # 5 minutes
        planning_horizon_days=60,
        enforce_sequence=True,
        enforce_deadlines=True
    )
    
    status = result.get('_metadata', {}).get('status')
    scheduled = len([k for k in result.keys() if k != '_metadata'])
    solve_time = result.get('_metadata', {}).get('solver_time', 0)
    
    results[size] = {
        'status': status,
        'scheduled': scheduled,
        'time': solve_time,
        'success_rate': scheduled/size if size > 0 else 0
    }
    
    print(f'  Result: {status}, Scheduled: {scheduled}/{size} ({scheduled/size*100:.1f}%), Time: {solve_time:.2f}s')
    
    # Stop if we get consistent infeasible results
    if status == 'INFEASIBLE' and size >= 10:
        break

print(f'\n=== THRESHOLD ANALYSIS ===')
print(f'Job Size | Status      | Scheduled | Success Rate | Time')
print(f'---------|-------------|-----------|--------------|------')

max_feasible_size = 0
min_infeasible_size = 1000

for size in sorted(results.keys()):
    r = results[size]
    status_short = r['status'][:10].ljust(10)
    print(f'{size:8d} | {status_short} | {r["scheduled"]:4d}/{size:4d} | {r["success_rate"]*100:9.1f}% | {r["time"]:5.2f}s')
    
    if r['status'] in ['OPTIMAL', 'FEASIBLE'] and r['scheduled'] > 0:
        max_feasible_size = max(max_feasible_size, size)
    elif r['status'] == 'INFEASIBLE':
        min_infeasible_size = min(min_infeasible_size, size)

print(f'\nKEY FINDINGS:')
print(f'Maximum feasible batch size: {max_feasible_size} jobs')
if min_infeasible_size < 1000:
    print(f'Minimum infeasible batch size: {min_infeasible_size} jobs')

# Analyze what makes the difference
print(f'\nANALYZING WHY SCHEDULING BREAKS AT SIZE {min_infeasible_size}:')

if min_infeasible_size <= len(jobs):
    # Look at the jobs in the breaking batch
    breaking_jobs = jobs[:min_infeasible_size]
    families = {}
    
    for job in breaking_jobs:
        job_id = job.get('job_id', '')
        if '_CP' in job_id:
            family = job_id.split('_CP')[0]
            if family not in families:
                families[family] = 0
            families[family] += 1
    
    print(f'Breaking batch contains:')
    print(f'  Total families: {len(families)}')
    print(f'  Jobs per family: {[f"{fam}: {count}" for fam, count in families.items()]}')
    
    multi_process_families = sum(1 for count in families.values() if count > 1)
    print(f'  Multi-process families: {multi_process_families}')
    
    # Check for specific constraint conflicts
    machine_conflicts = {}
    for job in breaking_jobs:
        machine = job.get('MachineName_v')
        if machine not in machine_conflicts:
            machine_conflicts[machine] = 0
        machine_conflicts[machine] += 1
    
    heavy_machines = {m: count for m, count in machine_conflicts.items() if count > 3}
    if heavy_machines:
        print(f'  Machines with >3 jobs: {heavy_machines}')

print(f'\n=== CONCLUSION ===')
if max_feasible_size > 0:
    print(f'✅ CP-SAT CAN schedule jobs, but only in small batches (<= {max_feasible_size} jobs)')
    print(f'❌ CP-SAT CANNOT handle larger batches (>= {min_infeasible_size} jobs) due to constraint complexity')
    print(f'💡 SOLUTION: Break 1000 jobs into batches of {max_feasible_size} jobs each')
    print(f'   This would require {1000//max_feasible_size + (1 if 1000%max_feasible_size else 0)} separate scheduling runs')
else:
    print(f'❌ CP-SAT cannot schedule even single jobs with current constraints')
    print(f'💡 SOLUTION: Relax constraints (remove sequences, flexible deadlines)')

print(f'\nTHE REAL PROBLEM: Not "impossible to schedule" but "too complex for large batches"')
print(f'Current system tries to schedule all 1000 jobs at once → INFEASIBLE')
print(f'Better approach: Schedule in small batches → SUCCESS')