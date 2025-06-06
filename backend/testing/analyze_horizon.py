#!/usr/bin/env python3

import logging
from app.data_ingestion.mariadb_parser import load_jobs_planning_data
from datetime import datetime

logging.basicConfig(level=logging.WARNING)

print('=== HORIZON FILTERING ANALYSIS ===')

jobs, machines, setup = load_jobs_planning_data(max_jobs=100, planning_horizon_days=60)
print(f'Loaded {len(jobs)} jobs')

# Current time analysis
current_time_epoch = datetime.now().timestamp()
current_time_str = datetime.fromtimestamp(current_time_epoch).strftime('%Y-%m-%d %H:%M:%S')
print(f'Current time: {current_time_str}')

# Analyze horizon filtering
horizon_days = 7
horizon_cutoff_epoch = current_time_epoch + (horizon_days * 24 * 3600)
horizon_cutoff_str = datetime.fromtimestamp(horizon_cutoff_epoch).strftime('%Y-%m-%d %H:%M:%S')
print(f'7-day horizon cutoff: {horizon_cutoff_str}')

# Check job LCD dates vs horizon
jobs_within_horizon = 0
jobs_beyond_horizon = 0
jobs_no_lcd = 0

print(f'\nJOB LCD DATE ANALYSIS:')
for i, job in enumerate(jobs[:10]):  # Check first 10 jobs
    job_id = job.get('job_id', 'Unknown')
    lcd_date_epoch = job.get('lcd_date_epoch')
    priority = job.get('priority', 5)
    
    if lcd_date_epoch:
        lcd_date_str = datetime.fromtimestamp(lcd_date_epoch).strftime('%Y-%m-%d %H:%M:%S')
        days_from_now = (lcd_date_epoch - current_time_epoch) / (24 * 3600)
        
        if priority <= 2:
            status = 'INCLUDED (high priority)'
            jobs_within_horizon += 1
        elif lcd_date_epoch <= horizon_cutoff_epoch:
            status = 'INCLUDED (within horizon)'
            jobs_within_horizon += 1
        else:
            status = 'EXCLUDED (beyond horizon)'
            jobs_beyond_horizon += 1
            
        print(f'{job_id}: LCD={lcd_date_str} ({days_from_now:.1f} days), Priority={priority} -> {status}')
    else:
        jobs_no_lcd += 1
        print(f'{job_id}: No LCD date, Priority={priority} -> INCLUDED')

# Summary
print(f'\nHORIZON FILTER SUMMARY:')
print(f'Jobs within 7-day horizon: {jobs_within_horizon}')
print(f'Jobs beyond 7-day horizon: {jobs_beyond_horizon}') 
print(f'Jobs without LCD dates: {jobs_no_lcd}')

# Test with longer horizon
print(f'\nTEST WITH 60-DAY HORIZON:')
horizon_days_long = 60
horizon_cutoff_long = current_time_epoch + (horizon_days_long * 24 * 3600)

jobs_within_long = 0
for job in jobs:
    lcd_date_epoch = job.get('lcd_date_epoch')
    priority = job.get('priority', 5)
    
    if priority <= 2:  # High priority always included
        jobs_within_long += 1
    elif not lcd_date_epoch:  # No LCD date, include
        jobs_within_long += 1  
    elif lcd_date_epoch <= horizon_cutoff_long:  # Within long horizon
        jobs_within_long += 1

print(f'Jobs that would pass 60-day horizon filter: {jobs_within_long} out of {len(jobs)}')