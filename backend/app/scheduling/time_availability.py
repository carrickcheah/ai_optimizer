"""
Time availability checker for job scheduling.
Validates if time slots are available based on holidays, break times, and working hours.
"""

import logging
from datetime import datetime, timedelta, time
from typing import List, Dict, Any, Optional, Tuple
import pytz

from app.api.fastapi_app import get_db_connection_from_pool
from app.utils.time_utils import epoch_to_datetime

logger = logging.getLogger(__name__)

SINGAPORE_TZ = pytz.timezone('Asia/Singapore')

def timedelta_to_time(td):
    """Convert timedelta to time object."""
    if isinstance(td, timedelta):
        total_seconds = int(td.total_seconds())
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        seconds = total_seconds % 60
        return time(hours, minutes, seconds)
    elif isinstance(td, time):
        return td
    else:
        return td  # Return as-is if unknown type

class TimeAvailabilityChecker:
    """Checks time availability based on holidays, breaks, and working hours."""
    
    def __init__(self):
        self._holidays_cache = {}
        self._shifts_cache = {}
        self._breaktimes_cache = {}
        self._cache_expiry = None
        self._cache_duration = timedelta(hours=1)  # Cache for 1 hour
    
    def _refresh_cache_if_needed(self):
        """Refresh cache if expired."""
        now = datetime.now()
        if self._cache_expiry is None or now > self._cache_expiry:
            self._load_holidays()
            self._load_shifts_and_breaktimes()
            self._cache_expiry = now + self._cache_duration
            logger.info("Time availability cache refreshed")
    
    def _load_holidays(self):
        """Load holiday data from database."""
        try:
            with get_db_connection_from_pool() as conn:
                cursor = conn.cursor(dictionary=True)
                
                query = """
                SELECT id, holiday_id, override_date, is_observed, reason, created_at
                FROM nex_valiant.ai_holiday_overrides;
                """
                
                cursor.execute(query)  # Remove parameters since query doesn't use them
                holidays = cursor.fetchall()
                
                self._holidays_cache = {}
                for holiday in holidays:
                    # Handle overrides from ai_holiday_overrides table
                    if holiday['override_date']:
                        date_key = holiday['override_date'].strftime('%Y-%m-%d')
                        is_observed = holiday['is_observed']
                        
                        self._holidays_cache[date_key] = {
                            'name': f"Holiday Override {holiday['holiday_id']}",  # Use holiday_id since name not available
                            'scope': 'all',  # Default scope
                            'is_observed': is_observed,
                            'reason': holiday.get('reason', '')
                        }
                
                logger.info(f"Loaded {len(self._holidays_cache)} holiday entries")
                
        except Exception as e:
            logger.error(f"Error loading holidays: {e}")
            self._holidays_cache = {}
    
    def _load_shifts_and_breaktimes(self):
        """Load shift and breaktime data from database."""
        try:
            with get_db_connection_from_pool() as conn:
                cursor = conn.cursor(dictionary=True)
                
                # Load shifts
                shift_query = """
                SELECT * FROM ai_shifts 
                WHERE is_active = 1
                ORDER BY start_time
                """
                cursor.execute(shift_query)
                shifts = cursor.fetchall()
                
                self._shifts_cache = {}
                for shift in shifts:
                    # Handle working_days - could be a set or string depending on database
                    working_days = shift['working_days']
                    if isinstance(working_days, set):
                        working_days_set = working_days
                    elif isinstance(working_days, str):
                        working_days_set = set(working_days.split(',')) if working_days else set()
                    else:
                        working_days_set = set()
                    
                    self._shifts_cache[shift['id']] = {
                        'name': shift['name'],
                        'start_time': timedelta_to_time(shift['start_time']),
                        'end_time': timedelta_to_time(shift['end_time']),
                        'working_days': working_days_set,
                        'is_overnight': bool(shift['is_overnight']),
                        'shift_type': shift['shift_type']
                    }
                
                # Load breaktimes
                breaktime_query = """
                SELECT id, name, description, start_time, end_time, duration_minutes, break_type, is_paid, is_mandatory, is_active, created_at, updated_at
                FROM nex_valiant.ai_breaktimes;
                """
                cursor.execute(breaktime_query)
                breaktimes = cursor.fetchall()
                
                self._breaktimes_cache = {}
                for breaktime in breaktimes:
                    # Since shift_id is not in the query, use 'default' for all breaktimes
                    shift_id = 'default'
                    if shift_id not in self._breaktimes_cache:
                        self._breaktimes_cache[shift_id] = []
                    
                    # Only include active breaktimes
                    if breaktime.get('is_active', True):
                        self._breaktimes_cache[shift_id].append({
                            'name': breaktime['name'],
                            'start_time': timedelta_to_time(breaktime['start_time']),
                            'end_time': timedelta_to_time(breaktime['end_time']),
                            'duration_minutes': breaktime['duration_minutes'],
                            'break_type': breaktime['break_type'],
                            'is_mandatory': bool(breaktime['is_mandatory'])
                        })
                
                logger.info(f"Loaded {len(self._shifts_cache)} shifts and breaktimes for {len(self._breaktimes_cache)} shift groups")
                
        except Exception as e:
            logger.error(f"Error loading shifts and breaktimes: {e}")
            self._shifts_cache = {}
            self._breaktimes_cache = {}
    
    def is_holiday(self, date_obj: datetime) -> bool:
        """Check if a date is a holiday."""
        self._refresh_cache_if_needed()
        
        date_key = date_obj.strftime('%Y-%m-%d')
        holiday = self._holidays_cache.get(date_key)
        
        if holiday:
            return holiday['is_observed']
        
        return False
    
    def get_working_hours(self, date_obj: datetime) -> List[Tuple[time, time]]:
        """Get working hours for a specific date."""
        self._refresh_cache_if_needed()
        
        # Check if it's a holiday
        if self.is_holiday(date_obj):
            return []  # No working hours on holidays
        
        # Get day of week (monday=0, sunday=6)
        weekday = date_obj.weekday()
        day_names = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']
        day_name = day_names[weekday]
        
        working_periods = []
        
        # Check all active shifts
        for shift_id, shift in self._shifts_cache.items():
            if day_name in shift['working_days']:
                start_time = shift['start_time']
                end_time = shift['end_time']
                
                if shift['is_overnight'] and end_time < start_time:
                    # Handle overnight shifts
                    working_periods.append((start_time, time(23, 59, 59)))
                    working_periods.append((time(0, 0, 0), end_time))
                else:
                    working_periods.append((start_time, end_time))
        
        # FALLBACK: If no shifts configured, use default working hours (8am-6pm, Mon-Fri)
        if not working_periods and not self._shifts_cache:
            weekdays = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday']
            if day_name in weekdays:
                working_periods.append((time(8, 0), time(18, 0)))  # 8am-6pm
                logger.debug(f"Using fallback working hours for {day_name}: 8am-6pm")
        
        return working_periods
    
    def get_break_times(self, date_obj: datetime, shift_id: Optional[int] = None) -> List[Tuple[time, time]]:
        """Get break times for a specific date and shift."""
        self._refresh_cache_if_needed()
        
        # Check if it's a holiday
        if self.is_holiday(date_obj):
            return []  # No breaks on holidays (no work)
        
        break_periods = []
        
        # Get breaks for specific shift or default breaks
        shift_key = shift_id if shift_id and shift_id in self._shifts_cache else 'default'
        
        if shift_key in self._breaktimes_cache:
            for breaktime in self._breaktimes_cache[shift_key]:
                if breaktime['is_mandatory']:
                    break_periods.append((breaktime['start_time'], breaktime['end_time']))
        
        # If no shift-specific breaks found, use default breaks
        if not break_periods and shift_key != 'default' and 'default' in self._breaktimes_cache:
            for breaktime in self._breaktimes_cache['default']:
                if breaktime['is_mandatory']:
                    break_periods.append((breaktime['start_time'], breaktime['end_time']))
        
        return break_periods
    
    def is_time_available(self, start_epoch: float, end_epoch: float, shift_id: Optional[int] = None) -> bool:
        """Check if a time period is available for scheduling."""
        self._refresh_cache_if_needed()
        
        try:
            start_dt = epoch_to_datetime(start_epoch)
            end_dt = epoch_to_datetime(end_epoch)
            
            # Convert to Singapore timezone if not already timezone-aware
            if start_dt.tzinfo is None:
                start_dt = SINGAPORE_TZ.localize(start_dt)
            else:
                start_dt = start_dt.astimezone(SINGAPORE_TZ)
                
            if end_dt.tzinfo is None:
                end_dt = SINGAPORE_TZ.localize(end_dt)
            else:
                end_dt = end_dt.astimezone(SINGAPORE_TZ)
        except Exception as e:
            logger.error(f"Error converting epoch times: {e}")
            return False
        
        # Check each day in the time period
        current_dt = start_dt.replace(hour=0, minute=0, second=0, microsecond=0)
        
        while current_dt <= end_dt:
            # Check if it's a holiday
            if self.is_holiday(current_dt):
                # Check if any part of the job falls on this holiday
                day_start = current_dt
                day_end = current_dt.replace(hour=23, minute=59, second=59)
                
                if not (end_dt <= day_start or start_dt >= day_end):
                    logger.debug(f"Job conflicts with holiday on {current_dt.strftime('%Y-%m-%d')}")
                    return False
            
            # Check working hours for this day
            working_periods = self.get_working_hours(current_dt)
            if working_periods:
                # Check if job time overlaps with non-working hours
                job_start_time = start_dt.time() if start_dt.date() == current_dt.date() else time(0, 0, 0)
                job_end_time = end_dt.time() if end_dt.date() == current_dt.date() else time(23, 59, 59)
                
                # Check if job time is within working hours
                job_in_working_hours = False
                for work_start, work_end in working_periods:
                    if (job_start_time >= work_start and job_end_time <= work_end):
                        job_in_working_hours = True
                        break
                
                if not job_in_working_hours:
                    logger.debug(f"Job time {job_start_time}-{job_end_time} outside working hours on {current_dt.strftime('%Y-%m-%d')}")
                    return False
                
                # Check break times
                break_periods = self.get_break_times(current_dt, shift_id)
                for break_start, break_end in break_periods:
                    # Check if job overlaps with break time
                    if not (job_end_time <= break_start or job_start_time >= break_end):
                        logger.debug(f"Job conflicts with break time {break_start}-{break_end} on {current_dt.strftime('%Y-%m-%d')}")
                        return False
            
            current_dt += timedelta(days=1)
        
        return True
    
    def get_next_available_slot(self, start_epoch: float, duration_hours: float, shift_id: Optional[int] = None) -> Optional[float]:
        """Find the next available time slot for a job."""
        self._refresh_cache_if_needed()
        
        duration_seconds = duration_hours * 3600
        current_start = start_epoch
        max_search_days = 30  # Limit search to 30 days
        
        for day_offset in range(max_search_days):
            try:
                search_dt = epoch_to_datetime(current_start).astimezone(SINGAPORE_TZ)
                search_date = search_dt.date()
                
                # Skip holidays
                if self.is_holiday(datetime.combine(search_date, time(0, 0, 0))):
                    next_day = datetime.combine(search_date + timedelta(days=1), time(0, 0, 0))
                    # Make sure next_day is timezone-aware
                    next_day = SINGAPORE_TZ.localize(next_day) if next_day.tzinfo is None else next_day
                    current_start = next_day.timestamp()
                    continue
                
                # Get working periods for this day
                working_periods = self.get_working_hours(datetime.combine(search_date, time(0, 0, 0)))
                if not working_periods:
                    next_day = datetime.combine(search_date + timedelta(days=1), time(0, 0, 0))
                    # Make sure next_day is timezone-aware
                    next_day = SINGAPORE_TZ.localize(next_day) if next_day.tzinfo is None else next_day
                    current_start = next_day.timestamp()
                    continue
                
                # Try each working period
                for work_start, work_end in working_periods:
                    # Calculate available time considering breaks
                    break_periods = self.get_break_times(datetime.combine(search_date, time(0, 0, 0)), shift_id)
                    
                    # Find gaps between breaks
                    available_slots = self._find_available_slots_in_period(work_start, work_end, break_periods)
                    
                    for slot_start, slot_end in available_slots:
                        slot_duration = (datetime.combine(search_date, slot_end) - datetime.combine(search_date, slot_start)).total_seconds()
                        
                        if slot_duration >= duration_seconds:
                            # Found a suitable slot
                            slot_start_dt = datetime.combine(search_date, slot_start)
                            
                            # Make sure slot_start_dt is timezone-aware
                            if slot_start_dt.tzinfo is None:
                                slot_start_dt = SINGAPORE_TZ.localize(slot_start_dt)
                            
                            # If we're looking at today, make sure it's not in the past
                            if search_date == datetime.now(SINGAPORE_TZ).date():
                                now = datetime.now(SINGAPORE_TZ)
                                if slot_start_dt < now:
                                    # Adjust to current time if slot starts in the past
                                    slot_start_dt = now
                            
                            return slot_start_dt.timestamp()
                
                # Move to next day
                next_day = datetime.combine(search_date + timedelta(days=1), time(0, 0, 0))
                # Make sure next_day is timezone-aware
                next_day = SINGAPORE_TZ.localize(next_day) if next_day.tzinfo is None else next_day
                current_start = next_day.timestamp()
                
            except Exception as e:
                logger.error(f"Error in get_next_available_slot: {e}")
                break
        
        return None
    
    def _find_available_slots_in_period(self, work_start: time, work_end: time, break_periods: List[Tuple[time, time]]) -> List[Tuple[time, time]]:
        """Find available time slots within a working period, excluding breaks."""
        # Sort break periods by start time
        sorted_breaks = sorted(break_periods, key=lambda x: x[0])
        
        available_slots = []
        current_time = work_start
        
        for break_start, break_end in sorted_breaks:
            # Add slot before this break if there's time
            if current_time < break_start:
                available_slots.append((current_time, break_start))
            
            # Move current time to after this break
            current_time = max(current_time, break_end)
        
        # Add final slot after last break
        if current_time < work_end:
            available_slots.append((current_time, work_end))
        
        return available_slots


# Global instance
time_checker = TimeAvailabilityChecker()


def is_time_available(start_epoch: float, end_epoch: float, shift_id: Optional[int] = None) -> bool:
    """Check if a time period is available for scheduling."""
    return time_checker.is_time_available(start_epoch, end_epoch, shift_id)


def get_next_available_slot(start_epoch: float, duration_hours: float, shift_id: Optional[int] = None) -> Optional[float]:
    """Find the next available time slot for a job."""
    return time_checker.get_next_available_slot(start_epoch, duration_hours, shift_id)


def is_holiday(date_obj: datetime) -> bool:
    """Check if a date is a holiday."""
    return time_checker.is_holiday(date_obj) 