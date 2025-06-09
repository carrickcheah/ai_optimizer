#!/usr/bin/env python3
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.core.orchestrator import SchedulingOrchestrator

def test_cpsat_directly():
    print("=== DIRECT CP-SAT TEST WITH FLEXIBLE CONSTRAINTS ===")
    
    orchestrator = SchedulingOrchestrator()
    
    # Test CP-SAT solver directly
    result = orchestrator.schedule_jobs(
        solver="cpsat",
        time_limit=60,
        enforce_sequence=True,
        enforce_deadlines=True
    )
    
    print(f"\n=== CP-SAT RESULTS ===")
    print(f"Status: {result.get('status', 'Unknown')}")
    
    if 'stats' in result:
        stats = result['stats']
        print(f"Total jobs: {stats.get('total_jobs', 'Unknown')}")
        print(f"Scheduled: {stats.get('scheduled_jobs', 'Unknown')}")
        print(f"Unscheduled: {stats.get('unscheduled_jobs', 'Unknown')}")
        
        scheduled = stats.get('scheduled_jobs', 0)
        total = stats.get('total_jobs', 1)
        success_rate = (scheduled / total) * 100 if total > 0 else 0
        print(f"Success rate: {success_rate:.1f}%")
    
    # Check if problem was declared INFEASIBLE
    if 'solver_result' in result:
        solver_status = result['solver_result']
        print(f"Solver status: {solver_status}")
        
        if solver_status == "INFEASIBLE":
            print("❌ PROBLEM STILL INFEASIBLE - flexible constraints didn't help")
        elif solver_status in ["OPTIMAL", "FEASIBLE"]:
            print("✅ PROBLEM NOW SOLVABLE - flexible constraints worked!")
    
    return result

if __name__ == "__main__":
    test_cpsat_directly() 