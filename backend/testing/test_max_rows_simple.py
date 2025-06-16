#!/usr/bin/env python3
"""
Simple Maximum Rows Data Loading Test
Tests loading all available data without limits
"""

import time
import os
import sys
import psutil
import gc
from datetime import datetime

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from app.data_ingestion.mariadb_parser import load_jobs_planning_data
except ImportError:
    from backend.app.data_ingestion.mariadb_parser import load_jobs_planning_data

def test_max_data_loading():
    """Test loading data with maximum limits"""
    print("🚀 Testing Maximum Data Loading Performance")
    print("=" * 60)
    
    process = psutil.Process()
    
    # Test configurations
    test_configs = [
        {"name": "Current limit (from env)", "max_jobs": None, "horizon": None},
        {"name": "10,000 jobs limit", "max_jobs": 10000, "horizon": None},
        {"name": "50,000 jobs limit", "max_jobs": 50000, "horizon": None},
        {"name": "100,000 jobs limit", "max_jobs": 100000, "horizon": None},
        {"name": "No limit, 365 days", "max_jobs": 999999, "horizon": 365},
        {"name": "No limit, 730 days", "max_jobs": 999999, "horizon": 730},
    ]
    
    results = []
    
    for config in test_configs:
        print(f"\n📊 Testing: {config['name']}")
        
        # Set environment variables
        original_max_jobs = os.getenv('MAX_JOBS_LIMIT')
        original_horizon = os.getenv('PLANNING_HORIZON_DAYS')
        
        if config['max_jobs']:
            os.environ['MAX_JOBS_LIMIT'] = str(config['max_jobs'])
        if config['horizon']:
            os.environ['PLANNING_HORIZON_DAYS'] = str(config['horizon'])
        
        # Garbage collection
        gc.collect()
        start_memory = process.memory_info().rss / 1024 / 1024
        
        # Load data
        start_time = time.time()
        try:
            jobs, machines, setup_times = load_jobs_planning_data()
            end_time = time.time()
            end_memory = process.memory_info().rss / 1024 / 1024
            
            result = {
                'config': config['name'],
                'status': 'success',
                'jobs_loaded': len(jobs),
                'machines': len(machines),
                'setup_times': len(setup_times),
                'time_seconds': end_time - start_time,
                'memory_mb': end_memory - start_memory,
                'jobs_per_second': len(jobs) / (end_time - start_time) if end_time > start_time else 0
            }
            
            print(f"   ✅ Loaded: {len(jobs):,} jobs in {result['time_seconds']:.2f}s")
            print(f"   📈 Speed: {result['jobs_per_second']:.0f} jobs/second")
            print(f"   💾 Memory: {result['memory_mb']:.1f} MB")
            
        except Exception as e:
            result = {
                'config': config['name'],
                'status': 'error',
                'error': str(e),
                'time_seconds': time.time() - start_time
            }
            print(f"   ❌ Error: {result['error']}")
        
        results.append(result)
        
        # Restore environment
        if original_max_jobs:
            os.environ['MAX_JOBS_LIMIT'] = original_max_jobs
        elif 'MAX_JOBS_LIMIT' in os.environ:
            del os.environ['MAX_JOBS_LIMIT']
            
        if original_horizon:
            os.environ['PLANNING_HORIZON_DAYS'] = original_horizon
        elif 'PLANNING_HORIZON_DAYS' in os.environ:
            del os.environ['PLANNING_HORIZON_DAYS']
        
        # Small delay
        time.sleep(1)
    
    # Print summary
    print("\n" + "=" * 60)
    print("SUMMARY REPORT")
    print("=" * 60)
    
    print("\n| Configuration | Jobs | Time (s) | Memory (MB) | Speed (jobs/s) | Status |")
    print("|---------------|------|----------|-------------|----------------|--------|")
    
    for r in results:
        if r['status'] == 'success':
            print(f"| {r['config']:13} | {r['jobs_loaded']:4} | {r['time_seconds']:8.2f} | {r['memory_mb']:11.1f} | {r['jobs_per_second']:14.0f} | ✅ |")
        else:
            print(f"| {r['config']:13} | -    | {r['time_seconds']:8.2f} | -           | -              | ❌ |")
    
    # Find maximum
    successful_results = [r for r in results if r['status'] == 'success']
    if successful_results:
        max_result = max(successful_results, key=lambda x: x['jobs_loaded'])
        print(f"\n🏆 Maximum Jobs Loaded: {max_result['jobs_loaded']:,} ({max_result['config']})")
        
        # Calculate efficiency
        if max_result['jobs_loaded'] > 0:
            mb_per_1k = (max_result['memory_mb'] / max_result['jobs_loaded']) * 1000
            print(f"💾 Memory Efficiency: {mb_per_1k:.2f} MB per 1,000 jobs")
    
    print("\n✅ Test completed!")

if __name__ == "__main__":
    test_max_data_loading()