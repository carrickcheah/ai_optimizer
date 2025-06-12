#!/usr/bin/env python3
"""
Test script to debug the get_next_available_slot function.
"""

import logging
from datetime import datetime, timedelta
import pytz

# Setup logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def test_next_available_slot():
    """Test the get_next_available_slot function."""
    try:
        from app.scheduling.time_availability import get_next_available_slot, is_time_available_for_scheduling
        from app.utils.time_utils import datetime_to_epoch, epoch_to_datetime
        
        print("=== TESTING get_next_available_slot ===")
        
        # Test current time
        singapore_tz = pytz.timezone('Asia/Singapore')
        current_time = datetime.now(tz=singapore_tz)
        current_epoch = datetime_to_epoch(current_time)
        
        print(f"Current time: {current_time}")
        print(f"Current epoch: {current_epoch}")
        print(f"Is current time available: {is_time_available_for_scheduling(current_time)}")
        
        # Test for 12-hour job
        job_duration = 12.0  # hours
        print(f"\nTesting {job_duration}-hour job:")
        
        next_slot = get_next_available_slot(current_epoch, job_duration)
        
        if next_slot:
            next_datetime = epoch_to_datetime(next_slot)
            end_datetime = epoch_to_datetime(next_slot + job_duration * 3600)
            print(f"✅ Found next slot: {next_datetime}")
            print(f"Job would end at: {end_datetime}")
            print(f"Next slot is available: {is_time_available_for_scheduling(next_datetime)}")
        else:
            print(f"❌ No available slot found for {job_duration}-hour job")
        
        # Test for tomorrow 6:30 AM specifically
        tomorrow = current_time.replace(hour=6, minute=30, second=0, microsecond=0) + timedelta(days=1)
        tomorrow_epoch = datetime_to_epoch(tomorrow)
        
        print(f"\nTesting tomorrow 6:30 AM: {tomorrow}")
        print(f"Is tomorrow 6:30 available: {is_time_available_for_scheduling(tomorrow)}")
        
        # Test the get_next_available_slot logic manually
        print(f"\nManual test from tomorrow 6:30:")
        manual_next = get_next_available_slot(tomorrow_epoch, job_duration)
        if manual_next:
            manual_datetime = epoch_to_datetime(manual_next)
            print(f"✅ Manual test found: {manual_datetime}")
        else:
            print(f"❌ Manual test failed")
            
        # Test working hours for today and tomorrow
        from app.scheduling.time_availability import TimeAvailabilityManager
        checker = TimeAvailabilityManager.get_instance()
        
        print(f"\nWorking hours for today:")
        today_hours = checker.get_working_hours_for_date(current_time)
        for start, end in today_hours:
            print(f"  {start} to {end}")
            
        print(f"\nWorking hours for tomorrow:")
        tomorrow_hours = checker.get_working_hours_for_date(tomorrow)
        for start, end in tomorrow_hours:
            print(f"  {start} to {end}")
            
        # Check if tomorrow is a holiday
        print(f"\nIs tomorrow a holiday: {checker.is_holiday(tomorrow)}")
            
    except Exception as e:
        logger.error(f"Error in test: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_next_available_slot()