# backend/app/reporting/schedule_orchestrator.py
"""Schedule orchestration and solver coordination for reporting endpoints."""

import logging
import os
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass

from app.data_ingestion.mariadb_parser import load_jobs_planning_data
from app.scheduling.greedy_solver import greedy_schedule as run_greedy_solver
from app.scheduling.batch_scheduler import smart_batch_schedule_jobs
from app.reporting.chart_generator import normalize_schedule_format

logger = logging.getLogger(__name__)

@dataclass
class ScheduleOrchestratorConfig:
    """Configuration for schedule orchestrator - loaded from .env."""
    
    max_jobs_limit: int
    planning_horizon_days: int
    default_solver_type: str = 'greedy'  # Hardcoded - only greedy solver available
    
    @classmethod
    def from_env(cls) -> 'ScheduleOrchestratorConfig':
        """Load configuration from environment variables with strict validation."""
        missing_vars = []
        invalid_vars = []
        
        def get_required_int_env(key: str) -> Optional[int]:
            """Get required integer environment variable."""
            value = os.getenv(key)
            if value is None:
                missing_vars.append(key)
                return None
            
            try:
                return int(value)
            except (ValueError, TypeError):
                invalid_vars.append(f"{key}={value}")
                return None
        
        def get_required_str_env(key: str) -> Optional[str]:
            """Get required string environment variable."""
            value = os.getenv(key)
            if value is None:
                missing_vars.append(key)
                return None
            return value.strip()
        
        # Load required variables
        max_jobs_limit = get_required_int_env('MAX_JOBS_LIMIT')
        planning_horizon_days = get_required_int_env('PLANNING_HORIZON_DAYS')
        
        # DEFAULT_SOLVER_TYPE is now hardcoded as 'greedy'
        default_solver_type = 'greedy'
        
        # Check for errors
        if missing_vars:
            error_msg = f"❌ CRITICAL ORCHESTRATOR CONFIG ERROR: Missing required environment variables: {', '.join(missing_vars)}"
            logger.error(error_msg)
            raise ValueError(error_msg)
        
        if invalid_vars:
            error_msg = f"❌ CRITICAL ORCHESTRATOR CONFIG ERROR: Invalid environment variable values: {', '.join(invalid_vars)}"
            logger.error(error_msg)
            raise ValueError(error_msg)
        
        logger.info(f"✅ Successfully loaded schedule orchestrator configuration from .env")
        
        return cls(
            max_jobs_limit=max_jobs_limit,
            planning_horizon_days=planning_horizon_days,
            default_solver_type=default_solver_type
        )

# Initialize configuration at module level
try:
    ORCHESTRATOR_CONFIG = ScheduleOrchestratorConfig.from_env()
    logger.info(f"✅ Schedule orchestrator initialized with {ORCHESTRATOR_CONFIG.default_solver_type} solver")
except Exception as e:
    logger.error(f"❌ FAILED to initialize schedule orchestrator configuration: {e}")
    raise

# Cache removed - always generate fresh results for real-time responsiveness

class ScheduleOrchestrator:
    """Orchestrates job data loading and solver execution."""
    
    @staticmethod
    def validate_solver_type(solver_type: str) -> str:
        """Validate solver type with strict checks."""
        if not isinstance(solver_type, str):
            raise ValueError(f"Solver type must be a string, got {type(solver_type)}")
        
        solver_type = solver_type.lower().strip()
        
        if solver_type not in ['greedy']:
            raise ValueError(f"Invalid solver type '{solver_type}'. Only 'greedy' solver is available")
        
        return solver_type
    
    @staticmethod
    def validate_schedule_output(schedule_output: Dict[str, List]) -> None:
        """Validate schedule output structure."""
        if not isinstance(schedule_output, dict):
            raise ValueError(f"Schedule output must be a dictionary, got {type(schedule_output)}")
        
        if not schedule_output:
            raise ValueError("Schedule output is empty")
        
        total_jobs = 0
        for machine, jobs in schedule_output.items():
            if not isinstance(jobs, list):
                raise ValueError(f"Jobs for machine '{machine}' must be a list, got {type(jobs)}")
            
            for i, job_tuple in enumerate(jobs):
                if not isinstance(job_tuple, (list, tuple)) or len(job_tuple) < 3:
                    raise ValueError(f"Job {i} for machine '{machine}' must be tuple/list with at least 3 elements")
                
                job_id, start_time, end_time = job_tuple[0], job_tuple[1], job_tuple[2]
                
                if not job_id:
                    raise ValueError(f"Job {i} for machine '{machine}' has empty job_id")
                
                if not isinstance(start_time, (int, float)) or not isinstance(end_time, (int, float)):
                    raise ValueError(f"Job {i} for machine '{machine}' has invalid timestamp types")
                
                if end_time <= start_time:
                    raise ValueError(f"Job {i} for machine '{machine}' has invalid timing: end <= start")
                
                total_jobs += 1
        
        if total_jobs == 0:
            raise ValueError("No valid jobs found in schedule output")
        
        logger.info(f"✅ Schedule validation passed: {total_jobs} jobs across {len(schedule_output)} machines")
    
    @staticmethod
    def validate_jobs_data(jobs_data: List[Dict]) -> None:
        """Validate jobs data structure."""
        if not isinstance(jobs_data, list):
            raise ValueError(f"Jobs data must be a list, got {type(jobs_data)}")
        
        if not jobs_data:
            raise ValueError("Jobs data is empty")
        
        required_fields = ['job_id']
        
        for i, job in enumerate(jobs_data):
            if not isinstance(job, dict):
                raise ValueError(f"Job {i} must be a dictionary, got {type(job)}")
            
            for field in required_fields:
                if field not in job:
                    raise ValueError(f"Job {i} missing required field '{field}'")
                
                if not job[field]:
                    raise ValueError(f"Job {i} has empty value for required field '{field}'")
        
        logger.info(f"✅ Jobs data validation passed: {len(jobs_data)} jobs")
    

async def get_schedule_and_job_data(
    solver_type: str, 
    max_jobs: Optional[int] = None
) -> Tuple[Dict[str, List], List[Dict[str, Any]]]:
    """Load job data and run scheduler with fresh results every time."""
    try:
        # Validate solver type
        solver_type = ScheduleOrchestrator.validate_solver_type(solver_type)
        
        effective_max_jobs = max_jobs or ORCHESTRATOR_CONFIG.max_jobs_limit
        
        logger.info(f"🔄 Generating fresh schedule data for solver '{solver_type}'")
        logger.info(f"🔄 Loading jobs data (max: {effective_max_jobs}, horizon: {ORCHESTRATOR_CONFIG.planning_horizon_days} days)")
        
        # Load data using MariaDB parser
        jobs_data, machines_data, setup_times_data = load_jobs_planning_data(
            max_jobs=effective_max_jobs,
            planning_horizon_days=ORCHESTRATOR_CONFIG.planning_horizon_days
        )
        
        if not jobs_data:
            logger.error("❌ NO JOBS DATA LOADED from database")
            raise ValueError("No jobs data available from database")
        
        # Validate jobs data
        ScheduleOrchestrator.validate_jobs_data(jobs_data)
        
        # Extract machine names with strict validation
        machine_names_list = []
        if machines_data and isinstance(machines_data, list):
            for machine in machines_data:
                if isinstance(machine, dict) and machine.get('MachineName_v'):
                    machine_names_list.append(machine['MachineName_v'])
        
        if not machine_names_list:
            # Fallback to extracting from jobs data
            machine_names_set = set()
            for job in jobs_data:
                if job.get('MachineName_v'):
                    machine_names_set.add(job['MachineName_v'])
            machine_names_list = list(machine_names_set)
        
        if not machine_names_list:
            logger.error("❌ NO MACHINE NAMES FOUND in data")
            raise ValueError("No machine names available for scheduling")
        
        logger.info(f"✅ Loaded {len(jobs_data)} jobs for {len(machine_names_list)} machines")
        
        # Run selected scheduling algorithm with parameter mismatch handling
        schedule_output = None
        
        # Only greedy solver is available
        logger.info("🔄 Running Greedy Solver")
        schedule_output = run_greedy_solver(jobs_data, machine_names_list, setup_times_data)
        
        if not schedule_output:
            logger.error("❌ GREEDY SOLVER RETURNED EMPTY RESULT")
            raise ValueError("Greedy solver failed to generate schedule")
        
        # Validate and normalize schedule output
        ScheduleOrchestrator.validate_schedule_output(schedule_output)
        schedule_output = normalize_schedule_format(schedule_output)
        
        total_scheduled = sum(len(jobs) for jobs in schedule_output.values())
        logger.info(f"✅ Fresh schedule ready: {total_scheduled} jobs scheduled")
        
        return (schedule_output, jobs_data)
        
    except Exception as e:
        logger.error(f"❌ SCHEDULE GENERATION FAILED: {e}")
        raise ValueError(f"Failed to generate schedule: {str(e)}")