#!/usr/bin/env python3
"""
debug_deep_dive.py - CP-SAT Solver Testing and Evaluation
Tests the CP-SAT solver with loaded job data and evaluates scheduling performance


⏺ Looking at the cache refresh error in the CP-SAT solver, I can see the issue. The code is calling time_checker._refresh_cache_if_needed() but the correct
  method is time_checker.cache.refresh_if_needed() based on the TimeAvailabilityChecker class structure.

  Let me fix this:

⏺ Update(app/scheduling/cpsat_solver.py)
  ⎿  Updated app/scheduling/cpsat_solver.py with 1 addition and 1 removal
     797           logger.info("Adding working hours constraints from ai_arrangable_hour table")
     798 
     799           # Force cache refresh
     800 -         time_checker._refresh_cache_if_needed()
     800 +         time_checker.cache.refresh_if_needed()
     801 
     802           # Get working hours for each day (1=Monday, 7=Sunday)
     803           working_hours_by_day = self._get_working_hours_by_day(time_checker)
  ⎿  Claude usage limit reached. Your limit will reset at 4am (Asia/Kuala_Lumpur).
"""

import sys
import os
from datetime import datetime
from typing import Dict, List, Any
import time

# Add the parent directory to sys.path to import from app
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.data_ingestion.mariadb_parser import load_jobs_planning_data
from app.scheduling.cpsat_solver import schedule_jobs, SchedulingConfigManager


def print_separator(title: str, char: str = "=", width: int = 80):
    """Print a formatted separator with title"""
    print(f"\n{char * width}")
    print(f"{title:^{width}}")
    print(f"{char * width}")


def print_subsection(title: str, char: str = "-", width: int = 60):
    """Print a formatted subsection header"""
    print(f"\n{char * width}")
    print(f" {title}")
    print(f"{char * width}")


def analyze_job_data(jobs: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Analyze job data before scheduling"""
    if not jobs:
        return {}
    
    analysis = {
        'total_jobs': len(jobs),
        'jobs_with_processing_time': 0,
        'jobs_without_processing_time': 0,
        'total_processing_hours': 0,
        'machine_distribution': {},
        'priority_distribution': {},
        'avg_processing_time': 0,
        'jobs_with_deadlines': 0,
        'urgent_jobs': 0,  # jobs due within 7 days
        'processing_time_distribution': {
            '0-1 hours': 0,
            '1-5 hours': 0, 
            '5-10 hours': 0,
            '10-20 hours': 0,
            '20-50 hours': 0,
            '50+ hours': 0
        },
        'processing_times_raw': []
    }
    
    current_time = datetime.now().timestamp()
    seven_days = 7 * 24 * 3600  # 7 days in seconds
    
    for job in jobs:
        # Processing time analysis
        processing_time = job.get('processing_time', 0)
        if processing_time and processing_time > 0:
            analysis['jobs_with_processing_time'] += 1
            hours = processing_time / 3600  # Convert to hours
            analysis['total_processing_hours'] += hours
            analysis['processing_times_raw'].append(hours)
            
            # Categorize processing time
            if hours <= 1:
                analysis['processing_time_distribution']['0-1 hours'] += 1
            elif hours <= 5:
                analysis['processing_time_distribution']['1-5 hours'] += 1
            elif hours <= 10:
                analysis['processing_time_distribution']['5-10 hours'] += 1
            elif hours <= 20:
                analysis['processing_time_distribution']['10-20 hours'] += 1
            elif hours <= 50:
                analysis['processing_time_distribution']['20-50 hours'] += 1
            else:
                analysis['processing_time_distribution']['50+ hours'] += 1
        else:
            analysis['jobs_without_processing_time'] += 1
        
        # Machine distribution
        machine = job.get('MachineName_v', 'Unknown')
        analysis['machine_distribution'][machine] = analysis['machine_distribution'].get(machine, 0) + 1
        
        # Priority distribution
        priority = job.get('priority', 'Unknown')
        analysis['priority_distribution'][priority] = analysis['priority_distribution'].get(priority, 0) + 1
        
        # Deadline analysis
        lcd_epoch = job.get('lcd_date_epoch')
        if lcd_epoch:
            analysis['jobs_with_deadlines'] += 1
            if lcd_epoch - current_time <= seven_days:
                analysis['urgent_jobs'] += 1
    
    # Calculate averages
    if analysis['jobs_with_processing_time'] > 0:
        analysis['avg_processing_time'] = analysis['total_processing_hours'] / analysis['jobs_with_processing_time']
    
    return analysis


def display_job_analysis(analysis: Dict[str, Any]):
    """Display job data analysis"""
    print_subsection("Job Data Analysis")
    
    print(f"Total Jobs: {analysis['total_jobs']}")
    print(f"Jobs with Processing Time: {analysis['jobs_with_processing_time']}")
    print(f"Jobs without Processing Time: {analysis['jobs_without_processing_time']}")
    print(f"Total Processing Hours: {analysis['total_processing_hours']:.1f} hours")
    print(f"Average Processing Time: {analysis['avg_processing_time']:.1f} hours")
    print(f"🚨 WARNING: {analysis['total_processing_hours']:.0f} hours = {analysis['total_processing_hours']/8:.0f} working days!")
    
    # Show distribution of processing times
    print(f"\nProcessing Time Distribution:")
    for range_str, count in analysis['processing_time_distribution'].items():
        print(f"  • {range_str}: {count} jobs")
    
    # Show some sample processing times
    if analysis['processing_times_raw']:
        raw_times = sorted(analysis['processing_times_raw'])
        print(f"\nSample Processing Times (hours):")
        print(f"  • Min: {raw_times[0]:.1f}h")
        print(f"  • Max: {raw_times[-1]:.1f}h") 
        print(f"  • Median: {raw_times[len(raw_times)//2]:.1f}h")
        print(f"  • Top 5 longest: {[f'{t:.1f}h' for t in raw_times[-5:]]}")
        
        # Show my calculation step by step
        print(f"\n🔍 MY CALCULATION BREAKDOWN:")
        print(f"  • Total jobs with processing_time: {analysis['jobs_with_processing_time']}")
        print(f"  • Sum of all processing times: {analysis['total_processing_hours']:.1f} hours")
        print(f"  • Average per job: {analysis['total_processing_hours'] / analysis['jobs_with_processing_time']:.1f} hours")
        
        # Count how many 87.5-hour jobs
        count_87_5 = sum(1 for t in raw_times if abs(t - 87.5) < 0.1)
        count_122_5 = sum(1 for t in raw_times if abs(t - 122.5) < 0.1)
        print(f"  • Jobs with exactly 87.5 hours: {count_87_5}")
        print(f"  • Jobs with exactly 122.5 hours: {count_122_5}")
        print(f"  • Contribution from 87.5h jobs: {count_87_5 * 87.5:.1f} hours")
        print(f"  • Contribution from 122.5h jobs: {count_122_5 * 122.5:.1f} hours")
        
        # Show the math
        total_from_these = (count_87_5 * 87.5) + (count_122_5 * 122.5)
        print(f"  • Total from these patterns: {total_from_these:.1f} hours")
        print(f"  • Remaining from other jobs: {analysis['total_processing_hours'] - total_from_these:.1f} hours")
    print(f"Jobs with Deadlines: {analysis['jobs_with_deadlines']}")
    print(f"Urgent Jobs (due <=7 days): {analysis['urgent_jobs']}")
    
    # Top machines
    print(f"\nTop 5 Machines by Job Count:")
    top_machines = sorted(analysis['machine_distribution'].items(), key=lambda x: x[1], reverse=True)[:5]
    for machine, count in top_machines:
        percentage = (count / analysis['total_jobs']) * 100
        print(f"  • {machine}: {count} jobs ({percentage:.1f}%)")
    
    # Priority distribution
    print(f"\nPriority Distribution:")
    for priority, count in sorted(analysis['priority_distribution'].items()):
        percentage = (count / analysis['total_jobs']) * 100
        print(f"  • Priority {priority}: {count} jobs ({percentage:.1f}%)")


def test_scheduler_config():
    """Test scheduler configuration loading"""
    print_subsection("Scheduler Configuration Test")
    
    try:
        config = SchedulingConfigManager.load_config()
        print("✅ Scheduler configuration loaded successfully")
        print(f"  • Solver Time Limit: {config.solver_time_limit_seconds}s")
        print(f"  • Max Jobs Limit: {config.max_jobs_limit}")
        print(f"  • Planning Horizon: {config.planning_horizon_days} days")
        print(f"  • Max Workers: {config.max_workers_limit}")
        print(f"  • Normal Working Hours: {config.normal_working_hours}")
        return config
    except Exception as e:
        print(f"❌ Scheduler configuration failed: {e}")
        return None


def run_scheduler_test(jobs: List[Dict[str, Any]], machines: List[Dict[str, str]], 
                      setup_times: Dict[str, Dict[str, float]], config):
    """Run the CP-SAT scheduler with loaded data"""
    print_subsection("CP-SAT Solver Test")
    
    try:
        print(f"✅ Scheduler function available")
        
        # Run scheduling
        print(f"Starting scheduling for {len(jobs)} jobs...")
        start_time = time.time()
        
        result = schedule_jobs(
            jobs=jobs,
            machines=machines,
            setup_times=setup_times,
            time_limit_seconds=60,  # Short test
            max_operators=config.max_workers_limit,
            max_jobs_limit=50,  # Small test batch
            planning_horizon_days=180  # Use your real planning horizon
        )
        
        end_time = time.time()
        solving_time = end_time - start_time
        
        print(f"Scheduling completed in {solving_time:.2f} seconds")
        
        return result, solving_time
        
    except Exception as e:
        print(f"❌ Scheduler failed: {e}")
        import traceback
        traceback.print_exc()
        return None, 0


def analyze_scheduling_result(result: Dict[str, Any], solving_time: float):
    """Analyze and display scheduling results"""
    print_subsection("Scheduling Results Analysis")
    
    if not result:
        print("❌ No scheduling result to analyze")
        return
    
    # Basic statistics
    status = result.get('status', 'Unknown')
    objective_value = result.get('objective_value', 0)
    scheduled_jobs = result.get('scheduled_jobs', [])
    unscheduled_jobs = result.get('unscheduled_jobs', [])
    
    print(f"Scheduling Status: {status}")
    print(f"Objective Value: {objective_value}")
    print(f"Scheduled Jobs: {len(scheduled_jobs)}")
    print(f"Unscheduled Jobs: {len(unscheduled_jobs)}")
    print(f"Solving Time: {solving_time:.2f} seconds")
    
    if scheduled_jobs:
        # Calculate scheduling efficiency
        total_jobs = len(scheduled_jobs) + len(unscheduled_jobs)
        efficiency = (len(scheduled_jobs) / total_jobs) * 100 if total_jobs > 0 else 0
        print(f"Scheduling Efficiency: {efficiency:.1f}%")
        
        # Analyze machine utilization
        machine_usage = {}
        total_scheduled_time = 0
        
        for job in scheduled_jobs:
            machine = job.get('machine', 'Unknown')
            duration = job.get('duration', 0)
            machine_usage[machine] = machine_usage.get(machine, 0) + duration
            total_scheduled_time += duration
        
        print(f"\nMachine Utilization (Top 5):")
        top_machines = sorted(machine_usage.items(), key=lambda x: x[1], reverse=True)[:5]
        for machine, usage_seconds in top_machines:
            usage_hours = usage_seconds / 3600
            percentage = (usage_seconds / total_scheduled_time) * 100 if total_scheduled_time > 0 else 0
            print(f"  • {machine}: {usage_hours:.1f} hours ({percentage:.1f}%)")
        
        # Timeline analysis
        if scheduled_jobs:
            start_times = [job.get('start_time', 0) for job in scheduled_jobs if job.get('start_time')]
            end_times = [job.get('end_time', 0) for job in scheduled_jobs if job.get('end_time')]
            
            if start_times and end_times:
                earliest_start = min(start_times)
                latest_end = max(end_times)
                total_span = latest_end - earliest_start
                
                print(f"\nTimeline Analysis:")
                print(f"  • Earliest Start: {datetime.fromtimestamp(earliest_start).strftime('%Y-%m-%d %H:%M')}")
                print(f"  • Latest End: {datetime.fromtimestamp(latest_end).strftime('%Y-%m-%d %H:%M')}")
                print(f"  • Total Span: {total_span / 3600:.1f} hours")
    
    # Show unscheduled jobs summary
    if unscheduled_jobs:
        print(f"\nUnscheduled Jobs Analysis:")
        print(f"  • Count: {len(unscheduled_jobs)}")
        
        # Group by reason if available
        reasons = {}
        for job in unscheduled_jobs:
            reason = job.get('reason', 'Unknown')
            reasons[reason] = reasons.get(reason, 0) + 1
        
        for reason, count in sorted(reasons.items(), key=lambda x: x[1], reverse=True):
            print(f"  • {reason}: {count} jobs")


def main():
    """Main test execution"""
    print_separator("CP-SAT Scheduler Deep Dive Test", "=", 80)
    print(f"Test started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Step 1: Load job data
    print_subsection("Loading Job Data")
    
    try:
        jobs, machines, setup_times = load_jobs_planning_data(
            max_jobs=None,  # Load all jobs
            planning_horizon_days=180
        )
        print(f"✅ Loaded {len(jobs)} jobs, {len(machines)} machines")
    except Exception as e:
        print(f"❌ Failed to load job data: {e}")
        return
    
    # Step 2: Analyze job data
    analysis = analyze_job_data(jobs)
    display_job_analysis(analysis)
    
    # Step 3: Test scheduler configuration
    config = test_scheduler_config()
    if not config:
        print("❌ Cannot proceed without valid configuration")
        return
    
    # Step 4: Run scheduler
    result, solving_time = run_scheduler_test(jobs, machines, setup_times, config)
    
    # Step 5: Analyze results
    if result:
        analyze_scheduling_result(result, solving_time)
    
    # Summary
    print_separator("Test Summary", "=", 80)
    print("✅ CP-SAT Scheduler deep dive test completed!")
    
    if result:
        scheduled_count = len(result.get('scheduled_jobs', []))
        total_count = len(jobs)
        efficiency = (scheduled_count / total_count) * 100 if total_count > 0 else 0
        
        print(f"\nFinal Results:")
        print(f"  • Total Jobs: {total_count}")
        print(f"  • Scheduled: {scheduled_count}")
        print(f"  • Efficiency: {efficiency:.1f}%")
        print(f"  • Solving Time: {solving_time:.2f}s")
        print(f"  • Status: {result.get('status', 'Unknown')}")


if __name__ == "__main__":
    main()