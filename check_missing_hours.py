#!/usr/bin/env python3
import json
import sys

# Read JSON data from stdin
data = json.load(sys.stdin)

missing_jobs = [
    'JOAW25060037_CD11-026-9/6',
    'JOST25050164_CP08-259-5/4', 
    'JOST25050055_CP08-086-4/4',
    'JOST25050054_CP08-085-4/4',
    'JOAW25050031_CD11-026-9/6',
    'JOAW25040171_CP08-071-3/3'
]

print('=== Analysis of 6 jobs missing hours_need ===')
for job_id in missing_jobs:
    job = next((j for j in data if j['job_id'] == job_id), None)
    if job:
        qty = job.get('job_quantity', 'Missing')
        output_hr = job.get('expect_output_per_hour', 'Missing') 
        hours_need = job.get('hours_need', 'Missing')
        print(f'{job_id}:')
        print(f'  Job Qty: {qty}')
        print(f'  Output Per Hr: {output_hr}')
        print(f'  Hours Need: {hours_need}')
        
        if qty != 'Missing' and output_hr != 'Missing':
            if output_hr == 0:
                print(f'  ❌ ISSUE: Output Per Hr is 0 - cannot divide by zero!')
            elif qty == 0:
                print(f'  ❌ ISSUE: Job Qty is 0 - no work to do!')
            else:
                calculated = qty / output_hr
                print(f'  ✅ Calculated hours_need should be: {calculated:.3f}')
        print()
    else:
        print(f'{job_id}: ❌ NOT FOUND in API response')
        print()

# Also show some working jobs for comparison
print('=== Sample of working jobs for comparison ===')
working_jobs = [j for j in data if j.get('hours_need') and j.get('hours_need') > 0][:5]
for job in working_jobs:
    qty = job.get('job_quantity', 0)
    output_hr = job.get('expect_output_per_hour', 0)
    hours_need = job.get('hours_need', 0)
    calculated = qty / output_hr if output_hr > 0 else 0
    print(f"{job['job_id']}:")
    print(f"  Job Qty: {qty}, Output Per Hr: {output_hr}")
    print(f"  Hours Need: {hours_need:.3f}, Calculated: {calculated:.3f}")
    print()