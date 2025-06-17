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
from app.reporting.schedule_orchestrator import get_schedule_and_job_data, ORCHESTRATOR_CONFIG

logger = logging.getLogger(__name__)
router = APIRouter()

@dataclass
class ReportingConfig:
    """Simplified configuration for reporting endpoints using orchestrator config."""
    
    # Data quality thresholds
    max_buffer_threshold_days: int
    data_quality_min_score: float
    
    @classmethod
    def from_env(cls) -> 'ReportingConfig':
        """Load additional configuration from environment variables."""
        missing_vars = []
        invalid_vars = []
        
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
        
        # Check for critical errors
        if missing_vars:
            error_msg = f"❌ CRITICAL REPORTING CONFIG ERROR: Missing required environment variables: {', '.join(missing_vars)}"
            logger.error(error_msg)
            raise ValueError(error_msg)
        
        if invalid_vars:
            error_msg = f"❌ CRITICAL REPORTING CONFIG ERROR: Invalid environment variable values: {', '.join(invalid_vars)}"
            logger.error(error_msg)
            raise ValueError(error_msg)
        
        # Validate business logic
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
            max_buffer_threshold_days=max_buffer_threshold_days,
            data_quality_min_score=data_quality_min_score
        )

# Initialize configuration at module level - FAIL IF MISSING
try:
    REPORTING_CONFIG = ReportingConfig.from_env()
    logger.info(f"✅ Reporting endpoints initialized with {ORCHESTRATOR_CONFIG.default_solver_type} solver")
except Exception as e:
    logger.error(f"❌ FAILED to initialize reporting configuration: {e}")
    raise

# Simple validation helper for HTTP parameters
class ParameterValidator:
    """Simple parameter validation for HTTP endpoints."""
    
    @staticmethod
    def validate_solver_type(solver_type: str) -> str:
        """Validate solver type parameter."""
        if not isinstance(solver_type, str):
            raise ValueError(f"Solver type must be a string, got {type(solver_type)}")
        
        solver_type = solver_type.lower().strip()
        
        if solver_type not in ['greedy']:
            raise ValueError(f"Invalid solver type '{solver_type}'. Only 'greedy' solver is available")
        
        return solver_type

@router.get("/gantt/priority-view", response_model=List[Dict[str, Any]])
async def get_gantt_priority_data(
    solver: Optional[str] = Query(ORCHESTRATOR_CONFIG.default_solver_type, description="Solver type (greedy)"),
    max_jobs: Optional[int] = Query(None, description="Maximum number of jobs to schedule (for testing)")
):
    """Get Gantt chart data colored by priority with STRICT validation - NO FALLBACKS."""
    try:
        solver_type = ParameterValidator.validate_solver_type(solver or ORCHESTRATOR_CONFIG.default_solver_type)
        
        schedule_output, jobs_input_data = await get_schedule_and_job_data(solver_type, max_jobs)
        
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
    solver: Optional[str] = Query(ORCHESTRATOR_CONFIG.default_solver_type, description="Solver type (greedy)"),
    max_jobs: Optional[int] = Query(None, description="Maximum number of jobs to schedule (for testing)")
):
    """Get Gantt chart data grouped by resource with STRICT validation - NO FALLBACKS."""
    try:
        solver_type = ParameterValidator.validate_solver_type(solver or ORCHESTRATOR_CONFIG.default_solver_type)
        
        schedule_output, jobs_input_data = await get_schedule_and_job_data(solver_type, max_jobs)
        
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
    solver: Optional[str] = Query(ORCHESTRATOR_CONFIG.default_solver_type, description="Solver type (greedy)"),
    max_jobs: Optional[int] = Query(None, description="Maximum number of jobs to schedule (for testing)")
):
    """Get detailed schedule table data with STRICT validation - NO FALLBACKS."""
    try:
        solver_type = ParameterValidator.validate_solver_type(solver or ORCHESTRATOR_CONFIG.default_solver_type)
        
        schedule_output, jobs_input_data = await get_schedule_and_job_data(solver_type, max_jobs)
        
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
    solver: Optional[str] = Query(ORCHESTRATOR_CONFIG.default_solver_type, description="Solver type (greedy)"),
    max_jobs: Optional[int] = Query(None, description="Maximum number of jobs to schedule (for testing)")
):
    """Get schedule overview with STRICT validation - NO FALLBACKS."""
    try:
        solver_type = ParameterValidator.validate_solver_type(solver or ORCHESTRATOR_CONFIG.default_solver_type)
        
        schedule_output, jobs_input_data = await get_schedule_and_job_data(solver_type, max_jobs)
        
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
                "max_jobs_limit": ORCHESTRATOR_CONFIG.max_jobs_limit,
                "planning_horizon_days": ORCHESTRATOR_CONFIG.planning_horizon_days
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
    solver: Optional[str] = Query(ORCHESTRATOR_CONFIG.default_solver_type, description="Solver type (greedy)"),
    max_jobs: Optional[int] = Query(None, description="Maximum number of jobs to schedule (for testing)")
):
    """Analyze data quality with STRICT validation - NO FALLBACKS."""
    try:
        solver_type = ParameterValidator.validate_solver_type(solver or ORCHESTRATOR_CONFIG.default_solver_type)
        
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
            "max_jobs_limit": ORCHESTRATOR_CONFIG.max_jobs_limit,
            "planning_horizon_days": ORCHESTRATOR_CONFIG.planning_horizon_days,
            "default_solver_type": ORCHESTRATOR_CONFIG.default_solver_type
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
            "available_solvers": ["greedy"]
        }
    except Exception as e:
        health_data["status"] = "unhealthy"
        health_data["checks"]["solvers"] = {
            "status": "unhealthy",
            "error": str(e)
        }
    
    status_code = 200 if health_data["status"] == "healthy" else 503
    return JSONResponse(content=health_data, status_code=status_code)

@router.get("/working-hours", response_model=Dict[str, Any])
async def get_working_hours_configuration():
    """Get working hours configuration from database tables with STRICT validation."""
    try:
        # Import time availability module
        try:
            from app.scheduling.time_availability import TimeAvailabilityManager
        except ImportError:
            logger.error("❌ Failed to import TimeAvailabilityManager")
            raise HTTPException(status_code=500, detail="Time availability module not available")
        
        # Get instance and refresh cache
        time_checker = TimeAvailabilityManager.get_instance()
        if not time_checker:
            logger.error("❌ Failed to get TimeAvailabilityManager instance")
            raise HTTPException(status_code=500, detail="Time availability manager not available")
        
        # Refresh cache to get latest data
        time_checker.cache.refresh_if_needed()
        
        # Extract working hours configuration
        working_hours_by_day = {}
        for day, hours_list in time_checker.cache._arrangable_hours_cache.items():
            working_hours_by_day[str(day)] = []
            for hour_config in hours_list:
                working_hours_by_day[str(day)].append({
                    "start_time": hour_config['start_time'].strftime("%H:%M:%S"),
                    "end_time": hour_config['end_time'].strftime("%H:%M:%S"),
                    "is_working": hour_config['is_working']
                })
        
        # Extract break times
        break_times = []
        for breaktime in time_checker.cache._breaktimes_cache:
            break_times.append({
                "name": breaktime['name'],
                "description": breaktime['description'],
                "start_time": breaktime['start_time'].strftime("%H:%M:%S"),
                "end_time": breaktime['end_time'].strftime("%H:%M:%S"),
                "duration_minutes": breaktime['duration_minutes'],
                "break_type": breaktime['break_type'],
                "is_mandatory": breaktime['is_mandatory']
            })
        
        # Extract holidays (sample for current year)
        current_year = datetime.now().year
        holidays = []
        for date_key, holiday_info in time_checker.cache._holidays_cache.items():
            if date_key.startswith(str(current_year)):
                holidays.append({
                    "date": date_key,
                    "name": holiday_info['name'],
                    "description": holiday_info['description'],
                    "scope": holiday_info['scope'],
                    "is_recurring": holiday_info['is_recurring']
                })
        
        # Get environment configuration for working hours types
        normal_hours = os.getenv('NORMAL_WORKING_HOURS', '17.5')
        ot_hours = os.getenv('OT_WORKING_HOURS', '19.5')
        emergency_hours = os.getenv('EMERGENCY_OT_HOURS', '22.0')
        
        configuration = {
            "working_hours_by_day": working_hours_by_day,
            "break_times": break_times,
            "holidays": holidays,
            "environment_config": {
                "normal_working_hours": float(normal_hours),
                "ot_working_hours": float(ot_hours),
                "emergency_ot_hours": float(emergency_hours),
                "timezone": "Asia/Singapore"
            },
            "cache_info": {
                "last_refreshed": datetime.now().isoformat(),
                "working_days_count": len(working_hours_by_day),
                "break_times_count": len(break_times),
                "holidays_count": len(holidays)
            }
        }
        
        logger.info(f"✅ Working hours configuration retrieved: {len(working_hours_by_day)} days, {len(break_times)} breaks, {len(holidays)} holidays")
        return configuration
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ WORKING HOURS CONFIGURATION FAILED: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to retrieve working hours configuration: {str(e)}")