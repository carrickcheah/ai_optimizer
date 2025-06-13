"""
cpsat_solver.py - FIXED VERSION
Constraint Programming (CP-SAT) solver for production scheduling with improved structure
All configuration loaded from .env without defaults
"""

import logging
import math
import os
import time
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple, Union

from ortools.sat.python import cp_model

# Load environment variables from .env file
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # dotenv not available, assume env vars are set

# Configure logging to suppress OR-Tools verbose output
logger = logging.getLogger(__name__)
ortools_logger = logging.getLogger('ortools')
ortools_logger.setLevel(logging.ERROR)


class SchedulingError(Exception):
    """Base exception for scheduling errors."""
    pass


class ConfigurationError(SchedulingError):
    """Exception for configuration-related errors."""
    pass


@dataclass
class SchedulingConfig:
    """Configuration for scheduling parameters loaded from .env."""
    solver_time_limit_seconds: int
    max_jobs_limit: int
    planning_horizon_days: int
    max_workers_limit: int
    relative_gap_limit: float
    absolute_gap_limit: int
    priority_weight: int
    minimum_horizon_hours: int
    emergency_minimum_start_hour: int
    grace_period_hours: int
    scheduler_search_days: int
    cpsat_batch_size: int
    # Add missing variables from .env
    normal_working_hours: float
    ot_working_hours: float
    emergency_ot_hours: float
    
    def get_dynamic_limits(self, num_jobs: int) -> Dict[str, int]:
        """Get dynamic limits based on problem size."""
        if num_jobs > 500:
            return {
                'time_limit_seconds': max(self.solver_time_limit_seconds // 2, 120),
                'planning_horizon_days': max(self.planning_horizon_days // 2, 7),
                'max_jobs_limit': min(self.max_jobs_limit, 500)
            }
        elif num_jobs > 200:
            return {
                'time_limit_seconds': max(self.solver_time_limit_seconds * 3 // 4, 180),
                'planning_horizon_days': max(self.planning_horizon_days * 3 // 4, 14),
                'max_jobs_limit': min(self.max_jobs_limit, 800)
            }
        else:
            return {
                'time_limit_seconds': self.solver_time_limit_seconds,
                'planning_horizon_days': self.planning_horizon_days,
                'max_jobs_limit': self.max_jobs_limit
            }


@dataclass
class TaskInfo:
    """Information about a scheduled task."""
    start: Any  # CP-SAT variable
    end: Any    # CP-SAT variable
    interval: Any  # CP-SAT interval
    machine: str
    hours: int
    job: Dict[str, Any]


@dataclass
class SolverResult:
    """Result from CP-SAT solver."""
    solver: cp_model.CpSolver
    status: int
    solve_time: float
    model: cp_model.CpModel
    performance_warning: bool = False


class SchedulingConfigManager:
    """Manages scheduling configuration from environment variables only."""
    
    @staticmethod
    def load_config() -> SchedulingConfig:
        """Load configuration from .env variables with validation - NO DEFAULTS."""
        config_vars = {
            'SOLVER_TIME_LIMIT_SECONDS': 'solver_time_limit_seconds',
            'MAX_JOBS_LIMIT': 'max_jobs_limit',
            'PLANNING_HORIZON_DAYS': 'planning_horizon_days',
            'MAX_WORKERS_LIMIT': 'max_workers_limit',
            'RELATIVE_GAP_LIMIT': 'relative_gap_limit',
            'ABSOLUTE_GAP_LIMIT': 'absolute_gap_limit',
            'PRIORITY_WEIGHT': 'priority_weight',
            'MINIMUM_HORIZON_HOURS': 'minimum_horizon_hours',
            'EMERGENCY_MINIMUM_START_HOUR': 'emergency_minimum_start_hour',
            'GRACE_PERIOD_HOURS': 'grace_period_hours',
            'SCHEDULER_SEARCH_DAYS': 'scheduler_search_days',
            'CPSAT_BATCH_SIZE': 'cpsat_batch_size',
            'NORMAL_WORKING_HOURS': 'normal_working_hours',
            'OT_WORKING_HOURS': 'ot_working_hours',
            'EMERGENCY_OT_HOURS': 'emergency_ot_hours'
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
            raise ConfigurationError(
                f"❌ MISSING CONFIGURATION: Required environment variables not set: {missing_vars}"
            )
        
        # Convert and validate values
        try:
            config = SchedulingConfig(
                solver_time_limit_seconds=int(config_values['solver_time_limit_seconds']),
                max_jobs_limit=int(config_values['max_jobs_limit']),
                planning_horizon_days=int(config_values['planning_horizon_days']),
                max_workers_limit=int(config_values['max_workers_limit']),
                relative_gap_limit=float(config_values['relative_gap_limit']),
                absolute_gap_limit=int(config_values['absolute_gap_limit']),
                priority_weight=int(config_values['priority_weight']),
                minimum_horizon_hours=int(config_values['minimum_horizon_hours']),
                emergency_minimum_start_hour=int(config_values['emergency_minimum_start_hour']),
                grace_period_hours=int(config_values['grace_period_hours']),
                scheduler_search_days=int(config_values['scheduler_search_days']),
                cpsat_batch_size=int(config_values['cpsat_batch_size']),
                normal_working_hours=float(config_values['normal_working_hours']),
                ot_working_hours=float(config_values['ot_working_hours']),
                emergency_ot_hours=float(config_values['emergency_ot_hours'])
            )
            
            # Validate configuration values
            SchedulingConfigManager._validate_config(config)
            return config
            
        except (ValueError, TypeError) as e:
            raise ConfigurationError(f"❌ INVALID CONFIGURATION: Error converting values: {e}")
    
    @staticmethod
    def _validate_config(config: SchedulingConfig) -> None:
        """Validate configuration values."""
        validations = [
            (config.solver_time_limit_seconds > 0, "SOLVER_TIME_LIMIT_SECONDS must be positive"),
            (config.max_jobs_limit > 0, "MAX_JOBS_LIMIT must be positive"),
            (config.planning_horizon_days > 0, "PLANNING_HORIZON_DAYS must be positive"),
            (config.max_workers_limit > 0, "MAX_WORKERS_LIMIT must be positive"),
            (0.0 <= config.relative_gap_limit <= 1.0, "RELATIVE_GAP_LIMIT must be between 0 and 1"),
            (config.absolute_gap_limit >= 0, "ABSOLUTE_GAP_LIMIT must be non-negative"),
            (config.priority_weight > 0, "PRIORITY_WEIGHT must be positive"),
            (config.minimum_horizon_hours > 0, "MINIMUM_HORIZON_HOURS must be positive"),
            (config.grace_period_hours >= 0, "GRACE_PERIOD_HOURS must be non-negative"),
            (config.scheduler_search_days > 0, "SCHEDULER_SEARCH_DAYS must be positive"),
            (config.cpsat_batch_size > 0, "CPSAT_BATCH_SIZE must be positive"),
            (config.normal_working_hours > 0, "NORMAL_WORKING_HOURS must be positive"),
            (config.ot_working_hours > 0, "OT_WORKING_HOURS must be positive"),
            (config.emergency_ot_hours > 0, "EMERGENCY_OT_HOURS must be positive")
        ]
        
        for condition, error_msg in validations:
            if not condition:
                raise ConfigurationError(f"❌ INVALID CONFIGURATION: {error_msg}")


class JobValidator:
    """Validates and normalizes job data."""
    
    @staticmethod
    def validate_jobs(jobs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Validate and filter valid jobs."""
        valid_jobs = []
        
        for job in jobs:
            if not isinstance(job, dict):
                logger.warning(f"Skipping non-dictionary job: {job}")
                continue
                
            if not job.get('job_id'):
                logger.warning(f"Skipping job without job_id: {job}")
                continue
                
            if not job.get('MachineName_v'):
                logger.warning(f"Skipping job {job.get('job_id')} without machine assignment")
                continue
                
            valid_jobs.append(job)
        
        return valid_jobs
    
    @staticmethod
    def normalize_machines(machines: List[Union[str, Dict[str, Any]]]) -> List[str]:
        """Normalize machines list to strings."""
        if not machines:
            return []
            
        if isinstance(machines[0], dict):
            machine_names = []
            for m in machines:
                name = m.get('MachineName_v') or m.get('machine_name') or str(m)
                machine_names.append(name)
            logger.debug(f"Converted machine dictionaries to names: {machine_names}")
            return machine_names
        else:
            return machines


class JobFilterer:
    """Handles job filtering and prioritization."""
    
    def __init__(self, config: SchedulingConfig):
        self.config = config
    
    def filter_and_limit_jobs(self, jobs: List[Dict[str, Any]], 
                             current_time_epoch: int) -> List[Dict[str, Any]]:
        """Filter jobs by planning horizon and apply limits."""
        # Calculate horizon cutoff using 24 hours per day
        hours_per_day = 24.0
        horizon_cutoff_epoch = (
            current_time_epoch + (self.config.planning_horizon_days * hours_per_day * 3600)
        )
        
        # Filter jobs by planning horizon and priority
        filtered_jobs = []
        for job in jobs:
            if self._should_include_job(job, horizon_cutoff_epoch):
                filtered_jobs.append(job)
        
        # Apply job limit with prioritization
        if len(filtered_jobs) > self.config.max_jobs_limit:
            filtered_jobs = self._prioritize_jobs(filtered_jobs, current_time_epoch)
            logger.warning(
                f"Limited to {self.config.max_jobs_limit} jobs for performance "
                f"(from {len(jobs)} total)"
            )
        
        logger.info(
            f"Performance filtering: {len(jobs)} → {len(filtered_jobs)} jobs "
            f"(horizon: {self.config.planning_horizon_days} days, "
            f"limit: {self.config.max_jobs_limit})"
        )
        
        return filtered_jobs
    
    def _should_include_job(self, job: Dict[str, Any], horizon_cutoff_epoch: int) -> bool:
        """Determine if job should be included based on horizon and priority."""
        lcd_date_epoch = job.get('lcd_date_epoch')
        priority = job.get('priority', 5)  # Fallback for missing priority
        
        # Include high priority jobs regardless of horizon
        if priority <= 2:
            return True
            
        # Apply horizon filter for lower priority jobs
        if lcd_date_epoch and lcd_date_epoch > horizon_cutoff_epoch:
            return False
            
        return True
    
    def _prioritize_jobs(self, jobs: List[Dict[str, Any]], 
                        current_time_epoch: int) -> List[Dict[str, Any]]:
        """Sort and limit jobs by priority and urgency."""
        return sorted(jobs, key=lambda x: (
            x.get('priority', 5),  # Lower number = higher priority
            x.get('lcd_date_epoch', current_time_epoch + 999999)  # Earlier due date = higher priority
        ))[:self.config.max_jobs_limit]


class HorizonCalculator:
    """Calculates solver time horizon."""
    
    @staticmethod
    def calculate_horizon(jobs: List[Dict[str, Any]], min_horizon: int) -> int:
        """Calculate solver horizon based on job durations."""
        max_hours_need = 0
        
        for job_item in jobs:
            hours_val = HorizonCalculator._get_job_duration(job_item)
            
            try:
                hours_val = float(hours_val)
                if hours_val > max_hours_need:
                    max_hours_need = hours_val
            except (ValueError, TypeError):
                logger.warning(f"Job {job_item.get('job_id')} has invalid duration values")
        
        if max_hours_need == 0:
            max_hours_need = 1.0  # Use 1.0 instead of MIN_DAILY_HOURS constant
            
        # Use 1.5 multiplier and 24 hour buffer (matching your .env philosophy)
        horizon = int(max_hours_need * len(jobs) * 1.5) + 24
        return max(horizon, min_horizon)
    
    @staticmethod
    def _get_job_duration(job_item: Dict[str, Any]) -> float:
        """Get job duration using HOURS_NEED as primary field."""
        # Primary: Use HOURS_NEED
        hours_need = job_item.get('hours_need')
        if hours_need is not None:
            try:
                return float(hours_need)
            except (ValueError, TypeError):
                pass
        
        return 1.0  # Fallback minimum


class JobDurationCalculator:
    """Calculates total job duration including overhead."""
    
    @staticmethod
    def calculate_total_job_hours(job_item: Dict[str, Any]) -> Optional[float]:
        """Calculate total hours needed including non-working time components."""
        # Get base duration using priority logic
        total_hours = JobDurationCalculator._get_base_duration(job_item)
        if total_hours is None or total_hours <= 0:
            return None
        
        # Add overhead time components
        total_hours += JobDurationCalculator._calculate_overhead(job_item)
        
        return total_hours
    
    @staticmethod
    def _get_base_duration(job_item: Dict[str, Any]) -> Optional[float]:
        """Get base duration using HOURS_NEED as primary field."""
        job_id = job_item.get('job_id', 'Unknown')
        
        # Primary: HOURS_NEED
        hours_need = job_item.get('hours_need')
        if hours_need is not None:
            try:
                hours_val = float(hours_need)
                if hours_val > 0:
                    logger.debug(f"Using HOURS_NEED for job {job_id}: {hours_val} hours")
                    return hours_val
            except (ValueError, TypeError):
                pass
        
        # Fallback: Calculate from quantity and output rate
        return JobDurationCalculator._calculate_from_quantity(job_item)
    
    @staticmethod
    def _calculate_from_quantity(job_item: Dict[str, Any]) -> Optional[float]:
        """Calculate duration from job quantity and output rate."""
        job_id = job_item.get('job_id', 'Unknown')
        job_quantity = job_item.get('job_quantity', 0)
        output_per_hour = job_item.get('expect_output_per_hour', 0)
        
        if (job_quantity and output_per_hour and 
            job_quantity > 0 and output_per_hour > 0):
            try:
                calculated_hours = job_quantity / output_per_hour
                logger.info(
                    f"Calculated hours_need for job {job_id}: "
                    f"{calculated_hours} hours from {job_quantity} qty / "
                    f"{output_per_hour} per hour"
                )
                return calculated_hours
            except ZeroDivisionError:
                logger.error(f"Division by zero for job {job_id}")
                return None
        
        logger.error(
            f"❌ Job {job_id} has no valid duration data - cannot schedule"
        )
        return None
    
    @staticmethod
    def _calculate_overhead(job_item: Dict[str, Any]) -> float:
        """Calculate overhead time from setup, break, and non-productive time."""
        overhead = 0.0
        
        # Setup time
        setup_time = job_item.get('setup_time') or job_item.get('setting_hours', 0)
        if setup_time:
            try:
                if 'setup_time' in job_item:
                    overhead += float(setup_time) / 3600  # Convert seconds to hours
                else:
                    overhead += float(setup_time)  # Already in hours
            except (ValueError, TypeError):
                pass
        
        # Break time
        break_time = job_item.get('break_time') or job_item.get('break_hours', 0)
        if break_time:
            try:
                if 'break_time' in job_item:
                    overhead += float(break_time) / 3600
                else:
                    overhead += float(break_time)
            except (ValueError, TypeError):
                pass
        
        # Non-productive time
        no_prod_time = job_item.get('no_prod_time') or job_item.get('no_prod', 0)
        if no_prod_time:
            try:
                if 'no_prod_time' in job_item:
                    overhead += float(no_prod_time) / 3600
                else:
                    overhead += float(no_prod_time)
            except (ValueError, TypeError):
                pass
        
        return overhead


class CPSATModelBuilder:
    """Builds CP-SAT model with variables and constraints."""
    
    def __init__(self, config: SchedulingConfig):
        self.config = config
        self.model = cp_model.CpModel()
        self.all_tasks: Dict[str, TaskInfo] = {}
        self.all_starts: List[Any] = []
        self.all_ends: List[Any] = []
        self.all_intervals: List[Any] = []
        self.jobs_on_machine: Dict[str, List[Any]] = defaultdict(list)
        self.job_dependencies: Dict[str, List[str]] = defaultdict(list)
        self.start_date_processes: Dict[str, int] = {}
        self.jobs_with_due_dates: Dict[str, int] = {}
        # start_time_preferences removed - no longer using START_DATE constraints
    
    def create_model(self, jobs: List[Dict[str, Any]], 
                    machines: List[str], horizon: int) -> None:
        """Create CP-SAT model with variables and basic constraints."""
        logger.info(f"Creating CP-SAT model for {len(jobs)} jobs, horizon: {horizon}")
        
        self._create_job_variables(jobs, horizon)
        self._add_machine_constraints(machines)
        
        if not self.all_tasks:
            raise SchedulingError("No valid tasks created after processing constraints")
    
    def _create_job_variables(self, jobs: List[Dict[str, Any]], horizon: int) -> None:
        """Create variables and intervals for all jobs."""
        for job_item in jobs:
            task_info = self._create_single_job_variables(job_item, horizon)
            if task_info:
                job_id = job_item['job_id']
                self.all_tasks[job_id] = task_info
                self._record_job_metadata(job_item, job_id)
    
    def _create_single_job_variables(self, job_item: Dict[str, Any], 
                                   horizon: int) -> Optional[TaskInfo]:
        """Create variables for a single job."""
        job_id = job_item['job_id']
        machine_name = job_item.get('MachineName_v')
        
        # Calculate total hours needed
        total_hours = JobDurationCalculator.calculate_total_job_hours(job_item)
        if total_hours is None or total_hours <= 0:
            logger.warning(f"Job {job_id} has invalid duration, skipping")
            return None
        
        # Convert to integer hours for solver
        hours_need = int(math.ceil(total_hours))
        logger.debug(
            f"Job {job_id}: Total hours={total_hours:.2f}, solver hours={hours_need}"
        )
        
        # Create CP-SAT variables
        start_var = self.model.NewIntVar(0, horizon, f'start_{job_id}')
        end_var = self.model.NewIntVar(0, horizon + hours_need, f'end_{job_id}')
        interval_var = self.model.NewIntervalVar(
            start_var, hours_need, end_var, f'interval_{job_id}'
        )
        
        # Record variables
        self.all_starts.append(start_var)
        self.all_ends.append(end_var)
        self.all_intervals.append(interval_var)
        
        # Add to machine-specific list
        self.jobs_on_machine[machine_name].append(interval_var)
        
        return TaskInfo(
            start=start_var,
            end=end_var,
            interval=interval_var,
            machine=machine_name,
            hours=hours_need,
            job=job_item
        )
    
    def _record_job_metadata(self, job_item: Dict[str, Any], job_id: str) -> None:
        """Record job metadata for constraints."""
        # Import here to avoid circular imports
        try:
            from app.utils.time_utils import epoch_to_relative_hours
            from app.scheduling.setup_buffer import get_start_date_epoch
        except ImportError:
            logger.warning("Could not import utility functions - using placeholder logic")
            return
        
        # Due dates
        if 'lcd_date_epoch' in job_item and job_item['lcd_date_epoch']:
            due_date_rel = epoch_to_relative_hours(job_item['lcd_date_epoch'])
            self.jobs_with_due_dates[job_id] = int(due_date_rel)
        
        # Start date constraints
        job_start_date_epoch_val = get_start_date_epoch(job_item)
        if job_start_date_epoch_val:
            start_date_rel = epoch_to_relative_hours(job_start_date_epoch_val)
            # START_DATE preferences no longer collected or used
            self.start_date_processes[job_id] = job_start_date_epoch_val
    
    def _add_machine_constraints(self, machines: List[str]) -> None:
        """Add NoOverlap constraints for each machine."""
        for machine_key in machines:
            if self.jobs_on_machine[machine_key]:
                self.model.AddNoOverlap(self.jobs_on_machine[machine_key])
                logger.debug(
                    f"Added NoOverlap constraint for machine {machine_key} "
                    f"with {len(self.jobs_on_machine[machine_key])} jobs"
                )


class ConstraintManager:
    """Manages different types of scheduling constraints."""
    
    def __init__(self, config: SchedulingConfig):
        self.config = config
    
    def add_all_constraints(self, model_builder: CPSATModelBuilder, 
                          enforce_sequence: bool, max_operators: Optional[int],
                          enforce_deadlines: bool) -> None:
        """Add all scheduling constraints to the model."""
        if enforce_sequence:
            self._add_sequence_constraints(model_builder)
        
        if max_operators is not None and max_operators > 0:
            self._add_operator_constraints(model_builder, max_operators)
        
        # START_DATE constraints removed - solver has full flexibility for job scheduling
        
        if enforce_deadlines:
            self._add_deadline_constraints(model_builder)
        
        self._add_working_hours_constraints(model_builder)
    
    def _add_sequence_constraints(self, model_builder: CPSATModelBuilder) -> None:
        """Add sequence constraints between processes of the same family."""
        logger.info("Adding sequence constraints between processes of the same family")
        
        try:
            from app.scheduling.scheduler_utils import (
                extract_job_family, extract_process_number
            )
        except ImportError:
            logger.warning("Could not import scheduler utilities - skipping sequence constraints")
            return
        
        # Group jobs by family
        job_families = defaultdict(list)
        for job_id, task_info in model_builder.all_tasks.items():
            original_job_id = task_info.job.get('job')
            family = extract_job_family(job_id, job_id_suffix=original_job_id)
            process_num = extract_process_number(job_id)
            
            if process_num != 999:
                job_families[family].append((process_num, job_id))
            else:
                logger.warning(f"Job {job_id} has invalid process number, cannot enforce sequence")
        
        # Add precedence constraints
        for family_key, processes in job_families.items():
            processes.sort()  # Sort by process number
            for i in range(len(processes) - 1):
                pred_job_id = processes[i][1]
                succ_job_id = processes[i+1][1]
                
                if (pred_job_id in model_builder.all_tasks and 
                    succ_job_id in model_builder.all_tasks):
                    pred_end = model_builder.all_tasks[pred_job_id].end
                    succ_start = model_builder.all_tasks[succ_job_id].start
                    model_builder.model.Add(pred_end <= succ_start)
                    model_builder.job_dependencies[succ_job_id].append(pred_job_id)
                    logger.debug(f"Added sequence constraint: {pred_job_id} before {succ_job_id}")
    
    def _add_operator_constraints(self, model_builder: CPSATModelBuilder, 
                                max_operators: int) -> None:
        """Add cumulative operator constraints."""
        logger.info(f"Adding cumulative operator constraint with capacity {max_operators}")
        
        operator_demands = []
        operator_intervals = []
        
        for job_id, task_info in model_builder.all_tasks.items():
            num_ops = task_info.job.get('operators') or task_info.job.get('number_operator', 1)
            try:
                num_ops = int(num_ops) if num_ops is not None else 1
                if num_ops > 0:
                    operator_intervals.append(task_info.interval)
                    operator_demands.append(num_ops)
            except (ValueError, TypeError):
                logger.warning(f"Invalid operator count for job {job_id}: {num_ops}")
        
        if operator_intervals:
            model_builder.model.AddCumulative(operator_intervals, operator_demands, max_operators)
            logger.info(f"Added Cumulative constraint for {len(operator_intervals)} tasks requiring operators")
    
    # START_DATE constraint methods removed - solver now has full flexibility to schedule jobs
    # without being restricted by start date preferences
    
    def _add_deadline_constraints(self, model_builder: CPSATModelBuilder) -> None:
        """Log LCD_DATE (deadline) information as soft constraints - no hard enforcement."""
        logger.info("Logging LCD_DATE (deadline) information as soft constraints - no hard enforcement")
        
        try:
            from app.utils.time_utils import epoch_to_relative_hours, datetime_to_epoch
            current_time_rel = epoch_to_relative_hours(datetime_to_epoch(datetime.now()))
        except ImportError:
            logger.warning("Could not import time utilities - using fallback")
            current_time_rel = 0
        
        deadline_count = 0
        overdue_count = 0
        
        for job_id, due_date_rel_int in model_builder.jobs_with_due_dates.items():
            if job_id in model_builder.all_tasks:
                # Only log deadline information - no hard constraints
                if due_date_rel_int < current_time_rel:
                    adjusted_deadline = current_time_rel + self.config.grace_period_hours
                    logger.debug(
                        f"Soft deadline (LCD_DATE) for overdue job {job_id}: "
                        f"target end <= {int(adjusted_deadline)} (original: {due_date_rel_int})"
                    )
                    overdue_count += 1
                else:
                    logger.debug(f"Soft deadline (LCD_DATE) for job {job_id}: target end <= {due_date_rel_int}")
                
                deadline_count += 1
        
        logger.info(f"✅ Logged {deadline_count} soft deadline constraints ({overdue_count} overdue) - no hard enforcement")
    
    def _add_working_hours_constraints(self, model_builder: CPSATModelBuilder) -> None:
        """Add simplified working hours constraints using time_availability module (like greedy solver)."""
        try:
            from app.scheduling.time_availability import is_time_available_for_scheduling, get_next_available_slot
            from app.utils.time_utils import relative_hours_to_epoch, epoch_to_datetime
        except ImportError:
            logger.error("❌ CRITICAL: Could not import time_availability module - working hours constraints DISABLED")
            raise ImportError("time_availability module required for working hours constraints")
        
        logger.info("Adding simplified working hours constraints using time_availability module")
        
        constraints_added = 0
        failed_jobs = []
        
        for job_id, task_info in model_builder.all_tasks.items():
            if self._add_simplified_working_hours_constraint(model_builder, job_id, task_info):
                constraints_added += 1
            else:
                failed_jobs.append(job_id)
        
        if failed_jobs:
            logger.error(f"❌ WORKING HOURS CONSTRAINT FAILURES: {len(failed_jobs)} jobs cannot be scheduled")
            logger.error(f"❌ Failed jobs: {failed_jobs[:10]}{'...' if len(failed_jobs) > 10 else ''}")
            raise ValueError(f"Working hours constraints failed for {len(failed_jobs)} jobs: {failed_jobs[:5]}")
        
        logger.info(f"✅ Added simplified working hours constraints for {constraints_added} jobs")
    
    def _add_simplified_working_hours_constraint(self, model_builder: CPSATModelBuilder,
                                               job_id: str, task_info: TaskInfo) -> bool:
        """Add preemptive working hours constraint - jobs can pause during breaks and resume.
        
        This implementation:
        1. Allows jobs to start during ANY working hour
        2. Jobs automatically pause during breaks and non-working hours
        3. Jobs resume after breaks and can span multiple days
        4. No matter how many hundred hours a job takes, it follows this principle
        """
        try:
            from app.scheduling.time_availability import is_time_available_for_scheduling
            from app.utils.time_utils import relative_hours_to_epoch, epoch_to_datetime
        except ImportError:
            logger.error(f"❌ Could not import time_availability module for job {job_id} - CONSTRAINT FAILED")
            return False
        
        start_var = task_info.start
        end_var = task_info.end
        job_duration = task_info.hours  # This is the actual work hours needed
        
        # Find all valid working hour slots where job can START
        valid_start_hours = []
        
        # Check potential start times over next 60 days (to handle very long jobs)
        max_search_days = 60
        for day_offset in range(max_search_days):
            for hour_offset in range(24):
                absolute_hour = day_offset * 24 + hour_offset
                
                try:
                    # Check if this hour is a valid working hour for STARTING a job
                    epoch_time = relative_hours_to_epoch(absolute_hour)
                    dt = epoch_to_datetime(epoch_time)
                    
                    if dt and is_time_available_for_scheduling(dt):
                        valid_start_hours.append(absolute_hour)
                except Exception:
                    continue
        
        if not valid_start_hours:
            logger.error(f"❌ CONSTRAINT FAILED: No working hours found for job {job_id} within {max_search_days} days")
            return False
        
        # For preemptive scheduling, we need to calculate the END time considering breaks
        # The job will take job_duration WORKING hours, not wall clock hours
        
        # Create constraint: job must start during a working hour
        if len(valid_start_hours) == 1:
            # Simple case - only one valid start time
            model_builder.model.Add(start_var == valid_start_hours[0])
            logger.info(f"✅ Preemptive scheduling for job {job_id}: Single start slot at hour {valid_start_hours[0]}")
        else:
            # Multiple valid start times - create OR constraint
            start_time_bools = []
            
            # Group consecutive hours into ranges for efficiency
            ranges = self._group_consecutive_hours(valid_start_hours)
            
            # Limit ranges to prevent solver overload, but ensure good coverage
            max_ranges = 100  # Increased from 50 to handle long planning horizons
            for i, (range_start, range_end) in enumerate(ranges[:max_ranges]):
                range_bool = model_builder.model.NewBoolVar(f'start_range_{job_id}_{i}')
                
                # If this range is chosen, start must be within it
                model_builder.model.Add(start_var >= range_start).OnlyEnforceIf(range_bool)
                model_builder.model.Add(start_var <= range_end).OnlyEnforceIf(range_bool)
                start_time_bools.append(range_bool)
            
            if start_time_bools:
                # Exactly one valid range must be chosen
                model_builder.model.AddExactlyOne(start_time_bools)
                logger.info(f"✅ Preemptive scheduling for job {job_id} (duration: {job_duration}h): "
                          f"{len(ranges)} valid start ranges, job will pause/resume across breaks")
            else:
                logger.error(f"❌ CONSTRAINT FAILED: Could not create valid time ranges for job {job_id}")
                return False
        
        # Add constraint to ensure END time accounts for breaks
        # The END variable should be at least START + duration + break_time
        # This is a simplified constraint - the actual break calculation happens in post-processing
        
        # Calculate minimum wall clock time needed (rough estimate with breaks)
        # Assuming ~2.25 hours of breaks per day (from database)
        days_needed = job_duration / 17.5  # 17.5 working hours per day
        estimated_breaks = days_needed * 2.25
        min_wall_clock_hours = job_duration + estimated_breaks
        
        # Ensure end time is realistic
        model_builder.model.Add(end_var >= start_var + int(min_wall_clock_hours))
        
        logger.debug(f"Job {job_id}: {job_duration}h work = ~{days_needed:.1f} days = "
                    f"~{min_wall_clock_hours:.1f}h wall clock time")
        
        return True
    
    def _can_job_run_continuously(self, start_hour: float, duration: float) -> bool:
        """Check if a job can run continuously from start_hour for duration hours without hitting breaks."""
        try:
            from app.scheduling.time_availability import is_time_available_for_scheduling
            from app.utils.time_utils import relative_hours_to_epoch, epoch_to_datetime
            
            # Check every hour the job would run
            for hour_offset in range(int(duration) + 1):  # +1 to include the end hour
                check_hour = start_hour + hour_offset
                
                try:
                    epoch_time = relative_hours_to_epoch(check_hour)
                    dt = epoch_to_datetime(epoch_time)
                    
                    if not dt or not is_time_available_for_scheduling(dt):
                        return False  # Hit a break or non-working time
                except Exception:
                    return False  # Error in time conversion
            
            return True  # All hours are available
            
        except ImportError:
            return False  # Can't check without time_availability
    
    def _group_consecutive_hours(self, hours: List[int]) -> List[Tuple[int, int]]:
        """Group consecutive hours into ranges for efficient constraint creation."""
        if not hours:
            return []
        
        hours = sorted(set(hours))  # Remove duplicates and sort
        ranges = []
        range_start = hours[0]
        range_end = hours[0]
        
        for hour in hours[1:]:
            if hour == range_end + 1:
                # Consecutive hour - extend current range
                range_end = hour
            else:
                # Gap found - close current range and start new one
                ranges.append((range_start, range_end))
                range_start = hour
                range_end = hour
        
        # Add the final range
        ranges.append((range_start, range_end))
        return ranges
    


class ObjectiveBuilder:
    """Builds objective function for the CP-SAT model."""
    
    def __init__(self, config: SchedulingConfig):
        self.config = config
    
    def create_objective(self, model_builder: CPSATModelBuilder, horizon: int) -> List[Any]:
        """Create multi-objective function."""
        objective_terms = []
        
        if not model_builder.all_ends:
            return objective_terms
        
        # 1. Priority penalties
        priority_terms = self._create_priority_objective(model_builder, horizon)
        if priority_terms:
            objective_terms.extend(priority_terms)
        
        # 2. Makespan
        makespan = model_builder.model.NewIntVar(0, horizon * 2, 'makespan')
        model_builder.model.AddMaxEquality(makespan, model_builder.all_ends)
        objective_terms.append(makespan)
        
        return objective_terms
    
    def _create_priority_objective(self, model_builder: CPSATModelBuilder,
                                 horizon: int) -> List[Any]:
        """Create priority-based objective terms."""
        priority_penalty_vars = []
        
        for job_id, task_info in model_builder.all_tasks.items():
            priority = task_info.job.get('priority', 3)
            try:
                priority = int(priority)
            except (ValueError, TypeError):
                priority = 3
            
            if priority > 0:
                start_var = task_info.start
                priority_penalty = model_builder.model.NewIntVar(
                    0, horizon * priority * 10, f'priority_penalty_{job_id}'
                )
                model_builder.model.Add(priority_penalty == start_var * priority)
                priority_penalty_vars.append(priority_penalty)
        
        if priority_penalty_vars:
            total_priority_penalty = model_builder.model.NewIntVar(
                0, horizon * len(priority_penalty_vars) * 30, 'total_priority_penalty'
            )
            model_builder.model.Add(total_priority_penalty == sum(priority_penalty_vars))
            weighted_penalty = total_priority_penalty * self.config.priority_weight
            logger.debug(
                f"Added priority optimization for {len(priority_penalty_vars)} jobs "
                f"with weight {self.config.priority_weight}"
            )
            return [weighted_penalty]
        
        return []


class CPSATSolver:
    """Handles CP-SAT solver configuration and execution."""
    
    def __init__(self, config: SchedulingConfig):
        self.config = config
    
    def solve_model(self, model: cp_model.CpModel) -> SolverResult:
        """Solve the CP-SAT model with optimized configuration."""
        solver = cp_model.CpSolver()
        
        # Configure solver parameters
        solver.parameters.max_time_in_seconds = float(self.config.solver_time_limit_seconds)
        solver.parameters.log_search_progress = False
        solver.parameters.log_to_stdout = False
        
        # Performance optimizations
        solver.parameters.num_search_workers = min(
            os.cpu_count() or 4, self.config.max_workers_limit
        )
        solver.parameters.search_branching = cp_model.PORTFOLIO_SEARCH
        solver.parameters.cp_model_presolve = True
        solver.parameters.linearization_level = 2
        
        # Gap limits for early termination
        solver.parameters.relative_gap_limit = self.config.relative_gap_limit
        solver.parameters.absolute_gap_limit = self.config.absolute_gap_limit
        
        # Additional optimizations
        solver.parameters.cp_model_probing_level = 0
        solver.parameters.symmetry_level = 1
        
        logger.info(
            f"Solver configured: time_limit={self.config.solver_time_limit_seconds}s, "
            f"workers={solver.parameters.num_search_workers}, "
            f"gap_limits=[rel:{self.config.relative_gap_limit*100:.1f}%, "
            f"abs:{self.config.absolute_gap_limit}]"
        )
        
        # Solve with timing
        start_solve_time = time.time()
        status = solver.Solve(model)
        solve_time = time.time() - start_solve_time
        
        # Log results
        self._log_solver_results(solver, status, solve_time)
        
        return SolverResult(
            solver=solver,
            status=status,
            solve_time=solve_time,
            model=model,
            performance_warning=solve_time > 25
        )
    
    def _log_solver_results(self, solver: cp_model.CpSolver, status: int, solve_time: float) -> None:
        """Log solver results with appropriate level."""
        if status == cp_model.OPTIMAL:
            logger.info(f"✅ OPTIMAL solution found in {solve_time:.2f}s, objective: {solver.ObjectiveValue()}")
        elif status == cp_model.FEASIBLE:
            logger.info(f"✅ FEASIBLE solution found in {solve_time:.2f}s, objective: {solver.ObjectiveValue()}")
        elif status == cp_model.UNKNOWN:
            logger.warning(f"⏱️  Solver timed out after {solve_time:.2f}s")
        elif status == cp_model.INFEASIBLE:
            logger.error(f"❌ INFEASIBLE problem in {solve_time:.2f}s")
        else:
            logger.error(f"❌ Solver failed with status: {solver.StatusName(status)} in {solve_time:.2f}s")
        
        if solve_time > 25:
            logger.warning(f"⚠️  Solver took {solve_time:.1f}s (>25s) - consider reducing problem size")


class ResultProcessor:
    """Processes solver results into final schedule format."""
    
    def __init__(self, config: SchedulingConfig):
        self.config = config
    
    def process_results(self, solver_result: SolverResult, model_builder: CPSATModelBuilder,
                       reference_time_epoch: int, enforce_sequence: bool) -> Dict[str, Any]:
        """Process solver results and create final schedule."""
        metadata = self._create_metadata(solver_result, model_builder, reference_time_epoch)
        results = {'_metadata': metadata}
        
        if solver_result.status in [cp_model.OPTIMAL, cp_model.FEASIBLE]:
            job_results = self._process_successful_solution(solver_result, model_builder)
            results.update(job_results)
            
            if enforce_sequence:
                self._validate_sequence_constraints(results, model_builder.job_dependencies)
        else:
            self._handle_failed_solution(solver_result, metadata)
        
        return results
    
    def _create_metadata(self, solver_result: SolverResult, model_builder: CPSATModelBuilder,
                        reference_time_epoch: int) -> Dict[str, Any]:
        """Create comprehensive metadata for the results."""
        solver = solver_result.solver
        status = solver_result.status
        solve_time = solver_result.solve_time
        
        metadata = {
            'status': solver.StatusName(status),
            'solver_time': solve_time,
            'objective_value': solver.ObjectiveValue() if status in [cp_model.OPTIMAL, cp_model.FEASIBLE] else None,
            'reference_time_epoch': reference_time_epoch,
            'job_dependencies': model_builder.job_dependencies,
            'start_date_constraints': model_builder.start_date_processes,
            'due_dates_considered': model_builder.jobs_with_due_dates,
            'solver_stats': solver.ResponseStats(),
            'performance_metrics': {
                'solve_time_seconds': solve_time,
                'is_optimal': status == cp_model.OPTIMAL,
                'is_feasible': status in [cp_model.OPTIMAL, cp_model.FEASIBLE],
                'timed_out': status == cp_model.UNKNOWN,
                'performance_warning': solver_result.performance_warning,
                'num_jobs_processed': len(model_builder.all_tasks),
                'solver_efficiency': 'FAST' if solve_time < 10 else 'MEDIUM' if solve_time < 25 else 'SLOW'
            }
        }
        
        # Add performance recommendations
        recommendations = []
        if solver_result.performance_warning:
            recommendations.append("Consider reducing planning horizon or job limit")
        if status == cp_model.UNKNOWN:
            recommendations.append("Solver timed out - try smaller problem size")
        if solve_time < 5 and len(model_builder.all_tasks) < 50:
            recommendations.append("Problem size is small - could increase planning horizon")
        
        metadata['recommendations'] = recommendations
        return metadata
    
    def _process_successful_solution(self, solver_result: SolverResult,
                                   model_builder: CPSATModelBuilder) -> Dict[str, Any]:
        """Process successful solver solution."""
        solver = solver_result.solver
        job_results = {}
        
        for job_id, task_info in model_builder.all_tasks.items():
            start_val_rel = solver.Value(task_info.start)
            end_val_rel = solver.Value(task_info.end)
            
            # Convert relative times back to epoch timestamps
            start_epoch, end_epoch = self._convert_relative_to_epoch(start_val_rel, end_val_rel)
            
            # Skip time availability adjustments - CP-SAT already enforces working hours constraints
            # The solver's working hours constraints (lines 788-817) handle this properly
            # Post-processing adjustments would override the solver's optimized decisions
            
            job_result = {
                'job_id': job_id,
                'machine': task_info.machine,
                'start': int(start_epoch),
                'end': int(end_epoch),
                'priority': task_info.job.get('priority', 3),
                'duration_hours': task_info.hours,
                'original_job_data': task_info.job
            }
            job_results[job_id] = job_result
            
            self._log_job_schedule(job_id, task_info.machine, start_epoch, end_epoch)
        
        # No post-processing adjustments made - CP-SAT solver handles working hours constraints
        logger.info(f"CP-SAT solution respects working hours constraints without post-processing adjustments")
        
        return job_results
    
    def _convert_relative_to_epoch(self, start_val_rel: int, end_val_rel: int) -> Tuple[int, int]:
        """Convert relative solver times to epoch timestamps."""
        try:
            from app.utils.time_utils import relative_hours_to_epoch
            start_epoch = relative_hours_to_epoch(start_val_rel)
            end_epoch = relative_hours_to_epoch(end_val_rel)
            return start_epoch, end_epoch
        except ImportError:
            logger.warning("Could not import time utilities - using placeholder conversion")
            # Fallback: assume current time as reference
            current_time = int(time.time())
            start_epoch = current_time + (start_val_rel * 3600)
            end_epoch = current_time + (end_val_rel * 3600)
            return start_epoch, end_epoch
    
    def _adjust_for_working_hours(self, start_epoch: int, end_epoch: int,
                                job_id: str) -> Tuple[int, int]:
        """Adjust job times for working hours compliance."""
        try:
            from app.scheduling.time_availability import is_time_available, get_next_available_slot
            
            if not is_time_available(start_epoch, end_epoch):
                duration_hours = (end_epoch - start_epoch) / 3600
                next_available_start = get_next_available_slot(start_epoch, duration_hours)
                
                if next_available_start:
                    new_start_epoch = next_available_start
                    new_end_epoch = new_start_epoch + (end_epoch - start_epoch)
                    logger.info(f"Moved job {job_id} to comply with working hours")
                    return new_start_epoch, new_end_epoch
        except ImportError:
            logger.warning("Could not import time availability utilities")
        
        return start_epoch, end_epoch
    
    def _log_job_schedule(self, job_id: str, machine: str, start_epoch: int, end_epoch: int) -> None:
        """Log individual job schedule."""
        try:
            from app.utils.time_utils import epoch_to_datetime, format_datetime_for_display
            start_str = format_datetime_for_display(epoch_to_datetime(start_epoch))
            end_str = format_datetime_for_display(epoch_to_datetime(end_epoch))
            logger.debug(f"Scheduled {job_id} on {machine}: Start={start_str}, End={end_str}")
        except ImportError:
            logger.debug(f"Scheduled {job_id} on {machine}: Start={start_epoch}, End={end_epoch}")
    
    def _handle_failed_solution(self, solver_result: SolverResult, metadata: Dict[str, Any]) -> None:
        """Handle failed solver solutions."""
        status = solver_result.status
        solver = solver_result.solver
        
        if status == cp_model.INFEASIBLE:
            logger.error("No solution found: The problem is infeasible")
            metadata['message'] = "The scheduling problem is infeasible with the given constraints"
        elif status == cp_model.MODEL_INVALID:
            logger.error("No solution found: The model is invalid")
            metadata['message'] = "The CP-SAT model is invalid"
        else:
            logger.warning(f"No optimal/feasible solution found. Status: {solver.StatusName(status)}")
            metadata['message'] = f"Solver did not find optimal/feasible solution. Status: {solver.StatusName(status)}"
    
    def _validate_sequence_constraints(self, results: Dict[str, Any],
                                     job_dependencies: Dict[str, List[str]]) -> None:
        """Validate sequence constraints in final schedule."""
        logger.info("Validating sequence constraints in final schedule")
        violations = 0
        
        for succ_job_id, pred_job_ids in job_dependencies.items():
            if succ_job_id not in results:
                continue
            
            succ_start_epoch = results[succ_job_id]['start']
            for pred_job_id in pred_job_ids:
                if pred_job_id not in results:
                    continue
                
                pred_end_epoch = results[pred_job_id]['end']
                if pred_end_epoch > succ_start_epoch:
                    violations += 1
                    logger.error(
                        f"SEQUENCE VIOLATION: {pred_job_id} (ends {pred_end_epoch}) "
                        f"should end before {succ_job_id} (starts {succ_start_epoch})"
                    )
        
        if violations > 0:
            logger.error(f"Found {violations} sequence violations in the CP-SAT schedule!")
            results['_metadata']['sequence_violations'] = violations
        else:
            logger.info("All sequence constraints are satisfied")


def schedule_jobs(
    jobs: List[Dict[str, Any]], 
    machines: List[Union[str, Dict[str, Any]]], 
    setup_times: Optional[Dict] = None, 
    enforce_sequence: bool = True, 
    time_limit_seconds: Optional[int] = None,
    max_operators: Optional[int] = None,
    max_jobs_limit: Optional[int] = None,
    planning_horizon_days: Optional[int] = None,
    enforce_deadlines: bool = True
) -> Dict[str, Any]:
    """
    Schedule jobs using Google's CP-SAT solver with performance optimizations.
    
    Args:
        jobs: List of job dictionaries with job_id, MachineName_v, hours_need, etc.
        machines: List of machine names or machine dictionaries
        setup_times: Optional setup times (not used in CP-SAT)
        enforce_sequence: Whether to enforce job sequence constraints
        time_limit_seconds: Solver time limit (from .env if None)
        max_operators: Maximum number of operators (optional)
        max_jobs_limit: Maximum number of jobs (from .env if None)
        planning_horizon_days: Planning horizon (from .env if None)
        enforce_deadlines: Whether to enforce deadline constraints
        
    Returns:
        Schedule dictionary with results and metadata
    """
    try:
        # Load configuration from .env
        config = SchedulingConfigManager.load_config()
        
        # Override with function parameters if provided
        if time_limit_seconds is not None:
            config.solver_time_limit_seconds = time_limit_seconds
        if max_jobs_limit is not None:
            config.max_jobs_limit = max_jobs_limit
        if planning_horizon_days is not None:
            config.planning_horizon_days = planning_horizon_days
        
        # Apply dynamic limits based on problem size
        dynamic_limits = config.get_dynamic_limits(len(jobs))
        config.solver_time_limit_seconds = dynamic_limits['time_limit_seconds']
        config.planning_horizon_days = min(
            config.planning_horizon_days, 
            dynamic_limits['planning_horizon_days']
        )
        config.max_jobs_limit = min(config.max_jobs_limit, dynamic_limits['max_jobs_limit'])
        
        logger.info(
            f"Using CP-SAT solver to schedule {len(jobs)} jobs on {len(machines)} machines"
        )
        logger.info(
            f"Configuration: time_limit={config.solver_time_limit_seconds}s, "
            f"max_jobs={config.max_jobs_limit}, horizon={config.planning_horizon_days}d"
        )
        
        start_time = time.time()
        
        # Validate and normalize inputs
        valid_jobs = JobValidator.validate_jobs(jobs)
        machine_names = JobValidator.normalize_machines(machines)
        
        if not valid_jobs:
            logger.error("No valid jobs found")
            return _create_error_result("No valid jobs found")
        
        # Filter and limit jobs for performance
        try:
            from app.utils.time_utils import datetime_to_epoch
            current_time_epoch = datetime_to_epoch(datetime.now())
        except ImportError:
            current_time_epoch = int(time.time())
        
        filterer = JobFilterer(config)
        filtered_jobs = filterer.filter_and_limit_jobs(valid_jobs, current_time_epoch)
        
        if not filtered_jobs:
            logger.error("No jobs remaining after filtering")
            return _create_error_result("No jobs remaining after filtering")
        
        # Calculate horizon
        horizon = HorizonCalculator.calculate_horizon(filtered_jobs, config.minimum_horizon_hours)
        logger.info(f"Solver horizon set to {horizon} relative hours")
        
        # Build CP-SAT model
        model_builder = CPSATModelBuilder(config)
        try:
            model_builder.create_model(filtered_jobs, machine_names, horizon)
        except SchedulingError as e:
            logger.error(f"Failed to create model: {e}")
            return _create_error_result(str(e))
        
        # Add constraints
        constraint_manager = ConstraintManager(config)
        constraint_manager.add_all_constraints(
            model_builder, enforce_sequence, max_operators, enforce_deadlines
        )
        
        # Create objective function
        objective_builder = ObjectiveBuilder(config)
        objective_terms = objective_builder.create_objective(model_builder, horizon)
        
        if objective_terms:
            model_builder.model.Minimize(sum(objective_terms))
            logger.info("Objective function set to minimize makespan, tardiness, and priority penalties")
        else:
            logger.warning("No objective function created")
        
        # Solve model
        cpsat_solver = CPSATSolver(config)
        solver_result = cpsat_solver.solve_model(model_builder.model)
        
        # Process results
        result_processor = ResultProcessor(config)
        results = result_processor.process_results(
            solver_result, model_builder, current_time_epoch, enforce_sequence
        )
        
        total_time = time.time() - start_time
        logger.info(f"Total CP-SAT scheduling completed in {total_time:.2f} seconds")
        
        return results
        
    except ConfigurationError as e:
        logger.error(f"Configuration error: {e}")
        return _create_error_result(f"Configuration error: {e}")
    except Exception as e:
        logger.error(f"Unexpected error in schedule_jobs: {e}")
        return _create_error_result(f"Unexpected error: {e}")


def _create_error_result(message: str) -> Dict[str, Any]:
    """Create a standardized error result dictionary."""
    try:
        from app.utils.time_utils import datetime_to_epoch
        reference_time = datetime_to_epoch(datetime.now())
    except ImportError:
        reference_time = int(time.time())
    
    return {
        '_metadata': {
            'status': 'ERROR',
            'solver_time': 0,
            'objective_value': None,
            'reference_time_epoch': reference_time,
            'message': message
        }
    }


if __name__ == '__main__':
    """Example usage and testing."""
    logging.basicConfig(level=logging.INFO)
    start_time = time.time()
    results = None
    
    try:
        # Load configuration
        config = SchedulingConfigManager.load_config()
        logger.info("Configuration loaded successfully from .env")
        
        # Import test data loader
        try:
            from app.data_ingestion.mariadb_parser import load_jobs_planning_data
            
            # Load test data
            jobs, machines, setup_times = load_jobs_planning_data()
            if jobs and machines:
                logger.info(f"Loaded {len(jobs)} jobs and {len(machines)} machines for testing")
                results = schedule_jobs(jobs, machines, setup_times)
            else:
                logger.error("No jobs or machines loaded from database")
                results = _create_error_result("No jobs or machines loaded from database")
                
        except ImportError as e:
            logger.error(f"Could not import data loader: {e}")
            results = _create_error_result(f"Could not import data loader: {e}")
            
    except ConfigurationError as e:
        logger.error(f"Configuration error: {e}")
        results = _create_error_result(f"Configuration error: {e}")
    except Exception as e:
        logger.error(f"Error in main execution: {e}")
        results = _create_error_result(f"Error in main execution: {e}")
    finally:
        total_time = time.time() - start_time
        logger.info(f"Total execution time: {total_time:.2f} seconds")

    # Display results
    if results and results.get('_metadata', {}).get('status') in ['OPTIMAL', 'FEASIBLE']:
        print("\nCP-SAT Schedule Output (First 5 tasks per machine):")
        
        # Group by machine for display
        machine_grouped = defaultdict(list)
        for job_id_key, details in results.items():
            if job_id_key == '_metadata':
                continue
            machine_grouped[details['machine']].append(
                (details['job_id'], details['start'], details['end'], details['priority'])
            )

        # Sort by start time and display
        for machine_key in machine_grouped:
            machine_grouped[machine_key].sort(key=lambda x: x[1])

        for machine_key, tasks_list in machine_grouped.items():
            if tasks_list:
                print(f"  Machine: {machine_key}")
                for i, (job_id, start_epoch, end_epoch, priority) in enumerate(tasks_list[:5]):
                    try:
                        from app.utils.time_utils import epoch_to_datetime, format_datetime_for_display
                        start_str = format_datetime_for_display(epoch_to_datetime(start_epoch))
                        end_str = format_datetime_for_display(epoch_to_datetime(end_epoch))
                    except ImportError:
                        start_str = f"Epoch_{start_epoch}"
                        end_str = f"Epoch_{end_epoch}"
                    
                    print(f"    Task {i+1}: Job={job_id}, Start={start_str}, End={end_str}, Priority={priority}")
        
        metadata = results['_metadata']
        print(f"\nObjective Value: {metadata['objective_value']}")
        print(f"Solver Time: {metadata['solver_time']:.2f}s")
        print(f"Status: {metadata['status']}")
        
        perf_metrics = metadata.get('performance_metrics', {})
        print(f"Solver Efficiency: {perf_metrics.get('solver_efficiency', 'UNKNOWN')}")
        
        if metadata.get('recommendations'):
            print(f"Recommendations: {', '.join(metadata['recommendations'])}")
            
    else:
        print("No schedule generated or solution was not optimal/feasible")
        if results and '_metadata' in results:
            print(f"  Status: {results['_metadata'].get('status')}")
            print(f"  Message: {results['_metadata'].get('message')}")