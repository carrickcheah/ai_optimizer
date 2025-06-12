#!/usr/bin/env python3
"""
Final comprehensive analysis of why JOST25050207_CP08-560-1/2 cannot find slots in full dataset.
"""

import os
import sys
import logging
import time
from datetime import datetime, timedelta
from collections import defaultdict

# Add the project root to the Python path
sys.path.append('/Users/carrickcheah/Project/ai_optimizer/backend')

# Set up logging
logging.basicConfig(
    level=logging.WARNING,  # Reduce noise
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def final_scheduling_analysis():
    """Final comprehensive analysis of scheduling issues."""
    print("🔬 FINAL SCHEDULING ANALYSIS")
    print("=" * 80)
    
    try:
        # Import required modules
        from app.data_ingestion.mariadb_parser import load_jobs_planning_data
        from app.scheduling.greedy_solver import greedy_schedule, GreedyConfigManager
        from app.scheduling.scheduler_utils import extract_job_family, extract_process_number
        from app.utils.time_utils import epoch_to_datetime, format_datetime_for_display
        
        print("✅ Successfully imported required modules")
        
        # Load configuration and data
        config = GreedyConfigManager.load_config()
        jobs, machines, setup_times = load_jobs_planning_data()
        
        target_job_id = "JOST25050207_CP08-560-1/2"
        target_job = None
        
        for job in jobs:
            if job.get('job_id') == target_job_id:
                target_job = job
                break
        
        print(f"\n🎯 TARGET JOB ANALYSIS: {target_job_id}")
        print("=" * 50)
        
        if target_job:
            required_machine = target_job.get('MachineName_v')
            processing_time = target_job.get('processing_time', 8100.0)
            
            print(f"Required machine: {required_machine}")
            print(f"Processing time: {processing_time/3600:.2f} hours")
            print(f"Priority: {target_job.get('priority', 3)}")
            
            # Analyze machine loading
            machine_jobs = []
            for job in jobs:
                if job.get('MachineName_v') == required_machine:
                    machine_jobs.append(job)
            
            print(f"Total jobs requiring {required_machine}: {len(machine_jobs)}")
            
            # Calculate total processing time for this machine
            total_processing_hours = sum(
                job.get('processing_time', 0) for job in machine_jobs
            ) / 3600
            
            print(f"Total processing hours for {required_machine}: {total_processing_hours:.1f} hours")
            print(f"Total processing days (17.5h/day): {total_processing_hours/17.5:.1f} days")
            
            # Analyze overdue vs future jobs
            current_time = time.time()
            overdue_jobs = []
            future_jobs = []
            
            for job in machine_jobs:
                lcd_date = job.get('lcd_date_epoch')
                if lcd_date and lcd_date < current_time:
                    overdue_jobs.append(job)
                else:
                    future_jobs.append(job)
            
            print(f"Overdue jobs on {required_machine}: {len(overdue_jobs)}")
            print(f"Future jobs on {required_machine}: {len(future_jobs)}")
            
            if overdue_jobs:
                overdue_hours = sum(job.get('processing_time', 0) for job in overdue_jobs) / 3600
                print(f"Overdue processing time: {overdue_hours:.1f} hours ({overdue_hours/17.5:.1f} days)")
        
        print(f"\n🏭 MACHINE CAPACITY ANALYSIS")
        print("=" * 50)
        
        # Extract machine names
        if machines and isinstance(machines[0], dict):
            machine_names = [m.get('MachineName_v', str(m)) for m in machines if m.get('MachineName_v')]
        else:
            machine_names = machines
        
        # Analyze machine loading across all machines
        machine_loading = defaultdict(list)
        machine_hours = defaultdict(float)
        
        for job in jobs:
            machine = job.get('MachineName_v')
            if machine and machine != 'NOT_ASSIGN':
                machine_loading[machine].append(job)
                machine_hours[machine] += job.get('processing_time', 0) / 3600
        
        # Sort machines by loading
        sorted_machines = sorted(machine_hours.items(), key=lambda x: x[1], reverse=True)
        
        print("Top 10 most loaded machines:")
        for machine, hours in sorted_machines[:10]:
            job_count = len(machine_loading[machine])
            days = hours / 17.5
            print(f"  {machine}: {job_count} jobs, {hours:.1f} hours ({days:.1f} days)")
        
        print(f"\n🔄 SCHEDULING SEQUENCE ANALYSIS")
        print("=" * 50)
        
        # Analyze CP08 job dependencies
        cp08_families = defaultdict(list)
        for job in jobs:
            family = extract_job_family(job.get('job_id', ''))
            if 'CP08' in family:
                process_num = extract_process_number(job.get('job_id', ''))
                cp08_families[family].append((process_num, job))
        
        print(f"CP08 families found: {len(cp08_families)}")
        
        dependency_blocked = 0
        for family, family_jobs in cp08_families.items():
            family_jobs.sort(key=lambda x: x[0])  # Sort by process number
            
            # Check if we have all process steps
            process_numbers = [pn for pn, _ in family_jobs]
            max_process = max(process_numbers) if process_numbers else 0
            
            if max_process > 1:
                missing_processes = []
                for i in range(1, max_process):
                    if i not in process_numbers:
                        missing_processes.append(i)
                
                if missing_processes:
                    dependency_blocked += len([pn for pn, _ in family_jobs if pn > min(missing_processes)])
        
        print(f"Jobs potentially blocked by dependencies: {dependency_blocked}")
        
        print(f"\n🔍 ROOT CAUSE ANALYSIS")
        print("=" * 50)
        
        print("Based on analysis, job JOST25050207_CP08-560-1/2 cannot find slots due to:")
        print()
        print("1. 🏭 MACHINE CAPACITY BOTTLENECK:")
        print(f"   - Machine {required_machine} is heavily loaded")
        print(f"   - Total demand: {total_processing_hours:.1f} hours ({total_processing_hours/17.5:.1f} days)")
        print(f"   - Current search limit: {config.scheduler_search_days} days")
        print(f"   - If machine is overbooked, jobs cannot find free slots")
        print()
        
        print("2. 🔄 SCHEDULING ORDER PRIORITY:")
        print("   - Jobs are scheduled by priority (lower number = higher priority)")
        print(f"   - Target job priority: {target_job.get('priority', 3) if target_job else 'Unknown'}")
        print("   - Higher priority jobs may consume all available machine time")
        print()
        
        print("3. ⏰ DEADLINE CONSTRAINTS:")
        print(f"   - {len(overdue_jobs)} overdue jobs on the same machine")
        print("   - Overdue jobs get priority and extended grace periods")
        print("   - This can push lower priority jobs beyond search horizon")
        print()
        
        print("4. 🔗 PROCESS DEPENDENCIES:")
        print(f"   - {dependency_blocked} jobs potentially blocked by missing dependencies")
        print("   - Sequential processes must wait for previous steps")
        print("   - This creates cascading delays")
        print()
        
        print("📊 VERIFICATION:")
        print("=" * 30)
        print("Test scheduling with reduced dataset to confirm...")
        
        # Test with just target machine jobs
        machine_only_jobs = [job for job in jobs if job.get('MachineName_v') == required_machine]
        machine_only_machines = [required_machine, 'Subcon']
        
        try:
            start_time = time.time()
            result = greedy_schedule(machine_only_jobs, machine_only_machines, {}, 
                                   enforce_sequence=True, max_operators=0)
            elapsed = time.time() - start_time
            
            scheduled_count = sum(len(tasks) for tasks in result.values())
            success_rate = (scheduled_count / len(machine_only_jobs)) * 100
            
            target_scheduled = any(
                task[0] == target_job_id 
                for tasks in result.values() 
                for task in tasks
            )
            
            print(f"✅ Machine-only test completed in {elapsed:.2f}s")
            print(f"   Jobs for {required_machine}: {len(machine_only_jobs)}")
            print(f"   Successfully scheduled: {scheduled_count} ({success_rate:.1f}%)")
            print(f"   Target job scheduled: {'✅ YES' if target_scheduled else '❌ NO'}")
            
            if not target_scheduled:
                print(f"   ⚠️  Even with isolated machine, target job cannot be scheduled!")
                print(f"   This confirms machine capacity or constraint issues.")
            
        except Exception as e:
            print(f"❌ Machine-only test failed: {e}")
        
        print(f"\n💡 RECOMMENDATIONS:")
        print("=" * 30)
        print("1. Increase SCHEDULER_SEARCH_DAYS beyond current", config.scheduler_search_days, "days")
        print("2. Review machine capacity planning for bottleneck machines")
        print("3. Consider alternative machines for flexible jobs")
        print("4. Optimize job priorities to balance workload")
        print("5. Review deadline constraints for overdue jobs")
        print("6. Consider parallel processing where dependencies allow")
        
    except Exception as e:
        print(f"❌ Error during final analysis: {e}")
        logger.exception("Final analysis error details:")

if __name__ == "__main__":
    final_scheduling_analysis()