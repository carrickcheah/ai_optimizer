"""
greedy_solver.py - PRODUCTION GRADE VERSION
Greedy scheduling algorithm with all configuration from .env
No defaults, comprehensive validation, modular structure
"""

import logging
import os
import time
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from dotenv import load_dotenv

# Load environment variables
load_dotenv()

logger = logging.getLogger(__name__)


class GreedySchedulingError(Exception):
    """Base exception for greedy scheduling errors."""
    pass


class GreedyConfigurationError(GreedySchedulingError):
    """Exception for configuration-related errors."""
    pass


@dataclass
class GreedyConfig:
    """Configuration for greedy scheduling parameters loaded from .env."""
    normal_working_hours: float
    ot_working_hours: float
    emergency_ot_hours: float
    emergency_minimum_start_hour: int
    grace_period_hours: int
    scheduler_search_days: int
    overloaded_machine_search_days: int
    urgent_buffer_threshold_hours: int
    urgent_reduction_factor: float
    buffer_critical_hours: int
    buffer_warning_hours: int
    buffer_caution_hours: int
    minimum_time_shift_seconds: int
    same_machine_setup_time: float
    different_machine_setup_time: float


class GreedyConfigManager:
    """Manages greedy scheduling configuration from environment variables only."""
    
    @staticmethod
    def load_config() -> GreedyConfig:
        """Load configuration from .env variables with validation - NO DEFAULTS."""
        config_vars = {
            'NORMAL_WORKING_HOURS': 'normal_working_hours',
            'OT_WORKING_HOURS': 'ot_working_hours',
            'EMERGENCY_OT_HOURS': 'emergency_ot_hours',
            'EMERGENCY_MINIMUM_START_HOUR': 'emergency_minimum_start_hour',
            'GRACE_PERIOD_HOURS': 'grace_period_hours',
            'SCHEDULER_SEARCH_DAYS': 'scheduler_search_days',
            'OVERLOADED_MACHINE_SEARCH_DAYS': 'overloaded_machine_search_days',
            'URGENT_BUFFER_THRESHOLD_HOURS': 'urgent_buffer_threshold_hours',
            'URGENT_REDUCTION_FACTOR': 'urgent_reduction_factor',
            'BUFFER_CRITICAL_HOURS': 'buffer_critical_hours',
            'BUFFER_WARNING_HOURS': 'buffer_warning_hours',
            'BUFFER_CAUTION_HOURS': 'buffer_caution_hours',
            'MINIMUM_TIME_SHIFT_SECONDS': 'minimum_time_shift_seconds',
            'SAME_MACHINE_SETUP_TIME': 'same_machine_setup_time',
            'DIFFERENT_MACHINE_SETUP_TIME': 'different_machine_setup_time'
        }
        
        config_values = {}
        missing_vars = []
        
        # Check all required environment variables
        for env_var, config_key in config_vars.items():
            value = os.getenv(env_var)
            if value is None:
                missing_vars.append(env_var)
            else:
                config_values[config_key] = value
        
        if missing_vars:
            raise GreedyConfigurationError(
                f"❌ MISSING CONFIGURATION: Required environment variables not set: {missing_vars}"
            )
        
        # Convert and validate values
        try:
            config = GreedyConfig(
                normal_working_hours=float(config_values['normal_working_hours']),
                ot_working_hours=float(config_values['ot_working_hours']),
                emergency_ot_hours=float(config_values['emergency_ot_hours']),
                emergency_minimum_start_hour=int(config_values['emergency_minimum_start_hour']),
                grace_period_hours=int(config_values['grace_period_hours']),
                scheduler_search_days=int(config_values['scheduler_search_days']),
                overloaded_machine_search_days=int(config_values['overloaded_machine_search_days']),
                urgent_buffer_threshold_hours=int(config_values['urgent_buffer_threshold_hours']),
                urgent_reduction_factor=float(config_values['urgent_reduction_factor']),
                buffer_critical_hours=int(config_values['buffer_critical_hours']),
                buffer_warning_hours=int(config_values['buffer_warning_hours']),
                buffer_caution_hours=int(config_values['buffer_caution_hours']),
                minimum_time_shift_seconds=int(config_values['minimum_time_shift_seconds']),
                same_machine_setup_time=float(config_values['same_machine_setup_time']),
                different_machine_setup_time=float(config_values['different_machine_setup_time'])
            )
            
            # Validate configuration values
            GreedyConfigManager._validate_config(config)
            return config
            
        except (ValueError, TypeError) as e:
            raise GreedyConfigurationError(f"❌ INVALID CONFIGURATION: Error converting values: {e}")
    
    @staticmethod
    def _validate_config(config: GreedyConfig) -> None:
        """Validate configuration values."""
        validations = [
            (config.normal_working_hours > 0, "NORMAL_WORKING_HOURS must be positive"),
            (config.ot_working_hours >= config.normal_working_hours, "OT_WORKING_HOURS must be >= NORMAL_WORKING_HOURS"),
            (config.emergency_ot_hours >= config.ot_working_hours, "EMERGENCY_OT_HOURS must be >= OT_WORKING_HOURS"),
            (config.grace_period_hours >= 0, "GRACE_PERIOD_HOURS must be non-negative"),
            (config.scheduler_search_days > 0, "SCHEDULER_SEARCH_DAYS must be positive"),
            (config.overloaded_machine_search_days > 0, "OVERLOADED_MACHINE_SEARCH_DAYS must be positive"),
            (config.urgent_buffer_threshold_hours >= 0, "URGENT_BUFFER_THRESHOLD_HOURS must be non-negative"),
            (0.0 <= config.urgent_reduction_factor <= 1.0, "URGENT_REDUCTION_FACTOR must be between 0 and 1"),
            (config.buffer_critical_hours >= 0, "BUFFER_CRITICAL_HOURS must be non-negative"),
            (config.buffer_warning_hours >= config.buffer_critical_hours, "BUFFER_WARNING_HOURS must be >= BUFFER_CRITICAL_HOURS"),
            (config.buffer_caution_hours >= config.buffer_warning_hours, "BUFFER_CAUTION_HOURS must be >= BUFFER_WARNING_HOURS"),
            (config.minimum_time_shift_seconds >= 0, "MINIMUM_TIME_SHIFT_SECONDS must be non-negative"),
            (config.same_machine_setup_time >= 0, "SAME_MACHINE_SETUP_TIME must be non-negative"),
            (config.different_machine_setup_time >= 0, "DIFFERENT_MACHINE_SETUP_TIME must be non-negative")
        ]
        
        for condition, error_msg in validations:
            if not condition:
                raise GreedyConfigurationError(f"❌ INVALID CONFIGURATION: {error_msg}")


class JobValidator:
    """Validates and prepares jobs for greedy scheduling."""
    
    @staticmethod
    def validate_and_prepare_jobs(jobs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Validate and prepare jobs for scheduling."""
        if not isinstance(jobs, list) or not jobs:
            raise GreedySchedulingError("Jobs must be a non-empty list")
        
        valid_jobs = []
        
        for job in jobs:
            try:
                prepared_job = JobValidator._prepare_single_job(job)
                if prepared_job:
                    valid_jobs.append(prepared_job)
            except Exception as e:
                logger.warning(f"Skipping invalid job {job.get('job_id', 'unknown')}: {e}")
        
        if not valid_jobs:
            raise GreedySchedulingError("No valid jobs after validation and preparation")
        
        logger.info(f"Validated {len(valid_jobs)} jobs (from {len(jobs)} input)")
        return valid_jobs
    
    @staticmethod
    def _prepare_single_job(job: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Prepare a single job for scheduling."""
        # Import utility functions with error handling
        try:
            from app.scheduling.scheduler_utils import normalize_job_fields, validate_job_data
        except ImportError:
            logger.warning("Could not import scheduler utilities - using basic validation")
            normalize_job_fields = lambda x: x
            validate_job_data = lambda x: x.get('job_id') and x.get('MachineName_v')
        
        # Normalize job fields
        normalized_job = normalize_job_fields(job)
        
        # Validate basic requirements
        if not validate_job_data(normalized_job):
            return None
        
        # Calculate processing time if missing
        if not normalized_job.get('processing_time'):
            processing_time = JobValidator._calculate_processing_time(normalized_job)
            if processing_time is None:
                logger.error(
                    f"❌ Job {normalized_job.get('job_id')} has no valid duration data - "
                    f"cannot schedule without processing time"
                )
                return None
            normalized_job['processing_time'] = processing_time
        
        return normalized_job
    
    @staticmethod
    def _calculate_processing_time(job: Dict[str, Any]) -> Optional[float]:
        """Calculate processing time in seconds.
        
        Priority:
        1. Use hours_need if available
        2. Calculate from quantity / output_per_hour
        """
        job_id = job.get('job_id', 'Unknown')
        
        # Priority 1: hours_need
        hours_need = job.get('hours_need')
        if hours_need and hours_need > 0:
            try:
                processing_time = float(hours_need) * 3600  # Convert hours to seconds
                logger.debug(f"Using hours_need for job {job_id}: {hours_need} hours = {processing_time} seconds")
                return processing_time
            except (ValueError, TypeError):
                pass
        
        # Priority 2: Calculate from quantity and output rate
        job_quantity = job.get('job_quantity', 0)
        output_per_hour = job.get('expect_output_per_hour', 0)
        
        if job_quantity and output_per_hour and job_quantity > 0 and output_per_hour > 0:
            try:
                hours_calculated = job_quantity / output_per_hour
                processing_time = hours_calculated * 3600  # Convert to seconds
                logger.info(
                    f"Calculated processing time for job {job_id}: "
                    f"{hours_calculated} hours from {job_quantity} qty / {output_per_hour} per hour"
                )
                return processing_time
            except ZeroDivisionError:
                logger.error(f"Division by zero for job {job_id}")
        
        return None


class MachineManager:
    """Manages machine assignments and availability."""
    
    @staticmethod
    def prepare_machines(machines: List[Any]) -> List[str]:
        """Prepare and validate machine list."""
        if not isinstance(machines, list) or not machines:
            raise GreedySchedulingError("Machines must be a non-empty list")
        
        # Handle case where machines is a list of dictionaries
        if machines and isinstance(machines[0], dict):
            machine_names = [
                m.get('MachineName_v', str(m)) for m in machines 
                if m.get('MachineName_v')
            ]
            logger.info(f"Extracted {len(machine_names)} machine names from dictionary format")
        else:
            machine_names = machines
        
        # Add 'Subcon' for handling unassigned jobs
        if 'Subcon' not in machine_names:
            machine_names.append('Subcon')
            logger.info("Added 'Subcon' to machine list for unassigned jobs")
        
        return machine_names
    
    @staticmethod
    def find_best_machine(job: Dict[str, Any], machines: List[str], 
                         machine_available_time: Dict[str, float]) -> Optional[str]:
        """Find the best machine for a job."""
        # Check if job has specific machine requirement
        required_machine = job.get('MachineName_v')
        if required_machine:
            if required_machine == "NOT_ASSIGN":
                logger.debug(f"Job {job.get('job_id', 'Unknown')} has NOT_ASSIGN machine - assigning to 'Subcon'")
                return 'Subcon'
            elif required_machine in machines:
                return required_machine
        
        # Find least loaded compatible machine
        compatible_machines = [m for m in machines if m != 'Subcon']  # Prefer actual machines over Subcon
        
        if not compatible_machines:
            logger.warning(f"No compatible machines found for job {job.get('job_id')}")
            return 'Subcon'  # Fallback to Subcon
        
        # Return least loaded compatible machine
        return min(compatible_machines, key=lambda m: machine_available_time[m])


class JobCategorizer:
    """Categorizes jobs by dependency status and scheduling requirements."""
    
    @staticmethod
    def categorize_jobs(jobs: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
        """Categorize jobs by dependency status."""
        categories = {
            'not_assign': [],
            'independent': [],
            'dependency': []
        }
        
        try:
            from app.scheduling.scheduler_utils import extract_job_family, extract_process_number
        except ImportError:
            logger.warning("Could not import scheduler utilities - using fallback categorization")
            # Fallback: treat all jobs as independent
            for job in jobs:
                if job.get('MachineName_v') == 'NOT_ASSIGN':
                    categories['not_assign'].append(job)
                else:
                    categories['independent'].append(job)
            return categories
        
        for job in jobs:
            if job.get('MachineName_v') == 'NOT_ASSIGN':
                categories['not_assign'].append(job)
            else:
                family = extract_job_family(job['job_id'])
                process_num = extract_process_number(job['job_id'])
                
                if family and process_num > 1:
                    categories['dependency'].append(job)
                else:
                    categories['independent'].append(job)
        
        logger.info(
            f"Job categorization: {len(categories['not_assign'])} NOT_ASSIGN, "
            f"{len(categories['independent'])} independent, "
            f"{len(categories['dependency'])} with dependencies"
        )
        
        return categories


class SchedulingConstraints:
    """Handles scheduling constraints and validation."""
    
    def __init__(self, config: GreedyConfig):
        self.config = config
    
    def can_schedule_job(self, job: Dict[str, Any], machine_id: str, start_time: float,
                        schedule: Dict[str, List[Tuple]], operators_in_use: Dict[int, int],
                        max_operators: int) -> bool:
        """Check if job can be scheduled at given time."""
        end_time = start_time + job['processing_time']
        
        # Check machine availability
        if not self._check_machine_availability(machine_id, start_time, end_time, schedule):
            return False
        
        # Check operator constraints
        if not self._check_operator_availability(start_time, end_time, operators_in_use, max_operators):
            return False
        
        # Check deadline constraints (logging only - no enforcement)
        if not self._check_deadline_constraints(job, end_time):
            return False
        
        # Check time availability (working hours, holidays, breaks)
        if not self._check_time_availability(start_time, end_time, job):
            return False
        
        return True
    
    def _check_machine_availability(self, machine_id: str, start_time: float, end_time: float,
                                   schedule: Dict[str, List[Tuple]]) -> bool:
        """Check if machine is available during the time window."""
        machine_tasks = schedule.get(machine_id, [])
        if not machine_tasks:
            return True
            
        # Performance: Early exit if checking beyond all scheduled tasks
        if machine_tasks and start_time >= machine_tasks[-1][2]:
            return True
            
        # Binary search for potential conflicts
        left, right = 0, len(machine_tasks) - 1
        
        while left <= right:
            mid = (left + right) // 2
            scheduled_start = machine_tasks[mid][1]
            scheduled_end = machine_tasks[mid][2]
            
            # Check for overlap
            if not (end_time <= scheduled_start or start_time >= scheduled_end):
                return False
                
            if scheduled_end <= start_time:
                left = mid + 1
            else:
                right = mid - 1
                
        return True
    
    def _check_operator_availability(self, start_time: float, end_time: float,
                                   operators_in_use: Dict[int, int], max_operators: int) -> bool:
        """Check operator availability constraints."""
        if max_operators <= 0:
            return True
        
        try:
            from app.utils.time_utils import epoch_to_relative_hours
            start_rel = epoch_to_relative_hours(start_time)
            end_rel = epoch_to_relative_hours(end_time)
            
            for hour in range(int(start_rel), int(end_rel) + 1):
                # Ensure type consistency for comparison
                if int(operators_in_use[hour]) >= int(max_operators):
                    return False
        except ImportError:
            logger.warning("Could not import time utilities - skipping operator constraints")
        except (ValueError, TypeError) as e:
            logger.warning(f"Type conversion error in operator check: {e}")
            return True
        
        return True
    
    def _check_deadline_constraints(self, job: Dict[str, Any], end_time: float) -> bool:
        """Check LCD date deadline constraints - NO HARD DEADLINE ENFORCEMENT."""
        # Always allow scheduling regardless of LCD_DATE
        # Just log deadline information for monitoring purposes
        if 'lcd_date_epoch' not in job or not job['lcd_date_epoch']:
            return True
        
        lcd_deadline = job['lcd_date_epoch']
        processing_time_hours = job.get('processing_time', 3600) / 3600
        
        try:
            from app.utils.time_utils import datetime_to_epoch
            current_time = datetime_to_epoch(datetime.now())
        except ImportError:
            current_time = time.time()
        
        # Log deadline status for monitoring, but don't enforce
        if lcd_deadline < current_time:
            days_late = (current_time - lcd_deadline) / (24 * 3600)
            logger.info(f"Job {job.get('job_id')} is {days_late:.1f} days past LCD_DATE - scheduling anyway")
        elif end_time > lcd_deadline:
            days_over = (end_time - lcd_deadline) / (24 * 3600)
            logger.info(f"Job {job.get('job_id')} will finish {days_over:.1f} days after LCD_DATE - scheduling anyway")
        else:
            buffer_days = (lcd_deadline - end_time) / (24 * 3600)
            logger.debug(f"Job {job.get('job_id')} has {buffer_days:.1f} days buffer before LCD_DATE")
        
        # Always return True - no deadline enforcement
        return True
    
    def _check_time_availability(self, start_time: float, end_time: float, 
                                job: Dict[str, Any]) -> bool:
        """Check time availability - jobs must start during working hours."""
        try:
            from app.scheduling.time_availability import is_time_available_for_scheduling
            from datetime import datetime
            import pytz
            
            # For all jobs, check if the start time is during working hours
            # The job will automatically span multiple working days as needed
            singapore_tz = pytz.timezone('Asia/Singapore')
            start_dt = datetime.fromtimestamp(start_time, tz=singapore_tz)
            
            if not is_time_available_for_scheduling(start_dt):
                job_id = job.get('job_id', 'Unknown')
                logger.debug(f"Job {job_id} start time {start_dt} is not during working hours")
                return False
                
        except ImportError:
            logger.warning("Could not import time availability checker - skipping time constraints")
        except Exception as e:
            logger.warning(f"Time availability check failed: {e} - allowing scheduling")
        
        return True


class GreedyScheduler:
    """Main greedy scheduling algorithm implementation."""
    
    def __init__(self, config: GreedyConfig):
        self.config = config
        self.constraints = SchedulingConstraints(config)
    
    def schedule_jobs(self, jobs: List[Dict[str, Any]], machines: List[str],
                     setup_times: Optional[Dict] = None, enforce_sequence: bool = True,
                     max_operators: int = 0) -> Dict[str, List[Tuple]]:
        """Main greedy scheduling algorithm."""
        start_time = time.time()
        logger.info(f"Starting greedy scheduling for {len(jobs)} jobs on {len(machines)} machines")
        logger.info(f"Configuration: enforce_sequence={enforce_sequence}, max_operators={max_operators}")
        
        # Count jobs per machine for overload detection
        machine_job_counts = {}
        for job in jobs:
            machine_id = job.get('machine_id') or job.get('MachineName_v')
            if machine_id and machine_id != 'NOT_ASSIGN':
                machine_job_counts[machine_id] = machine_job_counts.get(machine_id, 0) + 1
        
        # Initialize scheduling state
        schedule_state = self._initialize_schedule_state(machines)
        schedule_state['machine_job_counts'] = machine_job_counts
        
        # Log machine workloads for debugging
        overloaded_machines = {m: count for m, count in machine_job_counts.items() if count > 20}
        if overloaded_machines:
            logger.info(f"Overloaded machines (>20 jobs): {dict(sorted(overloaded_machines.items(), key=lambda x: x[1], reverse=True))}")
        
        # Categorize jobs
        job_categories = JobCategorizer.categorize_jobs(jobs)
        
        # Schedule each category
        self._schedule_not_assign_jobs(job_categories['not_assign'], schedule_state, max_operators)
        self._schedule_independent_jobs(job_categories['independent'], schedule_state, max_operators)
        
        if enforce_sequence:
            self._schedule_dependency_jobs(job_categories['dependency'], schedule_state, max_operators)
        else:
            # Treat dependency jobs as independent if sequence enforcement is disabled
            self._schedule_independent_jobs(job_categories['dependency'], schedule_state, max_operators)
        
        # Finalize schedule
        self._finalize_schedule(schedule_state)
        
        # Log results
        self._log_scheduling_results(schedule_state, len(jobs), time.time() - start_time)
        
        return schedule_state['schedule']
    
    def _initialize_schedule_state(self, machines: List[str]) -> Dict[str, Any]:
        """Initialize scheduling state tracking."""
        try:
            from app.utils.time_utils import datetime_to_epoch
            current_time = datetime_to_epoch(datetime.now())
        except ImportError:
            current_time = time.time()
        
        return {
            'schedule': {machine: [] for machine in machines},
            'scheduled_jobs': set(),
            'unscheduled_jobs': [],
            'machine_available_time': {machine: current_time for machine in machines},
            'operators_in_use': defaultdict(int),
            'family_end_times': defaultdict(lambda: current_time),
            'process_end_times': {},
            'current_time': current_time
        }
    
    def _schedule_not_assign_jobs(self, not_assign_jobs: List[Dict[str, Any]],
                                 schedule_state: Dict[str, Any], max_operators: int) -> None:
        """Schedule NOT_ASSIGN jobs on Subcon machine."""
        logger.info(f"Scheduling {len(not_assign_jobs)} NOT_ASSIGN jobs on 'Subcon'")
        
        sorted_jobs = sorted(not_assign_jobs, key=lambda j: j.get('priority', 99))
        
        for job in sorted_jobs:
            machine_id = 'Subcon'
            start_search_time = schedule_state['machine_available_time'].get(machine_id, schedule_state['current_time'])
            
            self._find_and_schedule_job(
                job, machine_id, start_search_time, schedule_state,
                'NOT_ASSIGN_FAMILY', 99, max_operators
            )
    
    def _schedule_independent_jobs(self, independent_jobs: List[Dict[str, Any]],
                                  schedule_state: Dict[str, Any], max_operators: int) -> None:
        """Schedule independent jobs (no dependencies)."""
        logger.info(f"Scheduling {len(independent_jobs)} independent jobs")
        
        # Performance optimization: Sort by priority and processing time (shorter jobs first)
        sorted_jobs = sorted(independent_jobs, key=lambda j: (j.get('priority', 99), j.get('processing_time', float('inf'))))
        
        for job in sorted_jobs:
            if job['job_id'] in schedule_state['scheduled_jobs']:
                continue
            
            machines = list(schedule_state['machine_available_time'].keys())
            machine_id = MachineManager.find_best_machine(job, machines, schedule_state['machine_available_time'])
            
            if not machine_id:
                schedule_state['unscheduled_jobs'].append(job)
                continue
            
            start_search_time = schedule_state['machine_available_time'].get(machine_id, schedule_state['current_time'])
            
            try:
                from app.scheduling.scheduler_utils import extract_job_family, extract_process_number
                family = extract_job_family(job['job_id']) or 'INDEPENDENT'
                process_num = extract_process_number(job['job_id']) or 1
            except ImportError:
                family = 'INDEPENDENT'
                process_num = 1
            
            self._find_and_schedule_job(
                job, machine_id, start_search_time, schedule_state,
                family, process_num, max_operators
            )
    
    def _schedule_dependency_jobs(self, dependency_jobs: List[Dict[str, Any]],
                                 schedule_state: Dict[str, Any], max_operators: int) -> None:
        """Schedule jobs with dependencies by family and process order."""
        logger.info(f"Scheduling {len(dependency_jobs)} jobs with dependencies")
        
        try:
            from app.scheduling.scheduler_utils import group_jobs_by_family
            job_families = group_jobs_by_family([
                job for job in dependency_jobs 
                if job['job_id'] not in schedule_state['scheduled_jobs']
            ])
        except ImportError:
            logger.warning("Could not import group_jobs_by_family - treating as independent jobs")
            self._schedule_independent_jobs(dependency_jobs, schedule_state, max_operators)
            return
        
        # Process families in order
        for family, family_jobs in job_families.items():
            if not family_jobs:
                continue
            
            logger.info(f"Processing family '{family}' with {len(family_jobs)} jobs")
            
            for process_num, job_id, job_item in family_jobs:
                if job_id in schedule_state['scheduled_jobs']:
                    continue
                
                # Check dependency
                if process_num > 1:
                    prev_process_key = (family, process_num - 1)
                    if prev_process_key not in schedule_state['process_end_times']:
                        logger.warning(f"Job {job_id} cannot be scheduled due to unmet dependencies")
                        schedule_state['unscheduled_jobs'].append(job_item)
                        continue
                    
                    earliest_start = schedule_state['process_end_times'][prev_process_key]
                else:
                    earliest_start = schedule_state['current_time']
                
                # Find machine
                machines = list(schedule_state['machine_available_time'].keys())
                machine_id = MachineManager.find_best_machine(job_item, machines, schedule_state['machine_available_time'])
                
                if not machine_id:
                    logger.warning(f"No machine available for job {job_id}")
                    schedule_state['unscheduled_jobs'].append(job_item)
                    continue
                
                # Start search from the later of machine availability or dependency requirement
                start_search_time = max(
                    schedule_state['machine_available_time'].get(machine_id, schedule_state['current_time']),
                    earliest_start
                )
                
                self._find_and_schedule_job(
                    job_item, machine_id, start_search_time, schedule_state,
                    family, process_num, max_operators
                )
    
    def _find_and_schedule_job(self, job: Dict[str, Any], machine_id: str, start_search_time: float,
                              schedule_state: Dict[str, Any], family: str, process_num: int,
                              max_operators: int) -> bool:
        """Find next available slot and schedule job - uses 1-hour precision with smart time availability jumps."""
        job_id = job['job_id']
        
        # Detect overloaded machines and extend search window
        # Count total jobs assigned to this machine (not just currently scheduled)
        total_machine_jobs = schedule_state.get('machine_job_counts', {}).get(machine_id, 0)
        
        if total_machine_jobs > 20:  # Machine is overloaded
            search_limit_hours = self.config.overloaded_machine_search_days * 24
            logger.info(f"Job {job_id}: Machine {machine_id} overloaded ({total_machine_jobs} total jobs), extending search to {self.config.overloaded_machine_search_days} days")
        else:
            search_limit_hours = self.config.scheduler_search_days * 24
            logger.debug(f"Job {job_id}: Searching for slot within {self.config.scheduler_search_days} days")
        
        max_search_time = start_search_time + search_limit_hours * 3600
        
        # Performance optimization: Try time availability jumps first
        time_availability_works = self._try_time_availability_jump(job, machine_id, start_search_time, max_search_time, schedule_state, family, process_num, max_operators)
        if time_availability_works:
            return True
        
        # Fallback to incremental search if time availability module not available
        current_search_time = start_search_time
        increment = 3600  # Start with 1 hour increments
        attempts = 0
        max_attempts_per_increment = 48  # 2 days worth of attempts before adaptive scaling
        
        while current_search_time < max_search_time:
            if self.constraints.can_schedule_job(
                job, machine_id, current_search_time, schedule_state['schedule'],
                schedule_state['operators_in_use'], max_operators
            ):
                self._schedule_job_at_time(
                    job, machine_id, current_search_time, schedule_state,
                    family, process_num, max_operators
                )
                return True
            
            # Performance optimization: Use binary search for next conflict
            if attempts > 10 and increment == 3600:
                # After 10 failed attempts, try to binary search for next available slot
                next_gap = self._binary_search_next_gap(machine_id, current_search_time, max_search_time, job['processing_time'], schedule_state)
                if next_gap and next_gap > current_search_time:
                    current_search_time = next_gap
                    attempts = 0
                    continue
            
            # Fallback to incremental search
            current_search_time += increment
            attempts += 1
            
            # Adaptive search: increase increment after many failed attempts
            if attempts >= max_attempts_per_increment:
                if increment < 3600:  # Less than 1 hour
                    increment = min(increment * 2, 3600)  # Double, max 1 hour
                    logger.debug(f"Job {job_id}: Increasing search increment to {increment/3600:.1f} hours")
                attempts = 0
        
        # Could not schedule job
        logger.warning(f"Could not find available slot for job {job_id} on machine {machine_id} within {search_limit_hours/24:.0f} days")
        schedule_state['unscheduled_jobs'].append(job)
        return False
    
    def _try_time_availability_jump(self, job: Dict[str, Any], machine_id: str, start_search_time: float,
                                   max_search_time: float, schedule_state: Dict[str, Any], family: str, 
                                   process_num: int, max_operators: int) -> bool:
        """Try to use time availability module for smart jumps to available slots."""
        try:
            from app.scheduling.time_availability import get_next_available_slot
            processing_time_hours = job.get('processing_time', 3600) / 3600
            
            current_search_time = start_search_time
            max_jumps = 50  # Limit jumps to prevent infinite loops
            
            for _ in range(max_jumps):
                if current_search_time >= max_search_time:
                    break
                    
                # Get next available slot from time availability
                next_available = get_next_available_slot(current_search_time, processing_time_hours)
                if not next_available or next_available <= current_search_time:
                    break
                    
                current_search_time = next_available
                
                # Check if we can schedule at this time
                if self.constraints.can_schedule_job(
                    job, machine_id, current_search_time, schedule_state['schedule'],
                    schedule_state['operators_in_use'], max_operators
                ):
                    self._schedule_job_at_time(
                        job, machine_id, current_search_time, schedule_state,
                        family, process_num, max_operators
                    )
                    return True
                    
                # If not, advance by 1 hour for next attempt
                current_search_time += 3600
                
        except ImportError:
            pass
        
        return False
    
    def _binary_search_next_gap(self, machine_id: str, start_time: float, end_time: float, 
                               required_duration: float, schedule_state: Dict[str, Any]) -> Optional[float]:
        """Binary search for the next available gap in machine schedule."""
        machine_tasks = schedule_state['schedule'][machine_id]
        if not machine_tasks:
            return start_time
            
        # Find tasks that might conflict
        relevant_tasks = [(task[1], task[2]) for task in machine_tasks if task[2] > start_time]
        if not relevant_tasks:
            return start_time
            
        relevant_tasks.sort()
        
        # Check gap before first task
        if relevant_tasks[0][0] - start_time >= required_duration:
            return start_time
            
        # Check gaps between tasks
        for i in range(len(relevant_tasks) - 1):
            gap_start = relevant_tasks[i][1]
            gap_end = relevant_tasks[i + 1][0]
            if gap_end - gap_start >= required_duration and gap_start < end_time:
                return gap_start
                
        # Check after last task
        last_end = relevant_tasks[-1][1]
        if last_end < end_time:
            return last_end
            
        return None
    
    def _schedule_job_at_time(self, job: Dict[str, Any], machine_id: str, start_time: float,
                             schedule_state: Dict[str, Any], family: str, process_num: int,
                             max_operators: int) -> None:
        """Schedule job at specific time and update all tracking structures."""
        job_id = job['job_id']
        end_time = start_time + job['processing_time']
        
        # Create job entry
        additional_params = {
            'greedy_scheduled_at': schedule_state['current_time'],
            'original_priority': job.get('priority'),
            'family': family,
            'process_num': process_num
        }
        
        schedule_state['schedule'][machine_id].append(
            (job_id, start_time, end_time, job.get('priority', 0), additional_params)
        )
        
        # Update tracking structures
        schedule_state['scheduled_jobs'].add(job_id)
        schedule_state['machine_available_time'][machine_id] = end_time
        
        # Update operator usage
        if max_operators > 0:
            try:
                from app.utils.time_utils import epoch_to_relative_hours
                start_rel = epoch_to_relative_hours(start_time)
                end_rel = epoch_to_relative_hours(end_time)
                for hour in range(int(start_rel), int(end_rel) + 1):
                    schedule_state['operators_in_use'][hour] += 1
            except ImportError:
                pass
        
        # Update dependency tracking
        schedule_state['family_end_times'][family] = max(schedule_state['family_end_times'][family], end_time)
        schedule_state['process_end_times'][(family, process_num)] = end_time
        
        # Log scheduling
        try:
            from app.utils.time_utils import epoch_to_datetime, format_datetime_for_display
            start_str = format_datetime_for_display(epoch_to_datetime(start_time))
            end_str = format_datetime_for_display(epoch_to_datetime(end_time))
            logger.info(f"Scheduled job {job_id} (P{process_num:02d}) on {machine_id}: {start_str} to {end_str}")
        except ImportError:
            logger.info(f"Scheduled job {job_id} (P{process_num:02d}) on {machine_id}: {start_time} to {end_time}")
    
    def _finalize_schedule(self, schedule_state: Dict[str, Any]) -> None:
        """Finalize schedule by sorting tasks by start time."""
        for machine in schedule_state['schedule']:
            schedule_state['schedule'][machine].sort(key=lambda x: x[1])
    
    def _log_scheduling_results(self, schedule_state: Dict[str, Any], total_input_jobs: int, elapsed_time: float) -> None:
        """Log detailed scheduling results and statistics."""
        total_scheduled = len(schedule_state['scheduled_jobs'])
        total_unscheduled = len(schedule_state['unscheduled_jobs'])
        success_rate = (total_scheduled / total_input_jobs * 100) if total_input_jobs > 0 else 0
        
        logger.info(f"Greedy scheduling completed in {elapsed_time:.2f} seconds")
        logger.info(f"Scheduling Results:")
        logger.info(f"  Total jobs processed: {total_input_jobs}")
        logger.info(f"  Successfully scheduled: {total_scheduled} ({success_rate:.1f}%)")
        logger.info(f"  Failed to schedule: {total_unscheduled} ({100-success_rate:.1f}%)")
        
        # Log machine utilization
        machine_task_counts = {
            machine: len(tasks) for machine, tasks in schedule_state['schedule'].items() if tasks
        }
        if machine_task_counts:
            logger.info("Machine utilization:")
            for machine, count in sorted(machine_task_counts.items(), key=lambda x: x[1], reverse=True)[:10]:
                logger.info(f"  {machine}: {count} tasks")
        
        # Log unscheduled job breakdown
        if schedule_state['unscheduled_jobs']:
            self._log_unscheduled_breakdown(schedule_state['unscheduled_jobs'])
    
    def _log_unscheduled_breakdown(self, unscheduled_jobs: List[Dict[str, Any]]) -> None:
        """Log breakdown of unscheduled jobs."""
        logger.warning(f"Unscheduled jobs breakdown:")
        
        # Categorize unscheduled jobs
        not_assign_unscheduled = [job for job in unscheduled_jobs if job.get('MachineName_v') == 'NOT_ASSIGN']
        
        try:
            from app.scheduling.scheduler_utils import extract_process_number
            dependency_unscheduled = [job for job in unscheduled_jobs if extract_process_number(job['job_id']) > 1]
        except ImportError:
            dependency_unscheduled = []
        
        other_unscheduled = [
            job for job in unscheduled_jobs 
            if job not in not_assign_unscheduled and job not in dependency_unscheduled
        ]
        
        if not_assign_unscheduled:
            logger.warning(f"  NOT_ASSIGN jobs: {len(not_assign_unscheduled)}")
        if dependency_unscheduled:
            logger.warning(f"  Dependency failures: {len(dependency_unscheduled)}")
        if other_unscheduled:
            logger.warning(f"  Other scheduling failures: {len(other_unscheduled)}")
        
        # Log examples of unscheduled jobs
        for i, job_item in enumerate(unscheduled_jobs[:10]):
            logger.warning(f"  Unscheduled: {job_item['job_id']}")
        
        if len(unscheduled_jobs) > 10:
            logger.warning(f"  ... and {len(unscheduled_jobs) - 10} more")


def greedy_schedule(
    jobs: List[Dict[str, Any]], 
    machines: List[str], 
    setup_times: Optional[Dict] = None, 
    enforce_sequence: bool = True, 
    max_operators: int = 0
) -> Dict[str, List[Tuple]]:
    """
    Create a schedule using a greedy algorithm - PRODUCTION GRADE.
    
    Args:
        jobs: List of job dictionaries
        machines: List of machine IDs or dictionaries
        setup_times: Dictionary of setup times between processes (optional)
        enforce_sequence: Whether to enforce process sequence dependencies
        max_operators: Maximum number of operators available at any time
        
    Returns:
        Dictionary with machine IDs as keys and lists of scheduled jobs as values
        
    Raises:
        GreedyConfigurationError: If required .env variables are missing/invalid
        GreedySchedulingError: If input validation fails or scheduling cannot proceed
    """
    try:
        # Load configuration from .env (no defaults)
        config = GreedyConfigManager.load_config()
        logger.info("Greedy configuration loaded successfully from .env")
        
        # Validate and prepare inputs
        valid_jobs = JobValidator.validate_and_prepare_jobs(jobs)
        machine_names = MachineManager.prepare_machines(machines)
        
        # Create and run scheduler
        scheduler = GreedyScheduler(config)
        schedule = scheduler.schedule_jobs(valid_jobs, machine_names, setup_times, enforce_sequence, max_operators)
        
        return schedule
        
    except GreedyConfigurationError as e:
        logger.error(f"Configuration error in greedy scheduling: {e}")
        raise
    except GreedySchedulingError as e:
        logger.error(f"Scheduling error in greedy algorithm: {e}")
        raise
    except Exception as e:
        logger.error(f"Unexpected error in greedy scheduling: {e}")
        raise GreedySchedulingError(f"Unexpected error in greedy scheduling: {e}")


if __name__ == "__main__":
    """Example usage and testing."""
    logging.basicConfig(level=logging.INFO)
    
    try:
        # Load configuration to test
        config = GreedyConfigManager.load_config()
        logger.info("Configuration loaded successfully from .env")
        
        # Test with production data
        try:
            from app.data_ingestion.mariadb_parser import load_jobs_planning_data
            
            start_time = time.time()
            jobs, machines, setup_times = load_jobs_planning_data()
            
            if jobs and machines:
                logger.info(f"Loaded {len(jobs)} jobs and {len(machines)} machines for testing")
                
                # Run greedy scheduling
                schedule = greedy_schedule(jobs, machines, setup_times, enforce_sequence=True, max_operators=0)
                
                # Display results
                print(f"\nGreedy Schedule Results:")
                print(f"Processing time: {time.time() - start_time:.2f} seconds")
                
                total_tasks = sum(len(tasks) for tasks in schedule.values())
                print(f"Total scheduled tasks: {total_tasks}")
                
                # Show sample results
                print("\nSchedule Sample (First 5 machines, 3 tasks each):")
                task_count = 0
                for machine, tasks in sorted(schedule.items())[:5]:
                    if tasks:
                        print(f"\nMachine: {machine} - {len(tasks)} tasks")
                        for i, task in enumerate(tasks[:3]):
                            job_id, start, end, priority = task[:4]
                            
                            try:
                                from app.utils.time_utils import epoch_to_datetime, format_datetime_for_display
                                start_str = format_datetime_for_display(epoch_to_datetime(start))
                                end_str = format_datetime_for_display(epoch_to_datetime(end))
                            except ImportError:
                                start_str = f"Epoch_{int(start)}"
                                end_str = f"Epoch_{int(end)}"
                            
                            print(f"  Task {i+1}: {job_id} | {start_str} to {end_str} | Priority: {priority}")
                            task_count += 1
                        
                    if task_count >= 15:  # Limit output
                        break
                
                success_rate = (total_tasks / len(jobs)) * 100 if jobs else 0
                print(f"\nSuccess Rate: {success_rate:.1f}% ({total_tasks}/{len(jobs)} jobs scheduled)")
                
            else:
                logger.error("No jobs or machines loaded from database")
                
        except ImportError as e:
            logger.error(f"Could not import data loader: {e}")
            logger.info("Skipping database test - ensure mariadb_parser is available")
        
        except Exception as e:
            logger.error(f"Error during data loading test: {e}")
    
    except GreedyConfigurationError as e:
        logger.error(f"Configuration error: {e}")
        print(f"\n❌ Configuration Error: {e}")
        print("Ensure all required variables are set in your .env file:")
        print("- NORMAL_WORKING_HOURS, OT_WORKING_HOURS, EMERGENCY_OT_HOURS")
        print("- EMERGENCY_MINIMUM_START_HOUR, GRACE_PERIOD_HOURS") 
        print("- SCHEDULER_SEARCH_DAYS, URGENT_BUFFER_THRESHOLD_HOURS")
        print("- URGENT_REDUCTION_FACTOR, BUFFER_*_HOURS variables")
        print("- MINIMUM_TIME_SHIFT_SECONDS, SETUP_TIME variables")
        
    except Exception as e:
        logger.error(f"Unexpected error in main: {e}")
        print(f"\n❌ Unexpected Error: {e}")