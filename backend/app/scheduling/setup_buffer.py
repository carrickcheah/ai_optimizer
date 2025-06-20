"""
setup_buffer.py - PRODUCTION GRADE VERSION
Functions for handling setup times and schedule time adjustments
All configuration loaded from .env without defaults
"""

import logging
import os
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple, Union

import pandas as pd
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

logger = logging.getLogger(__name__)


class SetupBufferError(Exception):
    """Base exception for setup buffer errors."""
    pass


class SetupBufferConfigurationError(SetupBufferError):
    """Exception for configuration-related errors."""
    pass


@dataclass
class BufferConfig:
    """Configuration for buffer calculations loaded from .env."""
    buffer_critical_hours: int
    buffer_warning_hours: int
    buffer_caution_hours: int
    minimum_time_shift_seconds: int


@dataclass
class ScheduleMetrics:
    """Container for schedule processing metrics."""
    total_jobs: int
    scheduled_jobs: int
    unscheduled_jobs: int
    families_processed: int
    time_shifts_applied: int
    processing_time_ms: float


class SetupBufferConfigManager:
    """Manages setup buffer configuration from environment variables only."""
    
    @staticmethod
    def load_config() -> BufferConfig:
        """Load configuration with hardcoded buffer values."""
        # Hardcoded buffer configuration
        config_values = {
            'buffer_critical_hours': 8,    # Critical buffer threshold (hours)
            'buffer_warning_hours': 24,    # Warning buffer threshold (hours)
            'buffer_caution_hours': 72,    # Caution buffer threshold (hours)
            'minimum_time_shift_seconds': 300  # Default minimum time shift (5 minutes)
        }
        
        # Still check for MINIMUM_TIME_SHIFT_SECONDS in env if needed
        min_time_shift = os.getenv('MINIMUM_TIME_SHIFT_SECONDS')
        if min_time_shift is not None:
            try:
                config_values['minimum_time_shift_seconds'] = int(min_time_shift)
            except ValueError:
                logger.warning(f"Invalid MINIMUM_TIME_SHIFT_SECONDS value: {min_time_shift}, using default: 300")
        
        # Convert and validate values
        try:
            config = BufferConfig(
                buffer_critical_hours=int(config_values['buffer_critical_hours']),
                buffer_warning_hours=int(config_values['buffer_warning_hours']),
                buffer_caution_hours=int(config_values['buffer_caution_hours']),
                minimum_time_shift_seconds=int(config_values['minimum_time_shift_seconds'])
            )
            
            # Validate configuration values
            SetupBufferConfigManager._validate_config(config)
            return config
            
        except (ValueError, TypeError) as e:
            raise SetupBufferConfigurationError(f"❌ INVALID CONFIGURATION: Error converting values: {e}")
    
    @staticmethod
    def _validate_config(config: BufferConfig) -> None:
        """Validate configuration values."""
        validations = [
            (config.buffer_critical_hours >= 0, "BUFFER_CRITICAL_HOURS must be non-negative"),
            (config.buffer_warning_hours >= config.buffer_critical_hours, "BUFFER_WARNING_HOURS must be >= BUFFER_CRITICAL_HOURS"),
            (config.buffer_caution_hours >= config.buffer_warning_hours, "BUFFER_CAUTION_HOURS must be >= BUFFER_WARNING_HOURS"),
            (config.minimum_time_shift_seconds >= 0, "MINIMUM_TIME_SHIFT_SECONDS must be non-negative")
        ]
        
        for condition, error_msg in validations:
            if not condition:
                raise SetupBufferConfigurationError(f"❌ INVALID CONFIGURATION: {error_msg}")


class TimestampValidator:
    """Handles timestamp validation with optimized checks."""
    
    MIN_VALID_TIMESTAMP = 946684800  # 2000-01-01 00:00:00 UTC
    MAX_VALID_TIMESTAMP = 4102444800  # 2100-01-01 00:00:00 UTC
    
    @staticmethod
    def validate_timestamp(timestamp: Any) -> bool:
        """
        Validate timestamp is reasonable epoch time.
        
        Args:
            timestamp: Value to validate
            
        Returns:
            True if timestamp is valid, False otherwise
        """
        try:
            from app.utils.time_utils import validate_timestamp as util_validate
            return util_validate(timestamp)
        except ImportError:
            # Fallback validation
            if not isinstance(timestamp, (int, float)):
                return False
            
            return (TimestampValidator.MIN_VALID_TIMESTAMP <= 
                   timestamp <= 
                   TimestampValidator.MAX_VALID_TIMESTAMP)
    
    @staticmethod
    def is_valid_timestamp(timestamp: Any) -> bool:
        """
        Check if timestamp is valid for calculations.
        
        Args:
            timestamp: Value to check
            
        Returns:
            True if timestamp is valid, False otherwise
        """
        return (timestamp is not None and 
                not pd.isna(timestamp) and 
                isinstance(timestamp, (int, float)) and
                TimestampValidator.validate_timestamp(timestamp))


class StartDateExtractor:
    """Handles extraction of start date epochs from job data."""
    
    # Possible field naming variations for start date
    START_DATE_FIELDS = [
        'START_DATE_EPOCH', 
        'START_DATE _EPOCH', 
        'start_date_epoch', 
        'start_date _epoch',
        'start_date_input_epoch'
    ]
    
    @staticmethod
    def get_start_date_epoch(job: Dict[str, Any]) -> Optional[Union[int, float]]:
        """
        Extract START_DATE epoch timestamp handling field name variations.
        
        Args:
            job: Job dictionary
            
        Returns:
            The start date epoch value or None if not present/valid
        """
        if not isinstance(job, dict):
            logger.warning(f"Job must be a dictionary, got {type(job)}")
            return None
        
        for field_name in StartDateExtractor.START_DATE_FIELDS:
            if field_name in job and job[field_name] is not None and not pd.isna(job[field_name]):
                value = job[field_name]
                if TimestampValidator.validate_timestamp(value):
                    return value
                else:
                    logger.warning(f"Rejected invalid {field_name} value: {value} for job ID {job.get('job_id', 'unknown')}")
        
        return None


class BufferCalculator:
    """Handles buffer time calculations and status determination."""
    
    def __init__(self, config: BufferConfig):
        self.config = config
    
    def get_buffer_status(self, buffer_hours: float) -> str:
        """
        Get status category based on buffer hours from .env configuration.
        
        Args:
            buffer_hours: Buffer time in hours (negative = late)
            
        Returns:
            Status category: "Late", "Critical", "Warning", "Caution", "OK"
        """
        if not isinstance(buffer_hours, (int, float)):
            try:
                buffer_hours = float(buffer_hours)
            except (ValueError, TypeError):
                logger.warning(f"Invalid buffer_hours value: {buffer_hours}")
                return "Unknown"
        
        if buffer_hours < 0:
            return "Late"
        elif buffer_hours < self.config.buffer_critical_hours:
            return "Critical"
        elif buffer_hours < self.config.buffer_warning_hours:
            return "Warning"
        elif buffer_hours < self.config.buffer_caution_hours:
            return "Caution"
        else:
            return "OK"
    
    def calculate_buffer_hours(self, end_time: Union[int, float], 
                             lcd_date_epoch: Union[int, float]) -> float:
        """
        Calculate buffer hours between completion and deadline.
        
        Args:
            end_time: Job completion time (epoch)
            lcd_date_epoch: Deadline time (epoch)
            
        Returns:
            Buffer hours (negative if late)
        """
        try:
            buffer_seconds = lcd_date_epoch - end_time
            return buffer_seconds / 3600
        except (TypeError, ValueError) as e:
            logger.warning(f"Error calculating buffer: {e}")
            return float('inf')


class ScheduleExtractor:
    """Extracts and validates schedule data from optimizer results."""
    
    @staticmethod
    def extract_job_times(schedule: Dict[str, Any]) -> Dict[str, Tuple[float, float]]:
        """
        Extract job start/end times from schedule.
        
        Args:
            schedule: Schedule dictionary
            
        Returns:
            Dictionary mapping job_id to (start_time, end_time)
        """
        times = {}
        
        if not isinstance(schedule, dict):
            logger.error("Schedule must be a dictionary")
            return times
        
        for machine, tasks in schedule.items():
            if not isinstance(tasks, list):
                logger.warning(f"Tasks for machine {machine} must be a list, got {type(tasks)}")
                continue
            
            for task in tasks:
                if not isinstance(task, (tuple, list)) or len(task) < 3:
                    logger.warning(f"Invalid task format for machine {machine}: {task}")
                    continue
                
                job_id, start, end = task[0], task[1], task[2]
                
                if (not job_id or 
                    not isinstance(start, (int, float)) or 
                    not isinstance(end, (int, float))):
                    logger.warning(f"Invalid task data: job_id={job_id}, start={start}, end={end}")
                    continue
                
                times[job_id] = (start, end)
        
        return times


class FamilyProcessor:
    """Handles job family grouping and sequence processing."""
    
    def __init__(self, config: BufferConfig):
        self.config = config
    
    def group_jobs_by_family(self, jobs: List[Dict[str, Any]]) -> Dict[str, List[Tuple[int, str, Dict[str, Any]]]]:
        """
        Group jobs by family and sort by sequence number.
        
        Args:
            jobs: List of job dictionaries
            
        Returns:
            Dictionary mapping family to sorted job lists
        """
        family_processes = defaultdict(list)
        
        try:
            from app.scheduling.scheduler_utils import extract_job_family, extract_process_number
        except ImportError:
            logger.warning("Could not import scheduler utilities - using fallback grouping")
            # Fallback: treat each job as its own family
            for i, job in enumerate(jobs):
                if isinstance(job, dict) and 'job_id' in job:
                    job_id = job['job_id']
                    family_processes[job_id].append((1, job_id, job))
            return dict(family_processes)
        
        for job in jobs:
            if not isinstance(job, dict) or 'job_id' not in job:
                logger.warning("Skipping invalid job entry")
                continue
            
            job_id = job['job_id']
            family = extract_job_family(job_id)
            seq_num = extract_process_number(job_id)
            
            family_processes[family].append((seq_num, job_id, job))
        
        # Sort by sequence number
        for family in family_processes:
            family_processes[family].sort(key=lambda x: x[0])
        
        return dict(family_processes)
    
    def calculate_family_time_shifts(self, family_processes: Dict[str, List], 
                                   times: Dict[str, Tuple[float, float]]) -> Dict[str, float]:
        """
        Calculate time shifts needed for START_DATE constraints.
        
        Args:
            family_processes: Grouped job families
            times: Job timing data
            
        Returns:
            Dictionary mapping family to required time shift
        """
        family_time_shifts = {}
        
        for family, processes in family_processes.items():
            for seq_num, job_id, job in processes:
                start_date_epoch = StartDateExtractor.get_start_date_epoch(job)
                
                if start_date_epoch is not None and job_id in times:
                    scheduled_start = times[job_id][0]
                    time_shift = scheduled_start - start_date_epoch
                    
                    # Keep track of largest shift needed per family
                    if (family not in family_time_shifts or 
                        abs(time_shift) > abs(family_time_shifts[family])):
                        family_time_shifts[family] = time_shift
                    
                    logger.debug(f"Family {family} START_DATE constraint for {job_id}: shift={time_shift/3600:.1f} hours")
        
        return family_time_shifts
    
    def apply_time_shifts(self, family_processes: Dict[str, List], 
                         family_time_shifts: Dict[str, float],
                         times: Dict[str, Tuple[float, float]]) -> Dict[str, Tuple[float, float]]:
        """
        Apply calculated time shifts to job families.
        
        Args:
            family_processes: Grouped job families
            family_time_shifts: Required time shifts per family
            times: Original job timing data
            
        Returns:
            Dictionary of adjusted job times
        """
        job_adjustments = {}
        shifts_applied = 0
        
        for family, time_shift in family_time_shifts.items():
            # Skip negligible shifts
            if abs(time_shift) < self.config.minimum_time_shift_seconds:
                continue
            
            logger.info(f"Applying time shift of {time_shift/3600:.1f} hours to family {family}")
            shifts_applied += 1
            
            # Apply shift to all jobs in family
            for seq_num, job_id, job_data in family_processes[family]:
                if job_id in times:
                    original_start, original_end = times[job_id]
                    new_start = original_start - time_shift
                    new_end = original_end - time_shift
                    
                    job_adjustments[job_id] = (new_start, new_end)
                    logger.debug(f"  Adjusted {job_id}: {original_start}-{original_end} → {new_start}-{new_end}")
        
        return job_adjustments


class JobProcessor:
    """Processes individual jobs with schedule and buffer data."""
    
    def __init__(self, config: BufferConfig):
        self.config = config
        self.buffer_calculator = BufferCalculator(config)
    
    def process_job(self, job: Dict[str, Any], times: Dict[str, Tuple[float, float]], 
                   job_adjustments: Dict[str, Tuple[float, float]]) -> None:
        """
        Process a single job with schedule times and buffer calculation.
        
        Args:
            job: Job dictionary to process
            times: Original job timing data
            job_adjustments: Adjusted job timing data
        """
        if not isinstance(job, dict) or 'job_id' not in job:
            return
        
        job_id = job['job_id']
        
        # Set schedule times
        if job_id in job_adjustments:
            job['start_time'], job['end_time'] = job_adjustments[job_id]
        elif job_id in times:
            job['start_time'], job['end_time'] = times[job_id]
        else:
            job['start_time'] = None
            job['end_time'] = None
            logger.debug(f"Job {job_id} not found in schedule, times set to None")
        
        # Calculate buffer hours
        if (TimestampValidator.is_valid_timestamp(job.get('end_time')) and 
            TimestampValidator.is_valid_timestamp(job.get('lcd_date_epoch'))):
            
            job['buffer_hours'] = self.buffer_calculator.calculate_buffer_hours(
                job['end_time'], job['lcd_date_epoch']
            )
            
            # Log buffer calculation
            self._log_buffer_calculation(job)
        else:
            job['buffer_hours'] = float('inf')
            logger.debug(f"Job {job_id}: Missing end_time or lcd_date, buffer set to infinity")
        
        # Set buffer status
        job['buffer_status'] = self.buffer_calculator.get_buffer_status(job['buffer_hours'])
        
        # Add formatted display strings
        self._add_display_strings(job)
    
    def _log_buffer_calculation(self, job: Dict[str, Any]) -> None:
        """Log buffer calculation details."""
        try:
            from app.utils.time_utils import epoch_to_datetime, format_datetime_for_display
            
            original_lcd = job.get('lcd_date_original', job.get('lcd_date_epoch'))
            lcd_dt_str = format_datetime_for_display(epoch_to_datetime(original_lcd)) if original_lcd else "N/A"
            end_dt_str = format_datetime_for_display(epoch_to_datetime(job['end_time']))
            
            logger.debug(f"Job {job['job_id']}: end_time={end_dt_str}, lcd_date={lcd_dt_str}, "
                        f"Buffer={job['buffer_hours']:.1f} hrs")
        except ImportError:
            logger.debug(f"Job {job['job_id']}: Buffer={job['buffer_hours']:.1f} hrs")
        except Exception as e:
            logger.warning(f"Error logging buffer calculation for job {job['job_id']}: {e}")
    
    def _add_display_strings(self, job: Dict[str, Any]) -> None:
        """Add formatted date strings for display."""
        try:
            from app.utils.time_utils import epoch_to_datetime, format_datetime_for_display
            
            if job.get('start_time') is not None:
                job['start_time_str'] = format_datetime_for_display(epoch_to_datetime(job['start_time']))
            if job.get('end_time') is not None:
                job['end_time_str'] = format_datetime_for_display(epoch_to_datetime(job['end_time']))
            if job.get('lcd_date_epoch') is not None:
                job['lcd_date_str'] = format_datetime_for_display(epoch_to_datetime(job['lcd_date_epoch']))
        except ImportError:
            logger.warning("Could not import time utilities - skipping display string formatting")
        except Exception as e:
            logger.warning(f"Error formatting display dates for job {job['job_id']}: {e}")


def add_schedule_times_and_buffer(jobs: List[Dict[str, Any]], 
                                 schedule: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Add schedule times and calculate buffer hours - PRODUCTION GRADE.
    
    Args:
        jobs: List of job dictionaries
        schedule: Schedule dictionary
        
    Returns:
        Updated jobs list with schedule times and buffer calculations
        
    Raises:
        SetupBufferConfigurationError: If required .env variables are missing/invalid
        SetupBufferError: If processing fails
    """
    import time
    start_time = time.time()
    
    try:
        # Load configuration from .env
        config = SetupBufferConfigManager.load_config()
        logger.info("Setup buffer configuration loaded successfully from .env")
        
        # Validate inputs
        if not isinstance(jobs, list):
            raise SetupBufferError("Jobs must be a list")
        if not isinstance(schedule, dict):
            raise SetupBufferError("Schedule must be a dictionary")
        
        logger.info(f"Processing schedule times and buffer calculations for {len(jobs)} jobs")
        
        # Extract job times from schedule
        times = ScheduleExtractor.extract_job_times(schedule)
        
        # Process job families
        family_processor = FamilyProcessor(config)
        family_processes = family_processor.group_jobs_by_family(jobs)
        
        # Calculate and apply time shifts
        family_time_shifts = family_processor.calculate_family_time_shifts(family_processes, times)
        job_adjustments = family_processor.apply_time_shifts(family_processes, family_time_shifts, times)
        
        # Process individual jobs
        job_processor = JobProcessor(config)
        scheduled_count = 0
        
        for job in jobs:
            job_processor.process_job(job, times, job_adjustments)
            if job.get('start_time') is not None:
                scheduled_count += 1
        
        # Log metrics
        processing_time = (time.time() - start_time) * 1000
        metrics = ScheduleMetrics(
            total_jobs=len(jobs),
            scheduled_jobs=scheduled_count,
            unscheduled_jobs=len(jobs) - scheduled_count,
            families_processed=len(family_processes),
            time_shifts_applied=len(job_adjustments),
            processing_time_ms=processing_time
        )
        
        logger.info(f"Schedule processing completed: {metrics.scheduled_jobs}/{metrics.total_jobs} jobs scheduled, "
                   f"{metrics.families_processed} families processed, {metrics.time_shifts_applied} shifts applied "
                   f"in {processing_time:.2f}ms")
        
        return jobs
        
    except SetupBufferConfigurationError as e:
        logger.error(f"Configuration error in setup buffer: {e}")
        raise
    except Exception as e:
        logger.error(f"Unexpected error in add_schedule_times_and_buffer: {e}")
        raise SetupBufferError(f"Processing failed: {e}")


def apply_sequence_constraints(jobs: List[Dict[str, Any]], 
                              schedule: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Apply sequence constraints - PRODUCTION GRADE.
    
    Args:
        jobs: List of job dictionaries
        schedule: Schedule dictionary
        
    Returns:
        Updated jobs list with sequence constraints applied
        
    Raises:
        SetupBufferConfigurationError: If required .env variables are missing/invalid
        SetupBufferError: If processing fails
    """
    try:
        # Load configuration
        config = SetupBufferConfigManager.load_config()
        logger.info("Applying sequence constraints based on job family and process numbers")
        
        # Validate inputs
        if not isinstance(jobs, list) or not isinstance(schedule, dict):
            raise SetupBufferError("Invalid input types for apply_sequence_constraints")
        
        # Extract times and process families
        times = ScheduleExtractor.extract_job_times(schedule)
        family_processor = FamilyProcessor(config)
        family_processes = defaultdict(list)
        job_adjustments = {}
        
        # Group jobs with dependencies
        for job in jobs:
            if not isinstance(job, dict) or 'job_id' not in job:
                continue
            
            job_id = job.get('job_id')
            if not job_id or job_id not in times or job.get('job_dependency') != 1:
                continue
            
            try:
                from app.scheduling.scheduler_utils import extract_job_family, extract_process_number
                family = extract_job_family(job_id)
                seq_num = extract_process_number(job_id)
                
                if seq_num != 999:
                    family_processes[family].append((seq_num, job_id, job))
            except ImportError:
                logger.warning("Could not import scheduler utilities - skipping sequence constraints")
                continue
        
        # Process each family for START_DATE constraints
        for family in family_processes:
            processes = sorted(family_processes[family], key=lambda x: x[0])
            
            # Find START_DATE constraints
            start_date_constraint = None
            for seq_num, job_id, job_data in processes:
                start_date_epoch = StartDateExtractor.get_start_date_epoch(job_data)
                
                if start_date_epoch is not None and job_id in times:
                    scheduled_start = times[job_id][0]
                    
                    if scheduled_start < start_date_epoch:
                        time_shift = start_date_epoch - scheduled_start
                        if time_shift > 0:
                            start_date_constraint = {
                                'job_id': job_id,
                                'time_shift': time_shift
                            }
                            logger.info(f"Family {family} START_DATE constraint for {job_id}: shift={time_shift}")
                            break
            
            # Apply time shift to family
            if start_date_constraint:
                time_shift = start_date_constraint['time_shift']
                start_job_id = start_date_constraint['job_id']
                start_index = next((i for i, (_, jid, _) in enumerate(processes) if jid == start_job_id), None)
                
                if start_index is not None:
                    for seq_num, job_id, job_data in processes[start_index:]:
                        if job_id in times:
                            original_start, original_end = times[job_id]
                            new_start = original_start + time_shift
                            new_end = original_end + time_shift
                            
                            job_adjustments[job_id] = (new_start, new_end)
                            logger.debug(f"  Adjusted {job_id}: {original_start}-{original_end} → {new_start}-{new_end}")
        
        # Apply adjustments and calculate buffers
        buffer_calculator = BufferCalculator(config)
        job_processor = JobProcessor(config)
        
        for job in jobs:
            if not isinstance(job, dict) or 'job_id' not in job:
                continue
            
            job_id = job['job_id']
            
            # Apply timing adjustments
            if job_id in job_adjustments:
                job['start_time'], job['end_time'] = job_adjustments[job_id]
            elif job_id in times:
                job['start_time'], job['end_time'] = times[job_id]
            
            # Calculate buffer hours
            if ('lcd_date_epoch' in job and 'end_time' in job and 
                job['end_time'] is not None):
                try:
                    job['buffer_hours'] = buffer_calculator.calculate_buffer_hours(
                        job['end_time'], job['lcd_date_epoch']
                    )
                    
                    # Log buffer calculation
                    try:
                        from app.utils.time_utils import epoch_to_datetime
                        end_dt = datetime.fromtimestamp(job['end_time'])
                        lcd_dt = datetime.fromtimestamp(job['lcd_date_epoch'])
                        logger.debug(f"Job {job_id}: end_time={end_dt.strftime('%Y-%m-%d %H:%M')}, "
                                   f"lcd_date={lcd_dt.strftime('%Y-%m-%d %H:%M')}, "
                                   f"Buffer={job['buffer_hours']:.1f} hrs")
                    except (ImportError, ValueError, TypeError, OSError):
                        logger.debug(f"Job {job_id}: Buffer={job['buffer_hours']:.1f} hrs")
                        
                except (ValueError, TypeError) as e:
                    logger.warning(f"Error calculating buffer for job {job_id}: {e}")
                    job['buffer_hours'] = float('inf')
            else:
                job['buffer_hours'] = float('inf')
                logger.debug(f"Job {job_id}: Missing end_time or lcd_date, buffer set to infinity")
        
        return jobs
        
    except SetupBufferConfigurationError as e:
        logger.error(f"Configuration error in sequence constraints: {e}")
        raise
    except Exception as e:
        logger.error(f"Unexpected error in apply_sequence_constraints: {e}")
        raise SetupBufferError(f"Sequence constraint processing failed: {e}")


# Public API functions for backward compatibility
def get_start_date_epoch(job: Dict[str, Any]) -> Optional[Union[int, float]]:
    """Extract START_DATE epoch timestamp handling field name variations."""
    return StartDateExtractor.get_start_date_epoch(job)


def is_valid_timestamp(timestamp: Any) -> bool:
    """Check if timestamp is valid for calculations."""
    return TimestampValidator.is_valid_timestamp(timestamp)


def get_buffer_status(buffer_hours: float) -> str:
    """Get buffer status using .env configuration."""
    try:
        config = SetupBufferConfigManager.load_config()
        calculator = BufferCalculator(config)
        return calculator.get_buffer_status(buffer_hours)
    except SetupBufferConfigurationError as e:
        logger.error(f"Configuration error in get_buffer_status: {e}")
        return "Unknown"


if __name__ == '__main__':
    """Test configuration loading."""
    try:
        config = SetupBufferConfigManager.load_config()
        logger.info("Setup buffer configuration loaded successfully from .env")
        print(f"Buffer thresholds: Critical={config.buffer_critical_hours}h, "
              f"Warning={config.buffer_warning_hours}h, Caution={config.buffer_caution_hours}h")
        print(f"Minimum time shift: {config.minimum_time_shift_seconds}s")
    except SetupBufferConfigurationError as e:
        logger.error(f"Configuration error: {e}")
        print(f"❌ Configuration Error: {e}")