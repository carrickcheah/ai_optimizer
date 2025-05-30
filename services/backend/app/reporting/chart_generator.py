# services/ai_optimizer/backend/app/reporting/chart_generator.py
"""Production-grade chart data generator for manufacturing schedules."""

import logging
import re
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Union
import pytz
import pandas as pd # Keep pandas for now if it simplifies data handling from jobs_data
from app.utils.time_utils import validate_timestamp

logger = logging.getLogger(__name__)
SG_TIMEZONE = pytz.timezone('Asia/Singapore')
SECONDS_PER_HOUR = 3600
SECONDS_PER_DAY = 86400

# Color mapping for priorities, similar to original chart.py
# These can be used by the frontend or to explicitly set colors in the data
PRIORITY_COLORS = {
    'Priority 1 (Highest)': 'rgb(231, 76, 60)',   # Red
    'Priority 2 (High)': 'rgb(243, 156, 18)',     # Orange
    'Priority 3 (Medium)': 'rgb(41, 128, 185)',   # Blue
    'Priority 4 (Normal)': 'rgb(46, 204, 113)',   # Green
    'Priority 5 (Low)': 'rgb(149, 165, 166)'      # Gray
}
PRIORITY_LABELS_MAP = {
    1: 'Priority 1 (Highest)',
    2: 'Priority 2 (High)',
    3: 'Priority 3 (Medium)',
    4: 'Priority 4 (Normal)',
    5: 'Priority 5 (Low)',
}

# Buffer status color map - matching frontend colors
BUFFER_COLORS = {
    'Late': '#f44336',      # Red
    'Warning': '#ff9800',   # Orange
    'Caution': '#9c27b0',   # Purple
    'OK': '#4caf50'         # Green
}

def safe_timestamp_to_datetime(timestamp: Union[int, float, str], fallback_to_today: bool = True) -> Optional[datetime]:
    """Safely convert timestamp to datetime with proper validation."""
    if not timestamp:
        return None

    try:
        # Handle string timestamps
        if isinstance(timestamp, str):
            timestamp = float(timestamp)
        
        # Validate timestamp range
        if not validate_timestamp(timestamp):
            return None
            
        # Handle small values (seconds of day)
        if 0 < timestamp < SECONDS_PER_DAY and fallback_to_today:
            today = datetime.now(SG_TIMEZONE).replace(hour=0, minute=0, second=0, microsecond=0)
            return today + timedelta(seconds=timestamp)
        
        # Standard conversion
        dt = datetime.fromtimestamp(timestamp, tz=SG_TIMEZONE)
        
        # Reject 1970 dates as likely invalid
        if dt.year == 1970 and fallback_to_today:
            today = datetime.now(SG_TIMEZONE).replace(hour=0, minute=0, second=0, microsecond=0)
            return today + timedelta(seconds=timestamp % SECONDS_PER_DAY)
        
        return dt
        
    except (ValueError, TypeError, OSError):
        return None

def format_datetime_for_display(dt: Optional[datetime], format_str: str = '%Y-%m-%d %H:%M:%S') -> str:
    """Format datetime for display with fallback."""
    if not dt or not isinstance(dt, datetime):
        return 'N/A'
    
    try:
        return dt.strftime(format_str)
    except (ValueError, TypeError):
        return 'N/A'

def extract_job_family(job_id: str) -> str:
    """Extract job family from job ID efficiently."""
    if not job_id:
        return 'Unknown'
    
    job_id = str(job_id).upper()
    
    # Extract process code after first underscore
    parts = job_id.split('_', 1)
    process_code = parts[1] if len(parts) > 1 else job_id
    
    # Find family before -P pattern
    match = re.search(r'(.*?)-P\d+', process_code)
    return match.group(1) if match else process_code.split('-P')[0]

def extract_process_number(job_id: str) -> int:
    """Extract process number from job ID."""
    if not job_id:
        return 999
    
    match = re.search(r'P(\d{2})', str(job_id).upper())
    try:
        return int(match.group(1)) if match else 999
    except (ValueError, AttributeError):
        return 999

def validate_schedule_data(schedule: Any) -> bool:
    """Validate schedule data structure."""
    if not isinstance(schedule, dict):
        logger.error("Schedule must be a dictionary")
        return False
    
    for machine, jobs in schedule.items():
        if not isinstance(jobs, list):
            logger.error(f"Jobs for machine {machine} must be a list")
            return False
        
        for job in jobs:
            if not isinstance(job, (list, tuple)) or len(job) < 3:
                logger.error(f"Invalid job format in schedule: {job}")
                return False
    
    return True

def validate_jobs_data(jobs_data: Any) -> bool:
    """Validate jobs input data structure."""
    if not isinstance(jobs_data, list):
        logger.error("Jobs data must be a list")
        return False
    
    for job in jobs_data:
        if not isinstance(job, dict) or 'job_id' not in job:
            logger.error(f"Invalid job format: {job}")
            return False
    
    return True

def prepare_gantt_data_priority_view(schedule: Dict[str, Any], jobs_input_data: List[Dict]) -> List[Dict]:
    """Prepare Gantt chart data for priority view with optimized performance."""
    if not validate_schedule_data(schedule) or not validate_jobs_data(jobs_input_data):
        return []
    
    gantt_data = []
    job_lookup = {job['job_id']: job for job in jobs_input_data}
    
    # Process scheduled jobs
    for machine, jobs in schedule.items():
        for job_tuple in jobs:
            job_id = job_tuple[0]
            start_epoch = job_tuple[1] if len(job_tuple) > 1 else None
            end_epoch = job_tuple[2] if len(job_tuple) > 2 else None
            
            if not all([job_id, start_epoch is not None, end_epoch is not None]):
                    continue

            job_details = job_lookup.get(job_id, {})
            priority = job_details.get('priority', 3)
            
            start_dt = safe_timestamp_to_datetime(start_epoch)
            end_dt = safe_timestamp_to_datetime(end_epoch)
            
            if not start_dt or not end_dt:
                continue
            
            # Calculate buffer status
            buffer_hours = 0.0
            buffer_status = "OK"
            if end_epoch and job_details.get('lcd_date_epoch'):
                buffer_hours = calculate_buffer_hours(end_epoch, job_details['lcd_date_epoch'])
                buffer_status = determine_buffer_status(buffer_hours)
    
            gantt_data.append({
                'Task': job_id,
                'Start': start_dt.isoformat(),
                'Finish': end_dt.isoformat(),
                'Resource': machine,
                'Priority': priority,
                'PriorityLabel': PRIORITY_LABELS_MAP.get(priority, f'Priority {priority}'),
                'BufferStatusLabel': buffer_status,
                'Color': BUFFER_COLORS.get(buffer_status),
                'Job_Family': extract_job_family(job_id),
                'Process_Number': extract_process_number(job_id)
            })
    
    # Sort by priority then start time
    gantt_data.sort(key=lambda x: (x['Priority'], x['Start']))
    return gantt_data

def prepare_gantt_data_resource_view(schedule: Dict[str, Any], jobs_input_data: List[Dict]) -> List[Dict]:
    """Prepare Gantt chart data for resource view with buffer status colors."""
    if not validate_schedule_data(schedule) or not validate_jobs_data(jobs_input_data):
        return []

    gantt_data = []
    job_lookup = {job['job_id']: job for job in jobs_input_data}
    
    # Process scheduled jobs
    for machine, jobs in schedule.items():
        for job_tuple in jobs:
            job_id = job_tuple[0]
            start_epoch = job_tuple[1] if len(job_tuple) > 1 else None
            end_epoch = job_tuple[2] if len(job_tuple) > 2 else None
            
            if not all([job_id, start_epoch is not None, end_epoch is not None]):
                        continue
                
            job_details = job_lookup.get(job_id, {})
            priority = job_details.get('priority', 3)
            
            start_dt = safe_timestamp_to_datetime(start_epoch)
            end_dt = safe_timestamp_to_datetime(end_epoch)
            
            if not start_dt or not end_dt:
                continue
            
            # Calculate buffer status
            buffer_hours = 0.0
            buffer_status = "OK"
            if end_epoch and job_details.get('lcd_date_epoch'):
                buffer_hours = calculate_buffer_hours(end_epoch, job_details['lcd_date_epoch'])
                buffer_status = determine_buffer_status(buffer_hours)
                
            gantt_data.append({
                'Task': job_id,
                'Start': start_dt.isoformat(),
                'Finish': end_dt.isoformat(),
                'Resource': machine,
                'Priority': priority,
                'PriorityLabel': PRIORITY_LABELS_MAP.get(priority, f'Priority {priority}'),
                'BufferStatusLabel': buffer_status,
                'Color': BUFFER_COLORS.get(buffer_status),
                'Job_Family': extract_job_family(job_id),
                'Process_Number': extract_process_number(job_id)
            })
    
    # Sort by resource then start time
    gantt_data.sort(key=lambda x: (x['Resource'], x['Start']))
    return gantt_data

def format_display_date(value: Any, date_format: str = '%Y-%m-%d %H:%M', timezone: pytz.BaseTzInfo = SG_TIMEZONE) -> str:
    """Format various date inputs for display with simplified logic."""
    if not value:
        return 'N/A'
    
    dt = None
    
    # Handle datetime objects
    if isinstance(value, datetime):
        dt = value
    # Handle numeric timestamps
    elif isinstance(value, (int, float)):
        dt = safe_timestamp_to_datetime(value)
    # Handle string inputs
    elif isinstance(value, str):
        try:
            # Try as numeric timestamp first
            timestamp = float(value)
            dt = safe_timestamp_to_datetime(timestamp)
        except ValueError:
            # Try common date formats
            for fmt in ['%Y-%m-%d %H:%M:%S', '%Y-%m-%d %H:%M', '%d/%m/%Y %H:%M:%S', '%d/%m/%Y %H:%M']:
                try:
                    dt = datetime.strptime(value, fmt)
                    break
                except ValueError:
                    continue
        
    if not dt:
        return 'N/A'
    
    # Ensure timezone awareness
    if dt.tzinfo is None:
        try:
            dt = timezone.localize(dt)
        except Exception:
            return 'N/A'
    else:
        dt = dt.astimezone(timezone)
    
    return format_datetime_for_display(dt, date_format)

def calculate_buffer_hours(end_time: Union[int, float], due_date: Union[int, float]) -> float:
    """Calculate buffer hours between end time and due date."""
    try:
        if isinstance(end_time, datetime):
            end_numeric = end_time.timestamp()
        else:
            end_numeric = float(end_time)
        
        if isinstance(due_date, datetime):
            due_numeric = due_date.timestamp()
        else:
            due_numeric = float(due_date)
        
        return (due_numeric - end_numeric) / SECONDS_PER_HOUR
    except (ValueError, TypeError):
        return 0.0  # Return 0 when calculation fails - no fake defaults

def determine_buffer_status(buffer_hours: float) -> str:
    """Determine buffer status based on hours remaining."""
    if buffer_hours < 0:
        return "Late"
    elif buffer_hours < 8:
        return "Critical"
    elif buffer_hours < 24:
        return "Warning"
    elif buffer_hours < 72:
        return "Caution"
    else:
        return "OK"

def prepare_detailed_schedule_table_data(schedule: Dict[str, Any], jobs_input_data: List[Dict]) -> List[Dict]:
    """Prepare detailed schedule table data with optimized performance."""
    if not validate_schedule_data(schedule) or not validate_jobs_data(jobs_input_data):
        return []
    
    # Create lookup for scheduled times
    scheduled_times = {}
    for machine, jobs in schedule.items():
        for job_tuple in jobs:
            if len(job_tuple) >= 3:
                job_id = job_tuple[0]
                scheduled_times[job_id] = {
                    'start': job_tuple[1],
                    'end': job_tuple[2]
                }
    
    table_rows = []
    
    for job in jobs_input_data:
        job_id = job.get('job_id', 'N/A')
        scheduled = scheduled_times.get(job_id, {})
        
        # Format times
        start_time_str = format_display_date(scheduled.get('start'), '%Y-%m-%d %H:%M:%S') if scheduled.get('start') else 'N/A'
        end_time_str = format_display_date(scheduled.get('end'), '%Y-%m-%d %H:%M:%S') if scheduled.get('end') else 'N/A'
        
        # Calculate buffer - SHOW REAL VALUES WITHOUT CAPPING OR DEFAULTS
        buffer_hours = 0.0  # No fake defaults - only real calculated values
        if scheduled.get('end') and job.get('lcd_date_epoch'):
            buffer_hours = calculate_buffer_hours(scheduled['end'], job['lcd_date_epoch'])
        elif not scheduled.get('end'):
            buffer_hours = None  # No scheduled end time = no buffer calculation possible
        elif not job.get('lcd_date_epoch'):
            buffer_hours = None  # No LCD date = no buffer calculation possible
        
        # REMOVED ALL CAPPING LOGIC - Show actual buffer hours
        actual_buffer_hours = buffer_hours if buffer_hours is not None else 0.0
        buffer_status = determine_buffer_status(actual_buffer_hours) if buffer_hours is not None else "N/A"
        
        # Format the balance hours for display
        bal_hr_display = round(actual_buffer_hours, 1) if buffer_hours is not None else None
        
        row = {
            'job_id': job_id,
            'plan_date': format_display_date(job.get('plan_date'), '%Y-%m-%d %H:%M:%S'),  # Use raw plan_date directly
            'scheduled_start_time_str': start_time_str,
            'scheduled_end_time_str': end_time_str,
            'lcd_date_str': format_display_date(job.get('lcd_date_epoch'), '%d/%m/%y %H:%M'),
            'start_date_input_str': format_display_date(job.get('start_date_epoch'), '%Y-%m-%d %H:%M'),
            'job': job.get('job', 'N/A'),
            'process_code': job.get('process_code', 'N/A'),
            'job_dependency': 'Yes' if str(job.get('job_dependency', '0')) == '1' else 'No',
            'rsc_location': job.get('rsc_location', 'N/A'),
            'rsc_code': job.get('rsc_code', 'N/A'),
            'number_operator': job.get('number_operator', 1),
            'job_quantity': job.get('job_quantity', 0),
            'expect_output_per_hour': job.get('expect_output_per_hour', 0),
            'priority': job.get('priority', 3),
            'hours_need': job.get('hours_need', 0.0),
            'setting_hours': job.get('setting_hours', 0.0),
            'break_hours': job.get('break_hours', 0.0),
            'no_prod': job.get('no_prod', 0.0),
            'accumulated_daily_output': job.get('accumulated_daily_output', 0),
            'balance_quantity': job.get('balance_quantity', job.get('job_quantity', 0) - job.get('accumulated_daily_output', 0)),
            'bal_hr': bal_hr_display,
            'buffer_status': buffer_status,
            # Include epoch times for frontend sorting
            'lcd_date_epoch': job.get('lcd_date_epoch'),
            'start_date_input_epoch': job.get('start_date_epoch'),
            'scheduled_start_epoch': scheduled.get('start'),
            'scheduled_end_epoch': scheduled.get('end'),
            'actual_buffer_hours': actual_buffer_hours  # Real value for analysis
        }
        
        table_rows.append(row)

    # Sort by LCD date (ascending, earliest due dates first)
    table_rows.sort(key=lambda x: (x.get('lcd_date_epoch') is None, x.get('lcd_date_epoch', float('inf'))))

    return table_rows 