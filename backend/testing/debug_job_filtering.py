#!/usr/bin/env python3

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

import logging
from app.data_ingestion.mariadb_parser import load_jobs_planning_data

# Set up minimal logging
logging.basicConfig(level=logging.WARNING)

print("🔍 JOB FILTERING ANALYSIS")
print("=" * 50)

# Load jobs with detailed analysis
jobs, machines, setup_times = load_jobs_planning_data(max_jobs=1000, planning_horizon_days=60)

print(f"📊 LOADED DATA:")
print(f"   Total jobs from DB: {len(jobs)}")
print(f"   Total machines: {len(machines)}")

# Analyze machine assignments
machine_counts = {}
not_assign_jobs = []
valid_machine_jobs = []

for job in jobs:
    machine = job.get('MachineName_v', 'UNKNOWN')
    
    if machine == 'NOT_ASSIGN':
        not_assign_jobs.append(job.get('job_id', job.get('job', 'Unknown')))
    elif machine and machine != 'UNKNOWN':
        valid_machine_jobs.append(job.get('job_id', job.get('job', 'Unknown')))
    
    machine_counts[machine] = machine_counts.get(machine, 0) + 1

print(f"\n🏭 MACHINE ASSIGNMENT BREAKDOWN:")
for machine, count in sorted(machine_counts.items(), key=lambda x: x[1], reverse=True):
    percentage = (count / len(jobs)) * 100
    print(f"   {machine}: {count} jobs ({percentage:.1f}%)")

print(f"\n❌ NOT_ASSIGN JOBS EVIDENCE:")
print(f"   Jobs with NOT_ASSIGN: {len(not_assign_jobs)}")
print(f"   Jobs with valid machines: {len(valid_machine_jobs)}")
print(f"   Jobs with unknown/missing machines: {len(jobs) - len(not_assign_jobs) - len(valid_machine_jobs)}")

if not_assign_jobs:
    print(f"\n📝 FIRST 10 NOT_ASSIGN JOBS:")
    for i, job_id in enumerate(not_assign_jobs[:10]):
        print(f"   {i+1}. {job_id}")

print(f"\n🧮 MATH CHECK:")
print(f"   Total jobs loaded: {len(jobs)}")
print(f"   NOT_ASSIGN jobs: {len(not_assign_jobs)}")
print(f"   Valid machine jobs: {len(valid_machine_jobs)}")
print(f"   Difference (1000 - valid): {1000 - len(valid_machine_jobs)}")

print(f"\n✅ CONCLUSION:")
if len(not_assign_jobs) == 333:
    print(f"   CONFIRMED: Exactly 333 jobs have NOT_ASSIGN machines!")
elif len(not_assign_jobs) > 0:
    print(f"   PARTIAL: {len(not_assign_jobs)} jobs have NOT_ASSIGN machines")
    print(f"   Additional {333 - len(not_assign_jobs)} jobs missing for other reasons")
else:
    print(f"   NO NOT_ASSIGN jobs found - filtering happens elsewhere") 