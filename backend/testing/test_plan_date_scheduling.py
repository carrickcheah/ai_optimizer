#!/usr/bin/env python3
"""Test script to verify plan_date scheduling logic."""

import logging
import sys
from datetime import datetime

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

sys.path.insert(0, '/Users/carrickcheah/Project/ai_optimizer/backend')

try:
    from app.data_ingestion.mariadb_parser import load_jobs_planning_data
    from app.scheduling.greedy_solver import greedy_schedule
except ImportError as e:
    logger.error(f"Could not import required modules: {e}")
    sys.exit(1)

def test_plan_date_scheduling():
    """Test that jobs are scheduled according to their plan dates."""
    
    logger.info("Loading job data...")
    jobs, machines, setup_times = load_jobs_planning_data()
    
    if not jobs:
        logger.error("No jobs loaded")
        return
    
    # Find job JOST25050285
    target_job = None
    for job in jobs:
        if 'JOST25050285' in job.get('job_id', ''):
            target_job = job
            logger.info(f"\nFound target job: {job['job_id']}")
            logger.info(f"  Plan Date: {job.get('plan_date')}")
            logger.info(f"  Plan Date Epoch: {job.get('plan_date_epoch')}")
            logger.info(f"  LCD Date: {job.get('lcd_date')}")
            logger.info(f"  LCD Date Epoch: {job.get('lcd_date_epoch')}")
            logger.info(f"  Machine: {job.get('MachineName_v')}")
            
            if job.get('plan_date_epoch'):
                plan_dt = datetime.fromtimestamp(job['plan_date_epoch'])
                logger.info(f"  Plan Date (formatted): {plan_dt.strftime('%Y-%m-%d %H:%M:%S')}")
            
            break
    
    if not target_job:
        logger.error("Could not find job JOST25050285")
        return
    
    # Run scheduling with limited jobs to see the effect
    logger.info("\nRunning greedy scheduling...")
    
    # Filter to just a subset of jobs for clearer output
    test_jobs = [j for j in jobs if 'JOST25050285' in j.get('job_id', '') or 
                 'JOST25050286' in j.get('job_id', '') or
                 'JOST25050287' in j.get('job_id', '')]
    
    # Add a few more jobs for context
    test_jobs.extend(jobs[:10])
    
    logger.info(f"Scheduling {len(test_jobs)} test jobs...")
    
    schedule = greedy_schedule(test_jobs[:50], machines, setup_times, enforce_sequence=True)
    
    # Check the scheduled time for our target job
    logger.info("\nScheduling results:")
    for machine, tasks in schedule.items():
        for task in tasks:
            job_id, start_time, end_time = task[:3]
            if 'JOST25050285' in job_id:
                start_dt = datetime.fromtimestamp(start_time)
                end_dt = datetime.fromtimestamp(end_time)
                logger.info(f"\nJob {job_id} scheduled:")
                logger.info(f"  Machine: {machine}")
                logger.info(f"  Start: {start_dt.strftime('%Y-%m-%d %H:%M:%S')}")
                logger.info(f"  End: {end_dt.strftime('%Y-%m-%d %H:%M:%S')}")
                
                # Check if it's late
                if target_job.get('plan_date_epoch'):
                    days_late = (start_time - target_job['plan_date_epoch']) / 86400
                    if days_late > 0:
                        logger.warning(f"  ⚠️  Job is {days_late:.1f} days LATE from plan date!")
                    else:
                        logger.info(f"  ✅ Job starts on time or early ({days_late:.1f} days)")

if __name__ == "__main__":
    test_plan_date_scheduling()