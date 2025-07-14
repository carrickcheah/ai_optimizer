#!/usr/bin/env python3
"""
Test script for complex dependency patterns
Demonstrates support for non-sequential and repeated processes
"""

import logging
import sys
from datetime import datetime, timedelta

# Add backend to path
sys.path.insert(0, '/Users/carrickcheah/Project/ai_optimizer/backend')

from app.scheduling.dependency_manager import get_dependency_manager
from app.scheduling.greedy_solver import greedy_schedule

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def create_test_jobs():
    """Create test jobs with different dependency patterns."""
    base_time = datetime.now()
    
    jobs = []
    
    # Example 1: Sequential pattern (P01 → P02 → P03)
    jobs.extend([
        {
            'job_id': 'J001_SEQ-01/3',
            'MachineName_v': 'MACHINE_A',
            'hours_need': 8,
            'priority': 3,
            'processing_time': 8 * 3600,
            'lcd_date_epoch': (base_time + timedelta(days=10)).timestamp()
        },
        {
            'job_id': 'J001_SEQ-02/3',
            'MachineName_v': 'MACHINE_A',
            'hours_need': 6,
            'priority': 3,
            'processing_time': 6 * 3600,
            'lcd_date_epoch': (base_time + timedelta(days=10)).timestamp()
        },
        {
            'job_id': 'J001_SEQ-03/3',
            'MachineName_v': 'MACHINE_B',
            'hours_need': 4,
            'priority': 3,
            'processing_time': 4 * 3600,
            'lcd_date_epoch': (base_time + timedelta(days=10)).timestamp()
        }
    ])
    
    # Example 2: Non-sequential pattern (P01 → P02 → P05 → P09)
    jobs.extend([
        {
            'job_id': 'J002_NONSEQ-01/4',
            'MachineName_v': 'MACHINE_A',
            'hours_need': 5,
            'priority': 2,
            'processing_time': 5 * 3600,
            'lcd_date_epoch': (base_time + timedelta(days=7)).timestamp()
        },
        {
            'job_id': 'J002_NONSEQ-02/4',
            'MachineName_v': 'MACHINE_B',
            'hours_need': 7,
            'priority': 2,
            'processing_time': 7 * 3600,
            'lcd_date_epoch': (base_time + timedelta(days=7)).timestamp()
        },
        {
            'job_id': 'J002_NONSEQ-05/4',
            'MachineName_v': 'MACHINE_A',
            'hours_need': 6,
            'priority': 2,
            'processing_time': 6 * 3600,
            'lcd_date_epoch': (base_time + timedelta(days=7)).timestamp()
        },
        {
            'job_id': 'J002_NONSEQ-09/4',
            'MachineName_v': 'MACHINE_B',
            'hours_need': 4,
            'priority': 2,
            'processing_time': 4 * 3600,
            'lcd_date_epoch': (base_time + timedelta(days=7)).timestamp()
        }
    ])
    
    # Example 3: Repeated process pattern (P01 → P02 → P05 → P05 → P07)
    jobs.extend([
        {
            'job_id': 'J003_REPEAT-01/5',
            'MachineName_v': 'MACHINE_C',
            'hours_need': 3,
            'priority': 1,
            'processing_time': 3 * 3600,
            'lcd_date_epoch': (base_time + timedelta(days=5)).timestamp()
        },
        {
            'job_id': 'J003_REPEAT-02/5',
            'MachineName_v': 'MACHINE_C',
            'hours_need': 4,
            'priority': 1,
            'processing_time': 4 * 3600,
            'lcd_date_epoch': (base_time + timedelta(days=5)).timestamp()
        },
        {
            'job_id': 'J004_REPEAT-05/5',  # First P05
            'MachineName_v': 'MACHINE_C',
            'hours_need': 5,
            'priority': 1,
            'processing_time': 5 * 3600,
            'lcd_date_epoch': (base_time + timedelta(days=5)).timestamp()
        },
        {
            'job_id': 'J005_REPEAT-05/5',  # Second P05 (different job code)
            'MachineName_v': 'MACHINE_C',
            'hours_need': 5,
            'priority': 1,
            'processing_time': 5 * 3600,
            'lcd_date_epoch': (base_time + timedelta(days=5)).timestamp()
        },
        {
            'job_id': 'J003_REPEAT-07/5',
            'MachineName_v': 'MACHINE_C',
            'hours_need': 6,
            'priority': 1,
            'processing_time': 6 * 3600,
            'lcd_date_epoch': (base_time + timedelta(days=5)).timestamp()
        }
    ])
    
    return jobs


def test_dependency_detection():
    """Test that dependency manager correctly identifies patterns."""
    logger.info("=" * 80)
    logger.info("Testing Dependency Pattern Detection")
    logger.info("=" * 80)
    
    jobs = create_test_jobs()
    dep_manager = get_dependency_manager()
    
    # Let dependency manager learn from job data
    dep_manager.derive_sequence_from_jobs(jobs)
    
    # Check each family's sequence
    families = ['SEQ', 'NONSEQ', 'REPEAT']
    
    for family in families:
        seq_info = dep_manager.get_family_sequence_info(family)
        if seq_info['exists']:
            logger.info(f"\nFamily {family}:")
            logger.info(f"  Pattern: {seq_info['pattern']}")
            logger.info(f"  Sequence: {' → '.join(seq_info['sequence'])}")
            logger.info(f"  Total steps: {seq_info['total_steps']}")


def test_scheduling():
    """Test scheduling with complex dependencies."""
    logger.info("\n" + "=" * 80)
    logger.info("Testing Scheduling with Complex Dependencies")
    logger.info("=" * 80)
    
    jobs = create_test_jobs()
    machines = ['MACHINE_A', 'MACHINE_B', 'MACHINE_C']
    
    # Run greedy scheduling
    schedule = greedy_schedule(jobs, machines, enforce_sequence=True)
    
    # Display results
    logger.info("\nScheduling Results:")
    for machine, tasks in schedule.items():
        if tasks:
            logger.info(f"\n{machine}:")
            for task in sorted(tasks, key=lambda x: x[1]):  # Sort by start time
                job_id = task[0]
                start_time = datetime.fromtimestamp(task[1])
                end_time = datetime.fromtimestamp(task[2])
                logger.info(f"  {job_id}: {start_time.strftime('%Y-%m-%d %H:%M')} - {end_time.strftime('%Y-%m-%d %H:%M')}")


def test_dependency_validation():
    """Test dependency validation."""
    logger.info("\n" + "=" * 80)
    logger.info("Testing Dependency Validation")
    logger.info("=" * 80)
    
    jobs = create_test_jobs()
    dep_manager = get_dependency_manager()
    
    # Validate sequences
    errors = dep_manager.validate_job_sequence(jobs)
    
    if errors:
        logger.error("Validation errors found:")
        for family, error_list in errors.items():
            logger.error(f"  Family {family}: {', '.join(error_list)}")
    else:
        logger.info("All job sequences are valid!")


def main():
    """Run all tests."""
    test_dependency_detection()
    test_scheduling()
    test_dependency_validation()
    
    logger.info("\n" + "=" * 80)
    logger.info("Complex Dependency Testing Complete!")
    logger.info("=" * 80)


if __name__ == "__main__":
    main()