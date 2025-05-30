#!/usr/bin/env python3
"""
Performance test script for the production schedule API.
Tests different parameter combinations to identify performance bottlenecks.
"""

import requests
import time
import json

def test_api_performance():
    base_url = "http://localhost:8000/api/production-jobs/production-schedule"
    
    test_scenarios = [
        {
            "name": "Original (60-day horizon)",
            "params": {"page_size": 50, "planning_horizon_days": 60, "buffer_days": 7}
        },
        {
            "name": "Optimized (30-day horizon)",
            "params": {"page_size": 25, "planning_horizon_days": 30, "buffer_days": 5}
        },
        {
            "name": "Short horizon (14-day horizon)",
            "params": {"page_size": 25, "planning_horizon_days": 14, "buffer_days": 3}
        },
        {
            "name": "Large page size test",
            "params": {"page_size": 100, "planning_horizon_days": 30, "buffer_days": 5}
        }
    ]
    
    print("API Performance Test Results")
    print("=" * 60)
    
    for scenario in test_scenarios:
        print(f"\nTesting: {scenario['name']}")
        print(f"Parameters: {scenario['params']}")
        
        # Warm up request
        try:
            requests.get(base_url, params=scenario['params'], timeout=2)
        except:
            pass
        
        # Measure performance over 3 requests
        times = []
        total_items = 0
        
        for i in range(3):
            try:
                start_time = time.time()
                response = requests.get(base_url, params=scenario['params'], timeout=10)
                end_time = time.time()
                
                if response.status_code == 200:
                    data = response.json()
                    times.append(end_time - start_time)
                    total_items = data.get('total_items', 0)
                else:
                    print(f"  ❌ Request {i+1} failed: {response.status_code}")
                    
            except Exception as e:
                print(f"  ❌ Request {i+1} error: {e}")
        
        if times:
            avg_time = sum(times) / len(times)
            min_time = min(times)
            max_time = max(times)
            
            print(f"  📊 Results:")
            print(f"    Total items: {total_items}")
            print(f"    Average time: {avg_time:.3f}s")
            print(f"    Min time: {min_time:.3f}s")
            print(f"    Max time: {max_time:.3f}s")
            print(f"    Items/second: {total_items/avg_time:.1f}")
            
            # Performance rating
            if avg_time < 0.5:
                rating = "🟢 Excellent"
            elif avg_time < 1.0:
                rating = "🟡 Good"
            elif avg_time < 2.0:
                rating = "🟠 Acceptable"
            else:
                rating = "🔴 Slow"
                
            print(f"    Performance: {rating}")
        else:
            print(f"  ❌ All requests failed")

def test_data_loading_stats():
    """Test the data loading statistics endpoint"""
    print(f"\n{'='*60}")
    print("Data Loading Statistics Test")
    print("=" * 60)
    
    try:
        start_time = time.time()
        response = requests.get("http://localhost:8000/api/production-jobs/data-loading-stats", timeout=10)
        end_time = time.time()
        
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Statistics retrieved in {end_time - start_time:.3f}s")
            
            stats = data.get('statistics', {})
            recommendations = data.get('recommendations', {})
            
            print(f"\n📈 Current Data Overview:")
            print(f"  Total jobs: {stats.get('total_jobs', 'N/A')}")
            print(f"  Active jobs: {stats.get('active_jobs', 'N/A')}")
            print(f"  Overdue jobs: {stats.get('overdue_jobs', 'N/A')}")
            print(f"  Avg lead time: {stats.get('avg_lead_time_days', 'N/A')} days")
            
            print(f"\n🎯 Recommendations:")
            print(f"  Buffer days: {recommendations.get('buffer_days', 'N/A')}")
            print(f"  Planning horizon: {recommendations.get('planning_horizon_days', 'N/A')} days")
            
            optimization = data.get('or_tools_optimization', {})
            print(f"\n⚙️ OR-Tools Estimates:")
            print(f"  Variables: {optimization.get('estimated_variables', 'N/A')}")
            print(f"  Performance level: {optimization.get('performance_level', 'N/A')}")
            print(f"  Solver time: {optimization.get('solver_time_estimate', 'N/A')}")
            
            warnings = data.get('warnings', [])
            if warnings:
                print(f"\n⚠️ Warnings:")
                for warning in warnings:
                    print(f"  - {warning}")
        else:
            print(f"❌ Failed: {response.status_code}")
            
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    print("Starting performance tests...")
    test_api_performance()
    test_data_loading_stats()
    print(f"\nTests completed!") 