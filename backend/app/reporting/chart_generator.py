# backend/app/reporting/chart_generator.py
"""Production-grade chart data generator for manufacturing schedules with strict configuration."""

import logging
import re
import os
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Union
from dataclasses import dataclass
import pytz
from app.utils.time_utils import validate_timestamp
from app.api.fastapi_app import get_db_connection_from_pool

logger = logging.getLogger(__name__)

def normalize_schedule_format(schedule_output: Dict[str, List]) -> Dict[str, List]:
    """Normalize schedule output to 3-tuple format with strict validation."""
    if not isinstance(schedule_output, dict):
        raise ValueError(f"Schedule output must be a dictionary, got {type(schedule_output)}")
    
    if not schedule_output:
        raise ValueError("Schedule output is empty")
    
    normalized = {}
    total_normalized = 0
    
    for machine, jobs in schedule_output.items():
        if not isinstance(jobs, list):
            raise ValueError(f"Jobs for machine '{machine}' must be a list, got {type(jobs)}")
        
        normalized[machine] = []
        
        for job_tuple in jobs:
            if not isinstance(job_tuple, (list, tuple)) or len(job_tuple) < 3:
                raise ValueError(f"Job tuple must have at least 3 elements: {job_tuple}")
            
            # Extract only first 3 elements (job_id, start, end)
            normalized_tuple = (job_tuple[0], job_tuple[1], job_tuple[2])
            normalized[machine].append(normalized_tuple)
            total_normalized += 1
            logger.debug(f"Normalized job {job_tuple[0]} on {machine}")
    
    logger.info(f"✅ Normalized {total_normalized} jobs across {len(normalized)} machines")
    return normalized

@dataclass
class ChartConfig:
    """Chart configuration loaded from environment variables with strict validation."""
    
    # Time configuration
    timezone: str
    
    # Buffer thresholds
    buffer_critical_hours: float
    buffer_warning_hours: float
    buffer_caution_hours: float
    
    @classmethod
    def from_env(cls) -> 'ChartConfig':
        """Load configuration from environment variables with strict validation."""
        missing_vars = []
        invalid_vars = []
        
        def get_required_str_env(key: str) -> Optional[str]:
            """Get required string environment variable."""
            value = os.getenv(key)
            if value is None:
                missing_vars.append(key)
                return None
            return value.strip()
        
        def get_required_float_env(key: str) -> Optional[float]:
            """Get required float environment variable."""
            value = os.getenv(key)
            if value is None:
                missing_vars.append(key)
                return None
            
            try:
                return float(value)
            except (ValueError, TypeError):
                invalid_vars.append(f"{key}={value}")
                return None
        
        # Load required configuration
        timezone_str = 'Asia/Kuala_Lumpur'  # Hardcoded timezone
        buffer_critical = get_required_float_env('CHART_BUFFER_CRITICAL_HOURS')
        buffer_warning = get_required_float_env('CHART_BUFFER_WARNING_HOURS')
        buffer_caution = get_required_float_env('CHART_BUFFER_CAUTION_HOURS')
        
        # Check for critical errors
        if missing_vars:
            error_msg = f"❌ CRITICAL CHART CONFIG ERROR: Missing required environment variables: {', '.join(missing_vars)}"
            logger.error(error_msg)
            raise ValueError(error_msg)
        
        if invalid_vars:
            error_msg = f"❌ CRITICAL CHART CONFIG ERROR: Invalid environment variable values: {', '.join(invalid_vars)}"
            logger.error(error_msg)
            raise ValueError(error_msg)
        
        # Validate threshold logic
        if buffer_critical >= buffer_warning:
            error_msg = f"❌ CRITICAL CHART CONFIG ERROR: CHART_BUFFER_CRITICAL_HOURS ({buffer_critical}) must be less than CHART_BUFFER_WARNING_HOURS ({buffer_warning})"
            logger.error(error_msg)
            raise ValueError(error_msg)
        
        if buffer_warning >= buffer_caution:
            error_msg = f"❌ CRITICAL CHART CONFIG ERROR: CHART_BUFFER_WARNING_HOURS ({buffer_warning}) must be less than CHART_BUFFER_CAUTION_HOURS ({buffer_caution})"
            logger.error(error_msg)
            raise ValueError(error_msg)
        
        logger.info(f"✅ Successfully loaded chart configuration from .env")
        
        return cls(
            timezone=timezone_str,
            buffer_critical_hours=buffer_critical,
            buffer_warning_hours=buffer_warning,
            buffer_caution_hours=buffer_caution
        )

# Initialize configuration at module level
try:
    CHART_CONFIG = ChartConfig.from_env()
    TIMEZONE = pytz.timezone(CHART_CONFIG.timezone)
    logger.info(f"✅ Chart generator initialized with timezone: {CHART_CONFIG.timezone}")
except Exception as e:
    logger.error(f"❌ FAILED to initialize chart generator configuration: {e}")
    raise

SECONDS_PER_HOUR = 3600
SECONDS_PER_DAY = 86400

# Color mapping for priorities - these are fixed business rules
PRIORITY_COLORS = {
    'Priority 1 (Highest)': 'rgb(231, 76, 60)',   # Red
    'Priority 2 (High)': 'rgb(243, 156, 18)',     # Orange
    'Priority 3 (Medium)': 'rgb(41, 128, 185)',   # Blue
    'Priority 4 (Normal)': 'rgb(127, 255, 0)',    # Bright lime green
    'Priority 5 (Low)': 'rgb(149, 165, 166)'      # Gray
}

PRIORITY_LABELS_MAP = {
    1: 'Priority 1 (Highest)',
    2: 'Priority 2 (High)',
    3: 'Priority 3 (Medium)',
    4: 'Priority 4 (Normal)',
    5: 'Priority 5 (Low)',
}

# Buffer status color map - these are fixed business rules
BUFFER_COLORS = {
    'Late': '#f44336',      # Red
    'Critical': '#ff5722',  # Deep orange
    'Warning': '#ff9800',   # Orange
    'Caution': '#9c27b0',   # Purple
    'OK': '#7FFF00'         # Bright lime green (restored per user preference)
}

def safe_timestamp_to_datetime(timestamp: Union[int, float, str]) -> Optional[datetime]:
    """Safely convert timestamp to datetime with strict validation - NO FALLBACKS."""
    if not timestamp:
        return None

    try:
        # Handle string timestamps
        if isinstance(timestamp, str):
            try:
                timestamp = float(timestamp)
            except (ValueError, TypeError):
                logger.error(f"❌ INVALID TIMESTAMP: Cannot convert string '{timestamp}' to float")
                return None
        
        # Validate timestamp range - NO FALLBACKS
        if not validate_timestamp(timestamp):
            logger.error(f"❌ INVALID TIMESTAMP: Timestamp {timestamp} failed validation")
            return None
        
        # Reject unrealistic small values - NO FALLBACKS TO TODAY
        if 0 < timestamp < SECONDS_PER_DAY:
            logger.error(f"❌ INVALID TIMESTAMP: Timestamp {timestamp} appears to be seconds-of-day rather than epoch timestamp")
            return None
        
        # Standard conversion
        dt = datetime.fromtimestamp(timestamp, tz=TIMEZONE)
        
        # Reject 1970 dates as likely invalid - NO FALLBACKS
        if dt.year == 1970:
            logger.error(f"❌ INVALID TIMESTAMP: Timestamp {timestamp} converts to 1970 date, likely invalid")
            return None
        
        return dt
        
    except (ValueError, TypeError, OSError) as e:
        logger.error(f"❌ TIMESTAMP CONVERSION FAILED: {timestamp} - {e}")
        return None

def format_datetime_for_display(dt: Optional[datetime], format_str: str = '%Y-%m-%d %H:%M:%S') -> str:
    """Format datetime for display with strict validation."""
    if not dt or not isinstance(dt, datetime):
        return 'N/A'
    
    try:
        return dt.strftime(format_str)
    except (ValueError, TypeError) as e:
        logger.error(f"❌ DATETIME FORMATTING FAILED: {dt} with format {format_str} - {e}")
        return 'N/A'

def extract_job_family(job_id: str) -> str:
    """Extract job family from job ID with strict validation."""
    if not job_id or not isinstance(job_id, str):
        logger.warning(f"❌ INVALID JOB_ID: {job_id} is not a valid string")
        return 'Unknown'
    
    job_id = str(job_id).upper().strip()
    if not job_id:
        logger.warning(f"❌ EMPTY JOB_ID after processing")
        return 'Unknown'
    
    # Extract process code after first underscore
    parts = job_id.split('_', 1)
    process_code = parts[1] if len(parts) > 1 else job_id
    
    # Find family before -P pattern
    match = re.search(r'(.*?)-P\d+', process_code)
    result = match.group(1) if match else process_code.split('-P')[0]
    
    if not result or result == job_id:
        logger.debug(f"Could not extract job family from {job_id}, using full process code")
    
    return result if result else 'Unknown'

def extract_process_number(job_id: str) -> Optional[int]:
    """Extract process number from job ID with strict validation."""
    if not job_id or not isinstance(job_id, str):
        logger.warning(f"❌ INVALID JOB_ID for process extraction: {job_id}")
        return None
    
    match = re.search(r'P(\d{2})', str(job_id).upper())
    if not match:
        logger.debug(f"No process number found in job_id: {job_id}")
        return None
    
    try:
        return int(match.group(1))
    except (ValueError, AttributeError) as e:
        logger.error(f"❌ PROCESS NUMBER EXTRACTION FAILED for {job_id}: {e}")
        return None

def validate_schedule_data(schedule: Any) -> List[str]:
    """Validate schedule data structure with detailed error reporting."""
    errors = []
    
    if not isinstance(schedule, dict):
        errors.append(f"Schedule must be a dictionary, got {type(schedule).__name__}")
        return errors
    
    if not schedule:
        errors.append("Schedule dictionary is empty")
        return errors
    
    for machine, jobs in schedule.items():
        if not isinstance(jobs, list):
            errors.append(f"Jobs for machine '{machine}' must be a list, got {type(jobs).__name__}")
            continue
        
        for i, job in enumerate(jobs):
            if not isinstance(job, (list, tuple)):
                errors.append(f"Job {i} for machine '{machine}' must be a list or tuple, got {type(job).__name__}")
                continue
            
            if len(job) < 3:
                errors.append(f"Job {i} for machine '{machine}' must have at least 3 elements (job_id, start, end), got {len(job)}")
                continue
            
            job_id, start_time, end_time = job[0], job[1], job[2]
            
            if not job_id:
                errors.append(f"Job {i} for machine '{machine}' has empty job_id")
            
            if not isinstance(start_time, (int, float)) or not isinstance(end_time, (int, float)):
                errors.append(f"Job {i} for machine '{machine}' has invalid timestamp types: start={type(start_time)}, end={type(end_time)}")
                continue
            
            if end_time <= start_time:
                errors.append(f"Job {i} for machine '{machine}' has invalid timing: end ({end_time}) <= start ({start_time})")
            
            if start_time < 0 or end_time < 0:
                errors.append(f"Job {i} for machine '{machine}' has negative timestamps: start={start_time}, end={end_time}")
    
    return errors

def validate_jobs_data(jobs_data: Any) -> List[str]:
    """Validate jobs input data structure with detailed error reporting."""
    errors = []
    
    if not isinstance(jobs_data, list):
        errors.append(f"Jobs data must be a list, got {type(jobs_data).__name__}")
        return errors
    
    if not jobs_data:
        errors.append("Jobs data list is empty")
        return errors
    
    for i, job in enumerate(jobs_data):
        if not isinstance(job, dict):
            errors.append(f"Job {i} must be a dictionary, got {type(job).__name__}")
            continue
        
        if 'job_id' not in job:
            errors.append(f"Job {i} missing required 'job_id' field")
        elif not job['job_id']:
            errors.append(f"Job {i} has empty 'job_id'")
    
    return errors

def get_machine_name_lookup() -> Dict[str, str]:
    """Get machine name lookup dictionary with strict error handling."""
    machine_lookup = {}
    
    try:
        with get_db_connection_from_pool() as conn:
            cursor = conn.cursor(dictionary=True)
            
            cursor.execute("""
                SELECT DISTINCT 
                    jop.Machine_v as machine_code,
                    COALESCE(tm.MachineName_v, jop.Machine_v) as machine_name
                FROM tbl_jo_process jop
                LEFT JOIN tbl_machine tm ON (
                    tm.MachineName_v LIKE CONCAT('%', jop.Machine_v, '%') 
                    OR tm.machine_id_v = jop.Machine_v
                )
                INNER JOIN tbl_jo_txn jot ON jot.TxnId_i = jop.TxnId_i 
                WHERE jot.Void_c != 1 
                    AND jot.DocStatus_c != 'CP' 
                    AND jop.QtyStatus_c != 'FF'
                    AND jop.Machine_v IS NOT NULL
                    AND jop.Machine_v != ''
                    AND COALESCE(tm.MachineName_v, jop.Machine_v) != jop.Machine_v
                ORDER BY jop.Machine_v, tm.MachineName_v
            """)
            
            machines = cursor.fetchall()
            
            if not machines:
                logger.error("❌ CRITICAL DATABASE ERROR: No machine mappings found in database")
                cursor.close()
                return {}
            
            # Build lookup dictionary - prefer shorter, more specific names
            machine_groups = {}
            for machine in machines:
                code = str(machine['machine_code']).strip()
                name = str(machine['machine_name']).strip()
                
                if not code or not name or name == code:
                    continue
                
                if code not in machine_groups:
                    machine_groups[code] = []
                machine_groups[code].append(name)
            
            # For each machine code, pick the best representative name
            for code, names in machine_groups.items():
                if len(names) == 1:
                    machine_lookup[code] = names[0]
                else:
                    # Prefer names with specific patterns or shorter names
                    best_name = min(names, key=lambda n: (
                        len(n),  # Prefer shorter names
                        'MANUAL' in n,  # Avoid manual stations
                        'WS' in n,  # Prefer workshop stations last
                        not any(pattern in n for pattern in ['PP', 'PB', 'AD', 'AC'])
                    ))
                    machine_lookup[code] = best_name
            
            cursor.close()
            
    except Exception as e:
        logger.error(f"❌ CRITICAL DATABASE ERROR: Failed to load machine name lookup: {e}")
        return {}
    
    if len(machine_lookup) < 10:
        logger.error(f"❌ INSUFFICIENT MACHINE MAPPINGS: Only {len(machine_lookup)} machine name mappings found. This indicates a configuration or data problem.")
    else:
        logger.info(f"✅ Loaded machine name lookup for {len(machine_lookup)} machines")
    
    return machine_lookup

def calculate_buffer_hours(end_time: Union[int, float], due_date: Union[int, float]) -> Optional[float]:
    """Calculate buffer hours with strict validation."""
    try:
        if isinstance(end_time, datetime):
            end_numeric = end_time.timestamp()
        else:
            end_numeric = float(end_time)
        
        if isinstance(due_date, datetime):
            due_numeric = due_date.timestamp()
        else:
            due_numeric = float(due_date)
        
        # Validate timestamps
        if end_numeric <= 0 or due_numeric <= 0:
            logger.error(f"❌ INVALID TIMESTAMPS for buffer calculation: end={end_numeric}, due={due_numeric}")
            return None
        
        return (due_numeric - end_numeric) / SECONDS_PER_HOUR
        
    except (ValueError, TypeError) as e:
        logger.error(f"❌ BUFFER CALCULATION FAILED: end_time={end_time}, due_date={due_date} - {e}")
        return None

def determine_buffer_status(buffer_hours: Optional[float]) -> str:
    """Determine buffer status using configured thresholds with strict validation."""
    if buffer_hours is None:
        logger.warning("❌ BUFFER STATUS CALCULATION: buffer_hours is None")
        return "Unknown"
    
    try:
        if buffer_hours < 0:
            return "Late"
        elif buffer_hours < CHART_CONFIG.buffer_critical_hours:
            return "Critical"
        elif buffer_hours < CHART_CONFIG.buffer_warning_hours:
            return "Warning"
        elif buffer_hours < CHART_CONFIG.buffer_caution_hours:
            return "Caution"
        else:
            return "OK"
    except Exception as e:
        logger.error(f"❌ BUFFER STATUS DETERMINATION FAILED: buffer_hours={buffer_hours} - {e}")
        return "Unknown"

def prepare_gantt_data_priority_view(schedule: Dict[str, Any], jobs_input_data: List[Dict]) -> List[Dict]:
    """Prepare Gantt chart data for priority view with strict validation."""
    # Validate inputs
    schedule_errors = validate_schedule_data(schedule)
    jobs_errors = validate_jobs_data(jobs_input_data)
    
    if schedule_errors:
        logger.error(f"❌ SCHEDULE VALIDATION FAILED: {'; '.join(schedule_errors)}")
        return []
    
    if jobs_errors:
        logger.error(f"❌ JOBS DATA VALIDATION FAILED: {'; '.join(jobs_errors)}")
        return []
    
    gantt_data = []
    job_lookup = {job['job_id']: job for job in jobs_input_data}
    
    processed_jobs = 0
    failed_jobs = 0
    
    for machine, jobs in schedule.items():
        for job_tuple in jobs:
            job_id = job_tuple[0]
            start_epoch = job_tuple[1]
            end_epoch = job_tuple[2]
            
            if not all([job_id, start_epoch is not None, end_epoch is not None]):
                failed_jobs += 1
                logger.warning(f"❌ INVALID JOB TUPLE: machine={machine}, job={job_tuple}")
                continue

            job_details = job_lookup.get(job_id, {})
            if not job_details:
                failed_jobs += 1
                logger.warning(f"❌ JOB NOT FOUND in jobs_input_data: {job_id}")
                continue
            
            priority = job_details.get('priority')
            if priority is None:
                logger.warning(f"❌ MISSING PRIORITY for job {job_id}")
                failed_jobs += 1
                continue
            
            start_dt = safe_timestamp_to_datetime(start_epoch)
            end_dt = safe_timestamp_to_datetime(end_epoch)
            
            if not start_dt or not end_dt:
                failed_jobs += 1
                logger.warning(f"❌ TIMESTAMP CONVERSION FAILED for job {job_id}: start={start_epoch}, end={end_epoch}")
                continue
            
            # Calculate buffer status
            buffer_hours = None
            buffer_status = "Unknown"
            
            if job_details.get('lcd_date_epoch'):
                buffer_hours = calculate_buffer_hours(end_epoch, job_details['lcd_date_epoch'])
                if buffer_hours is not None:
                    buffer_status = determine_buffer_status(buffer_hours)
                else:
                    logger.warning(f"❌ BUFFER CALCULATION FAILED for job {job_id}")
    
            # Use special display for subcontractor jobs in priority view
            if str(machine) == 'SUBCONTRACTOR':
                color = '#dadada'  # Light grey for subcontractor work - matches frontend expectation
                resource_display = 'Subcontractor Work'
                buffer_label = 'Subcontractor'
            else:
                color = BUFFER_COLORS.get(buffer_status, '#808080')
                resource_display = machine
                buffer_label = buffer_status
            
            gantt_data.append({
                'Task': job_id,
                'Start': start_dt.isoformat(),
                'Finish': end_dt.isoformat(),
                'Resource': resource_display,
                'Priority': priority,
                'PriorityLabel': PRIORITY_LABELS_MAP.get(priority, f'Priority {priority}'),
                'BufferStatusLabel': buffer_label,
                'Color': color,
                'Job_Family': extract_job_family(job_id),
                'Process_Number': extract_process_number(job_id)
            })
            
            processed_jobs += 1
    
    if failed_jobs > 0:
        logger.warning(f"⚠️ GANTT DATA PREPARATION: {failed_jobs} jobs failed processing, {processed_jobs} jobs successful")
    else:
        logger.info(f"✅ GANTT DATA PREPARATION: {processed_jobs} jobs processed successfully")
    
    # Sort by priority then start time
    gantt_data.sort(key=lambda x: (x['Priority'], x['Start']))
    return gantt_data

def prepare_gantt_data_resource_view(schedule: Dict[str, Any], jobs_input_data: List[Dict]) -> List[Dict]:
    """Prepare Gantt chart data for resource view with strict validation."""
    # Validate inputs
    schedule_errors = validate_schedule_data(schedule)
    jobs_errors = validate_jobs_data(jobs_input_data)
    
    if schedule_errors:
        logger.error(f"❌ SCHEDULE VALIDATION FAILED: {'; '.join(schedule_errors)}")
        return []
    
    if jobs_errors:
        logger.error(f"❌ JOBS DATA VALIDATION FAILED: {'; '.join(jobs_errors)}")
        return []

    gantt_data = []
    job_lookup = {job['job_id']: job for job in jobs_input_data}
    
    # Get machine name lookup
    machine_name_lookup = get_machine_name_lookup()
    if not machine_name_lookup:
        logger.error("❌ CRITICAL ERROR: Failed to load machine name lookup, using machine codes")
    
    processed_jobs = 0
    failed_jobs = 0
    
    for machine, jobs in schedule.items():
        for job_tuple in jobs:
            if len(job_tuple) < 3:
                failed_jobs += 1
                logger.warning(f"❌ INVALID JOB TUPLE LENGTH: machine={machine}, job={job_tuple}")
                continue
                
            job_id = job_tuple[0]
            start_epoch = job_tuple[1]
            end_epoch = job_tuple[2]
            
            if not all([job_id, start_epoch is not None, end_epoch is not None]):
                failed_jobs += 1
                logger.warning(f"❌ INVALID JOB DATA: machine={machine}, job={job_tuple}")
                continue
                
            job_details = job_lookup.get(job_id, {})
            if not job_details:
                failed_jobs += 1
                logger.warning(f"❌ JOB NOT FOUND in jobs_input_data: {job_id}")
                continue
            
            priority = job_details.get('priority')
            if priority is None:
                logger.warning(f"❌ MISSING PRIORITY for job {job_id}")
                failed_jobs += 1
                continue
            
            start_dt = safe_timestamp_to_datetime(start_epoch)
            end_dt = safe_timestamp_to_datetime(end_epoch)
            
            if not start_dt or not end_dt:
                failed_jobs += 1
                logger.warning(f"❌ TIMESTAMP CONVERSION FAILED for job {job_id}: start={start_epoch}, end={end_epoch}")
                continue
            
            # Calculate buffer status
            buffer_hours = None
            buffer_status = "Unknown"
            
            if job_details.get('lcd_date_epoch'):
                buffer_hours = calculate_buffer_hours(end_epoch, job_details['lcd_date_epoch'])
                if buffer_hours is not None:
                    buffer_status = determine_buffer_status(buffer_hours)
                else:
                    logger.warning(f"❌ BUFFER CALCULATION FAILED for job {job_id}")
            
            # Get machine name from lookup, with special handling for SUBCONTRACTOR
            if str(machine) == 'SUBCONTRACTOR':
                machine_name = 'Subcontractor Work'
            else:
                machine_name = machine_name_lookup.get(str(machine))
                if machine_name is None:
                    machine_name = str(machine)  # Use machine code if no mapping found
                    logger.debug(f"No machine name mapping found for code: {machine}")
                
            # Use special color for subcontractor jobs
            if str(machine) == 'SUBCONTRACTOR':
                color = '#dadada'  # Light grey for subcontractor work - matches frontend expectation
                resource_label = 'Subcontractor Work'
            else:
                color = BUFFER_COLORS.get(buffer_status, '#808080')
                resource_label = machine_name
            
            gantt_data.append({
                'Task': job_id,
                'Start': start_dt.isoformat(),
                'Finish': end_dt.isoformat(),
                'Resource': resource_label,
                'Priority': priority,
                'PriorityLabel': PRIORITY_LABELS_MAP.get(priority, f'Priority {priority}'),
                'BufferStatusLabel': buffer_status if str(machine) != 'SUBCONTRACTOR' else 'Subcontractor',
                'Color': color,
                'Job_Family': extract_job_family(job_id),
                'Process_Number': extract_process_number(job_id)
            })
            
            processed_jobs += 1
    
    if failed_jobs > 0:
        logger.warning(f"⚠️ RESOURCE VIEW PREPARATION: {failed_jobs} jobs failed processing, {processed_jobs} jobs successful")
    else:
        logger.info(f"✅ RESOURCE VIEW PREPARATION: {processed_jobs} jobs processed successfully")
    
    # Sort by resource then start time
    gantt_data.sort(key=lambda x: (x['Resource'], x['Start']))
    return gantt_data

def format_display_date(value: Any, date_format: str = '%Y-%m-%d %H:%M') -> str:
    """Format various date inputs for display with strict validation."""
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
        logger.debug(f"❌ DATE FORMATTING FAILED: Could not parse value '{value}'")
        return 'N/A'
    
    # Ensure timezone awareness
    if dt.tzinfo is None:
        try:
            dt = TIMEZONE.localize(dt)
        except Exception as e:
            logger.error(f"❌ TIMEZONE LOCALIZATION FAILED: {dt} - {e}")
            return 'N/A'
    else:
        dt = dt.astimezone(TIMEZONE)
    
    return format_datetime_for_display(dt, date_format)

def prepare_detailed_schedule_table_data(schedule: Dict[str, Any], jobs_input_data: List[Dict]) -> List[Dict]:
    """Prepare detailed schedule table data with strict validation."""
    # Validate inputs
    schedule_errors = validate_schedule_data(schedule)
    jobs_errors = validate_jobs_data(jobs_input_data)
    
    if schedule_errors:
        logger.error(f"❌ SCHEDULE VALIDATION FAILED: {'; '.join(schedule_errors)}")
        return []
    
    if jobs_errors:
        logger.error(f"❌ JOBS DATA VALIDATION FAILED: {'; '.join(jobs_errors)}")
        return []
    
    # Create lookup for scheduled times
    scheduled_times = {}
    for machine, jobs in schedule.items():
        for job_tuple in jobs:
            if len(job_tuple) >= 3:
                job_id = job_tuple[0]
                start_time = job_tuple[1]
                end_time = job_tuple[2]
                
                if not job_id:
                    logger.warning(f"❌ EMPTY JOB_ID in scheduled times for machine {machine}")
                    continue
                
                scheduled_times[job_id] = {
                    'start': start_time,
                    'end': end_time,
                    'machine': machine
                }
    
    table_rows = []
    processed_jobs = 0
    failed_jobs = 0
    
    for job in jobs_input_data:
        job_id = job.get('job_id')
        if not job_id:
            failed_jobs += 1
            logger.warning(f"❌ JOB MISSING job_id: {job}")
            continue
        
        scheduled = scheduled_times.get(job_id, {})
        
        # Format times with strict validation
        start_time_str = format_display_date(scheduled.get('start'), '%Y-%m-%d %H:%M:%S') if scheduled.get('start') else 'N/A'
        end_time_str = format_display_date(scheduled.get('end'), '%Y-%m-%d %H:%M:%S') if scheduled.get('end') else 'N/A'
        
        # Calculate buffer with strict validation - NO DEFAULTS OR FALLBACKS
        buffer_hours = None
        buffer_status = "N/A"
        
        if scheduled.get('end') and job.get('lcd_date_epoch'):
            buffer_hours = calculate_buffer_hours(scheduled['end'], job['lcd_date_epoch'])
            if buffer_hours is not None:
                buffer_status = determine_buffer_status(buffer_hours)
        
        # Format balance hours for display
        bal_hr_display = round(buffer_hours, 1) if buffer_hours is not None else None
        
        try:
            row = {
                'job_id': job_id,
                'plan_date': format_display_date(job.get('plan_date'), '%Y-%m-%d %H:%M:%S'),
                'scheduled_start_time_str': start_time_str,
                'scheduled_end_time_str': end_time_str,
                'lcd_date_str': format_display_date(job.get('lcd_date_epoch'), '%d/%m/%y %H:%M'),
                'start_date_input_str': format_display_date(job.get('start_date_epoch'), '%Y-%m-%d %H:%M'),
                'job': job.get('job', 'N/A'),
                'process_code': job.get('process_code', 'N/A'),
                'job_dependency': 'Yes' if str(job.get('job_dependency', '0')) == '1' else 'No',
                'rsc_location': job.get('rsc_location', 'N/A'),
                'MachineName_v': job.get('MachineName_v', 'N/A'),
                'number_operator': job.get('number_operator', 1),
                'job_quantity': job.get('job_quantity', 0),
                'expect_output_per_hour': job.get('expect_output_per_hour', 0),
                'priority': job.get('priority'),
                'hours_need': job.get('hours_need', 0.0),
                'setting_hours': job.get('setting_hours', 0.0),
                'break_hours': job.get('break_hours', 0.0),
                'no_prod': job.get('no_prod', 0.0),
                'accumulated_daily_output': job.get('accumulated_daily_output', 0),
                'balance_quantity': job.get('balance_quantity', job.get('job_quantity', 0) - job.get('accumulated_daily_output', 0)),
                'bal_hr': bal_hr_display,
                'buffer_status': buffer_status,
                # Include machine information from schedule
                'machine_name': scheduled.get('machine', job.get('MachineName_v', 'N/A')),
                # Include epoch times for frontend sorting
                'lcd_date_epoch': job.get('lcd_date_epoch'),
                'start_date_input_epoch': job.get('start_date_epoch'),
                'scheduled_start_epoch': scheduled.get('start'),
                'scheduled_end_epoch': scheduled.get('end'),
                'actual_buffer_hours': buffer_hours
            }
            
            # Validate critical fields
            if row['priority'] is None:
                logger.warning(f"❌ MISSING PRIORITY for job {job_id}")
                failed_jobs += 1
                continue
            
            if not isinstance(row['priority'], (int, float)) or row['priority'] < 1 or row['priority'] > 5:
                logger.warning(f"❌ INVALID PRIORITY VALUE for job {job_id}: {row['priority']}")
                failed_jobs += 1
                continue
            
            table_rows.append(row)
            processed_jobs += 1
            
        except Exception as e:
            failed_jobs += 1
            logger.error(f"❌ FAILED to process job {job_id}: {e}")
            continue
            
        except Exception as e:
            failed_jobs += 1
            logger.error(f"❌ FAILED to process job {job_id}: {e}")
            continue

    if failed_jobs > 0:
        logger.warning(f"⚠️ TABLE DATA PREPARATION: {failed_jobs} jobs failed processing, {processed_jobs} jobs successful")
    else:
        logger.info(f"✅ TABLE DATA PREPARATION: {processed_jobs} jobs processed successfully")

    # Sort by LCD date (ascending, earliest due dates first) with strict validation
    def sort_key(row):
        lcd_epoch = row.get('lcd_date_epoch')
        if lcd_epoch is None:
            return (1, float('inf'))  # Put jobs without LCD at end
        try:
            return (0, float(lcd_epoch))
        except (ValueError, TypeError):
            logger.warning(f"❌ INVALID LCD_DATE_EPOCH for sorting: {lcd_epoch}")
            return (1, float('inf'))
    
    table_rows.sort(key=sort_key)
    
    return table_rows

def validate_chart_data_integrity(gantt_data: List[Dict]) -> List[str]:
    """Validate the integrity of generated chart data."""
    errors = []
    
    if not gantt_data:
        errors.append("Generated chart data is empty")
        return errors
    
    required_fields = ['Task', 'Start', 'Finish', 'Resource', 'Priority', 'PriorityLabel', 'BufferStatusLabel']
    
    for i, item in enumerate(gantt_data):
        if not isinstance(item, dict):
            errors.append(f"Chart item {i} is not a dictionary")
            continue
        
        for field in required_fields:
            if field not in item:
                errors.append(f"Chart item {i} missing required field: {field}")
            elif item[field] is None:
                errors.append(f"Chart item {i} has None value for field: {field}")
        
        # Validate datetime format
        try:
            datetime.fromisoformat(item.get('Start', '').replace('Z', '+00:00'))
        except (ValueError, AttributeError):
            errors.append(f"Chart item {i} has invalid Start datetime: {item.get('Start')}")
        
        try:
            datetime.fromisoformat(item.get('Finish', '').replace('Z', '+00:00'))
        except (ValueError, AttributeError):
            errors.append(f"Chart item {i} has invalid Finish datetime: {item.get('Finish')}")
        
        # Validate priority
        priority = item.get('Priority')
        if not isinstance(priority, (int, float)) or priority < 1 or priority > 5:
            errors.append(f"Chart item {i} has invalid priority: {priority}")
    
    return errors

def get_chart_configuration() -> Dict[str, Any]:
    """Get current chart configuration for debugging/monitoring."""
    return {
        'timezone': CHART_CONFIG.timezone,
        'buffer_thresholds': {
            'critical_hours': CHART_CONFIG.buffer_critical_hours,
            'warning_hours': CHART_CONFIG.buffer_warning_hours,
            'caution_hours': CHART_CONFIG.buffer_caution_hours
        },
        'priority_colors': PRIORITY_COLORS,
        'buffer_colors': BUFFER_COLORS,
        'validation_enabled': True,
        'fallback_handling': 'strict_no_fallbacks'
    }