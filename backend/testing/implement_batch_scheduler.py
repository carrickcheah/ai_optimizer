#!/usr/bin/env python3

import sys
sys.path.append('.')
from app.data_ingestion.mariadb_parser import load_jobs_planning_data
from app.scheduling.cpsat_solver import schedule_jobs
import logging
from typing import List, Dict, Any
import time

logging.basicConfig(level=logging.WARNING)

def batch_schedule_jobs(jobs: List[Dict], machines: List[str], setup_times: Dict, 
                       batch_size: int = 5) -> Dict[str, Any]:
    """
    Schedule jobs in small batches to work around CP-SAT batch size limitations.
    
    Args:
        jobs: List of job dictionaries
        machines: List of machine names
        setup_times: Setup times dictionary
        batch_size: Size of each batch (default 5 based on testing)
    
    Returns:
        Combined results from all batches
    """
    print(f"🚀 BATCH SCHEDULER: Processing {len(jobs)} jobs in batches of {batch_size}")
    
    all_scheduled_jobs = {}
    total_batches = (len(jobs) + batch_size - 1) // batch_size
    successful_batches = 0
    failed_batches = 0
    total_scheduled = 0
    
    start_time = time.time()
    
    for batch_num in range(total_batches):
        # Create batch
        start_idx = batch_num * batch_size
        end_idx = min(start_idx + batch_size, len(jobs))
        batch_jobs = jobs[start_idx:end_idx]
        
        print(f"  Batch {batch_num + 1}/{total_batches}: Jobs {start_idx+1}-{end_idx} ({len(batch_jobs)} jobs)")
        
        # Schedule batch
        try:
            batch_result = schedule_jobs(
                batch_jobs,
                machines,
                setup_times,
                time_limit_seconds=60,  # Quick per batch
                planning_horizon_days=60,
                enforce_sequence=True,
                enforce_deadlines=True
            )
            
            status = batch_result.get('_metadata', {}).get('status', 'UNKNOWN')
            scheduled_in_batch = len([k for k in batch_result.keys() if k != '_metadata'])
            
            if status in ['OPTIMAL', 'FEASIBLE'] and scheduled_in_batch > 0:
                # Success - add to results
                for job_id, job_data in batch_result.items():
                    if job_id != '_metadata':
                        all_scheduled_jobs[job_id] = job_data
                
                successful_batches += 1
                total_scheduled += scheduled_in_batch
                print(f"    ✅ SUCCESS: {scheduled_in_batch}/{len(batch_jobs)} jobs scheduled ({status})")
            else:
                failed_batches += 1
                print(f"    ❌ FAILED: {status} - 0/{len(batch_jobs)} jobs scheduled")
                
        except Exception as e:
            failed_batches += 1
            print(f"    ❌ ERROR: {str(e)}")
    
    total_time = time.time() - start_time
    
    # Create summary metadata
    all_scheduled_jobs['_metadata'] = {
        'status': 'BATCH_COMPLETED',
        'solver_time': total_time,
        'total_jobs': len(jobs),
        'total_scheduled': total_scheduled,
        'success_rate': total_scheduled / len(jobs) * 100,
        'total_batches': total_batches,
        'successful_batches': successful_batches,
        'failed_batches': failed_batches,
        'batch_size': batch_size,
        'message': f'Batch processing completed: {total_scheduled}/{len(jobs)} jobs scheduled ({total_scheduled/len(jobs)*100:.1f}%)'
    }
    
    print(f"\n📊 BATCH RESULTS SUMMARY:")
    print(f"  Total jobs: {len(jobs)}")
    print(f"  Jobs scheduled: {total_scheduled} ({total_scheduled/len(jobs)*100:.1f}%)")
    print(f"  Successful batches: {successful_batches}/{total_batches}")
    print(f"  Total time: {total_time:.2f} seconds")
    print(f"  Average per batch: {total_time/total_batches:.3f} seconds")
    
    return all_scheduled_jobs

def test_batch_scheduler():
    """Test the batch scheduler with real data"""
    print("=== TESTING BATCH SCHEDULER IMPLEMENTATION ===")
    
    # Load data
    jobs, machines, setup = load_jobs_planning_data(max_jobs=100, planning_horizon_days=60)
    print(f"Loaded {len(jobs)} jobs for testing")
    
    # Test current system (should fail)
    print(f"\n1. CURRENT SYSTEM TEST (all jobs at once):")
    current_result = schedule_jobs(
        jobs, machines, setup,
        time_limit_seconds=60,
        planning_horizon_days=60
    )
    current_status = current_result.get('_metadata', {}).get('status')
    current_scheduled = len([k for k in current_result.keys() if k != '_metadata'])
    print(f"   Result: {current_status}, Scheduled: {current_scheduled}/{len(jobs)}")
    
    # Test batch system
    print(f"\n2. NEW BATCH SYSTEM TEST:")
    batch_result = batch_schedule_jobs(jobs, machines, setup, batch_size=5)
    batch_scheduled = batch_result.get('_metadata', {}).get('total_scheduled', 0)
    success_rate = batch_result.get('_metadata', {}).get('success_rate', 0)
    
    print(f"\n🎯 IMPROVEMENT COMPARISON:")
    print(f"  Current system: {current_scheduled}/{len(jobs)} jobs ({current_scheduled/len(jobs)*100:.1f}%)")
    print(f"  Batch system:   {batch_scheduled}/{len(jobs)} jobs ({success_rate:.1f}%)")
    improvement = batch_scheduled - current_scheduled
    print(f"  Improvement: +{improvement} jobs ({improvement/len(jobs)*100:.1f}% increase)")
    
    if batch_scheduled > current_scheduled:
        print(f"  ✅ BATCH SCHEDULER WORKS! {improvement}x better than current system")
    else:
        print(f"  ❌ Batch scheduler needs tuning")
    
    return batch_result

if __name__ == "__main__":
    test_batch_scheduler()