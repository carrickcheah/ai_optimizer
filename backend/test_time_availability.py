#!/usr/bin/env python3
"""
Test script for the new time availability logic using:
- ai_holidays
- ai_arrangable_hour  
- ai_breaktimes
"""

import os
import sys
from datetime import datetime, timedelta
import pytz

# Add the project root to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from backend.app.scheduling.time_availability import (
    is_time_available_for_scheduling,
    is_time_range_available, 
    get_next_available_datetime,
    is_holiday,
    TimeAvailabilityChecker
)

SINGAPORE_TZ = pytz.timezone('Asia/Singapore')

def test_time_availability():
    """Test the new time availability logic."""
    print("🔍 Testing Time Availability Logic")
    print("=" * 50)
    
    checker = TimeAvailabilityChecker()
    
    # Test 1: Check working hours (should be available Mon-Fri 6:30-18:00)
    print("\n📅 Test 1: Working Hours Check")
    
    # Monday 10:00 AM (should be available)
    monday_10am = datetime(2025, 6, 9, 10, 0, 0, tzinfo=SINGAPORE_TZ)  # Monday
    result = is_time_available_for_scheduling(monday_10am)
    print(f"Monday 10:00 AM available: {result} ✅" if result else f"Monday 10:00 AM available: {result} ❌")
    
    # Sunday 10:00 AM (should NOT be available - configured as is_working=0)
    sunday_10am = datetime(2025, 6, 8, 10, 0, 0, tzinfo=SINGAPORE_TZ)  # Sunday
    result = is_time_available_for_scheduling(sunday_10am)
    print(f"Sunday 10:00 AM available: {result} ❌" if not result else f"Sunday 10:00 AM available: {result} ✅")
    
    # Monday 5:00 AM (should NOT be available - before 6:30 AM)
    monday_5am = datetime(2025, 6, 9, 5, 0, 0, tzinfo=SINGAPORE_TZ)
    result = is_time_available_for_scheduling(monday_5am)
    print(f"Monday 5:00 AM available: {result} ❌" if not result else f"Monday 5:00 AM available: {result} ✅")
    
    # Monday 7:00 PM (should NOT be available - after 6:00 PM)
    monday_7pm = datetime(2025, 6, 9, 19, 0, 0, tzinfo=SINGAPORE_TZ)
    result = is_time_available_for_scheduling(monday_7pm)
    print(f"Monday 7:00 PM available: {result} ❌" if not result else f"Monday 7:00 PM available: {result} ✅")
    
    # Test 2: Check holidays
    print("\n🏖️  Test 2: Holiday Check")
    
    # Test a known holiday (you'll need to check what's in your ai_holidays table)
    # For now, let's just test the holiday function
    test_date = datetime(2025, 12, 25, 10, 0, 0, tzinfo=SINGAPORE_TZ)  # Christmas
    is_holiday_result = is_holiday(test_date)
    print(f"Christmas Day is holiday: {is_holiday_result}")
    
    # Test 3: Check break times
    print("\n☕ Test 3: Break Time Check")
    
    # Test if our break time logic works (depends on what's in ai_breaktimes)
    monday_lunch = datetime(2025, 6, 9, 12, 30, 0, tzinfo=SINGAPORE_TZ)  # Typical lunch time
    result = is_time_available_for_scheduling(monday_lunch)
    print(f"Monday 12:30 PM (lunch time) available: {result}")
    
    # Test 4: Time range availability
    print("\n⏰ Test 4: Time Range Check")
    
    # Test a 2-hour job on Monday morning
    start_time = datetime(2025, 6, 9, 8, 0, 0, tzinfo=SINGAPORE_TZ)
    end_time = start_time + timedelta(hours=2)
    result = is_time_range_available(start_time, end_time)
    print(f"Monday 8:00-10:00 AM range available: {result}")
    
    # Test 5: Find next available slot
    print("\n🔍 Test 5: Next Available Slot")
    
    # Try to find next available 3-hour slot starting from now
    now = datetime.now(SINGAPORE_TZ)
    next_slot = get_next_available_datetime(now, 3.0)
    if next_slot:
        print(f"Next 3-hour slot available at: {next_slot.strftime('%Y-%m-%d %H:%M:%S %Z')}")
    else:
        print("No 3-hour slot found in next 30 days")
    
    # Test 6: Display cache information
    print("\n📊 Test 6: Cache Information")
    
    # Force cache refresh and show what was loaded
    checker._refresh_cache_if_needed()
    print(f"Holidays loaded: {len(checker._holidays_cache)}")
    print(f"Working days configured: {len(checker._arrangable_hours_cache)}")
    print(f"Break times loaded: {len(checker._breaktimes_cache)}")
    
    if checker._holidays_cache:
        print("\nSample holidays:")
        for i, (date_key, holiday) in enumerate(list(checker._holidays_cache.items())[:3]):
            print(f"  {date_key}: {holiday['name']}")
    
    if checker._arrangable_hours_cache:
        print("\nWorking hours by day:")
        day_names = ['', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
        for day_num, periods in checker._arrangable_hours_cache.items():
            day_name = day_names[day_num] if day_num < len(day_names) else f"Day {day_num}"
            for period in periods:
                print(f"  {day_name}: {period['start_time']} - {period['end_time']}")
    
    if checker._breaktimes_cache:
        print("\nBreak times:")
        for breaktime in checker._breaktimes_cache:
            print(f"  {breaktime['name']}: {breaktime['start_time']} - {breaktime['end_time']} ({breaktime['break_type']})")

if __name__ == "__main__":
    try:
        test_time_availability()
        print("\n✅ Time availability test completed!")
    except Exception as e:
        print(f"\n❌ Error during testing: {e}")
        import traceback
        traceback.print_exc() 