"""
scheduler_utils.py - PRODUCTION GRADE VERSION
Helper functions for scheduling with optimized performance and error handling
"""

import logging
import re
from collections import defaultdict
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple, Union

logger = logging.getLogger(__name__)

# Import dependency manager for complex dependencies
try:
    from .dependency_manager import get_dependency_manager
    COMPLEX_DEPENDENCIES_ENABLED = True
except ImportError:
    COMPLEX_DEPENDENCIES_ENABLED = False
    logger.warning("Complex dependency support not available - using sequential dependencies only")

# Compiled regex patterns for performance
PROCESS_PATTERN = re.compile(r'(\d+)/\d+$')
FAMILY_PATTERN = re.compile(r'(.*?)-(?:P?\d+)(?:/\d+)?$')
FAMILY_SPLIT_PATTERN = re.compile(r'-(?:P?\d+)(?:/\d+)?$')


class SchedulerUtilsError(Exception):
    """Base exception for scheduler utilities errors."""
    pass


class JobValidationError(SchedulerUtilsError):
    """Exception for job validation errors."""
    pass


@dataclass
class JobMetrics:
    """Container for job processing metrics."""
    total_jobs: int
    valid_jobs: int
    invalid_jobs: int
    processing_time_ms: float


@dataclass
class ScheduleMetrics:
    """Container for schedule performance metrics."""
    total_jobs: int
    total_machines: int
    makespan_hours: float
    average_utilization: float
    machine_utilization: Dict[str, float]
    earliest_start: float
    latest_end: float


class ProcessExtractor:
    """Optimized process number extraction with caching."""
    
    _cache: Dict[str, int] = {}
    
    @classmethod
    def extract_process_number(cls, job_id: str) -> int:
        """
        Extract process sequence number with caching for performance.
        
        Args:
            job_id: Job identifier string
            
        Returns:
            Process sequence number or 999 if parsing fails
        """
        if not isinstance(job_id, str):
            logger.warning(f"job_id must be string, got {type(job_id)}: {job_id}")
            return 999
        
        # Check cache first
        if job_id in cls._cache:
            return cls._cache[job_id]
        
        try:
            process_code = job_id.split('_', 1)[1]
        except IndexError:
            logger.warning(f"Could not extract PROCESS_CODE from job_id {job_id}")
            cls._cache[job_id] = 999
            return 999
        
        # Try common patterns in order of specificity
        # 1) Explicit -P## marker (e.g., CD02-P01) - must be after hyphen to avoid matching CP08
        p_marker = re.search(r'-P(\d+)', process_code, re.IGNORECASE)
        if p_marker:
            seq = int(p_marker.group(1))
            cls._cache[job_id] = seq
            logger.debug(f"Extracted P-sequence {seq} from job_id {job_id}")
            return seq

        # 2) Legacy form with total count (e.g., CD02-01/3)
        match = PROCESS_PATTERN.search(process_code)
        if match:
            seq = int(match.group(1))
            cls._cache[job_id] = seq
            logger.debug(f"Extracted legacy sequence {seq} from job_id {job_id}")
            return seq

        # 3) Simple hyphen-number at end (e.g., CD02-01)
        hyphen_num = re.search(r'-(\d+)(?:$|[^0-9])', process_code)
        if hyphen_num:
            seq = int(hyphen_num.group(1))
            cls._cache[job_id] = seq
            logger.debug(f"Extracted simple sequence {seq} from job_id {job_id}")
            return seq
        
        cls._cache[job_id] = 999
        return 999
    
    @classmethod
    def clear_cache(cls) -> None:
        """Clear the process number cache."""
        cls._cache.clear()


class FamilyExtractor:
    """Optimized family extraction with caching."""
    
    _cache: Dict[str, str] = {}
    
    @classmethod
    def extract_job_family(cls, job_id: str, job_id_suffix: Optional[str] = None) -> str:
        """
        Extract job family with caching for performance.
        
        Args:
            job_id: Job identifier string
            job_id_suffix: Optional suffix to append
            
        Returns:
            Job family string
        """
        if not isinstance(job_id, str):
            logger.warning(f"job_id must be string, got {type(job_id)}: {job_id}")
            family = str(job_id)
            return f"{family}_{job_id_suffix}" if job_id_suffix else family
        
        # Create cache key
        cache_key = f"{job_id}|{job_id_suffix or ''}"
        if cache_key in cls._cache:
            return cls._cache[cache_key]
        
        try:
            process_code = job_id.split('_', 1)[1] if '_' in job_id else job_id
        except IndexError:
            logger.warning(f"Could not extract process_code from job_id {job_id}")
            family = job_id
            result = f"{family}_{job_id_suffix}" if job_id_suffix else family
            cls._cache[cache_key] = result
            return result
        
        process_code = process_code.upper()
        
        # Prefer explicit '-P##' split if present
        if '-P' in process_code.upper():
            family = process_code.upper().split('-P', 1)[0]
            logger.debug(f"Extracted family {family} from {job_id} (-P pattern)")
        else:
            # Use compiled regex for performance (supports -01/3, -P01/3, -01)
            match = FAMILY_PATTERN.search(process_code)
            if match:
                family = match.group(1)
                logger.debug(f"Extracted family {family} from {job_id}")
            else:
                # Fallback to split method
                if FAMILY_SPLIT_PATTERN.search(process_code):
                    parts = FAMILY_SPLIT_PATTERN.split(process_code)
                    family = parts[0] if parts else process_code
                    logger.debug(f"Extracted family {family} from {job_id} (using split)")
                else:
                    logger.warning(f"Could not extract family from {job_id}, using full code")
                    family = process_code
        
        result = f"{family}_{job_id_suffix}" if job_id_suffix else family
        cls._cache[cache_key] = result
        return result
    
    @classmethod
    def clear_cache(cls) -> None:
        """Clear the family extraction cache."""
        cls._cache.clear()


class JobValidator:
    """Optimized job validation with batch processing."""
    
    # Required fields for job validation
    REQUIRED_FIELDS = {'job_id'}
    
    # Numeric fields that should be validated
    NUMERIC_FIELDS = {
        'hours_need', 'priority', 'processing_time', 'setup_time', 
        'break_time', 'day_need', 'no_prod', 'job_quantity', 'expect_output_per_hour'
    }
    
    @staticmethod
    def validate_job_data(job: Dict[str, Any]) -> bool:
        """
        Optimized job validation.
        
        Args:
            job: Job dictionary to validate
            
        Returns:
            True if job is valid, False otherwise
        """
        if not isinstance(job, dict):
            logger.error(f"Job must be a dictionary, got {type(job)}")
            return False
        
        # Check required fields
        for field in JobValidator.REQUIRED_FIELDS:
            if field not in job or job[field] is None:
                logger.error(f"Job missing required field '{field}': {job}")
                return False
        
        # Validate job_id
        job_id = job['job_id']
        if not isinstance(job_id, str) or not job_id.strip():
            logger.error(f"Invalid job_id: {job_id}")
            return False
        
        # Validate numeric fields (non-blocking)
        for field in JobValidator.NUMERIC_FIELDS:
            if field in job and job[field] is not None:
                try:
                    float(job[field])
                except (ValueError, TypeError):
                    logger.warning(f"Invalid numeric value for {field} in job {job_id}: {job[field]}")
        
        return True
    
    @staticmethod
    def validate_jobs_batch(jobs: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], JobMetrics]:
        """
        Batch validate multiple jobs for performance.
        
        Args:
            jobs: List of job dictionaries
            
        Returns:
            Tuple of (valid_jobs, metrics)
        """
        import time
        start_time = time.time()
        
        valid_jobs = []
        invalid_count = 0
        
        for job in jobs:
            if JobValidator.validate_job_data(job):
                valid_jobs.append(job)
            else:
                invalid_count += 1
        
        processing_time = (time.time() - start_time) * 1000  # Convert to ms
        
        metrics = JobMetrics(
            total_jobs=len(jobs),
            valid_jobs=len(valid_jobs),
            invalid_jobs=invalid_count,
            processing_time_ms=processing_time
        )
        
        logger.info(f"Batch validation: {len(valid_jobs)}/{len(jobs)} valid jobs in {processing_time:.2f}ms")
        return valid_jobs, metrics


class JobNormalizer:
    """Optimized job field normalization."""
    
    # Field mappings for normalization
    FIELD_MAPPINGS = {
        'JOB_ID': 'job_id',
        'RSC_CODE': 'MachineName_v',
        'HOURS_NEED': 'hours_need',
        'DAY_NEED': 'day_need',
        'PRIORITY': 'priority',
        'PROCESSING_TIME': 'processing_time',
        'SETUP_TIME': 'setup_time',
        'BREAK_TIME': 'break_time',
        'NO_PROD': 'no_prod',
        'JOB_QUANTITY': 'job_quantity',
        'EXPECT_OUTPUT_PER_HOUR': 'expect_output_per_hour'
    }
    
    # Default values for missing fields
    DEFAULTS = {
        'priority': 3,
        'day_need': None,
        'processing_time': None,
        'setup_time': 0,
        'break_time': 0,
        'no_prod': 0
    }
    
    @staticmethod
    def normalize_job_fields(job: Dict[str, Any]) -> Dict[str, Any]:
        """
        Optimized job field normalization.
        
        Args:
            job: Job dictionary to normalize
            
        Returns:
            Normalized job dictionary
        """
        if not isinstance(job, dict):
            logger.error("Job must be a dictionary")
            return {}
        
        # Create normalized copy
        normalized_job = job.copy()
        
        # Apply field mappings efficiently
        for upper_field, lower_field in JobNormalizer.FIELD_MAPPINGS.items():
            if upper_field in normalized_job and lower_field not in normalized_job:
                normalized_job[lower_field] = normalized_job[upper_field]
        
        # Normalize numeric fields in batch
        for field in JobValidator.NUMERIC_FIELDS:
            if field in normalized_job and normalized_job[field] is not None:
                try:
                    normalized_job[field] = float(normalized_job[field])
                except (ValueError, TypeError):
                    job_id = normalized_job.get('job_id', 'Unknown')
                    logger.warning(f"Could not convert {field} to float for job {job_id}: {normalized_job[field]}")
        
        # Apply defaults efficiently
        for field, default_value in JobNormalizer.DEFAULTS.items():
            if field not in normalized_job or normalized_job[field] is None:
                normalized_job[field] = default_value
        
        # Validate hours_need requirement
        hours_need = normalized_job.get('hours_need')
        if not hours_need or hours_need <= 0:
            job_id = normalized_job.get('job_id', 'Unknown')
            logger.error(f"❌ MISSING HOURS_NEED for job {job_id} - unable to schedule without duration")
            normalized_job['hours_need'] = None
        
        return normalized_job
    
    @staticmethod
    def normalize_jobs_batch(jobs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Batch normalize multiple jobs for performance.
        
        Args:
            jobs: List of job dictionaries
            
        Returns:
            List of normalized job dictionaries
        """
        return [JobNormalizer.normalize_job_fields(job) for job in jobs]


class TimestampValidator:
    """Optimized timestamp validation."""
    
    MIN_VALID_TIMESTAMP = 1000  # Minimum valid timestamp
    
    @staticmethod
    def is_valid_timestamp(timestamp: Any, job_id: str = "Unknown", 
                          machine: str = "Unknown", field_name: str = "timestamp") -> bool:
        """
        Validate timestamp efficiently.
        
        Args:
            timestamp: Value to validate
            job_id: Job ID for logging
            machine: Machine name for logging
            field_name: Field name for logging
            
        Returns:
            True if timestamp is valid, False otherwise
        """
        if not isinstance(timestamp, (int, float)):
            logger.error(f"Invalid {field_name} type for job {job_id} on {machine}: {type(timestamp)}")
            return False
        
        if timestamp < TimestampValidator.MIN_VALID_TIMESTAMP:
            logger.error(f"Invalid {field_name}: {timestamp} for job {job_id} on {machine}. Value too small.")
            return False
        
        return True


class ScheduleConverter:
    """Optimized schedule format conversion."""
    
    @staticmethod
    def convert_cpsat_to_greedy_format(cpsat_schedule: Dict[str, Any]) -> Dict[str, List[Tuple]]:
        """
        Optimized CP-SAT to greedy format conversion.
        
        Args:
            cpsat_schedule: CP-SAT schedule dictionary
            
        Returns:
            Greedy format schedule
        """
        logger.info("Converting CP-SAT schedule format to greedy format")
        
        if not isinstance(cpsat_schedule, dict):
            logger.error(f"Schedule must be a dictionary, got {type(cpsat_schedule)}")
            return {}
        
        # Fast path: already in greedy format
        if '_metadata' not in cpsat_schedule:
            return ScheduleConverter._normalize_greedy_format(cpsat_schedule)
        
        # Convert from CP-SAT format
        greedy_format = {}
        processed_jobs = 0
        
        for job_id, details in cpsat_schedule.items():
            if job_id == '_metadata':
                continue
            
            if not isinstance(details, dict):
                logger.warning(f"Invalid details format for job {job_id}: {details}")
                continue
            
            # Extract required fields
            machine = details.get('machine')
            start = details.get('start')
            end = details.get('end')
            priority = details.get('priority', 3)
            
            if not all(x is not None for x in [machine, start, end]):
                logger.warning(f"Missing fields for job {job_id}: machine={machine}, start={start}, end={end}")
                continue
            
            # Validate timestamps
            if not TimestampValidator.is_valid_timestamp(start, job_id, machine, "start"):
                continue
            if not TimestampValidator.is_valid_timestamp(end, job_id, machine, "end"):
                continue
            
            # Add to schedule
            if machine not in greedy_format:
                greedy_format[machine] = []
            
            greedy_format[machine].append((job_id, start, end, priority, {}))
            processed_jobs += 1
        
        logger.info(f"Converted CP-SAT schedule: {processed_jobs} tasks scheduled")
        return greedy_format
    
    @staticmethod
    def _normalize_greedy_format(schedule: Dict[str, List]) -> Dict[str, List[Tuple]]:
        """Normalize greedy format to ensure 5-tuple structure."""
        normalized = {}
        
        for machine, tasks in schedule.items():
            if not isinstance(tasks, list):
                logger.warning(f"Tasks for machine {machine} must be a list, got {type(tasks)}")
                continue
            
            normalized[machine] = []
            for task in tasks:
                if not isinstance(task, (tuple, list)) or len(task) < 3:
                    logger.warning(f"Invalid task format for machine {machine}: {task}")
                    continue
                
                # Ensure 5-tuple format
                if len(task) == 3:
                    job_id, start, end = task
                    normalized[machine].append((job_id, start, end, 3, {}))
                elif len(task) == 4:
                    job_id, start, end, priority = task
                    normalized[machine].append((job_id, start, end, priority, {}))
                elif len(task) == 5:
                    normalized[machine].append(task)
                else:
                    job_id, start, end = task[:3]
                    priority = task[3] if len(task) > 3 else 3
                    normalized[machine].append((job_id, start, end, priority, {}))
        
        return normalized


class JobGrouper:
    """Optimized job grouping by family."""
    
    @staticmethod
    def group_jobs_by_family(jobs: List[Dict[str, Any]]) -> Dict[str, List[Tuple[int, str, Dict[str, Any]]]]:
        """
        Optimized job grouping by family.
        
        Args:
            jobs: List of job dictionaries
            
        Returns:
            Dictionary mapping families to sorted job lists
        """
        job_families = defaultdict(list)
        
        # Use dependency manager if available
        dep_manager = None
        if COMPLEX_DEPENDENCIES_ENABLED:
            dep_manager = get_dependency_manager()
            # Let dependency manager learn from job data
            dep_manager.derive_sequence_from_jobs(jobs)
        
        for job in jobs:
            if not JobValidator.validate_job_data(job):
                continue
            
            job_id = job['job_id']
            family = FamilyExtractor.extract_job_family(job_id)
            process_num = ProcessExtractor.extract_process_number(job_id)
            
            job_families[family].append((process_num, job_id, job))
        
        # Sort by sequence position if using dependency manager
        if dep_manager:
            for family, family_jobs in job_families.items():
                # Create a mapping of job_id to sequence position
                position_map = {}
                
                for process_num, job_id, job_item in family_jobs:
                    _, process_code, _ = dep_manager.extract_process_info(job_id)
                    
                    # Count occurrences of this process
                    process_count = 0
                    for pn, jid, _ in family_jobs:
                        if jid == job_id:
                            break
                        _, pc, _ = dep_manager.extract_process_info(jid)
                        if pc == process_code:
                            process_count += 1
                    
                    occurrence = process_count + 1
                    seq_position = dep_manager.get_sequence_position(family, process_code, occurrence)
                    position_map[job_id] = seq_position if seq_position else 999
                
                # Sort by sequence position
                family_jobs.sort(key=lambda x: (position_map.get(x[1], 999), x[0]))
        else:
            # Fallback: Sort by process number efficiently
            for family_jobs in job_families.values():
                family_jobs.sort(key=lambda x: x[0])
        
        return dict(job_families)


class ScheduleAnalyzer:
    """Optimized schedule analysis and metrics calculation."""
    
    @staticmethod
    def calculate_schedule_metrics(schedule: Dict[str, List[Tuple]]) -> ScheduleMetrics:
        """
        Optimized schedule metrics calculation.
        
        Args:
            schedule: Schedule dictionary
            
        Returns:
            ScheduleMetrics object
        """
        if not isinstance(schedule, dict):
            return ScheduleMetrics(0, 0, 0, 0, {}, 0, 0)
        
        total_jobs = 0
        total_machines = len(schedule)
        machine_utilization = {}
        earliest_start = float('inf')
        latest_end = 0
        
        for machine, tasks in schedule.items():
            if not isinstance(tasks, list) or not tasks:
                machine_utilization[machine] = 0
                continue
            
            machine_jobs = len(tasks)
            total_jobs += machine_jobs
            
            # Extract start and end times efficiently
            starts = []
            ends = []
            total_task_time = 0
            
            for task in tasks:
                if len(task) >= 3:
                    start, end = task[1], task[2]
                    starts.append(start)
                    ends.append(end)
                    total_task_time += end - start
            
            if starts and ends:
                machine_start = min(starts)
                machine_end = max(ends)
                
                earliest_start = min(earliest_start, machine_start)
                latest_end = max(latest_end, machine_end)
                
                # Calculate utilization
                if machine_end > machine_start:
                    utilization = total_task_time / (machine_end - machine_start)
                    machine_utilization[machine] = min(utilization, 1.0)
                else:
                    machine_utilization[machine] = 0
            else:
                machine_utilization[machine] = 0
        
        # Calculate final metrics
        makespan = latest_end - earliest_start if earliest_start != float('inf') else 0
        avg_utilization = (
            sum(machine_utilization.values()) / len(machine_utilization) 
            if machine_utilization else 0
        )
        
        return ScheduleMetrics(
            total_jobs=total_jobs,
            total_machines=total_machines,
            makespan_hours=makespan / 3600,
            average_utilization=avg_utilization,
            machine_utilization=machine_utilization,
            earliest_start=earliest_start if earliest_start != float('inf') else 0,
            latest_end=latest_end
        )


# Public API functions for backward compatibility
def extract_process_number(job_id: str) -> int:
    """Extract process number from job ID."""
    return ProcessExtractor.extract_process_number(job_id)


def extract_job_family(job_id: str, job_id_suffix: Optional[str] = None) -> str:
    """Extract job family from job ID."""
    return FamilyExtractor.extract_job_family(job_id, job_id_suffix)


def validate_job_data(job: Dict[str, Any]) -> bool:
    """Validate job data."""
    return JobValidator.validate_job_data(job)


def normalize_job_fields(job: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize job fields."""
    return JobNormalizer.normalize_job_fields(job)


def convert_cpsat_to_greedy_format(cpsat_schedule: Dict[str, Any]) -> Dict[str, List[Tuple]]:
    """Convert CP-SAT format to greedy format."""
    return ScheduleConverter.convert_cpsat_to_greedy_format(cpsat_schedule)


def group_jobs_by_family(jobs: List[Dict[str, Any]]) -> Dict[str, List[Tuple[int, str, Dict[str, Any]]]]:
    """Group jobs by family."""
    return JobGrouper.group_jobs_by_family(jobs)


def calculate_schedule_metrics(schedule: Dict[str, List[Tuple]]) -> Dict[str, Any]:
    """Calculate schedule metrics."""
    metrics = ScheduleAnalyzer.calculate_schedule_metrics(schedule)
    return {
        'total_jobs': metrics.total_jobs,
        'total_machines': metrics.total_machines,
        'makespan_hours': metrics.makespan_hours,
        'average_utilization': metrics.average_utilization,
        'machine_utilization': metrics.machine_utilization,
        'earliest_start': metrics.earliest_start,
    }


# Utility functions for cache management
def clear_all_caches() -> None:
    """Clear all internal caches for memory management."""
    ProcessExtractor.clear_cache()
    FamilyExtractor.clear_cache()
    logger.info("Cleared all scheduler utility caches")


# Legacy function for backward compatibility
def build_schedule_from_logs(cpsat_schedule: Dict[str, Any]) -> Dict[str, List[Tuple]]:
    """Legacy function - now uses optimized converter."""
    logger.warning("build_schedule_from_logs is deprecated, use convert_cpsat_to_greedy_format")
    return ScheduleConverter.convert_cpsat_to_greedy_format(cpsat_schedule)


def extract_total_processes(job_id: str) -> int:
    """Extract total processes (legacy function)."""
    if not isinstance(job_id, str):
        logger.warning(f"job_id must be string, got {type(job_id)}: {job_id}")
        return 1
    
    try:
        process_code = job_id.split('_', 1)[1]
    except IndexError:
        logger.warning(f"Could not extract PROCESS_CODE from job_id {job_id}")
        return 1
    
    match = re.search(r'\d+/(\d+)$', str(process_code))
    if match:
        return int(match.group(1))
    
    return 1


def _is_valid_timestamp(timestamp: Any, job_id: str, machine: str, field_name: str) -> bool:
    """Legacy function - now uses optimized validator."""
    return TimestampValidator.is_valid_timestamp(timestamp, job_id, machine, field_name)