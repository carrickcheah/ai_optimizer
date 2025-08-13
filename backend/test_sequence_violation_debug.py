#!/usr/bin/env python3
"""
Reproduce and debug the exact sequence violation issue.
Create the CD11-029 family jobs that are showing simultaneous starts.
"""

import logging
import sys
import os
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__)))

from app.scheduling.greedy_solver import greedy_schedule

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

def create_cd11_029_jobs():
    """Create the exact CD11-029 jobs that are causing problems."""
    jobs = [
        # CD11-029 family with processes 1-8
        {
            'job_id': 'JOAW25060055_CD11-029-1/8',
            'MachineName_v': 'WS02',
            'processing_time': 3600,  # 1 hour
            'priority': 3,
            'hours_need': 1.0,
            'job_quantity': 10,
            'expect_output_per_hour': 10,
            'plan_date_epoch': 1723651200  # Some past date to trigger urgency
        },
        {
            'job_id': 'JOAW25060055_CD11-029-2/8',
            'MachineName_v': 'WS02', 
            'processing_time': 3600,
            'priority': 3,
            'hours_need': 1.0,
            'job_quantity': 10,
            'expect_output_per_hour': 10,
            'plan_date_epoch': 1723651200
        },
        {
            'job_id': 'JOAW25060055_CD11-029-3/8',
            'MachineName_v': 'WS02',
            'processing_time': 3600,
            'priority': 3,
            'hours_need': 1.0,
            'job_quantity': 10,
            'expect_output_per_hour': 10,
            'plan_date_epoch': 1723651200
        },
        {
            'job_id': 'JOAW25060055_CD11-029-4/8',
            'MachineName_v': 'SW08',
            'processing_time': 86400 * 9,  # 9 days (long process)
            'priority': 1,  # High priority - this is key!
            'hours_need': 216.0,  # 9 days
            'job_quantity': 100,
            'expect_output_per_hour': 0.46,
            'plan_date_epoch': 1723651200
        },
        {
            'job_id': 'JOAW25060055_CD11-029-5/8',
            'MachineName_v': 'LVL01',
            'processing_time': 3600 * 19,  # 19 hours
            'priority': 1,  # High priority
            'hours_need': 19.0,
            'job_quantity': 50,
            'expect_output_per_hour': 2.6,
            'plan_date_epoch': 1723651200
        },
        {
            'job_id': 'JOAW25060055_CD11-029-6/8',
            'MachineName_v': 'PP05-060T',
            'processing_time': 3600 * 40,  # 40 hours
            'priority': 1,  # High priority
            'hours_need': 40.0,
            'job_quantity': 80,
            'expect_output_per_hour': 2.0,
            'plan_date_epoch': 1723651200
        },
        {
            'job_id': 'JOAW25060055_CD11-029-7/8',
            'MachineName_v': 'SUBCONTRACTOR',
            'processing_time': 3600 * 192,  # 8 days
            'priority': 1,
            'hours_need': 192.0,
            'job_quantity': 100,
            'expect_output_per_hour': 0.52,
            'plan_date_epoch': 1723651200
        },
        {
            'job_id': 'JOAW25060055_CD11-029-8/8',
            'MachineName_v': 'WH01B-CSPK',
            'processing_time': 3600 * 6,  # 6 hours
            'priority': 2,
            'hours_need': 6.0,
            'job_quantity': 30,
            'expect_output_per_hour': 5.0,
            'plan_date_epoch': 1723651200
        }
    ]
    return jobs

def test_sequence_violation_reproduction():
    """Test if we can reproduce the sequence violation."""
    logger.info("🧪 Testing CD11-029 Sequence Violation Reproduction")
    logger.info("=" * 60)
    
    jobs = create_cd11_029_jobs()
    machines = ['WS02', 'SW08', 'LVL01', 'PP05-060T', 'SUBCONTRACTOR', 'WH01B-CSPK']
    setup_times = {}
    
    logger.info(f"📋 Test Jobs ({len(jobs)} CD11-029 processes):")
    for job in jobs:
        logger.info(f"  - {job['job_id']} (Priority: {job['priority']}, Machine: {job['MachineName_v']})")
    
    logger.info("\n🔄 Running Scheduler with Sequence Enforcement...")
    
    try:
        schedule = greedy_schedule(
            jobs=jobs,
            machines=machines,
            setup_times=setup_times,
            enforce_sequence=True,
            max_operators=0
        )
        
        logger.info("\n📊 Scheduling Results:")
        logger.info("=" * 40)
        
        # Collect all scheduled jobs with their times
        all_jobs = []
        for machine, machine_jobs in schedule.items():
            for task in machine_jobs:
                job_id = task[0]
                start_time = task[1] 
                end_time = task[2]
                all_jobs.append((job_id, start_time, end_time, machine))
        
        # Sort by start time
        all_jobs.sort(key=lambda x: x[1])
        
        logger.info("Scheduled in chronological order:")
        for job_id, start_time, end_time, machine in all_jobs:
            # Extract process number
            if '/' in job_id:
                process = job_id.split('-')[-1].split('/')[0]
                logger.info(f"  P{process}: {job_id} | {start_time:.0f} -> {end_time:.0f} ({machine})")
        
        # Check for sequence violations
        logger.info("\n🔍 Sequence Validation Check:")
        cd11_jobs = [(job_id, start_time, end_time) for job_id, start_time, end_time, _ in all_jobs if 'CD11-029' in job_id]
        
        violations = []
        for i in range(len(cd11_jobs)):
            job_id, start_time, end_time = cd11_jobs[i]
            process_num = int(job_id.split('-')[-1].split('/')[0])
            
            # Check if any previous process is scheduled after this one starts
            for j in range(i):
                other_job_id, other_start, other_end = cd11_jobs[j] 
                other_process = int(other_job_id.split('-')[-1].split('/')[0])
                
                if other_process < process_num and other_start >= start_time:
                    violations.append(f"P{process_num} starts at {start_time} but P{other_process} starts at {other_start}")
        
        if violations:
            logger.error(f"❌ SEQUENCE VIOLATIONS DETECTED:")
            for violation in violations:
                logger.error(f"  {violation}")
            return False
        else:
            logger.info("✅ Sequence is correct: P1 -> P2 -> P3 -> P4 -> P5 -> P6 -> P7 -> P8")
            return True
            
    except Exception as e:
        logger.error(f"❌ Test failed with exception: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_sequence_violation_reproduction()
    if success:
        print("\n🎯 SEQUENCE TEST PASSED - No violations detected")
        sys.exit(0) 
    else:
        print("\n💥 SEQUENCE VIOLATIONS REPRODUCED - Need to fix!")
        sys.exit(1)