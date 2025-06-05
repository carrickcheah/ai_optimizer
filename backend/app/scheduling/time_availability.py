"""
Time availability checker for job scheduling.
Validates if time slots are available based on holidays, break times, and working hours.
"""

import logging
from datetime import datetime, timedelta, time, date
from typing import List, Dict, Any, Optional, Tuple
import pytz
import mysql.connector

from app.data_ingestion.mariadb_parser import get_db_connection

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
    """Checks time availability based on ai_holidays, ai_arrangable_hour, and ai_breaktimes."""
    
    def __init__(self):
        self._holidays_cache = {}
        self._arrangable_hours_cache = {}
        self._breaktimes_cache = []
        self._cache_expiry = None
        self._cache_duration = timedelta(hours=1)  # Cache for 1 hour
    
    def _refresh_cache_if_needed(self):
        """Refresh cache if expired."""
        now = datetime.now()
        if self._cache_expiry is None or now > self._cache_expiry:
            self._load_holidays()
            self._load_arrangable_hours()
            self._load_breaktimes()
            self._cache_expiry = now + self._cache_duration
            logger.info("Time availability cache refreshed")
    
    def _load_holidays(self):
        """Load holiday data from ai_holidays table."""
        try:
            from app.api.fastapi_app import get_db_connection_from_pool
            
            with get_db_connection_from_pool() as conn:
                cursor = conn.cursor(dictionary=True)
            
            # Load holidays from ai_holidays table
            query = """
            SELECT id, name, description, holiday_date, month_day, is_recurring, 
                   scope, location, country_code, is_active, created_at, updated_at
            FROM ai_holidays 
            WHERE is_active = 1
            ORDER BY holiday_date
            """
            
            cursor.execute(query)
            holidays = cursor.fetchall()
            
            self._holidays_cache = {}
            current_year = datetime.now().year
            
            for holiday in holidays:
                if holiday['holiday_date']:
                    # Specific date holiday
                    date_key = holiday['holiday_date'].strftime('%Y-%m-%d')
                    self._holidays_cache[date_key] = {
                        'name': holiday['name'],
                        'description': holiday.get('description', ''),
                        'scope': holiday.get('scope', 'company'),
                        'is_recurring': holiday.get('is_recurring', False)
                    }
                elif holiday['month_day'] and holiday['is_recurring']:
                    # Recurring holiday (e.g., "01-01" for New Year)
                    try:
                        month, day = map(int, holiday['month_day'].split('-'))
                        # Add for current year and next year
                        for year in [current_year, current_year + 1]:
                            date_key = f"{year:04d}-{month:02d}-{day:02d}"
                            self._holidays_cache[date_key] = {
                                'name': holiday['name'],
                                'description': holiday.get('description', ''),
                                'scope': holiday.get('scope', 'company'),
                                'is_recurring': True
                            }
                    except (ValueError, AttributeError):
                        logger.warning(f"Invalid month_day format for holiday {holiday['name']}: {holiday['month_day']}")
            
            logger.info(f"Loaded {len(self._holidays_cache)} holiday entries from ai_holidays")
            cursor.close()
                
        except Exception as e:
            logger.error(f"Error loading holidays from ai_holidays: {e}")
            self._holidays_cache = {}
    
    def _load_arrangable_hours(self):
        """Load working hours from ai_arrangable_hour table."""
        try:
            from app.api.fastapi_app import get_db_connection_from_pool
            
            with get_db_connection_from_pool() as conn:
                cursor = conn.cursor(dictionary=True)
                
                query = """
                SELECT id, arrange_day, start_time, end_time, is_working, created_at, updated_at
                FROM ai_arrangable_hour 
                WHERE is_working = 1
                ORDER BY arrange_day, start_time
                """
                
                cursor.execute(query)
                hours = cursor.fetchall()
                
                self._arrangable_hours_cache = {}
                for hour in hours:
                    day = hour['arrange_day']  # 1=Monday, 2=Tuesday, ..., 7=Sunday
                    if day not in self._arrangable_hours_cache:
                        self._arrangable_hours_cache[day] = []
                    
                    self._arrangable_hours_cache[day].append({
                        'start_time': timedelta_to_time(hour['start_time']),
                        'end_time': timedelta_to_time(hour['end_time']),
                        'is_working': hour['is_working']
                    })
                
                logger.info(f"Loaded arrangable hours for {len(self._arrangable_hours_cache)} days from ai_arrangable_hour")
                cursor.close()
                
        except Exception as e:
            logger.error(f"Error loading arrangable hours from ai_arrangable_hour: {e}")
            self._arrangable_hours_cache = {}
    
    def _load_breaktimes(self):
        """Load break times from ai_breaktimes table."""
        try:
            from app.api.fastapi_app import get_db_connection_from_pool
            
            with get_db_connection_from_pool() as conn:
                cursor = conn.cursor(dictionary=True)
            
            query = """
            SELECT id, name, description, start_time, end_time, duration_minutes, 
                   break_type, is_paid, is_mandatory, is_active, created_at, updated_at
            FROM ai_breaktimes 
            WHERE is_active = 1
            ORDER BY start_time
            """
            
            cursor.execute(query)
            breaktimes = cursor.fetchall()
            
            self._breaktimes_cache = []
            for breaktime in breaktimes:
                self._breaktimes_cache.append({
                    'name': breaktime['name'],
                    'description': breaktime.get('description', ''),
                    'start_time': timedelta_to_time(breaktime['start_time']),
                    'end_time': timedelta_to_time(breaktime['end_time']),
                    'duration_minutes': breaktime['duration_minutes'],
                    'break_type': breaktime['break_type'],
                    'is_mandatory': bool(breaktime['is_mandatory'])
                })
            
            logger.info(f"Loaded {len(self._breaktimes_cache)} active breaktimes from ai_breaktimes")
            cursor.close()
                
        except Exception as e:
            logger.error(f"Error loading breaktimes from ai_breaktimes: {e}")
            self._breaktimes_cache = []
    
    def is_holiday(self, date_obj: datetime) -> bool:
        """Check if a date is a holiday using ai_holidays table."""
        self._refresh_cache_if_needed()
        
        date_key = date_obj.strftime('%Y-%m-%d')
        holiday = self._holidays_cache.get(date_key)
        
        if holiday:
            logger.debug(f"Date {date_key} is a holiday: {holiday['name']}")
            return True
        
        return False
    
    def is_within_working_hours(self, datetime_obj: datetime) -> bool:
        """Check if datetime falls within arrangable working hours."""
        self._refresh_cache_if_needed()
        
        # Convert datetime to day of week (1=Monday, 7=Sunday)
        # Python's weekday(): Monday=0, Sunday=6
        # Our database: Monday=1, Sunday=7
        day_of_week = datetime_obj.weekday() + 1
        if day_of_week == 8:  # Sunday (7) becomes 8, fix it
            day_of_week = 7
            
        current_time = datetime_obj.time()
        
        # Check if this day has any working hours configured
        working_periods = self._arrangable_hours_cache.get(day_of_week, [])
        
        for period in working_periods:
            start_time = period['start_time']
            end_time = period['end_time']
            
            # Handle case where end_time might be next day (e.g., night shift)
            if end_time < start_time:
                # Overnight shift: check if time is after start OR before end
                if current_time >= start_time or current_time <= end_time:
                    return True
            else:
                # Regular shift: check if time is between start and end
                if start_time <= current_time <= end_time:
                    return True
        
        return False
    
    def is_break_time(self, datetime_obj: datetime) -> bool:
        """Check if datetime falls within any break time."""
        self._refresh_cache_if_needed()
        
        current_time = datetime_obj.time()
        
        for breaktime in self._breaktimes_cache:
            start_time = breaktime['start_time']
            end_time = breaktime['end_time']
            
            # Handle potential overnight breaks
            if end_time < start_time:
                # Overnight break: check if time is after start OR before end
                if current_time >= start_time or current_time <= end_time:
                    logger.debug(f"Time {current_time} is during break: {breaktime['name']}")
                    return True
            else:
                # Regular break: check if time is between start and end
                if start_time <= current_time <= end_time:
                    logger.debug(f"Time {current_time} is during break: {breaktime['name']}")
                    return True
        
        return False
    
    def is_time_available_for_scheduling(self, datetime_obj: datetime) -> bool:
        """
        Main logic: Check if a datetime is available for job scheduling.
        
        Logic:
        1. NOT a holiday (ai_holidays)
        2. Within working hours (ai_arrangable_hour with is_working=1)  
        3. NOT during break time (ai_breaktimes)
        
        Returns True only if ALL conditions are met.
        """
        # Check if it's a holiday
        if self.is_holiday(datetime_obj):
            logger.debug(f"Time {datetime_obj} unavailable: holiday")
            return False
        
        # Check if within working hours
        if not self.is_within_working_hours(datetime_obj):
            logger.debug(f"Time {datetime_obj} unavailable: outside working hours")
            return False
        
        # Check if it's break time
        if self.is_break_time(datetime_obj):
            logger.debug(f"Time {datetime_obj} unavailable: break time")
            return False
        
        # All checks passed
        return True
    
    def is_time_range_available(self, start_datetime: datetime, end_datetime: datetime) -> bool:
        """
        Check if an entire time range is available for scheduling.
        Checks every hour within the range.
        """
        current = start_datetime
        while current < end_datetime:
            if not self.is_time_available_for_scheduling(current):
                return False
            current += timedelta(hours=1)
        
        # Also check the end time
        return self.is_time_available_for_scheduling(end_datetime)
    
    def get_next_available_datetime(self, start_datetime: datetime, duration_hours: float) -> Optional[datetime]:
        """
        Find the next available datetime slot that can accommodate the given duration.
        """
        current = start_datetime
        max_search_days = 30  # Limit search to 30 days ahead
        
        while current < start_datetime + timedelta(days=max_search_days):
            # Check if we can fit the entire duration starting from current time
            end_time = current + timedelta(hours=duration_hours)
            
            if self.is_time_range_available(current, end_time):
                return current
            
            # Move to next hour
            current += timedelta(hours=1)
        
        return None
    
    def get_working_hours_for_date(self, date_obj: datetime) -> List[Tuple[time, time]]:
        """Get all working time periods for a specific date."""
        self._refresh_cache_if_needed()
        
        # Check if it's a holiday first
        if self.is_holiday(date_obj):
            return []
        
        # Convert to day of week for database lookup
        day_of_week = date_obj.weekday() + 1
        if day_of_week == 8:
            day_of_week = 7
            
        working_periods = []
        periods = self._arrangable_hours_cache.get(day_of_week, [])
        
        for period in periods:
            working_periods.append((period['start_time'], period['end_time']))
        
        return working_periods
    
    def get_break_times_for_date(self, date_obj: datetime) -> List[Dict[str, Any]]:
        """Get all break times for a specific date."""
        self._refresh_cache_if_needed()
        return self._breaktimes_cache.copy()

# Global instance for easy access
_time_checker = TimeAvailabilityChecker()

def is_time_available_for_scheduling(datetime_obj: datetime) -> bool:
    """Global function to check if time is available for scheduling."""
    return _time_checker.is_time_available_for_scheduling(datetime_obj)

def is_time_range_available(start_datetime: datetime, end_datetime: datetime) -> bool:
    """Global function to check if time range is available for scheduling."""
    return _time_checker.is_time_range_available(start_datetime, end_datetime)

def get_next_available_datetime(start_datetime: datetime, duration_hours: float) -> Optional[datetime]:
    """Global function to find next available datetime slot."""
    return _time_checker.get_next_available_datetime(start_datetime, duration_hours)

def is_holiday(date_obj: datetime) -> bool:
    """Global function to check if date is a holiday."""
    return _time_checker.is_holiday(date_obj)

# Legacy compatibility functions
def is_time_available(start_epoch: float, end_epoch: float, shift_id: Optional[int] = None) -> bool:
    """Legacy function - converts epoch to datetime and checks availability."""
    try:
        start_dt = datetime.fromtimestamp(start_epoch, tz=SINGAPORE_TZ)
        end_dt = datetime.fromtimestamp(end_epoch, tz=SINGAPORE_TZ)
        return _time_checker.is_time_range_available(start_dt, end_dt)
    except Exception as e:
        logger.error(f"Error in legacy is_time_available: {e}")
        return False

def get_next_available_slot(start_epoch: float, duration_hours: float, shift_id: Optional[int] = None) -> Optional[float]:
    """Legacy function - converts epoch and returns next available slot."""
    try:
        start_dt = datetime.fromtimestamp(start_epoch, tz=SINGAPORE_TZ)
        next_dt = _time_checker.get_next_available_datetime(start_dt, duration_hours)
        return next_dt.timestamp() if next_dt else None
    except Exception as e:
        logger.error(f"Error in legacy get_next_available_slot: {e}")
        return None 