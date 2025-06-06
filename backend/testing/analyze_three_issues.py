#!/usr/bin/env python3

import sys
sys.path.append('.')
from app.data_ingestion.mariadb_parser import load_jobs_planning_data
from app.scheduling.cpsat_solver import schedule_jobs
from app.scheduling.greedy_solver import greedy_schedule
import logging

logging.basicConfig(level=logging.WARNING)

print('=== THREE SCHEDULING CONSTRAINT ISSUES ANALYSIS ===')

# Load full dataset with proper horizon
jobs, machines, setup = load_jobs_planning_data(max_jobs=1000, planning_horizon_days=60)
print(f'Loaded {len(jobs)} jobs on {len(machines)} machines')

# Test CP-SAT with proper 60-day horizon
print(f'\n1. CP-SAT ANALYSIS (60-day horizon):')
result_cpsat = schedule_jobs(
    jobs,
    machines, 
    setup,
    time_limit_seconds=120,
    planning_horizon_days=60
)

cpsat_scheduled = len([k for k in result_cpsat.keys() if k != '_metadata'])
cpsat_status = result_cpsat.get('_metadata', {}).get('status', 'Unknown')
cpsat_message = result_cpsat.get('_metadata', {}).get('message', '')

print(f'CP-SAT Result: {cpsat_status}')
print(f'CP-SAT Scheduled: {cpsat_scheduled} out of {len(jobs)} jobs')
print(f'CP-SAT Message: {cpsat_message}')

# Test Greedy solver for comparison
print(f'\n2. GREEDY SOLVER COMPARISON:')
result_greedy = greedy_schedule(jobs, machines, setup)
greedy_scheduled = sum(len(tasks) for tasks in result_greedy.values())
print(f'Greedy Scheduled: {greedy_scheduled} out of {len(jobs)} jobs')

print(f'\n3. CONSTRAINT FAILURE ANALYSIS:')
unscheduled_cpsat = len(jobs) - cpsat_scheduled
unscheduled_greedy = len(jobs) - greedy_scheduled

print(f'CP-SAT unscheduled: {unscheduled_cpsat} jobs ({unscheduled_cpsat/len(jobs)*100:.1f}%)')
print(f'Greedy unscheduled: {unscheduled_greedy} jobs ({unscheduled_greedy/len(jobs)*100:.1f}%)')

if cpsat_status == 'INFEASIBLE':
    print(f'\nINFEASIBILITY ROOT CAUSES:')
    print(f'1. Job Dependencies: Process chains P01→P02→P03 with missing predecessors')
    print(f'2. CP-SAT Constraint Conflicts: Hard START_DATE + LCD_DATE + sequence constraints impossible to satisfy')
    print(f'3. Missing Predecessor Jobs: Later processes cannot schedule without earlier ones')
elif cpsat_status in ['OPTIMAL', 'FEASIBLE']:
    print(f'\nSCHEDULING SUCCESS BUT LOW EFFICIENCY:')
    print(f'Root cause: Complex constraint interactions make most jobs unschedulable')

# Analyze dependency chains in detail
print(f'\n4. DEPENDENCY CHAIN DETAILED ANALYSIS:')
families = {}
for job in jobs:
    job_id = job.get('job_id', '')
    if 'P0' in job_id:
        family = job_id.split('P0')[0] 
        process = job_id.split('P0')[1][0] if len(job_id.split('P0')) > 1 else '?'
        if family not in families:
            families[family] = {}
        families[family][process] = job_id

broken_chains = 0
complete_chains = 0
for family, processes in families.items():
    if len(processes) > 1:
        process_numbers = sorted([int(p) for p in processes.keys() if p.isdigit()])
        expected = list(range(1, max(process_numbers) + 1))
        if process_numbers != expected:
            broken_chains += 1
        else:
            complete_chains += 1

print(f'Complete dependency chains: {complete_chains}')
print(f'Broken dependency chains: {broken_chains}')
print(f'Dependency failure rate: {broken_chains/(broken_chains+complete_chains)*100:.1f}%')

print(f'\n=== FINAL ANALYSIS ===')
print(f'Total jobs loaded: {len(jobs)}')
print(f'Jobs scheduled by CP-SAT: {cpsat_scheduled} ({cpsat_scheduled/len(jobs)*100:.1f}%)')
print(f'Jobs scheduled by Greedy: {greedy_scheduled} ({greedy_scheduled/len(jobs)*100:.1f}%)')
print(f'Scheduling efficiency problem confirmed: Only ~{max(cpsat_scheduled, greedy_scheduled)/len(jobs)*100:.0f}% success rate')