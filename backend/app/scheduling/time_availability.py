"""
time_availability.py - PRODUCTION GRADE VERSION
Time availability checker for job scheduling with all configuration from .env
Validates time slots based on holidays, break times, and working hours
"""

import logging
import os
from dataclasses import dataclass
from datetime import datetime, timedelta, time, date
from typing import Any, Dict, List, Optional, Tuple

import mysql.connector
import pytz
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

logger = logging.getLogger(__name__)
MALAYSIA_TZ = pytz.timezone('Asia/Kuala_Lumpur')


class TimeAvailabilityError(Exception):
    """Base exception for time availability errors."""
    pass


class TimeAvailabilityConfigurationError(TimeAvailabilityError):
    """Exception for configuration-related errors."""
    pass


@dataclass
class TimeConfig:
    """Configuration for time availability loaded from .env."""
    grace_period_hours: int
    
    
class TimeAvailabilityConfigManager:
    """Manages time availability configuration from environment variables only."""
    
    @staticmethod
    def load_config() -> TimeConfig:
        """Load configuration with hardcoded values - NO ENVIRONMENT VARIABLES NEEDED."""
        # Hardcoded GRACE_PERIOD_HOURS value
        grace_period_hours = 48  # Grace period for late jobs (hours)
        
        # Convert and validate values
        try:
            config = TimeConfig(
                grace_period_hours=grace_period_hours
            )
            
            # Validate configuration values
            TimeAvailabilityConfigManager._validate_config(config)
            return config
            
        except (ValueError, TypeError) as e:
            raise TimeAvailabilityConfigurationError(f"❌ INVALID CONFIGURATION: Error converting values: {e}")
    
    @staticmethod
    def _validate_config(config: TimeConfig) -> None:
        """Validate configuration values."""
        validations = [
            (config.grace_period_hours >= 0, "GRACE_PERIOD_HOURS must be non-negative")
        ]
        
        for condition, error_msg in validations:
            if not condition:
                raise TimeAvailabilityConfigurationError(f"❌ INVALID CONFIGURATION: {error_msg}")


class DatabaseConnectionManager:
    """Manages database connections with error handling."""
    
    @staticmethod
    def get_connection():
        """Get database connection with proper error handling."""
        try:
            # Try to use connection pool first
            from app.api.fastapi_app import get_db_connection_from_pool
            return get_db_connection_from_pool()
        except ImportError:
            try:
                # Fallback to direct connection
                from app.data_ingestion.mariadb_parser import get_db_connection
                return get_db_connection()
            except ImportError:
                raise TimeAvailabilityError("Could not import database connection functions")


class TimeConverter:
    """Handles time format conversions and validations."""
    
    @staticmethod
    def timedelta_to_time(td: Any) -> time:
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
            return td
    
    @staticmethod
    def time_to_seconds(time_obj: time) -> int:
        """Convert time object to seconds since midnight."""
        return time_obj.hour * 3600 + time_obj.minute * 60 + time_obj.second
    
    @staticmethod
    def epoch_to_day_and_seconds(epoch_timestamp: float) -> Tuple[int, int]:
        """Convert epoch timestamp to day number and seconds in day."""
        epoch_day = int(epoch_timestamp // 86400)
        seconds_in_day = int(epoch_timestamp % 86400)
        return epoch_day, seconds_in_day
    
    @staticmethod
    def get_day_of_week(epoch_day: int) -> int:
        """Get day of week (1=Monday, 7=Sunday) from epoch day."""
        # Unix epoch started on Thursday (1970-01-01), so day 0 = Thursday = 4
        day_of_week = ((epoch_day + 4) % 7) + 1
        if day_of_week == 8:
            day_of_week = 1
        return day_of_week


class DatabaseCache:
    """Handles database caching with optimized structures."""
    
    def __init__(self, cache_duration_hours: int = 1):
        self.cache_duration = timedelta(hours=cache_duration_hours)
        self._cache_expiry = None
        
        # Standard caches
        self._holidays_cache = {}
        self._arrangable_hours_cache = {}
        self._breaktimes_cache = []
        
        # Optimized epoch caches
        self._holidays_epoch_cache = set()
        self._working_hours_epoch_cache = {}
        self._break_times_epoch_cache = []
    
    def refresh_if_needed(self) -> None:
        """Refresh cache if expired."""
        now = datetime.now()
        if self._cache_expiry is None or now > self._cache_expiry:
            self._load_all_data()
            self._build_epoch_caches()
            self._cache_expiry = now + self.cache_duration
            logger.info("Time availability cache refreshed")
    
    def _load_all_data(self) -> None:
        """Load all data from database."""
        self._load_holidays()
        self._load_arrangable_hours()
        self._load_breaktimes()
    
    def _load_holidays(self) -> None:
        """Load holiday data from ai_holidays table."""
        try:
            with DatabaseConnectionManager.get_connection() as conn:
                cursor = conn.cursor(dictionary=True)
                
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
                        # Recurring holiday
                        try:
                            month, day = map(int, holiday['month_day'].split('-'))
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
    
    def _load_arrangable_hours(self) -> None:
        """Load working hours from ai_arrangable_hour table."""
        try:
            with DatabaseConnectionManager.get_connection() as conn:
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
                    day = hour['arrange_day']
                    if day not in self._arrangable_hours_cache:
                        self._arrangable_hours_cache[day] = []
                    
                    self._arrangable_hours_cache[day].append({
                        'start_time': TimeConverter.timedelta_to_time(hour['start_time']),
                        'end_time': TimeConverter.timedelta_to_time(hour['end_time']),
                        'is_working': hour['is_working']
                    })
                
                logger.info(f"Loaded arrangable hours for {len(self._arrangable_hours_cache)} days")
                cursor.close()
                
        except Exception as e:
            logger.error(f"Error loading arrangable hours: {e}")
            self._arrangable_hours_cache = {}
    
    def _load_breaktimes(self) -> None:
        """Load break times from ai_breaktimes table."""
        try:
            with DatabaseConnectionManager.get_connection() as conn:
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
                        'start_time': TimeConverter.timedelta_to_time(breaktime['start_time']),
                        'end_time': TimeConverter.timedelta_to_time(breaktime['end_time']),
                        'duration_minutes': breaktime['duration_minutes'],
                        'break_type': breaktime['break_type'],
                        'is_mandatory': bool(breaktime['is_mandatory'])
                    })
                
                logger.info(f"Loaded {len(self._breaktimes_cache)} active breaktimes")
                cursor.close()
                
        except Exception as e:
            logger.error(f"Error loading breaktimes: {e}")
            self._breaktimes_cache = []
    
    def _build_epoch_caches(self) -> None:
        """Build optimized epoch-based caches."""
        try:
            # Build holidays epoch cache
            self._holidays_epoch_cache.clear()
            for date_str in self._holidays_cache.keys():
                holiday_date = datetime.strptime(date_str, '%Y-%m-%d').date()
                epoch_day = (holiday_date - datetime(1970, 1, 1).date()).days
                self._holidays_epoch_cache.add(epoch_day)
            
            # Build working hours epoch cache
            self._working_hours_epoch_cache.clear()
            for day_of_week, periods in self._arrangable_hours_cache.items():
                epoch_periods = []
                for period in periods:
                    start_seconds = TimeConverter.time_to_seconds(period['start_time'])
                    end_seconds = TimeConverter.time_to_seconds(period['end_time'])
                    epoch_periods.append((start_seconds, end_seconds))
                
                self._working_hours_epoch_cache[day_of_week] = epoch_periods
            
            # Build break times epoch cache
            self._break_times_epoch_cache.clear()
            for breaktime in self._breaktimes_cache:
                start_seconds = TimeConverter.time_to_seconds(breaktime['start_time'])
                end_seconds = TimeConverter.time_to_seconds(breaktime['end_time'])
                self._break_times_epoch_cache.append((start_seconds, end_seconds, breaktime['name']))
            
            logger.info(f"Built epoch caches: {len(self._holidays_epoch_cache)} holidays, "
                       f"{len(self._working_hours_epoch_cache)} working days, "
                       f"{len(self._break_times_epoch_cache)} break periods")
                       
        except Exception as e:
            logger.error(f"Error building epoch caches: {e}")
            self._holidays_epoch_cache.clear()
            self._working_hours_epoch_cache.clear()
            self._break_times_epoch_cache.clear()


class TimeAvailabilityChecker:
    """Production-grade time availability checker with optimized caching."""
    
    def __init__(self, config: TimeConfig):
        self.config = config
        self.cache = DatabaseCache()
    
    def is_holiday(self, date_obj: datetime) -> bool:
        """Check if a date is a holiday."""
        self.cache.refresh_if_needed()
        
        date_key = date_obj.strftime('%Y-%m-%d')
        holiday = self.cache._holidays_cache.get(date_key)
        
        if holiday:
            logger.debug(f"Date {date_key} is a holiday: {holiday['name']}")
            return True
        
        return False
    
    def is_within_working_hours(self, datetime_obj: datetime) -> bool:
        """Check if datetime falls within working hours."""
        self.cache.refresh_if_needed()
        
        # Convert to day of week (1=Monday, 7=Sunday)
        day_of_week = datetime_obj.weekday() + 1
        if day_of_week == 8:
            day_of_week = 7
        
        current_time = datetime_obj.time()
        working_periods = self.cache._arrangable_hours_cache.get(day_of_week, [])
        
        for period in working_periods:
            start_time = period['start_time']
            end_time = period['end_time']
            
            # Handle overnight shifts
            if end_time < start_time:
                if current_time >= start_time or current_time <= end_time:
                    return True
            else:
                if start_time <= current_time <= end_time:
                    return True
        
        return False
    
    def is_break_time(self, datetime_obj: datetime) -> bool:
        """Check if datetime falls within break time."""
        self.cache.refresh_if_needed()
        
        current_time = datetime_obj.time()
        
        for breaktime in self.cache._breaktimes_cache:
            start_time = breaktime['start_time']
            end_time = breaktime['end_time']
            
            # Handle overnight breaks
            if end_time < start_time:
                if current_time >= start_time or current_time <= end_time:
                    logger.debug(f"Time {current_time} is during break: {breaktime['name']}")
                    return True
            else:
                if start_time <= current_time <= end_time:
                    logger.debug(f"Time {current_time} is during break: {breaktime['name']}")
                    return True
        
        return False
    
    def is_time_available_for_scheduling(self, datetime_obj: datetime) -> bool:
        """
        Check if datetime is available for scheduling.
        
        Logic: NOT holiday AND within working hours AND NOT break time
        """
        if self.is_holiday(datetime_obj):
            logger.debug(f"Time {datetime_obj} unavailable: holiday")
            return False
        
        if not self.is_within_working_hours(datetime_obj):
            logger.debug(f"Time {datetime_obj} unavailable: outside working hours")
            return False
        
        if self.is_break_time(datetime_obj):
            logger.debug(f"Time {datetime_obj} unavailable: break time")
            return False
        
        return True
    
    def is_time_available_epoch(self, start_epoch: float, end_epoch: float) -> bool:
        """
        Optimized epoch-based time availability check.
        
        Args:
            start_epoch: Job start time as Unix timestamp
            end_epoch: Job end time as Unix timestamp
            
        Returns:
            True if entire time range is available
        """
        self.cache.refresh_if_needed()
        
        # Fall back to datetime method if epoch caches unavailable
        if not self.cache._working_hours_epoch_cache:
            logger.debug("Epoch caches not available, using datetime method")
            start_dt = datetime.fromtimestamp(start_epoch, tz=MALAYSIA_TZ)
            end_dt = datetime.fromtimestamp(end_epoch, tz=MALAYSIA_TZ)
            return self.is_time_range_available(start_dt, end_dt)
        
        # Check every hour in the range
        current_epoch = start_epoch
        check_interval = 3600  # 1 hour
        
        while current_epoch < end_epoch:
            if not self._is_single_time_available_epoch(current_epoch):
                return False
            current_epoch += check_interval
        
        # Check end time
        return self._is_single_time_available_epoch(end_epoch)
    
    def _is_single_time_available_epoch(self, epoch_timestamp: float) -> bool:
        """Check if single epoch timestamp is available."""
        epoch_day, seconds_in_day = TimeConverter.epoch_to_day_and_seconds(epoch_timestamp)
        day_of_week = TimeConverter.get_day_of_week(epoch_day)
        
        # Check holiday
        if epoch_day in self.cache._holidays_epoch_cache:
            return False
        
        # Check working hours
        working_periods = self.cache._working_hours_epoch_cache.get(day_of_week, [])
        is_working_hour = False
        
        for start_seconds, end_seconds in working_periods:
            if end_seconds < start_seconds:
                # Overnight period
                if seconds_in_day >= start_seconds or seconds_in_day <= end_seconds:
                    is_working_hour = True
                    break
            else:
                # Regular period
                if start_seconds <= seconds_in_day <= end_seconds:
                    is_working_hour = True
                    break
        
        if not is_working_hour:
            return False
        
        # Check break times
        for start_seconds, end_seconds, break_name in self.cache._break_times_epoch_cache:
            if end_seconds < start_seconds:
                if seconds_in_day >= start_seconds or seconds_in_day <= end_seconds:
                    return False
            else:
                if start_seconds <= seconds_in_day <= end_seconds:
                    return False
        
        return True
    
    def is_time_range_available(self, start_datetime: datetime, end_datetime: datetime) -> bool:
        """Check if entire time range is available."""
        current = start_datetime
        while current < end_datetime:
            if not self.is_time_available_for_scheduling(current):
                return False
            current += timedelta(hours=1)
        
        return self.is_time_available_for_scheduling(end_datetime)
    
    def get_next_available_datetime(self, start_datetime: datetime, duration_hours: float) -> Optional[datetime]:
        """Find earliest available datetime slot for given duration."""
        max_search_days = 365
        current_date = start_datetime.date()
        
        for day_offset in range(max_search_days):
            check_date = current_date + timedelta(days=day_offset)
            check_datetime = datetime.combine(check_date, time(0, 0), tzinfo=start_datetime.tzinfo)
            
            working_periods = self.get_working_hours_for_date(check_datetime)
            
            for start_time, end_time in working_periods:
                period_start = datetime.combine(check_date, start_time, tzinfo=start_datetime.tzinfo)
                period_end = datetime.combine(check_date, end_time, tzinfo=start_datetime.tzinfo)
                
                # Don't schedule before requested start time
                if day_offset == 0 and period_start < start_datetime:
                    period_start = start_datetime
                
                # For long jobs that span multiple days, just check if we can start during working hours
                duration_seconds = duration_hours * 3600
                job_end_time = period_start + timedelta(seconds=duration_seconds)
                
                # If job is longer than normal scheduling period, allow it to span multiple days
                if duration_hours >= 8:  # Jobs that may need flexible scheduling
                    # Just check if start time is available during working hours
                    if self.is_time_available_for_scheduling(period_start):
                        logger.debug(f"Long job ({duration_hours}h) can start at {period_start}")
                        return period_start
                else:
                    # Normal jobs must fit within working period
                    if job_end_time <= period_end and self.is_time_range_available(period_start, job_end_time):
                        return period_start
        
        return None
    
    def get_working_hours_for_date(self, date_obj: datetime) -> List[Tuple[time, time]]:
        """Get working time periods for specific date."""
        self.cache.refresh_if_needed()
        
        if self.is_holiday(date_obj):
            return []
        
        day_of_week = date_obj.weekday() + 1
        if day_of_week == 8:
            day_of_week = 7
        
        working_periods = []
        periods = self.cache._arrangable_hours_cache.get(day_of_week, [])
        
        for period in periods:
            working_periods.append((period['start_time'], period['end_time']))
        
        return working_periods
    
    def get_break_times_for_date(self, date_obj: datetime) -> List[Dict[str, Any]]:
        """Get break times for specific date."""
        self.cache.refresh_if_needed()
        return self.cache._breaktimes_cache.copy()


# Global instance manager
class TimeAvailabilityManager:
    """Singleton manager for global time availability checker."""
    
    _instance = None
    _config = None
    
    @classmethod
    def get_instance(cls) -> TimeAvailabilityChecker:
        """Get singleton instance with proper configuration."""
        if cls._instance is None or cls._config is None:
            try:
                cls._config = TimeAvailabilityConfigManager.load_config()
                cls._instance = TimeAvailabilityChecker(cls._config)
                logger.info("Time availability checker initialized from .env")
            except TimeAvailabilityConfigurationError as e:
                logger.error(f"Configuration error: {e}")
                raise
        
        return cls._instance
    
    @classmethod
    def reset_instance(cls) -> None:
        """Reset instance for testing or configuration changes."""
        cls._instance = None
        cls._config = None


# Global API functions
def is_time_available(start_epoch: float, end_epoch: float, shift_id: Optional[int] = None) -> bool:
    """Check if epoch time range is available for scheduling."""
    try:
        checker = TimeAvailabilityManager.get_instance()
        start_dt = datetime.fromtimestamp(start_epoch, tz=MALAYSIA_TZ)
        end_dt = datetime.fromtimestamp(end_epoch, tz=MALAYSIA_TZ)
        return checker.is_time_range_available(start_dt, end_dt)
    except Exception as e:
        logger.error(f"Error in is_time_available: {e}")
        return False


def get_next_available_slot(start_epoch: float, duration_hours: float, shift_id: Optional[int] = None) -> Optional[float]:
    """Find next available epoch slot."""
    try:
        checker = TimeAvailabilityManager.get_instance()
        start_dt = datetime.fromtimestamp(start_epoch, tz=MALAYSIA_TZ)
        next_dt = checker.get_next_available_datetime(start_dt, duration_hours)
        return next_dt.timestamp() if next_dt else None
    except Exception as e:
        logger.error(f"Error in get_next_available_slot: {e}")
        return None


def is_time_available_for_scheduling(datetime_obj: datetime) -> bool:
    """Check if datetime is available for scheduling."""
    try:
        checker = TimeAvailabilityManager.get_instance()
        return checker.is_time_available_for_scheduling(datetime_obj)
    except Exception as e:
        logger.error(f"Error in is_time_available_for_scheduling: {e}")
        return False


def is_time_range_available(start_datetime: datetime, end_datetime: datetime) -> bool:
    """Check if time range is available for scheduling."""
    try:
        checker = TimeAvailabilityManager.get_instance()
        return checker.is_time_range_available(start_datetime, end_datetime)
    except Exception as e:
        logger.error(f"Error in is_time_range_available: {e}")
        return False


def get_next_available_datetime(start_datetime: datetime, duration_hours: float) -> Optional[datetime]:
    """Find next available datetime slot."""
    try:
        checker = TimeAvailabilityManager.get_instance()
        return checker.get_next_available_datetime(start_datetime, duration_hours)
    except Exception as e:
        logger.error(f"Error in get_next_available_datetime: {e}")
        return None


def is_holiday(date_obj: datetime) -> bool:
    """Check if date is a holiday."""
    try:
        checker = TimeAvailabilityManager.get_instance()
        return checker.is_holiday(date_obj)
    except Exception as e:
        logger.error(f"Error in is_holiday: {e}")
        return False


# Legacy functions for backward compatibility
def is_time_available_legacy(start_epoch: float, end_epoch: float, shift_id: Optional[int] = None) -> bool:
    """Legacy function - same as is_time_available."""
    return is_time_available(start_epoch, end_epoch, shift_id)


def get_next_available_slot_legacy(start_epoch: float, duration_hours: float, shift_id: Optional[int] = None) -> Optional[float]:
    """Legacy function - same as get_next_available_slot."""
    return get_next_available_slot(start_epoch, duration_hours, shift_id)


if __name__ == '__main__':
    """Test configuration and functionality."""
    try:
        config = TimeAvailabilityConfigManager.load_config()
        print(f"✅ Configuration loaded: Grace period = {config.grace_period_hours} hours")
        
        # Test checker initialization
        checker = TimeAvailabilityManager.get_instance()
        print("✅ Time availability checker initialized successfully")
        
        # Test current time availability
        now = datetime.now(tz=MALAYSIA_TZ)
        is_available = checker.is_time_available_for_scheduling(now)
        print(f"✅ Current time availability: {is_available}")
        
    except TimeAvailabilityConfigurationError as e:
        print(f"❌ Configuration Error: {e}")
        print("Ensure GRACE_PERIOD_HOURS is set in your .env file")
    except Exception as e:
        print(f"❌ Error: {e}")