"""
Time utilities for the production planning system.
This implements a relative time approach to reduce the issue of large epoch numbers.
"""

import logging
import math
from datetime import datetime, timezone, timedelta
import pandas as pd
import pytz

logger = logging.getLogger(__name__)

# Global reference time (scheduling start time)
REFERENCE_TIME = None
SINGAPORE_TZ = timezone(timedelta(hours=8))

def initialize_reference_time():
    """Initialize the reference time to current time."""
    now = datetime.now(SINGAPORE_TZ)
    logging.info(f"Reference time initialized to {now.isoformat()}")
    return now

REFERENCE_TIME = initialize_reference_time()
REFERENCE_EPOCH = REFERENCE_TIME.timestamp()

def get_reference_time():
    """Get the reference time, initializing it if necessary."""
    global REFERENCE_TIME
    if REFERENCE_TIME is None:
        initialize_reference_time()
    return REFERENCE_TIME

def validate_timestamp(value, min_valid_timestamp=1000):
    """
    Validates whether a value is a proper timestamp and not a small value like a job ID.
    
    Args:
        value: The value to check (should be integer or float)
        min_valid_timestamp: The minimum acceptable value for a timestamp (default: 1000)
            - Values below this threshold are rejected as they likely represent
              job IDs or other small numbers being incorrectly used as timestamps
    
    Returns:
        bool: True if the value is a valid timestamp, False otherwise
    """
    # Check type
    if value is None or pd.isna(value):
        return False
        
    # Check if it's a number
    if not isinstance(value, (int, float)):
        try:
            value = float(value)
        except (ValueError, TypeError):
            return False
    
    # Check minimum threshold to avoid using IDs as timestamps
    if value < min_valid_timestamp:
        logger.warning(f"Value {value} is too small to be a valid timestamp")
        return False
        
    # Check if timestamp is unreasonably large (538 years from 1970)
    if value > 17_000_000_000:  # ~Year 2508
        logger.warning(f"Value {value} is too large to be a valid timestamp")
        return False
        
    # Try to convert to datetime as final validation
    try:
        dt = datetime.fromtimestamp(value, SINGAPORE_TZ)
        # Additional check: reject very old dates
        if dt.year < 2000:
            logger.warning(f"Timestamp {value} converts to {dt.year} which is suspiciously old")
            return False
        return True
    except (ValueError, OSError, TypeError):
        return False

def datetime_to_epoch(dt):
    """Convert a datetime object to epoch timestamp."""
    if dt is None:
        return None
    try:
        if not dt.tzinfo:
            dt = dt.replace(tzinfo=SINGAPORE_TZ)
        return dt.timestamp()
    except (AttributeError, TypeError):
        logging.warning(f"Could not convert to epoch: {dt}")
        return None

def epoch_to_datetime(epoch):
    """Convert an epoch timestamp to a datetime object."""
    if epoch is None or pd.isna(epoch):
        return None
        
    # Validate timestamp before conversion
    if not validate_timestamp(epoch):
        logging.warning(f"Invalid epoch value rejected: {epoch}")
        return None
        
    try:
        return datetime.fromtimestamp(epoch, SINGAPORE_TZ)
    except (ValueError, TypeError, OSError) as e:
        logging.warning(f"Invalid epoch value: {epoch}, error: {e}")
        return None

def epoch_to_relative_hours(epoch):
    """Convert an epoch timestamp to hours since reference time."""
    if epoch is None or pd.isna(epoch):
        return 0
    try:
        # Convert to relative hours from reference time
        hours = (epoch - REFERENCE_EPOCH) / 3600
        # If hours is negative (before reference time), return 0
        return max(0, hours)
    except (TypeError, ValueError):
        logging.warning(f"Could not convert epoch to relative hours: {epoch}")
        return 0

def relative_hours_to_epoch(hours):
    """Convert hours since reference time to epoch timestamp."""
    if hours is None or pd.isna(hours):
        return REFERENCE_EPOCH
    try:
        # Convert relative hours back to epoch time
        return REFERENCE_EPOCH + (hours * 3600)
    except (TypeError, ValueError):
        logging.warning(f"Could not convert relative hours to epoch: {hours}")
        return REFERENCE_EPOCH

def iso_to_datetime(iso_string):
    """Convert an ISO format string to a datetime object."""
    if not iso_string or pd.isna(iso_string):
        return None
    try:
        dt = datetime.fromisoformat(iso_string)
        if not dt.tzinfo:
            dt = dt.replace(tzinfo=SINGAPORE_TZ)
        return dt
    except (ValueError, TypeError):
        logging.warning(f"Could not parse ISO datetime: {iso_string}")
        return None

def datetime_to_iso(dt):
    """Convert a datetime object to ISO format string."""
    if dt is None:
        return None
    try:
        if not dt.tzinfo:
            dt = dt.replace(tzinfo=SINGAPORE_TZ)
        return dt.isoformat()
    except (AttributeError, TypeError):
        logging.warning(f"Could not convert to ISO: {dt}")
        return None

def format_datetime_for_display(dt):
    """Format a datetime object for display."""
    if dt is None:
        return "N/A"
    try:
        if not dt.tzinfo:
            dt = dt.replace(tzinfo=SINGAPORE_TZ)
        return dt.strftime('%Y-%m-%d %H:%M')
    except (AttributeError, TypeError):
        return "Invalid Date"

def convert_job_times_to_relative(job):
    """Convert job time fields from epoch to relative time."""
    if not job:
        return
        
    # Store original values
    for field in ['lcd_date_epoch', 'start_date_epoch', 'start_time', 'end_time']:
        if field in job and job[field] is not None:
            job[f"{field}_ORIGINAL"] = job[field]
    
    # Handle lcd_date_epoch (due date)
    if 'lcd_date_epoch' in job and job['lcd_date_epoch'] is not None and not pd.isna(job['lcd_date_epoch']):
        epoch_value = job['lcd_date_epoch']
        dt = epoch_to_datetime(epoch_value)
        if dt:
            job['lcd_date_iso'] = datetime_to_iso(dt)
            job['lcd_date_rel_hours'] = epoch_to_relative_hours(epoch_value)
            logger.debug(f"Converted lcd_date for {job.get('op_id')}: {epoch_value} -> {job['lcd_date_rel_hours']} hours")
    
    # Handle start_date_epoch (required start date)
    if 'start_date_epoch' in job and job['start_date_epoch'] is not None and not pd.isna(job['start_date_epoch']):
        epoch_value = job['start_date_epoch']
        dt = epoch_to_datetime(epoch_value)
        if dt:
            job['start_date_iso'] = datetime_to_iso(dt)
            job['start_date_rel_hours'] = epoch_to_relative_hours(epoch_value)
            logger.debug(f"Converted start_date for {job.get('op_id')}: {epoch_value} -> {job['start_date_rel_hours']} hours")
    
    # Handle start_time (scheduled start)
    if 'start_time' in job and job['start_time'] is not None and not pd.isna(job['start_time']):
        epoch_value = job['start_time']
        dt = epoch_to_datetime(epoch_value)
        if dt:
            job['start_time_iso'] = datetime_to_iso(dt)
            job['start_time_rel_hours'] = epoch_to_relative_hours(epoch_value)
            logger.debug(f"Converted start_time for {job.get('op_id')}: {epoch_value} -> {job['start_time_rel_hours']} hours")
    
    # Handle end_time (scheduled end)
    if 'end_time' in job and job['end_time'] is not None and not pd.isna(job['end_time']):
        epoch_value = job['end_time']
        dt = epoch_to_datetime(epoch_value)
        if dt:
            job['end_time_iso'] = datetime_to_iso(dt)
            job['end_time_rel_hours'] = epoch_to_relative_hours(epoch_value)
            logger.debug(f"Converted end_time for {job.get('op_id')}: {epoch_value} -> {job['end_time_rel_hours']} hours")

def convert_job_times_to_epoch(job):
    """Convert job time fields from relative time back to epoch."""
    if not job:
        return
    
    # Handle lcd_date_rel_hours
    if 'lcd_date_rel_hours' in job and job['lcd_date_rel_hours'] is not None and not pd.isna(job['lcd_date_rel_hours']):
        rel_hours = job['lcd_date_rel_hours']
        job['lcd_date_epoch'] = relative_hours_to_epoch(rel_hours)
        logger.debug(f"Converted lcd_date for {job.get('op_id')}: {rel_hours} hours -> {job['lcd_date_epoch']}")
    
    # Handle start_date_rel_hours
    if 'start_date_rel_hours' in job and job['start_date_rel_hours'] is not None and not pd.isna(job['start_date_rel_hours']):
        rel_hours = job['start_date_rel_hours']
        job['start_date_epoch'] = relative_hours_to_epoch(rel_hours)
        logger.debug(f"Converted start_date for {job.get('op_id')}: {rel_hours} hours -> {job['start_date_epoch']}")
    
    # Handle start_time_rel_hours
    if 'start_time_rel_hours' in job and job['start_time_rel_hours'] is not None and not pd.isna(job['start_time_rel_hours']):
        rel_hours = job['start_time_rel_hours']
        job['start_time'] = relative_hours_to_epoch(rel_hours)
        logger.debug(f"Converted start_time for {job.get('op_id')}: {rel_hours} hours -> {job['start_time']}")
    
    # Handle end_time_rel_hours
    if 'end_time_rel_hours' in job and job['end_time_rel_hours'] is not None and not pd.isna(job['end_time_rel_hours']):
        rel_hours = job['end_time_rel_hours']
        job['end_time'] = relative_hours_to_epoch(rel_hours)
        logger.debug(f"Converted end_time for {job.get('op_id')}: {rel_hours} hours -> {job['end_time']}") 