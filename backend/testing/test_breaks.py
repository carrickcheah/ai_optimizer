#!/usr/bin/env python3
"""
Test script to verify break time handling in schedulers
"""

import os
import sys
from datetime import datetime, timedelta
import pytz

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.scheduling.time_availability import (
    TimeAvailabilityManager,
    is_time_available_for_scheduling,
    is_time_range_available
)

def test_break_times():
    """Test if break times are being respected"""
    malaysia_tz = pytz.timezone('Asia/Kuala_Lumpur')
    
    # Get time availability checker instance
    checker = TimeAvailabilityManager.get_instance()
    
    # Force cache refresh
    checker.cache.refresh_if_needed()
    
    print("=== TESTING BREAK TIME DETECTION ===\n")
    
    # Test times throughout a typical workday
    test_date = datetime.now(malaysia_tz).replace(hour=0, minute=0, second=0, microsecond=0)
    
    # If today is weekend, move to Monday
    while test_date.weekday() >= 5:  # Saturday = 5, Sunday = 6
        test_date += timedelta(days=1)
    
    print(f"Testing for date: {test_date.strftime('%Y-%m-%d %A')}")
    print(f"Active breaks from database:")
    
    # Get and display active breaks
    breaks = checker.cache._breaktimes_cache
    for brk in breaks:
        print(f"  - {brk['name']}: {brk['start_time']} to {brk['end_time']} ({brk['duration_minutes']} min)")
    
    print("\n=== HOURLY AVAILABILITY CHECK ===")
    
    # Test every 30 minutes from 6:00 to 20:00
    for hour in range(6, 20):
        for minute in [0, 30]:
            test_time = test_date.replace(hour=hour, minute=minute)
            
            # Check if time is available
            is_available = is_time_available_for_scheduling(test_time)
            
            # Check individual components
            is_holiday = checker.is_holiday(test_time)
            is_working = checker.is_within_working_hours(test_time)
            is_break = checker.is_break_time(test_time)
            
            status = "✅ AVAILABLE" if is_available else "❌ NOT AVAILABLE"
            reasons = []
            if is_holiday:
                reasons.append("holiday")
            if not is_working:
                reasons.append("outside working hours")
            if is_break:
                reasons.append("break time")
            
            reason_str = f" ({', '.join(reasons)})" if reasons else ""
            print(f"{test_time.strftime('%H:%M')} - {status}{reason_str}")
    
    print("\n=== TESTING JOB SCHEDULING ACROSS BREAKS ===")
    
    # Test scheduling a 4-hour job starting at different times
    job_duration_hours = 4
    
    test_times = [
        (9, 0, "Morning start"),
        (11, 0, "Before lunch"),
        (14, 0, "After lunch"),
        (16, 0, "Late afternoon")
    ]
    
    for hour, minute, desc in test_times:
        start_time = test_date.replace(hour=hour, minute=minute)
        end_time = start_time + timedelta(hours=job_duration_hours)
        
        # Check if entire range is available
        range_available = is_time_range_available(start_time, end_time)
        
        print(f"\n{desc} - {job_duration_hours}h job from {start_time.strftime('%H:%M')} to {end_time.strftime('%H:%M')}:")
        print(f"  Range available: {'✅ YES' if range_available else '❌ NO'}")
        
        # Check each hour
        current = start_time
        while current < end_time:
            is_avail = is_time_available_for_scheduling(current)
            if not is_avail:
                is_break = checker.is_break_time(current)
                if is_break:
                    print(f"  - {current.strftime('%H:%M')} is during break time")
            current += timedelta(minutes=30)

if __name__ == "__main__":
    test_break_times()