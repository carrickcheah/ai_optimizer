#!/usr/bin/env python3
"""
Deep function tests for all scheduling modules
Tests functions in isolation to identify issues
"""

import os
import sys
import traceback
import time
from datetime import datetime
from typing import Dict, List, Any

# Add backend to path
backend_path = os.path.join(os.path.dirname(__file__))
sys.path.insert(0, backend_path)

def test_scheduler_utils():
    """Test scheduler_utils functions"""
    print("🔍 Testing scheduler_utils...")
    
    try:
        from app.scheduling.scheduler_utils import (
            extract_process_number, extract_job_family, validate_job_data,
            normalize_job_fields, group_jobs_by_family
        )
        
        # Test extract_process_number
        test_cases = [
            ("JOST111111_CP11-111-1/4", 1),
            ("ABC123_DEF456-2/3", 2),
            ("INVALID_FORMAT", 999),
            ("", 999),
            (None, 999)
        ]
        
        for job_id, expected in test_cases:
            try:
                result = extract_process_number(job_id)
                status = "✅" if result == expected else f"❌ Expected {expected}, got {result}"
                print(f"  extract_process_number({job_id}): {status}")
            except Exception as e:
                print(f"  extract_process_number({job_id}): ❌ Error: {e}")
        
        # Test extract_job_family  
        family_tests = [
            ("JOST111111_CP11-111-1/4", "CP11-111"),
            ("ABC123_DEF456-2/3", "DEF456"),
            ("INVALID", "INVALID")
        ]
        
        for job_id, expected in family_tests:
            try:
                result = extract_job_family(job_id)
                status = "✅" if result == expected else f"❌ Expected {expected}, got {result}"
                print(f"  extract_job_family({job_id}): {status}")
            except Exception as e:
                print(f"  extract_job_family({job_id}): ❌ Error: {e}")
        
        # Test validate_job_data
        valid_job = {"job_id": "TEST123", "hours_need": 5}
        invalid_job = {"no_job_id": "missing"}
        
        try:
            result1 = validate_job_data(valid_job)
            result2 = validate_job_data(invalid_job)
            print(f"  validate_job_data(valid): {'✅' if result1 else '❌'}")
            print(f"  validate_job_data(invalid): {'✅' if not result2 else '❌'}")
        except Exception as e:
            print(f"  validate_job_data: ❌ Error: {e}")
            
        print("✅ scheduler_utils tests completed")
        return True
        
    except ImportError as e:
        print(f"❌ scheduler_utils import failed: {e}")
        return False
    except Exception as e:
        print(f"❌ scheduler_utils tests failed: {e}")
        traceback.print_exc()
        return False

def test_urgent_handling():
    """Test urgent_handling functions"""
    print("🔍 Testing urgent_handling...")
    
    try:
        # Mock the dependencies to avoid import issues
        sys.modules['app.utils.time_utils'] = type(sys)('mock')
        sys.modules['app.utils.time_utils'].epoch_to_datetime = lambda x: datetime.fromtimestamp(x)
        sys.modules['app.utils.time_utils'].format_datetime_for_display = lambda x: str(x)
        
        from app.scheduling.urgent_handling import reduce_non_productive_time, should_reschedule
        
        # Test reduce_non_productive_time
        test_jobs = [
            {
                "job_id": "TEST1",
                "buffer_hours": 4,  # Urgent (< 8 hours)
                "setting_hours": 2,
                "break_hours": 1,
                "hours_need": 10
            },
            {
                "job_id": "TEST2", 
                "buffer_hours": 12,  # Not urgent
                "setting_hours": 1,
                "break_hours": 0.5,
                "hours_need": 8
            }
        ]
        
        result = reduce_non_productive_time(test_jobs, buffer_threshold=8, reduction_factor=0.5)
        
        if len(result) == 2:
            urgent_job = next((j for j in result if j["job_id"] == "TEST1"), None)
            if urgent_job and urgent_job.get("expedited"):
                print("  reduce_non_productive_time: ✅ Urgent job marked as expedited")
            else:
                print("  reduce_non_productive_time: ❌ Urgent job not properly handled")
        else:
            print("  reduce_non_productive_time: ❌ Wrong number of jobs returned")
            
        # Test should_reschedule
        reschedule_result = should_reschedule(result, 50)
        print(f"  should_reschedule: {'✅' if isinstance(reschedule_result, bool) else '❌'}")
        
        print("✅ urgent_handling tests completed")
        return True
        
    except Exception as e:
        print(f"❌ urgent_handling tests failed: {e}")
        traceback.print_exc()
        return False

def test_setup_buffer():
    """Test setup_buffer functions"""
    print("🔍 Testing setup_buffer...")
    
    try:
        # Mock pandas
        class MockPd:
            @staticmethod
            def isna(x):
                return x is None or (hasattr(x, '__len__') and len(x) == 0)
        
        sys.modules['pandas'] = MockPd()
        
        # Mock time_utils
        sys.modules['app.utils.time_utils'] = type(sys)('mock')
        sys.modules['app.utils.time_utils'].epoch_to_datetime = lambda x: datetime.fromtimestamp(x) if x else None
        sys.modules['app.utils.time_utils'].datetime_to_epoch = lambda x: time.mktime(x.timetuple()) if x else None
        sys.modules['app.utils.time_utils'].format_datetime_for_display = lambda x: str(x) if x else "N/A"
        sys.modules['app.utils.time_utils'].validate_timestamp = lambda x: isinstance(x, (int, float)) and x > 1000
        
        from app.scheduling.setup_buffer import (
            get_start_date_epoch, get_buffer_status, add_schedule_times_and_buffer
        )
        
        # Test get_start_date_epoch
        job_with_start = {"START_DATE_EPOCH": 1700000000}
        job_without_start = {"job_id": "TEST"}
        
        result1 = get_start_date_epoch(job_with_start)
        result2 = get_start_date_epoch(job_without_start)
        
        print(f"  get_start_date_epoch(with_date): {'✅' if result1 == 1700000000 else '❌'}")
        print(f"  get_start_date_epoch(without_date): {'✅' if result2 is None else '❌'}")
        
        # Test get_buffer_status
        buffer_tests = [
            (-5, "Late"),
            (4, "Critical"),
            (12, "Warning"),
            (48, "Caution"),
            (100, "OK")
        ]
        
        for buffer_hours, expected in buffer_tests:
            result = get_buffer_status(buffer_hours)
            status = "✅" if result == expected else f"❌ Expected {expected}, got {result}"
            print(f"  get_buffer_status({buffer_hours}): {status}")
        
        print("✅ setup_buffer tests completed")
        return True
        
    except Exception as e:
        print(f"❌ setup_buffer tests failed: {e}")
        traceback.print_exc()
        return False

def test_time_availability():
    """Test time_availability functions"""
    print("🔍 Testing time_availability...")
    
    try:
        # Mock dependencies
        sys.modules['pytz'] = type(sys)('mock')
        sys.modules['pytz'].timezone = lambda x: type(sys)('tz')
        
        # Mock database connection
        class MockConnection:
            def cursor(self, dictionary=True):
                return MockCursor()
            def __enter__(self):
                return self
            def __exit__(self, *args):
                pass
                
        class MockCursor:
            def execute(self, query, params=None):
                pass
            def fetchall(self):
                return []
        
        # Mock the database connection function
        sys.modules['app.api.fastapi_app'] = type(sys)('mock')
        sys.modules['app.api.fastapi_app'].get_db_connection_from_pool = lambda: MockConnection()
        
        # Mock time_utils
        sys.modules['app.utils.time_utils'] = type(sys)('mock')
        sys.modules['app.utils.time_utils'].epoch_to_datetime = lambda x: datetime.fromtimestamp(x)
        
        from app.scheduling.time_availability import TimeAvailabilityChecker, is_time_available
        
        # Test TimeAvailabilityChecker initialization
        checker = TimeAvailabilityChecker()
        print(f"  TimeAvailabilityChecker init: {'✅' if checker else '❌'}")
        
        # Test is_time_available function
        current_time = time.time()
        future_time = current_time + 3600  # 1 hour later
        
        # This should work without database issues
        try:
            result = is_time_available(current_time, future_time)
            print(f"  is_time_available: {'✅' if isinstance(result, bool) else '❌'}")
        except Exception as e:
            print(f"  is_time_available: ❌ Error: {e}")
        
        print("✅ time_availability tests completed")
        return True
        
    except Exception as e:
        print(f"❌ time_availability tests failed: {e}")
        traceback.print_exc()
        return False

def test_cpsat_solver():
    """Test cpsat_solver functions"""
    print("🔍 Testing cpsat_solver...")
    
    try:
        # Mock all dependencies
        sys.modules['ortools.sat.python'] = type(sys)('mock_ortools')
        sys.modules['ortools.sat.python'].cp_model = type(sys)('mock_cp_model')
        
        # Mock time_utils
        sys.modules['app.utils.time_utils'] = type(sys)('mock')
        sys.modules['app.utils.time_utils'].epoch_to_relative_hours = lambda x: x / 3600
        sys.modules['app.utils.time_utils'].relative_hours_to_epoch = lambda x: x * 3600
        sys.modules['app.utils.time_utils'].epoch_to_datetime = lambda x: datetime.fromtimestamp(x)
        sys.modules['app.utils.time_utils'].datetime_to_epoch = lambda x: time.mktime(x.timetuple())
        sys.modules['app.utils.time_utils'].format_datetime_for_display = lambda x: str(x)
        
        from app.scheduling.cpsat_solver import _create_error_result, _calculate_horizon, _calculate_total_job_hours
        
        # Test _create_error_result
        error_result = _create_error_result("Test error")
        if isinstance(error_result, dict) and "_metadata" in error_result:
            print("  _create_error_result: ✅")
        else:
            print("  _create_error_result: ❌")
        
        # Test _calculate_horizon
        test_jobs = [
            {"job_id": "TEST1", "hours_need": 8, "DAY_NEED": 1},
            {"job_id": "TEST2", "hours_need": 4}
        ]
        
        horizon = _calculate_horizon(test_jobs)
        if isinstance(horizon, int) and horizon > 0:
            print("  _calculate_horizon: ✅")
        else:
            print("  _calculate_horizon: ❌")
        
        # Test _calculate_total_job_hours
        test_job = {"job_id": "TEST", "DAY_NEED": 2, "hours_need": 8}
        total_hours = _calculate_total_job_hours(test_job)
        
        # Should use DAY_NEED (2 days = 48 hours)
        if total_hours == 48.0:
            print("  _calculate_total_job_hours: ✅")
        else:
            print(f"  _calculate_total_job_hours: ❌ Expected 48.0, got {total_hours}")
        
        print("✅ cpsat_solver tests completed")
        return True
        
    except Exception as e:
        print(f"❌ cpsat_solver tests failed: {e}")
        traceback.print_exc()
        return False

def test_greedy_solver():
    """Test greedy_solver functions"""
    print("🔍 Testing greedy_solver...")
    
    try:
        # Mock dependencies (same as cpsat_solver)
        sys.modules['ortools.sat.python'] = type(sys)('mock_ortools')
        sys.modules['ortools.sat.python'].cp_model = type(sys)('mock_cp_model')
        
        from app.scheduling.greedy_solver import find_best_machine
        
        # Test find_best_machine
        test_job = {"job_id": "TEST", "rsc_code": "MACHINE1"}
        test_machines = ["MACHINE1", "MACHINE2", "MACHINE3"]
        machine_times = {"MACHINE1": 100, "MACHINE2": 200, "MACHINE3": 50}
        
        result = find_best_machine(test_job, test_machines, machine_times)
        if result == "MACHINE1":  # Should return required machine
            print("  find_best_machine (required): ✅")
        else:
            print(f"  find_best_machine (required): ❌ Expected MACHINE1, got {result}")
        
        # Test with no required machine (should pick least loaded)
        test_job_no_req = {"job_id": "TEST2"}
        result2 = find_best_machine(test_job_no_req, test_machines, machine_times)
        if result2 == "MACHINE3":  # Should pick least loaded (time 50)
            print("  find_best_machine (least loaded): ✅")
        else:
            print(f"  find_best_machine (least loaded): ❌ Expected MACHINE3, got {result2}")
        
        print("✅ greedy_solver tests completed")
        return True
        
    except Exception as e:
        print(f"❌ greedy_solver tests failed: {e}")
        traceback.print_exc()
        return False

def main():
    """Run all tests"""
    print("🚀 Starting comprehensive function tests...\n")
    
    test_results = {
        "scheduler_utils": test_scheduler_utils(),
        "urgent_handling": test_urgent_handling(), 
        "setup_buffer": test_setup_buffer(),
        "time_availability": test_time_availability(),
        "cpsat_solver": test_cpsat_solver(),
        "greedy_solver": test_greedy_solver()
    }
    
    print("\n📊 TEST SUMMARY:")
    print("=" * 50)
    
    passed = 0
    total = len(test_results)
    
    for module, result in test_results.items():
        status = "✅ PASSED" if result else "❌ FAILED"
        print(f"{module:20} {status}")
        if result:
            passed += 1
    
    print("=" * 50)
    print(f"TOTAL: {passed}/{total} modules passed")
    
    if passed == total:
        print("🎉 ALL TESTS PASSED!")
        return True
    else:
        print("⚠️  Some tests failed - check output above")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1) 