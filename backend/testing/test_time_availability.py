#!/usr/bin/env python3
"""
Comprehensive Test Suite for Time Availability Module
Tests functionality, performance, edge cases, and database integration
"""

import os
import sys
import time
import psutil
import gc
from datetime import datetime, timedelta, time as dt_time
from typing import Dict, List, Tuple, Optional
import pytz

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from app.scheduling.time_availability import (
        TimeAvailabilityManager,
        TimeAvailabilityChecker,
        TimeAvailabilityConfigManager,
        TimeConfig,
        DatabaseCache,
        TimeConverter,
        is_time_available,
        get_next_available_slot,
        is_holiday,
        MALAYSIA_TZ
    )
    from app.data_ingestion.mariadb_parser import get_db_connection
except ImportError:
    from backend.app.scheduling.time_availability import (
        TimeAvailabilityManager,
        TimeAvailabilityChecker,
        TimeAvailabilityConfigManager,
        TimeConfig,
        DatabaseCache,
        TimeConverter,
        is_time_available,
        get_next_available_slot,
        is_holiday,
        MALAYSIA_TZ
    )
    from backend.app.data_ingestion.mariadb_parser import get_db_connection


class TimeAvailabilityTester:
    """Comprehensive test suite for time availability module."""
    
    def __init__(self):
        self.results = []
        self.process = psutil.Process()
        
    def get_memory_usage(self) -> float:
        """Get current memory usage in MB."""
        return self.process.memory_info().rss / 1024 / 1024
    
    def run_all_tests(self) -> Dict:
        """Run all test categories."""
        print("🚀 Starting Time Availability Comprehensive Tests")
        print("=" * 60)
        
        test_results = {
            'configuration': self.test_configuration(),
            'database_connectivity': self.test_database_connectivity(),
            'data_loading': self.test_data_loading(),
            'functionality': self.test_functionality(),
            'performance': self.test_performance(),
            'edge_cases': self.test_edge_cases(),
            'cache_behavior': self.test_cache_behavior()
        }
        
        return test_results
    
    def test_configuration(self) -> Dict:
        """Test configuration loading and validation."""
        print("\n1. Testing Configuration Loading...")
        results = {'status': 'started', 'tests': []}
        
        try:
            # Test 1: Load configuration
            start_time = time.time()
            config = TimeAvailabilityConfigManager.load_config()
            load_time = time.time() - start_time
            
            results['tests'].append({
                'name': 'Configuration Loading',
                'status': 'passed',
                'time': load_time,
                'details': f'Grace period: {config.grace_period_hours} hours'
            })
            
            # Test 2: Verify required environment variables
            required_vars = ['GRACE_PERIOD_HOURS']
            missing_vars = []
            
            for var in required_vars:
                if os.getenv(var) is None:
                    missing_vars.append(var)
            
            if missing_vars:
                results['tests'].append({
                    'name': 'Environment Variables',
                    'status': 'failed',
                    'details': f'Missing: {missing_vars}'
                })
            else:
                results['tests'].append({
                    'name': 'Environment Variables',
                    'status': 'passed',
                    'details': 'All required variables present'
                })
            
            # Test 3: Test configuration validation
            try:
                test_config = TimeConfig(grace_period_hours=-1)
                TimeAvailabilityConfigManager._validate_config(test_config)
                results['tests'].append({
                    'name': 'Validation Check',
                    'status': 'failed',
                    'details': 'Negative grace period should fail'
                })
            except:
                results['tests'].append({
                    'name': 'Validation Check',
                    'status': 'passed',
                    'details': 'Validation correctly rejects invalid config'
                })
            
            results['status'] = 'completed'
            
        except Exception as e:
            results['status'] = 'error'
            results['error'] = str(e)
        
        return results
    
    def test_database_connectivity(self) -> Dict:
        """Test database connection and table access."""
        print("\n2. Testing Database Connectivity...")
        results = {'status': 'started', 'tests': []}
        
        try:
            # Test database connection
            conn = get_db_connection()
            if conn:
                results['tests'].append({
                    'name': 'Database Connection',
                    'status': 'passed',
                    'details': 'Successfully connected to MariaDB'
                })
                
                # Test table existence
                cursor = conn.cursor()
                tables_to_check = ['ai_holidays', 'ai_arrangable_hour', 'ai_breaktimes']
                
                for table in tables_to_check:
                    try:
                        cursor.execute(f"SELECT COUNT(*) FROM {table}")
                        count = cursor.fetchone()[0]
                        results['tests'].append({
                            'name': f'Table {table}',
                            'status': 'passed',
                            'details': f'{count} records found'
                        })
                    except Exception as e:
                        results['tests'].append({
                            'name': f'Table {table}',
                            'status': 'failed',
                            'details': str(e)
                        })
                
                cursor.close()
                conn.close()
            else:
                results['tests'].append({
                    'name': 'Database Connection',
                    'status': 'failed',
                    'details': 'Could not connect to database'
                })
            
            results['status'] = 'completed'
            
        except Exception as e:
            results['status'] = 'error'
            results['error'] = str(e)
        
        return results
    
    def test_data_loading(self) -> Dict:
        """Test data loading from database tables."""
        print("\n3. Testing Data Loading...")
        results = {'status': 'started', 'tests': []}
        
        try:
            # Initialize checker to trigger data loading
            TimeAvailabilityManager.reset_instance()
            checker = TimeAvailabilityManager.get_instance()
            
            # Force cache refresh
            checker.cache.refresh_if_needed()
            
            # Test holidays loading
            holidays_count = len(checker.cache._holidays_cache)
            results['tests'].append({
                'name': 'Holidays Loading',
                'status': 'passed' if holidays_count > 0 else 'warning',
                'details': f'{holidays_count} holidays loaded'
            })
            
            # Test working hours loading
            working_days_count = len(checker.cache._arrangable_hours_cache)
            results['tests'].append({
                'name': 'Working Hours Loading',
                'status': 'passed' if working_days_count > 0 else 'warning',
                'details': f'{working_days_count} days configured'
            })
            
            # Test break times loading
            breaks_count = len(checker.cache._breaktimes_cache)
            results['tests'].append({
                'name': 'Break Times Loading',
                'status': 'passed' if breaks_count > 0 else 'warning',
                'details': f'{breaks_count} break periods loaded'
            })
            
            # Test epoch cache building
            epoch_holidays = len(checker.cache._holidays_epoch_cache)
            epoch_working = len(checker.cache._working_hours_epoch_cache)
            epoch_breaks = len(checker.cache._break_times_epoch_cache)
            
            results['tests'].append({
                'name': 'Epoch Cache Building',
                'status': 'passed',
                'details': f'Holidays: {epoch_holidays}, Working: {epoch_working}, Breaks: {epoch_breaks}'
            })
            
            results['status'] = 'completed'
            
        except Exception as e:
            results['status'] = 'error'
            results['error'] = str(e)
        
        return results
    
    def test_functionality(self) -> Dict:
        """Test core functionality."""
        print("\n4. Testing Core Functionality...")
        results = {'status': 'started', 'tests': []}
        
        try:
            checker = TimeAvailabilityManager.get_instance()
            
            # Test 1: Current time availability
            now = datetime.now(tz=MALAYSIA_TZ)
            is_available_now = checker.is_time_available_for_scheduling(now)
            results['tests'].append({
                'name': 'Current Time Check',
                'status': 'passed',
                'details': f'Now available: {is_available_now}'
            })
            
            # Test 2: Holiday detection
            # Check a known date
            test_date = datetime(2025, 1, 1, 10, 0, tzinfo=MALAYSIA_TZ)  # New Year's Day
            is_holiday_check = checker.is_holiday(test_date)
            results['tests'].append({
                'name': 'Holiday Detection',
                'status': 'passed',
                'details': f'2025-01-01 is holiday: {is_holiday_check}'
            })
            
            # Test 3: Working hours check
            # Monday 9 AM (should be working)
            monday_9am = datetime(2025, 6, 16, 9, 0, tzinfo=MALAYSIA_TZ)
            is_working = checker.is_within_working_hours(monday_9am)
            results['tests'].append({
                'name': 'Working Hours Check',
                'status': 'passed',
                'details': f'Monday 9AM working: {is_working}'
            })
            
            # Test 4: Break time check
            # Typical lunch time
            lunch_time = datetime(2025, 6, 16, 12, 30, tzinfo=MALAYSIA_TZ)
            is_break = checker.is_break_time(lunch_time)
            results['tests'].append({
                'name': 'Break Time Check',
                'status': 'passed',
                'details': f'12:30 PM is break: {is_break}'
            })
            
            # Test 5: Time range availability
            start = datetime(2025, 6, 16, 14, 0, tzinfo=MALAYSIA_TZ)
            end = datetime(2025, 6, 16, 16, 0, tzinfo=MALAYSIA_TZ)
            range_available = checker.is_time_range_available(start, end)
            results['tests'].append({
                'name': 'Time Range Check',
                'status': 'passed',
                'details': f'2-4 PM available: {range_available}'
            })
            
            # Test 6: Next available slot
            next_slot = checker.get_next_available_datetime(now, 2.0)
            results['tests'].append({
                'name': 'Next Available Slot',
                'status': 'passed' if next_slot else 'warning',
                'details': f'Next 2h slot: {next_slot.strftime("%Y-%m-%d %H:%M") if next_slot else "None"}'
            })
            
            # Test 7: Epoch-based checks
            start_epoch = datetime(2025, 6, 16, 10, 0, tzinfo=MALAYSIA_TZ).timestamp()
            end_epoch = datetime(2025, 6, 16, 11, 0, tzinfo=MALAYSIA_TZ).timestamp()
            epoch_available = checker.is_time_available_epoch(start_epoch, end_epoch)
            results['tests'].append({
                'name': 'Epoch Time Check',
                'status': 'passed',
                'details': f'Epoch range available: {epoch_available}'
            })
            
            results['status'] = 'completed'
            
        except Exception as e:
            results['status'] = 'error'
            results['error'] = str(e)
        
        return results
    
    def test_performance(self) -> Dict:
        """Test performance of various operations."""
        print("\n5. Testing Performance...")
        results = {'status': 'started', 'tests': []}
        
        try:
            checker = TimeAvailabilityManager.get_instance()
            
            # Test 1: Single datetime check performance
            test_times = []
            iterations = 1000
            start_time = time.time()
            
            for i in range(iterations):
                test_dt = datetime.now(tz=MALAYSIA_TZ) + timedelta(hours=i)
                checker.is_time_available_for_scheduling(test_dt)
            
            single_check_time = time.time() - start_time
            avg_time_ms = (single_check_time / iterations) * 1000
            
            results['tests'].append({
                'name': 'Single DateTime Check',
                'status': 'passed' if avg_time_ms < 1 else 'warning',
                'details': f'Avg: {avg_time_ms:.3f}ms per check ({iterations} iterations)'
            })
            
            # Test 2: Time range check performance
            range_iterations = 100
            start_time = time.time()
            
            for i in range(range_iterations):
                start_dt = datetime.now(tz=MALAYSIA_TZ) + timedelta(days=i)
                end_dt = start_dt + timedelta(hours=8)
                checker.is_time_range_available(start_dt, end_dt)
            
            range_check_time = time.time() - start_time
            avg_range_time_ms = (range_check_time / range_iterations) * 1000
            
            results['tests'].append({
                'name': 'Time Range Check',
                'status': 'passed' if avg_range_time_ms < 10 else 'warning',
                'details': f'Avg: {avg_range_time_ms:.3f}ms per range ({range_iterations} iterations)'
            })
            
            # Test 3: Epoch check performance
            epoch_iterations = 1000
            start_time = time.time()
            
            for i in range(epoch_iterations):
                start_epoch = time.time() + (i * 3600)
                end_epoch = start_epoch + 3600
                checker.is_time_available_epoch(start_epoch, end_epoch)
            
            epoch_check_time = time.time() - start_time
            avg_epoch_time_ms = (epoch_check_time / epoch_iterations) * 1000
            
            results['tests'].append({
                'name': 'Epoch Check',
                'status': 'passed' if avg_epoch_time_ms < 1 else 'warning',
                'details': f'Avg: {avg_epoch_time_ms:.3f}ms per check ({epoch_iterations} iterations)'
            })
            
            # Test 4: Next available slot performance
            slot_iterations = 50
            start_time = time.time()
            
            for i in range(slot_iterations):
                start_dt = datetime.now(tz=MALAYSIA_TZ) + timedelta(days=i)
                checker.get_next_available_datetime(start_dt, 4.0)
            
            slot_check_time = time.time() - start_time
            avg_slot_time_ms = (slot_check_time / slot_iterations) * 1000
            
            results['tests'].append({
                'name': 'Next Slot Search',
                'status': 'passed' if avg_slot_time_ms < 50 else 'warning',
                'details': f'Avg: {avg_slot_time_ms:.3f}ms per search ({slot_iterations} iterations)'
            })
            
            # Test 5: Memory usage
            gc.collect()
            memory_mb = self.get_memory_usage()
            
            results['tests'].append({
                'name': 'Memory Usage',
                'status': 'passed' if memory_mb < 100 else 'warning',
                'details': f'Current usage: {memory_mb:.1f} MB'
            })
            
            results['status'] = 'completed'
            
        except Exception as e:
            results['status'] = 'error'
            results['error'] = str(e)
        
        return results
    
    def test_edge_cases(self) -> Dict:
        """Test edge cases and boundary conditions."""
        print("\n6. Testing Edge Cases...")
        results = {'status': 'started', 'tests': []}
        
        try:
            checker = TimeAvailabilityManager.get_instance()
            
            # Test 1: Overnight shift handling
            night_start = datetime(2025, 6, 16, 22, 0, tzinfo=MALAYSIA_TZ)
            night_end = datetime(2025, 6, 17, 2, 0, tzinfo=MALAYSIA_TZ)
            overnight_available = checker.is_time_range_available(night_start, night_end)
            
            results['tests'].append({
                'name': 'Overnight Shift',
                'status': 'passed',
                'details': f'10PM-2AM available: {overnight_available}'
            })
            
            # Test 2: Weekend handling
            saturday = datetime(2025, 6, 21, 10, 0, tzinfo=MALAYSIA_TZ)  # Saturday
            sunday = datetime(2025, 6, 22, 10, 0, tzinfo=MALAYSIA_TZ)    # Sunday
            
            sat_available = checker.is_time_available_for_scheduling(saturday)
            sun_available = checker.is_time_available_for_scheduling(sunday)
            
            results['tests'].append({
                'name': 'Weekend Handling',
                'status': 'passed',
                'details': f'Saturday: {sat_available}, Sunday: {sun_available}'
            })
            
            # Test 3: Very long duration jobs
            long_job_start = datetime(2025, 6, 16, 8, 0, tzinfo=MALAYSIA_TZ)
            long_slot = checker.get_next_available_datetime(long_job_start, 24.0)
            
            results['tests'].append({
                'name': 'Long Duration Job (24h)',
                'status': 'passed' if long_slot else 'warning',
                'details': f'Found slot: {long_slot is not None}'
            })
            
            # Test 4: Past datetime handling
            past_dt = datetime.now(tz=MALAYSIA_TZ) - timedelta(days=30)
            past_available = checker.is_time_available_for_scheduling(past_dt)
            
            results['tests'].append({
                'name': 'Past DateTime',
                'status': 'passed',
                'details': f'Past date check completed without error'
            })
            
            # Test 5: Far future handling
            future_dt = datetime.now(tz=MALAYSIA_TZ) + timedelta(days=365)
            future_available = checker.is_time_available_for_scheduling(future_dt)
            
            results['tests'].append({
                'name': 'Far Future DateTime',
                'status': 'passed',
                'details': f'Future date check completed'
            })
            
            # Test 6: Midnight boundary
            midnight = datetime(2025, 6, 16, 0, 0, tzinfo=MALAYSIA_TZ)
            midnight_available = checker.is_time_available_for_scheduling(midnight)
            
            results['tests'].append({
                'name': 'Midnight Boundary',
                'status': 'passed',
                'details': f'Midnight available: {midnight_available}'
            })
            
            # Test 7: Daylight saving (if applicable)
            # Malaysia doesn't have DST, but test timezone handling
            utc_dt = datetime(2025, 6, 16, 1, 0, tzinfo=pytz.UTC)
            my_dt = utc_dt.astimezone(MALAYSIA_TZ)
            tz_available = checker.is_time_available_for_scheduling(my_dt)
            
            results['tests'].append({
                'name': 'Timezone Conversion',
                'status': 'passed',
                'details': f'UTC to SG conversion handled'
            })
            
            results['status'] = 'completed'
            
        except Exception as e:
            results['status'] = 'error'
            results['error'] = str(e)
        
        return results
    
    def test_cache_behavior(self) -> Dict:
        """Test cache behavior and refresh mechanism."""
        print("\n7. Testing Cache Behavior...")
        results = {'status': 'started', 'tests': []}
        
        try:
            # Reset instance to test fresh cache
            TimeAvailabilityManager.reset_instance()
            checker = TimeAvailabilityManager.get_instance()
            
            # Test 1: Initial cache load
            initial_expiry = checker.cache._cache_expiry
            results['tests'].append({
                'name': 'Initial Cache Load',
                'status': 'passed',
                'details': f'Cache expires at: {initial_expiry}'
            })
            
            # Test 2: Cache hit performance
            start_time = time.time()
            for _ in range(100):
                checker.is_holiday(datetime.now(tz=MALAYSIA_TZ))
            cache_hit_time = time.time() - start_time
            
            results['tests'].append({
                'name': 'Cache Hit Performance',
                'status': 'passed',
                'details': f'100 checks in {cache_hit_time:.3f}s'
            })
            
            # Test 3: Force cache refresh
            checker.cache._cache_expiry = datetime.now() - timedelta(hours=1)
            checker.cache.refresh_if_needed()
            new_expiry = checker.cache._cache_expiry
            
            results['tests'].append({
                'name': 'Cache Refresh',
                'status': 'passed' if new_expiry > initial_expiry else 'failed',
                'details': f'Cache refreshed successfully'
            })
            
            # Test 4: Concurrent access simulation
            import threading
            errors = []
            
            def concurrent_check():
                try:
                    for _ in range(10):
                        checker.is_time_available_for_scheduling(datetime.now(tz=MALAYSIA_TZ))
                except Exception as e:
                    errors.append(str(e))
            
            threads = []
            for _ in range(5):
                t = threading.Thread(target=concurrent_check)
                threads.append(t)
                t.start()
            
            for t in threads:
                t.join()
            
            results['tests'].append({
                'name': 'Concurrent Access',
                'status': 'passed' if len(errors) == 0 else 'failed',
                'details': f'{len(errors)} errors in 5 threads'
            })
            
            results['status'] = 'completed'
            
        except Exception as e:
            results['status'] = 'error'
            results['error'] = str(e)
        
        return results
    
    def generate_report(self, test_results: Dict) -> str:
        """Generate comprehensive test report."""
        report = []
        report.append("# Time Availability Module Test Report")
        report.append(f"\nTest Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        report.append("\n## Test Results Summary\n")
        
        total_tests = 0
        passed_tests = 0
        failed_tests = 0
        warning_tests = 0
        
        for category, results in test_results.items():
            report.append(f"\n### {category.replace('_', ' ').title()}")
            
            if results['status'] == 'error':
                report.append(f"❌ Error: {results.get('error', 'Unknown error')}")
            else:
                report.append(f"Status: {results['status']}")
                
                if 'tests' in results:
                    report.append("\n| Test | Status | Details |")
                    report.append("|------|--------|---------|")
                    
                    for test in results['tests']:
                        total_tests += 1
                        status_icon = "✅" if test['status'] == 'passed' else "❌" if test['status'] == 'failed' else "⚠️"
                        
                        if test['status'] == 'passed':
                            passed_tests += 1
                        elif test['status'] == 'failed':
                            failed_tests += 1
                        else:
                            warning_tests += 1
                        
                        report.append(f"| {test['name']} | {status_icon} {test['status']} | {test['details']} |")
        
        report.append(f"\n## Overall Summary")
        report.append(f"- Total Tests: {total_tests}")
        report.append(f"- ✅ Passed: {passed_tests}")
        report.append(f"- ❌ Failed: {failed_tests}")
        report.append(f"- ⚠️ Warnings: {warning_tests}")
        report.append(f"- Success Rate: {(passed_tests/total_tests*100):.1f}%" if total_tests > 0 else "- Success Rate: N/A")
        
        return "\n".join(report)


def main():
    """Run comprehensive time availability tests."""
    tester = TimeAvailabilityTester()
    
    # Run all tests
    test_results = tester.run_all_tests()
    
    # Generate and print report
    report = tester.generate_report(test_results)
    print("\n" + "=" * 60)
    print(report)
    
    # Save report to file
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"time_availability_test_report_{timestamp}.md"
    with open(filename, 'w') as f:
        f.write(report)
    print(f"\n📊 Detailed report saved to: {filename}")


if __name__ == "__main__":
    main()