#!/usr/bin/env python3

import sys
import json
import requests

def analyze_late_jobs():
    """Analyze late jobs from the greedy scheduler."""
    
    # Get detailed schedule data
    response = requests.get("http://localhost:8000/api/reports/detailed-schedule?solver=greedy")
    if response.status_code != 200:
        print(f"Error fetching data: {response.status_code}")
        return
    
    data = response.json()
    late_jobs = [j for j in data if j.get('buffer_status') == 'Late']
    
    print(f"📊 LATE JOBS ANALYSIS")
    print(f"Total jobs: {len(data)}")
    print(f"Late jobs: {len(late_jobs)}")
    print(f"Late percentage: {len(late_jobs)/len(data)*100:.1f}%")
    print()
    
    # Check LCD date vs scheduled start
    lcd_comparison = [j for j in late_jobs if j.get('lcd_date_epoch') and j.get('scheduled_start_epoch') and j['scheduled_start_epoch'] > j['lcd_date_epoch']]
    print(f"Jobs starting after LCD date: {len(lcd_comparison)}")
    
    # Check by machine type
    subcontractor_late = [j for j in late_jobs if j.get('machine_name') == 'SUBCONTRACTOR']
    print(f"Late SUBCONTRACTOR jobs: {len(subcontractor_late)}")
    
    machine_late = [j for j in late_jobs if j.get('machine_name') != 'SUBCONTRACTOR']
    print(f"Late machine jobs: {len(machine_late)}")
    
    # Check buffer hours
    negative_buffer = [j for j in late_jobs if j.get('actual_buffer_hours', 0) < 0]
    print(f"Jobs with negative buffer hours: {len(negative_buffer)}")
    print()
    
    # Show worst late jobs
    print("🚨 TOP 5 WORST LATE JOBS:")
    worst_late = sorted(late_jobs, key=lambda x: x.get('actual_buffer_hours', 0))[:5]
    for i, job in enumerate(worst_late, 1):
        print(f"{i}. Job: {job.get('job', 'N/A')} | Process: {job.get('process_code', 'N/A')}")
        print(f"   LCD Date: {job.get('lcd_date_str', 'N/A')}")
        print(f"   Scheduled Start: {job.get('scheduled_start_time_str', 'N/A')}")
        print(f"   Buffer Hours: {job.get('actual_buffer_hours', 'N/A')}")
        print(f"   Machine: {job.get('machine_name', 'N/A')}")
        print()
    
    # Check LCD date priority effectiveness
    print("🎯 LCD DATE PRIORITY CHECK:")
    jobs_with_lcd = [j for j in data if j.get('lcd_date_epoch')]
    jobs_without_lcd = [j for j in data if not j.get('lcd_date_epoch')]
    print(f"Jobs with LCD date: {len(jobs_with_lcd)}")
    print(f"Jobs without LCD date: {len(jobs_without_lcd)}")
    
    # Check if LCD prioritization is working
    if len(jobs_with_lcd) > 1:
        sorted_by_start = sorted(jobs_with_lcd, key=lambda x: x.get('scheduled_start_epoch', 0))
        sorted_by_lcd = sorted(jobs_with_lcd, key=lambda x: x.get('lcd_date_epoch', 0))
        
        # Compare first 10 jobs
        print("\nFirst 10 jobs by LCD date vs by scheduled start:")
        print("LCD Order:", [j.get('job', 'N/A')[:8] for j in sorted_by_lcd[:10]])
        print("Scheduled Order:", [j.get('job', 'N/A')[:8] for j in sorted_by_start[:10]])

if __name__ == "__main__":
    analyze_late_jobs()