#!/usr/bin/env python3
"""
Test script for the new rolling window data loading strategy.
Tests the production-schedule endpoint with different parameters.
"""

import requests
import json
from datetime import datetime

def test_production_schedule_endpoint():
    """Test the production schedule endpoint with rolling window parameters."""
    base_url = "http://localhost:8000/production-jobs"
    
    # Test cases with different buffer_days and planning_horizon_days
    test_cases = [
        {
            "name": "Default parameters",
            "params": {}
        },
        {
            "name": "Short horizon (3 weeks)",
            "params": {"buffer_days": 5, "planning_horizon_days": 21}
        },
        {
            "name": "Long horizon (12 weeks)", 
            "params": {"buffer_days": 10, "planning_horizon_days": 84}
        },
        {
            "name": "Minimal buffer",
            "params": {"buffer_days": 1, "planning_horizon_days": 30}
        }
    ]
    
    print("Testing Rolling Window Data Loading Strategy")
    print("=" * 50)
    
    for test_case in test_cases:
        print(f"\n{test_case['name']}:")
        print(f"Parameters: {test_case['params']}")
        
        try:
            response = requests.get(
                f"{base_url}/production-schedule",
                params=test_case['params'],
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                print(f"✓ Success - Retrieved {data['total_items']} jobs")
                print(f"  Pages: {data['total_pages']}, Current page: {data['page']}")
                
                if 'data_loading_config' in data:
                    config = data['data_loading_config']
                    print(f"  Data range: {config['date_range']['start_date']} to {config['date_range']['end_date']}")
                    
            else:
                print(f"✗ Error {response.status_code}: {response.text}")
                
        except Exception as e:
            print(f"✗ Exception: {e}")

def test_data_loading_stats():
    """Test the new data loading statistics endpoint."""
    print("\n" + "=" * 50)
    print("Testing Data Loading Statistics Endpoint")
    print("=" * 50)
    
    try:
        response = requests.get(
            "http://localhost:8000/production-jobs/data-loading-stats",
            timeout=10
        )
        
        if response.status_code == 200:
            data = response.json()
            print("✓ Statistics retrieved successfully")
            
            stats = data['statistics']
            print(f"  Total jobs: {stats['total_jobs']}")
            print(f"  Active jobs: {stats['active_jobs']}")
            print(f"  Overdue jobs: {stats['overdue_jobs']}")
            print(f"  Average lead time: {stats['avg_lead_time_days']} days")
            
            recommendations = data['recommendations']
            print(f"\nRecommendations:")
            print(f"  Buffer days: {recommendations['buffer_days']}")
            print(f"  Planning horizon: {recommendations['planning_horizon_days']} days")
            print(f"  Buffer logic: {recommendations['reasoning']['buffer_logic']}")
            print(f"  Horizon logic: {recommendations['reasoning']['horizon_logic']}")
            
            optimization = data['or_tools_optimization']
            print(f"\nOR-Tools Optimization:")
            print(f"  Estimated variables: {optimization['estimated_variables']}")
            print(f"  Performance level: {optimization['performance_level']}")
            print(f"  Solver time estimate: {optimization['solver_time_estimate']}")
            
            if data['warnings']:
                print(f"\nWarnings:")
                for warning in data['warnings']:
                    print(f"  ⚠️  {warning}")
        else:
            print(f"✗ Error {response.status_code}: {response.text}")
            
    except Exception as e:
        print(f"✗ Exception: {e}")

if __name__ == "__main__":
    print(f"Starting tests at {datetime.now()}")
    
    # Test the main production schedule endpoint
    test_production_schedule_endpoint()
    
    # Test the statistics endpoint
    test_data_loading_stats()
    
    print(f"\nTests completed at {datetime.now()}") 