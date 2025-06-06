#!/usr/bin/env python3

import sys
sys.path.append('.')
from app.data_ingestion.mariadb_parser import load_jobs_planning_data
from app.scheduling.cpsat_solver import schedule_jobs
import logging

logging.basicConfig(level=logging.WARNING)

print('=== TESTING: CAN CP-SAT SCHEDULE WITH MORE TIME? ===')

# Load small dataset for testing
jobs, machines, setup = load_jobs_planning_data(max_jobs=50, planning_horizon_days=60)
print(f'Loaded {len(jobs)} jobs')

print(f'\n1. CURRENT SYSTEM TEST (120 seconds):')
result1 = schedule_jobs(
    jobs[:20], machines, setup,
    time_limit_seconds=120,  # Current system limit
    planning_horizon_days=60,
    enforce_sequence=True,
    enforce_deadlines=True
)
status1 = result1.get('_metadata', {}).get('status')
scheduled1 = len([k for k in result1.keys() if k != '_metadata'])
print(f'Result: {status1}, Scheduled: {scheduled1}/20')

print(f'\n2. LONGER TIME TEST (600 seconds = 10 minutes):')
result2 = schedule_jobs(
    jobs[:20], machines, setup,
    time_limit_seconds=600,  # 5x longer
    planning_horizon_days=60,
    enforce_sequence=True,
    enforce_deadlines=True
)
status2 = result2.get('_metadata', {}).get('status')
scheduled2 = len([k for k in result2.keys() if k != '_metadata'])
solve_time2 = result2.get('_metadata', {}).get('solver_time', 0)
print(f'Result: {status2}, Scheduled: {scheduled2}/20, Time: {solve_time2:.2f}s')

print(f'\n3. VERY LONG TIME TEST (1800 seconds = 30 minutes):')
result3 = schedule_jobs(
    jobs[:15], machines, setup,  # Even fewer jobs
    time_limit_seconds=1800,
    planning_horizon_days=60,
    enforce_sequence=True,
    enforce_deadlines=True
)
status3 = result3.get('_metadata', {}).get('status')
scheduled3 = len([k for k in result3.keys() if k != '_metadata'])
solve_time3 = result3.get('_metadata', {}).get('solver_time', 0)
print(f'Result: {status3}, Scheduled: {scheduled3}/15, Time: {solve_time3:.2f}s')

print(f'\n4. RELAXED CONSTRAINTS TEST (flexible deadlines):')
# Test with relaxed deadline constraints
jobs_relaxed = []
for job in jobs[:20]:
    job_copy = job.copy()
    # Push LCD dates further into future to make them achievable
    if job_copy.get('lcd_date_epoch'):
        job_copy['lcd_date_epoch'] = job_copy['lcd_date_epoch'] + (30 * 24 * 3600)  # +30 days
    jobs_relaxed.append(job_copy)

result4 = schedule_jobs(
    jobs_relaxed, machines, setup,
    time_limit_seconds=300,
    planning_horizon_days=90,  # Longer horizon
    enforce_sequence=True,
    enforce_deadlines=True
)
status4 = result4.get('_metadata', {}).get('status')
scheduled4 = len([k for k in result4.keys() if k != '_metadata'])
solve_time4 = result4.get('_metadata', {}).get('solver_time', 0)
print(f'Result: {status4}, Scheduled: {scheduled4}/20, Time: {solve_time4:.2f}s')

print(f'\n5. SMALL BATCH TEST (just 5 jobs):')
result5 = schedule_jobs(
    jobs[:5], machines, setup,
    time_limit_seconds=300,
    planning_horizon_days=60,
    enforce_sequence=True,
    enforce_deadlines=True
)
status5 = result5.get('_metadata', {}).get('status')
scheduled5 = len([k for k in result5.keys() if k != '_metadata'])
solve_time5 = result5.get('_metadata', {}).get('solver_time', 0)
print(f'Result: {status5}, Scheduled: {scheduled5}/5, Time: {solve_time5:.2f}s')

print(f'\n=== ANALYSIS: IS IT TIME OR CONSTRAINTS? ===')

print(f'\nTIME SCALING TEST RESULTS:')
print(f'120s (current):     {status1} - {scheduled1}/20 jobs')
print(f'600s (5x longer):   {status2} - {scheduled2}/20 jobs ({solve_time2:.1f}s used)')
print(f'1800s (15x longer): {status3} - {scheduled3}/15 jobs ({solve_time3:.1f}s used)')
print(f'Small batch (5):    {status5} - {scheduled5}/5 jobs ({solve_time5:.1f}s used)')
print(f'Relaxed constraints: {status4} - {scheduled4}/20 jobs ({solve_time4:.1f}s used)')

if status2 == 'INFEASIBLE' and status3 == 'INFEASIBLE':
    print(f'\n❌ CONCLUSION: More time does NOT solve the problem')
    print(f'Even 30 minutes cannot find a solution - this proves it is')
    print(f'a CONSTRAINT CONFLICT issue, not a time/complexity issue')
elif scheduled2 > scheduled1 or scheduled3 > scheduled1:
    print(f'\n✅ CONCLUSION: More time DOES help!')
    print(f'The scheduling can work but needs longer computation time')
    print(f'Current 120s limit is insufficient for complex problems')
else:
    print(f'\n🤔 MIXED RESULTS: Need further investigation')

print(f'\nRECOMMENDATION:')
if scheduled4 > max(scheduled1, scheduled2, scheduled3):
    print(f'Relaxing constraints works better than more time')
    print(f'Problem is over-constrained, not under-timed')
else:
    print(f'Time limits may need to be increased significantly')
    print(f'Consider 10-30 minute solve times for complex schedules')