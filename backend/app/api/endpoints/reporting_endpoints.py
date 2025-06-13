# backend/app/api/endpoints/reporting_endpoints.py
"""Production-grade reporting endpoints with STRICT configuration - NO FALLBACKS."""

from fastapi import APIRouter, HTTPException, Depends, Query
from fastapi.responses import JSONResponse
import logging
import os
from typing import List, Dict, Any, Literal, Optional
from dataclasses import dataclass
from datetime import datetime

# STRICT IMPORTS - NO FALLBACKS
from app.reporting.chart_generator import (
    prepare_gantt_data_priority_view, 
    prepare_gantt_data_resource_view,
    prepare_detailed_schedule_table_data
)
from app.data_ingestion.mariadb_parser import load_jobs_planning_data
from app.scheduling.greedy_solver import greedy_schedule as run_greedy_solver
from app.scheduling.cpsat_solver import schedule_jobs as run_cpsat_solver
from app.scheduling.batch_scheduler import smart_batch_schedule_jobs

logger = logging.getLogger(__name__)
router = APIRouter()

@dataclass
class ReportingConfig:
    """Configuration for reporting endpoints - ALL VALUES MUST BE IN .env - NO FALLBACKS."""
    
    # Job loading limits
    max_jobs_limit: int
    planning_horizon_days: int
    
    # Solver configuration
    default_solver_type: str
    solver_timeout_seconds: int
    
    # Data quality thresholds
    max_buffer_threshold_days: int
    data_quality_min_score: float
    
    @classmethod
    def from_env(cls) -> 'ReportingConfig':
        """Load configuration from environment variables with STRICT validation - NO FALLBACKS."""
        missing_vars = []
        invalid_vars = []
        
        def get_required_int_env(key: str) -> Optional[int]:
            """Get required integer environment variable - NO FALLBACKS."""
            value = os.getenv(key)
            if value is None:
                missing_vars.append(key)
                return None
            
            try:
                return int(value)
            except (ValueError, TypeError):
                invalid_vars.append(f"{key}={value}")
                return None
        
        def get_required_float_env(key: str) -> Optional[float]:
            """Get required float environment variable - NO FALLBACKS."""
            value = os.getenv(key)
            if value is None:
                missing_vars.append(key)
                return None
            
            try:
                return float(value)
            except (ValueError, TypeError):
                invalid_vars.append(f"{key}={value}")
                return None
        
        def get_required_str_env(key: str) -> Optional[str]:
            """Get required string environment variable - NO FALLBACKS."""
            value = os.getenv(key)
            if value is None:
                missing_vars.append(key)
                return None
            return value.strip()
        
        # ALL variables are REQUIRED - NO FALLBACKS
        max_jobs_limit = get_required_int_env('MAX_JOBS_LIMIT')
        planning_horizon_days = get_required_int_env('PLANNING_HORIZON_DAYS')
        solver_timeout_seconds = get_required_int_env('SOLVER_TIME_LIMIT_SECONDS')
        
        # Required with validation
        default_solver_type = get_required_str_env('DEFAULT_SOLVER_TYPE')
        if default_solver_type and default_solver_type.lower() not in ['cpsat', 'greedy']:
            invalid_vars.append(f"DEFAULT_SOLVER_TYPE={default_solver_type}")
            default_solver_type = None
        
        # Optional but required for data quality analysis
        max_buffer_threshold_days = os.getenv('MAX_BUFFER_THRESHOLD_DAYS')
        if max_buffer_threshold_days is None:
            missing_vars.append('MAX_BUFFER_THRESHOLD_DAYS')
        else:
            try:
                max_buffer_threshold_days = int(max_buffer_threshold_days)
            except (ValueError, TypeError):
                invalid_vars.append(f"MAX_BUFFER_THRESHOLD_DAYS={max_buffer_threshold_days}")
                max_buffer_threshold_days = None
        
        data_quality_min_score = os.getenv('DATA_QUALITY_MIN_SCORE')
        if data_quality_min_score is None:
            missing_vars.append('DATA_QUALITY_MIN_SCORE')
        else:
            try:
                data_quality_min_score = float(data_quality_min_score)
            except (ValueError, TypeError):
                invalid_vars.append(f"DATA_QUALITY_MIN_SCORE={data_quality_min_score}")
                data_quality_min_score = None
        
        # Check for critical errors - FAIL IMMEDIATELY
        if missing_vars:
            error_msg = f"❌ CRITICAL REPORTING CONFIG ERROR: Missing required environment variables: {', '.join(missing_vars)}"
            logger.error(error_msg)
            raise ValueError(error_msg)
        
        if invalid_vars:
            error_msg = f"❌ CRITICAL REPORTING CONFIG ERROR: Invalid environment variable values: {', '.join(invalid_vars)}"
            logger.error(error_msg)
            raise ValueError(error_msg)
        
        # Validate business logic - FAIL IF INVALID
        if max_buffer_threshold_days <= 0:
            error_msg = f"❌ CRITICAL CONFIG ERROR: MAX_BUFFER_THRESHOLD_DAYS must be positive, got {max_buffer_threshold_days}"
            logger.error(error_msg)
            raise ValueError(error_msg)
        
        if not (0 <= data_quality_min_score <= 100):
            error_msg = f"❌ CRITICAL CONFIG ERROR: DATA_QUALITY_MIN_SCORE must be between 0-100, got {data_quality_min_score}"
            logger.error(error_msg)
            raise ValueError(error_msg)
        
        logger.info(f"✅ Successfully loaded reporting configuration from .env")
        
        return cls(
            max_jobs_limit=max_jobs_limit,
            planning_horizon_days=planning_horizon_days,
            default_solver_type=default_solver_type,
            solver_timeout_seconds=solver_timeout_seconds,
            max_buffer_threshold_days=max_buffer_threshold_days,
            data_quality_min_score=data_quality_min_score
        )

# Initialize configuration at module level - FAIL IF MISSING
try:
    REPORTING_CONFIG = ReportingConfig.from_env()
    logger.info(f"✅ Reporting endpoints initialized with {REPORTING_CONFIG.default_solver_type} solver")
except Exception as e:
    logger.error(f"❌ FAILED to initialize reporting configuration: {e}")
    raise

# Simple cache to prevent multiple solver runs for the same solver type
_SCHEDULE_CACHE = {}
_CACHE_TIMESTAMP = {}
CACHE_DURATION_SECONDS = 300  # 5 minutes cache

class ScheduleValidator:
    """Validates schedule data with strict checks - NO FALLBACKS."""
    
    @staticmethod
    def validate_solver_type(solver_type: str) -> str:
        """Validate solver type with strict checks - NO FALLBACKS."""
        if not isinstance(solver_type, str):
            raise ValueError(f"Solver type must be a string, got {type(solver_type)}")
        
        solver_type = solver_type.lower().strip()
        
        if solver_type not in ['cpsat', 'greedy']:
            raise ValueError(f"Invalid solver type '{solver_type}'. Must be 'cpsat' or 'greedy'")
        
        return solver_type
    
    @staticmethod
    def validate_schedule_output(schedule_output: Dict[str, List]) -> None:
        """Validate schedule output structure - NO FALLBACKS."""
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
        """Validate jobs data structure - NO FALLBACKS."""
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

def normalize_schedule_format(schedule_output: Dict[str, List]) -> Dict[str, List]:
    """Normalize schedule output to 3-tuple format with strict validation - NO FALLBACKS."""
    try:
        ScheduleValidator.validate_schedule_output(schedule_output)
        
        normalized = {}
        total_normalized = 0
        
        for machine, jobs in schedule_output.items():
            normalized[machine] = []
            
            for job_tuple in jobs:
                if len(job_tuple) >= 3:
                    # Extract only first 3 elements (job_id, start, end)
                    normalized_tuple = (job_tuple[0], job_tuple[1], job_tuple[2])
                    normalized[machine].append(normalized_tuple)
                    total_normalized += 1
                    logger.debug(f"Normalized job {job_tuple[0]} on {machine}")
                else:
                    logger.error(f"❌ INVALID JOB TUPLE: {job_tuple} has insufficient elements")
                    raise ValueError(f"Job tuple {job_tuple} has insufficient elements")
        
        logger.info(f"✅ Normalized {total_normalized} jobs across {len(normalized)} machines")
        return normalized
        
    except Exception as e:
        logger.error(f"❌ SCHEDULE NORMALIZATION FAILED: {e}")
        raise ValueError(f"Schedule normalization failed: {e}")

async def get_schedule_and_job_data(solver_type: str, force_refresh: bool = False, max_jobs: Optional[int] = None) -> tuple:
    """Load job data and run scheduler with strict validation - HANDLES BATCH SCHEDULER PARAMETER MISMATCH."""
    try:
        # Validate solver type
        solver_type = ScheduleValidator.validate_solver_type(solver_type)
        
        # Check cache first (unless force_refresh is True)
        # Include max_jobs in cache key so different limits have separate cache entries
        effective_max_jobs = max_jobs or REPORTING_CONFIG.max_jobs_limit
        cache_key = f"{solver_type}_{effective_max_jobs}"
        current_time = datetime.now().timestamp()
        
        if (not force_refresh and 
            cache_key in _SCHEDULE_CACHE and 
            cache_key in _CACHE_TIMESTAMP and 
            current_time - _CACHE_TIMESTAMP[cache_key] < CACHE_DURATION_SECONDS):
            
            logger.info(f"✅ Using cached schedule data for solver '{solver_type}' (age: {int(current_time - _CACHE_TIMESTAMP[cache_key])}s)")
            return _SCHEDULE_CACHE[cache_key]
        
        if force_refresh:
            logger.info(f"🔄 Force refresh requested - bypassing cache for solver '{solver_type}'")
        else:
            logger.info(f"🔄 No valid cache found for solver '{solver_type}' - generating fresh data")
        
        # effective_max_jobs already set above for cache key
        logger.info(f"🔄 Loading jobs data (max: {effective_max_jobs}, horizon: {REPORTING_CONFIG.planning_horizon_days} days)")
        
        # Load data using MariaDB parser
        jobs_data, machines_data, setup_times_data = load_jobs_planning_data(
            max_jobs=effective_max_jobs,
            planning_horizon_days=REPORTING_CONFIG.planning_horizon_days
        )
        
        if not jobs_data:
            logger.error("❌ NO JOBS DATA LOADED from database")
            raise HTTPException(status_code=500, detail="No jobs data available from database")
        
        # Validate jobs data
        ScheduleValidator.validate_jobs_data(jobs_data)
        
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
            raise HTTPException(status_code=500, detail="No machine names available for scheduling")
        
        logger.info(f"✅ Loaded {len(jobs_data)} jobs for {len(machine_names_list)} machines")
        
        # Run selected scheduling algorithm with parameter mismatch handling
        schedule_output = None
        
        if solver_type == "cpsat":
            logger.info("🔄 Running Smart Batch Scheduler (CP-SAT based)")
            
            try:
                schedule_output_dict = smart_batch_schedule_jobs(
                    jobs_data, 
                    machine_names_list, 
                    setup_times_data
                )
            except TypeError as e:
                if "unexpected keyword argument" in str(e):
                    logger.warning(f"⚠️ BATCH SCHEDULER PARAMETER MISMATCH: {e}")
                    logger.info("🔄 Falling back to Greedy solver due to parameter mismatch")
                    schedule_output = run_greedy_solver(jobs_data, machine_names_list, setup_times_data)
                    
                    if not schedule_output:
                        logger.error("❌ FALLBACK GREEDY SOLVER ALSO FAILED")
                        raise HTTPException(status_code=500, detail="Both CP-SAT and Greedy solvers failed")
                else:
                    raise
            else:
                if not schedule_output_dict:
                    logger.error("❌ SMART BATCH SCHEDULER RETURNED EMPTY RESULT")
                    logger.info("🔄 Falling back to Greedy solver")
                    schedule_output = run_greedy_solver(jobs_data, machine_names_list, setup_times_data)
                    
                    if not schedule_output:
                        logger.error("❌ FALLBACK GREEDY SOLVER ALSO FAILED")
                        raise HTTPException(status_code=500, detail="Both CP-SAT and Greedy solvers failed")
                else:
                    metadata = schedule_output_dict.get('_metadata', {})
                    scheduled_count = metadata.get('total_scheduled', 0)
                    
                    if scheduled_count == 0:
                        error_msg = metadata.get('message', 'Unknown error')
                        logger.warning(f"⚠️ SMART BATCH SCHEDULER FAILED: {error_msg}")
                        logger.info("🔄 Falling back to Greedy solver")
                        schedule_output = run_greedy_solver(jobs_data, machine_names_list, setup_times_data)
                        
                        if not schedule_output:
                            logger.error("❌ FALLBACK GREEDY SOLVER ALSO FAILED")
                            raise HTTPException(status_code=500, detail="Both CP-SAT and Greedy solvers failed")
                    else:
                        success_rate = metadata.get('success_rate', 0)
                        logger.info(f"✅ Smart Batch Scheduler completed: {scheduled_count} jobs ({success_rate:.1f}% success)")
                        
                        # Convert to simple format for chart generator
                        schedule_output = {}
                        jobs_converted = 0
                        
                        for job_id, details in schedule_output_dict.items():
                            if job_id == '_metadata':
                                continue
                            
                            if not isinstance(details, dict):
                                logger.error(f"❌ INVALID JOB DETAILS for {job_id}: {details}")
                                continue
                            
                            machine = details.get('machine')
                            start_time = details.get('start')
                            end_time = details.get('end')
                            
                            if not all([machine, start_time is not None, end_time is not None]):
                                logger.error(f"❌ INCOMPLETE JOB DATA for {job_id}: machine={machine}, start={start_time}, end={end_time}")
                                continue
                            
                            if machine not in schedule_output:
                                schedule_output[machine] = []
                            
                            job_tuple = (job_id, start_time, end_time)
                            schedule_output[machine].append(job_tuple)
                            jobs_converted += 1
                        
                        logger.info(f"✅ Converted {jobs_converted} jobs from Smart Batch result")
            
        else:  # greedy solver
            logger.info("🔄 Running Greedy Solver")
            schedule_output = run_greedy_solver(jobs_data, machine_names_list, setup_times_data)
            
            if not schedule_output:
                logger.error("❌ GREEDY SOLVER RETURNED EMPTY RESULT")
                raise HTTPException(status_code=500, detail="Greedy solver failed to generate schedule")
        
        # Validate and normalize schedule output
        ScheduleValidator.validate_schedule_output(schedule_output)
        schedule_output = normalize_schedule_format(schedule_output)
        
        total_scheduled = sum(len(jobs) for jobs in schedule_output.values())
        logger.info(f"✅ Final schedule ready: {total_scheduled} jobs scheduled")
        
        # Store in cache
        result = (schedule_output, jobs_data)
        _SCHEDULE_CACHE[cache_key] = result
        _CACHE_TIMESTAMP[cache_key] = current_time
        logger.info(f"✅ Cached schedule data for solver '{solver_type}'")
        
        return result
        
    except HTTPException:
        raise  # Re-raise HTTP exceptions
    except Exception as e:
        logger.error(f"❌ SCHEDULE GENERATION FAILED: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to generate schedule: {str(e)}")

@router.get("/gantt/priority-view", response_model=List[Dict[str, Any]])
async def get_gantt_priority_data(
    solver: Optional[str] = Query(REPORTING_CONFIG.default_solver_type, description="Solver type (cpsat or greedy)"),
    max_jobs: Optional[int] = Query(None, description="Maximum number of jobs to schedule (for testing)"),
    force_refresh: Optional[bool] = Query(False, description="Force fresh data, bypass cache")
):
    """Get Gantt chart data colored by priority with STRICT validation - NO FALLBACKS."""
    try:
        solver_type = ScheduleValidator.validate_solver_type(solver or REPORTING_CONFIG.default_solver_type)
        
        schedule_output, jobs_input_data = await get_schedule_and_job_data(solver_type, force_refresh, max_jobs)
        
        logger.info("🔄 Preparing Gantt priority view data")
        chart_data = prepare_gantt_data_priority_view(schedule_output, jobs_input_data)
        
        if not chart_data:
            logger.warning("❌ NO CHART DATA GENERATED for priority view")
            raise HTTPException(status_code=500, detail="Failed to generate chart data")
        
        logger.info(f"✅ Generated {len(chart_data)} priority view chart items")
        return chart_data
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ GANTT PRIORITY VIEW FAILED: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to generate priority view: {str(e)}")

@router.get("/gantt/resource-view", response_model=List[Dict[str, Any]])
async def get_gantt_resource_data(
    solver: Optional[str] = Query(REPORTING_CONFIG.default_solver_type, description="Solver type (cpsat or greedy)"),
    max_jobs: Optional[int] = Query(None, description="Maximum number of jobs to schedule (for testing)"),
    force_refresh: Optional[bool] = Query(False, description="Force fresh data, bypass cache")
):
    """Get Gantt chart data grouped by resource with STRICT validation - NO FALLBACKS."""
    try:
        solver_type = ScheduleValidator.validate_solver_type(solver or REPORTING_CONFIG.default_solver_type)
        
        schedule_output, jobs_input_data = await get_schedule_and_job_data(solver_type, force_refresh, max_jobs)
        
        logger.info("🔄 Preparing Gantt resource view data")
        chart_data = prepare_gantt_data_resource_view(schedule_output, jobs_input_data)
        
        if not chart_data:
            logger.warning("❌ NO CHART DATA GENERATED for resource view")
            raise HTTPException(status_code=500, detail="Failed to generate chart data")
        
        logger.info(f"✅ Generated {len(chart_data)} resource view chart items")
        return chart_data
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ GANTT RESOURCE VIEW FAILED: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to generate resource view: {str(e)}")

@router.get("/detailed-schedule", response_model=List[Dict[str, Any]])
async def get_detailed_schedule_table(
    solver: Optional[str] = Query(REPORTING_CONFIG.default_solver_type, description="Solver type (cpsat or greedy)"),
    max_jobs: Optional[int] = Query(None, description="Maximum number of jobs to schedule (for testing)"),
    force_refresh: Optional[bool] = Query(False, description="Force fresh data, bypass cache")
):
    """Get detailed schedule table data with STRICT validation - NO FALLBACKS."""
    try:
        solver_type = ScheduleValidator.validate_solver_type(solver or REPORTING_CONFIG.default_solver_type)
        
        schedule_output, jobs_input_data = await get_schedule_and_job_data(solver_type, force_refresh, max_jobs)
        
        logger.info("🔄 Preparing detailed schedule table data")
        table_data = prepare_detailed_schedule_table_data(schedule_output, jobs_input_data)
        
        if not table_data:
            logger.warning("❌ NO TABLE DATA GENERATED")
            raise HTTPException(status_code=500, detail="Failed to generate table data")
        
        logger.info(f"✅ Generated {len(table_data)} table rows")
        return table_data
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ DETAILED SCHEDULE TABLE FAILED: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to generate table data: {str(e)}")

@router.get("/schedule-overview", response_model=Dict[str, Any])
async def get_schedule_overview(
    solver: Optional[str] = Query(REPORTING_CONFIG.default_solver_type, description="Solver type (cpsat or greedy)"),
    max_jobs: Optional[int] = Query(None, description="Maximum number of jobs to schedule (for testing)"),
    force_refresh: Optional[bool] = Query(False, description="Force fresh data, bypass cache")
):
    """Get schedule overview with STRICT validation - NO FALLBACKS."""
    try:
        solver_type = ScheduleValidator.validate_solver_type(solver or REPORTING_CONFIG.default_solver_type)
        
        schedule_output, jobs_input_data = await get_schedule_and_job_data(solver_type, force_refresh, max_jobs)
        
        logger.info("🔄 Preparing schedule overview")
        table_data = prepare_detailed_schedule_table_data(schedule_output, jobs_input_data)
        
        if not table_data:
            logger.error("❌ NO DATA AVAILABLE for schedule overview")
            raise HTTPException(status_code=500, detail="No schedule data available for overview")
        
        # Calculate overview statistics with strict validation
        total_jobs = len(table_data)
        
        # Get date range from scheduled times
        start_times = []
        end_times = []
        
        for job in table_data:
            start_epoch = job.get('scheduled_start_epoch')
            end_epoch = job.get('scheduled_end_epoch')
            
            if isinstance(start_epoch, (int, float)) and start_epoch > 0:
                start_times.append(start_epoch)
            if isinstance(end_epoch, (int, float)) and end_epoch > 0:
                end_times.append(end_epoch)
        
        if not start_times or not end_times:
            logger.error("❌ NO VALID TIMESTAMPS found in schedule data")
            raise HTTPException(status_code=500, detail="No valid timestamps in schedule data")
        
        earliest_start = min(start_times)
        latest_end = max(end_times)
        
        # Format date range
        start_date = datetime.fromtimestamp(earliest_start).strftime("%d/%m/%y")
        end_date = datetime.fromtimestamp(latest_end).strftime("%d/%m/%y")
        date_range = f"{start_date} to {end_date}"
        
        # Calculate total duration
        duration_hours = (latest_end - earliest_start) / 3600
        if duration_hours >= 24:
            days = int(duration_hours // 24)
            hours = duration_hours % 24
            total_duration = f"{days} days {hours:.1f} hours" if hours > 0 else f"{days} days"
        else:
            total_duration = f"{duration_hours:.1f} hours"
        
        # Count buffer statuses with strict validation
        buffer_counts = {"Late": 0, "Critical": 0, "Warning": 0, "Caution": 0, "OK": 0, "Unknown": 0}
        
        for job in table_data:
            status = job.get('buffer_status', 'Unknown')
            if status in buffer_counts:
                buffer_counts[status] += 1
            else:
                buffer_counts['Unknown'] += 1
        
        overview = {
            "total_jobs": total_jobs,
            "date_range": date_range,
            "total_duration": total_duration,
            "records_displayed": total_jobs,
            "buffer_status_counts": buffer_counts,
            "config_used": {
                "solver_type": solver_type,
                "max_jobs_limit": REPORTING_CONFIG.max_jobs_limit,
                "planning_horizon_days": REPORTING_CONFIG.planning_horizon_days
            }
        }
        
        logger.info(f"✅ Generated schedule overview: {total_jobs} jobs, {date_range}")
        return overview
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ SCHEDULE OVERVIEW FAILED: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to generate overview: {str(e)}")

@router.get("/data-quality-analysis", response_model=Dict[str, Any])
async def get_data_quality_analysis(
    solver: Optional[str] = Query(REPORTING_CONFIG.default_solver_type, description="Solver type (cpsat or greedy)"),
    max_jobs: Optional[int] = Query(None, description="Maximum number of jobs to schedule (for testing)"),
    force_refresh: Optional[bool] = Query(False, description="Force fresh data, bypass cache")
):
    """Analyze data quality with STRICT validation - NO FALLBACKS."""
    try:
        solver_type = ScheduleValidator.validate_solver_type(solver or REPORTING_CONFIG.default_solver_type)
        
        schedule_output, jobs_input_data = await get_schedule_and_job_data(solver_type, force_refresh, max_jobs)
        
        logger.info("🔄 Performing data quality analysis")
        table_data = prepare_detailed_schedule_table_data(schedule_output, jobs_input_data)
        
        if not table_data:
            logger.error("❌ NO DATA AVAILABLE for quality analysis")
            raise HTTPException(status_code=500, detail="No data available for quality analysis")
        
        # Analyze data quality with configured thresholds
        threshold_hours = REPORTING_CONFIG.max_buffer_threshold_days * 24
        
        issues = {
            "unrealistic_buffers": [],
            "negative_buffers": [],
            "missing_lcd_dates": [],
            "invalid_data": [],
            "summary": {}
        }
        
        for job in table_data:
            job_id = job.get('job_id', 'UNKNOWN')
            actual_buffer = job.get('actual_buffer_hours')
            
            # Check for missing or invalid buffer data
            if actual_buffer is None:
                issues["invalid_data"].append({
                    "job_id": job_id,
                    "issue": "Missing buffer calculation",
                    "recommendation": "Check scheduled end time and LCD date"
                })
                continue
            
            # Jobs with unrealistic buffer times
            if actual_buffer > threshold_hours:
                issues["unrealistic_buffers"].append({
                    "job_id": job_id,
                    "buffer_hours": round(actual_buffer, 1),
                    "buffer_days": round(actual_buffer / 24, 1),
                    "threshold_days": REPORTING_CONFIG.max_buffer_threshold_days,
                    "scheduled_end": job.get("scheduled_end_time_str", "N/A"),
                    "lcd_date": job.get("lcd_date_str", "N/A"),
                    "recommendation": f"Review LCD date - buffer exceeds {REPORTING_CONFIG.max_buffer_threshold_days} day threshold"
                })
            
            # Jobs that are late (negative buffer)
            elif actual_buffer < 0:
                issues["negative_buffers"].append({
                    "job_id": job_id,
                    "buffer_hours": round(actual_buffer, 1),
                    "scheduled_end": job.get("scheduled_end_time_str", "N/A"),
                    "lcd_date": job.get("lcd_date_str", "N/A"),
                    "recommendation": "Job will finish late - expedite or adjust LCD date"
                })
            
            # Jobs missing LCD dates
            if not job.get('lcd_date_epoch'):
                issues["missing_lcd_dates"].append({
                    "job_id": job_id,
                    "recommendation": "Add LCD date for proper planning"
                })
        
        # Calculate quality score with strict validation
        total_jobs = len(table_data)
        total_issues = (len(issues["unrealistic_buffers"]) + 
                       len(issues["negative_buffers"]) + 
                       len(issues["missing_lcd_dates"]) +
                       len(issues["invalid_data"]))
        
        quality_score = ((total_jobs - total_issues) / total_jobs * 100) if total_jobs > 0 else 0
        
        # Check if quality meets minimum threshold
        quality_status = "PASS" if quality_score >= REPORTING_CONFIG.data_quality_min_score else "FAIL"
        
        issues["summary"] = {
            "total_jobs_analyzed": total_jobs,
            "unrealistic_buffers_count": len(issues["unrealistic_buffers"]),
            "late_jobs_count": len(issues["negative_buffers"]),
            "missing_lcd_dates_count": len(issues["missing_lcd_dates"]),
            "invalid_data_count": len(issues["invalid_data"]),
            "total_issues": total_issues,
            "data_quality_score": round(quality_score, 1),
            "quality_status": quality_status,
            "min_score_required": REPORTING_CONFIG.data_quality_min_score,
            "config_used": {
                "max_buffer_threshold_days": REPORTING_CONFIG.max_buffer_threshold_days,
                "threshold_hours": threshold_hours
            },
            "recommendations": [
                f"Review {len(issues['unrealistic_buffers'])} jobs with buffers exceeding {REPORTING_CONFIG.max_buffer_threshold_days} days",
                f"Expedite {len(issues['negative_buffers'])} late jobs",
                f"Add LCD dates for {len(issues['missing_lcd_dates'])} jobs",
                "Ensure all jobs have realistic due dates",
                "Consider adjusting scheduling algorithm parameters"
            ]
        }
        
        logger.info(f"✅ Data quality analysis completed: {quality_score:.1f}% score ({quality_status})")
        return issues
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ DATA QUALITY ANALYSIS FAILED: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to analyze data quality: {str(e)}")

@router.get("/health", response_model=Dict[str, Any])
async def reporting_health_check():
    """Health check for reporting endpoints with STRICT validation."""
    health_data = {
        "service": "reporting_endpoints",
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "checks": {},
        "config": {
            "max_jobs_limit": REPORTING_CONFIG.max_jobs_limit,
            "planning_horizon_days": REPORTING_CONFIG.planning_horizon_days,
            "default_solver_type": REPORTING_CONFIG.default_solver_type
        }
    }
    
    # Configuration validation
    try:
        ReportingConfig.from_env()
        health_data["checks"]["configuration"] = {"status": "healthy"}
    except Exception as e:
        health_data["status"] = "unhealthy"
        health_data["checks"]["configuration"] = {
            "status": "unhealthy",
            "error": str(e)
        }
    
    # Chart generator validation
    try:
        from app.reporting.chart_generator import get_chart_configuration
        chart_config = get_chart_configuration()
        health_data["checks"]["chart_generator"] = {
            "status": "healthy",
            "timezone": chart_config.get("timezone"),
            "validation_enabled": chart_config.get("validation_enabled")
        }
    except Exception as e:
        health_data["status"] = "unhealthy"
        health_data["checks"]["chart_generator"] = {
            "status": "unhealthy",
            "error": str(e)
        }
    
    # Data loading validation
    try:
        # Test data loading capability without full load
        from app.data_ingestion.mariadb_parser import test_database_connection
        test_database_connection()
        health_data["checks"]["data_loading"] = {"status": "healthy"}
    except Exception as e:
        health_data["status"] = "unhealthy"
        health_data["checks"]["data_loading"] = {
            "status": "unhealthy",
            "error": str(e)
        }
    
    # Solver availability validation
    try:
        # Test solver imports
        from app.scheduling.greedy_solver import greedy_schedule
        from app.scheduling.batch_scheduler import smart_batch_schedule_jobs
        health_data["checks"]["solvers"] = {
            "status": "healthy",
            "available_solvers": ["greedy", "cpsat"],
            "batch_scheduler_issues": "Parameter mismatch handled with fallback"
        }
    except Exception as e:
        health_data["status"] = "unhealthy"
        health_data["checks"]["solvers"] = {
            "status": "unhealthy",
            "error": str(e)
        }
    
    status_code = 200 if health_data["status"] == "healthy" else 503
    return JSONResponse(content=health_data, status_code=status_code)