#!/usr/bin/env python3
"""
Comprehensive Scheduling Debugger
Analyzes why 345+ jobs remain unscheduled by testing both CP-SAT and Greedy solvers
"""

import sys
import os
import logging
import time
import json
from collections import defaultdict, Counter
from datetime import datetime, timedelta

# Add the backend directory to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

# Import scheduling components
from app.scheduling.cpsat_solver import schedule_jobs as cpsat_schedule_jobs
from app.scheduling.greedy_solver import greedy_schedule
from app.scheduling.scheduler_utils import extract_job_family, extract_process_number
from app.core.orchestrator import SchedulingOrchestrator

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('comprehensive_debug.log')
    ]
)
logger = logging.getLogger(__name__)

class SchedulingDebugger:
    """Comprehensive scheduler debugging and analysis tool."""
    
    def __init__(self):
        self.orchestrator = SchedulingOrchestrator()
        
    def run_comprehensive_analysis(self):
        """Run complete debugging analysis comparing both solvers."""
        print("=" * 80)
        print("COMPREHENSIVE SCHEDULING DEBUGGER")
        print("=" * 80)
        
        # Load data
        print("\n1. Loading scheduling data...")
        jobs_data, machines_data = self._load_data()
        if not jobs_data:
            print("ERROR: No jobs data loaded")
            return
        
        print(f"   Loaded {len(jobs_data)} jobs and {len(machines_data)} machines")
        
        # Analyze data patterns
        print("\n2. Analyzing data patterns...")
        self._analyze_data_patterns(jobs_data, machines_data)
        
        # Test CP-SAT solver
        print("\n3. Testing CP-SAT solver...")
        cpsat_results = self._test_cpsat_solver(jobs_data, machines_data)
        
        # Test Greedy solver
        print("\n4. Testing Greedy solver...")
        greedy_results = self._test_greedy_solver(jobs_data, machines_data)
        
        # Compare results
        print("\n5. Comparing solver results...")
        self._compare_solver_results(cpsat_results, greedy_results, jobs_data)
        
        # Analyze constraint conflicts
        print("\n6. Analyzing constraint conflicts...")
        self._analyze_constraint_conflicts(jobs_data, machines_data)
        
        # Generate recommendations
        print("\n7. Generating recommendations...")
        self._generate_recommendations(cpsat_results, greedy_results, jobs_data)
        
    def _load_data(self):
        """Load jobs and machine data."""
        try:
            # Use orchestrator to load data
            self.orchestrator.load_data()
            jobs_data = self.orchestrator.jobs_data
            machines_data = self.orchestrator.machines_data
            return jobs_data, machines_data
        except Exception as e:
            logger.error(f"Failed to load data: {e}")
            return [], []
    
    def _analyze_data_patterns(self, jobs_data, machines_data):
        """Analyze patterns in the data that might cause scheduling issues."""
        print("   Data Pattern Analysis:")
        
        # Job family analysis
        families = defaultdict(list)
        process_counts = Counter()
        machine_assignments = Counter()
        duration_ranges = Counter()
        
        for job in jobs_data:
            job_id = job.get('job', job.get('job_id', ''))
            family = extract_job_family(job_id)
            process_num = extract_process_number(job_id)
            
            families[family].append(process_num)
            process_counts[process_num] += 1
            
            machine = job.get('MachineName_v', 'UNKNOWN')
            machine_assignments[machine] += 1
            
            # Duration analysis
            duration = job.get('processing_time', 0) / 3600  # Convert to hours
            if duration <= 8:
                duration_ranges['≤8h'] += 1
            elif duration <= 24:
                duration_ranges['8-24h'] += 1
            elif duration <= 80:
                duration_ranges['24-80h'] += 1
            else:
                duration_ranges['>80h'] += 1
        
        print(f"   → Job families: {len(families)}")
        print(f"   → Process distribution: {dict(process_counts.most_common())}")
        print(f"   → Top machines: {dict(machine_assignments.most_common(5))}")
        print(f"   → Duration distribution: {dict(duration_ranges)}")
        
        # Check for broken sequences
        broken_sequences = 0
        incomplete_families = 0
        for family, processes in families.items():
            processes.sort()
            expected_processes = list(range(1, max(processes) + 1))
            if processes != expected_processes:
                broken_sequences += 1
                print(f"   ⚠️  Broken sequence in {family}: has {processes}, expected {expected_processes}")
            
            if len(processes) < 2:
                incomplete_families += 1
        
        print(f"   → Broken sequences: {broken_sequences}/{len(families)} families")
        print(f"   → Single-process families: {incomplete_families}/{len(families)} families")
        
    def _test_cpsat_solver(self, jobs_data, machines_data):
        """Test CP-SAT solver performance."""
        print("   Testing CP-SAT solver...")
        
        start_time = time.time()
        try:
            result = self.orchestrator.run_cpsat_scheduler()
            solve_time = time.time() - start_time
            
            if result and 'schedule' in result:
                scheduled_count = len(result['schedule'])
                unscheduled_count = len(jobs_data) - scheduled_count
                status = result.get('status', 'UNKNOWN')
                
                print(f"   → Status: {status}")
                print(f"   → Solve time: {solve_time:.2f}s")
                print(f"   → Scheduled: {scheduled_count}/{len(jobs_data)} jobs")
                print(f"   → Unscheduled: {unscheduled_count} jobs")
                
                return {
                    'status': status,
                    'solve_time': solve_time,
                    'scheduled': scheduled_count,
                    'unscheduled': unscheduled_count,
                    'schedule': result['schedule'],
                    'success': status == 'OPTIMAL' or status == 'FEASIBLE'
                }
            else:
                print(f"   → Status: FAILED")
                print(f"   → Solve time: {solve_time:.2f}s")
                print(f"   → Error: No schedule returned")
                
                return {
                    'status': 'FAILED',
                    'solve_time': solve_time,
                    'scheduled': 0,
                    'unscheduled': len(jobs_data),
                    'schedule': [],
                    'success': False
                }
                
        except Exception as e:
            solve_time = time.time() - start_time
            print(f"   → Status: ERROR")
            print(f"   → Solve time: {solve_time:.2f}s")
            print(f"   → Error: {str(e)}")
            
            return {
                'status': 'ERROR',
                'solve_time': solve_time,
                'scheduled': 0,
                'unscheduled': len(jobs_data),
                'schedule': [],
                'success': False,
                'error': str(e)
            }
    
    def _test_greedy_solver(self, jobs_data, machines_data):
        """Test Greedy solver performance."""
        print("   Testing Greedy solver...")
        
        start_time = time.time()
        try:
            result = self.orchestrator.run_greedy_scheduler()
            solve_time = time.time() - start_time
            
            if result and 'schedule' in result:
                scheduled_count = len(result['schedule'])
                unscheduled_count = len(jobs_data) - scheduled_count
                
                print(f"   → Status: COMPLETED")
                print(f"   → Solve time: {solve_time:.2f}s")
                print(f"   → Scheduled: {scheduled_count}/{len(jobs_data)} jobs")
                print(f"   → Unscheduled: {unscheduled_count} jobs")
                
                return {
                    'status': 'COMPLETED',
                    'solve_time': solve_time,
                    'scheduled': scheduled_count,
                    'unscheduled': unscheduled_count,
                    'schedule': result['schedule'],
                    'success': True
                }
            else:
                print(f"   → Status: FAILED")
                print(f"   → Solve time: {solve_time:.2f}s")
                print(f"   → Error: No schedule returned")
                
                return {
                    'status': 'FAILED',
                    'solve_time': solve_time,
                    'scheduled': 0,
                    'unscheduled': len(jobs_data),
                    'schedule': [],
                    'success': False
                }
                
        except Exception as e:
            solve_time = time.time() - start_time
            print(f"   → Status: ERROR")
            print(f"   → Solve time: {solve_time:.2f}s")
            print(f"   → Error: {str(e)}")
            
            return {
                'status': 'ERROR',
                'solve_time': solve_time,
                'scheduled': 0,
                'unscheduled': len(jobs_data),
                'schedule': [],
                'success': False,
                'error': str(e)
            }
    
    def _compare_solver_results(self, cpsat_results, greedy_results, jobs_data):
        """Compare results from both solvers."""
        print("   Solver Comparison:")
        
        total_jobs = len(jobs_data)
        
        print(f"   → Total Jobs: {total_jobs}")
        print(f"   → CP-SAT:  {cpsat_results['scheduled']:3d} scheduled, {cpsat_results['unscheduled']:3d} unscheduled ({cpsat_results['scheduled']/total_jobs*100:.1f}% success)")
        print(f"   → Greedy: {greedy_results['scheduled']:3d} scheduled, {greedy_results['unscheduled']:3d} unscheduled ({greedy_results['scheduled']/total_jobs*100:.1f}% success)")
        
        # Performance comparison
        print(f"   → CP-SAT solve time:  {cpsat_results['solve_time']:.2f}s")
        print(f"   → Greedy solve time: {greedy_results['solve_time']:.2f}s")
        print(f"   → Speed ratio: {cpsat_results['solve_time']/greedy_results['solve_time']:.1f}x (CP-SAT vs Greedy)")
        
        # Success rate comparison
        if greedy_results['success'] and not cpsat_results['success']:
            print("   ⚠️  CP-SAT failed but Greedy succeeded - CP-SAT constraints too strict")
        elif cpsat_results['success'] and not greedy_results['success']:
            print("   ✅ CP-SAT succeeded but Greedy failed - CP-SAT found optimal solution")
        elif cpsat_results['success'] and greedy_results['success']:
            if cpsat_results['scheduled'] > greedy_results['scheduled']:
                print("   ✅ CP-SAT scheduled more jobs - CP-SAT found better solution")
            elif greedy_results['scheduled'] > cpsat_results['scheduled']:
                print("   ⚠️  Greedy scheduled more jobs - CP-SAT constraints may be too strict")
            else:
                print("   ✅ Both solvers scheduled same number of jobs")
        else:
            print("   ❌ Both solvers failed - system-level problem")
    
    def _analyze_constraint_conflicts(self, jobs_data, machines_data):
        """Analyze specific constraint conflicts."""
        print("   Constraint Conflict Analysis:")
        
        # Machine compatibility issues
        machine_names = {m.get('MachineName_v', m.get('name', '')) for m in machines_data}
        unassigned_machines = 0
        unknown_machines = 0
        
        for job in jobs_data:
            machine = job.get('MachineName_v', '')
            if not machine or machine == 'NOT_ASSIGN':
                unassigned_machines += 1
            elif machine not in machine_names:
                unknown_machines += 1
        
        print(f"   → Unassigned machines: {unassigned_machines} jobs")
        print(f"   → Unknown machines: {unknown_machines} jobs")
        
        # Duration vs working hours conflicts
        long_duration_jobs = 0
        very_long_duration_jobs = 0
        
        for job in jobs_data:
            duration_hours = job.get('processing_time', 0) / 3600
            if duration_hours > 80:  # More than 10 working days
                very_long_duration_jobs += 1
            elif duration_hours > 40:  # More than 5 working days
                long_duration_jobs += 1
        
        print(f"   → Long duration jobs (40-80h): {long_duration_jobs}")
        print(f"   → Very long duration jobs (>80h): {very_long_duration_jobs}")
        
        # START_DATE conflicts
        start_date_jobs = 0
        start_date_conflicts = defaultdict(list)
        
        for job in jobs_data:
            if job.get('START_DATE_EPOCH'):
                start_date_jobs += 1
                machine = job.get('MachineName_v', '')
                start_time = job.get('START_DATE_EPOCH')
                process_num = extract_process_number(job.get('job', ''))
                
                if process_num == 1:  # P01 jobs with fixed start dates
                    start_date_conflicts[f"{machine}_{start_time}"].append(job.get('job', ''))
        
        print(f"   → Jobs with START_DATE: {start_date_jobs}")
        
        conflicts = sum(1 for jobs in start_date_conflicts.values() if len(jobs) > 1)
        print(f"   → START_DATE conflicts: {conflicts} machine-time slots with multiple P01 jobs")
        
    def _generate_recommendations(self, cpsat_results, greedy_results, jobs_data):
        """Generate specific recommendations to improve scheduling."""
        print("   Recommendations:")
        
        total_jobs = len(jobs_data)
        
        if not cpsat_results['success'] and greedy_results['success']:
            print("   1. 🔧 RELAX CP-SAT CONSTRAINTS")
            print("      → CP-SAT is over-constrained while Greedy finds solutions")
            print("      → Change hard constraints (==) to soft constraints (>=)")
            print("      → Add constraint priorities and allow violations")
            
        elif not cpsat_results['success'] and not greedy_results['success']:
            print("   1. 🚨 SYSTEM-LEVEL PROBLEM")
            print("      → Both solvers failed - fundamental data or constraint issues")
            print("      → Check for missing machine assignments")
            print("      → Verify job dependencies and sequences")
            
        if greedy_results['unscheduled'] > total_jobs * 0.3:  # More than 30% unscheduled
            print("   2. 📊 HIGH UNSCHEDULED RATE")
            unscheduled_rate = greedy_results['unscheduled'] / total_jobs * 100
            print(f"      → {unscheduled_rate:.1f}% of jobs unscheduled")
            print("      → Review working hours vs job duration compatibility")
            print("      → Consider extending planning horizon")
            
        if cpsat_results['solve_time'] > 60:  # More than 1 minute
            print("   3. ⏱️  PERFORMANCE OPTIMIZATION")
            print(f"      → CP-SAT solve time: {cpsat_results['solve_time']:.1f}s")
            print("      → Reduce job count or simplify constraints")
            print("      → Implement time limits and heuristics")
            
        print("\n   SPECIFIC ACTIONS:")
        print("   • Run: uv run python testing/constraint_analysis_summary.py")
        print("   • Check: backend/app/config/scheduler_config.py for constraint settings")
        print("   • Review: cpsat_solver.py lines 461-552 for START_DATE constraint logic")
        print("   • Modify: Change model.Add(start_var == start_date) to model.Add(start_var >= start_date)")

def main():
    """Main entry point."""
    debugger = SchedulingDebugger()
    debugger.run_comprehensive_analysis()
    
    print("\n" + "=" * 80)
    print("DEBUG ANALYSIS COMPLETE")
    print("Check comprehensive_debug.log for detailed logs")
    print("=" * 80)

if __name__ == "__main__":
    main()