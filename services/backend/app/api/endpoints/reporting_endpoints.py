# services/ai_optimizer/backend/app/api/endpoints/reporting_endpoints.py
from fastapi import APIRouter, HTTPException, Depends, Query
import logging
from typing import List, Dict, Any, Literal, Optional

try:
    from app.reporting.chart_generator import (
        prepare_gantt_data_priority_view, 
        prepare_gantt_data_resource_view,
        prepare_detailed_schedule_table_data
    )
    from app.data_ingestion.mariadb_parser import load_jobs_planning_data
    from app.scheduling.greedy_solver import greedy_schedule as run_greedy_solver
    from app.scheduling.cpsat_solver import schedule_jobs as run_cpsat_solver
except ImportError:
    # Fallback for different import contexts
    try:
        from backend.app.reporting.chart_generator import (
            prepare_gantt_data_priority_view, 
            prepare_gantt_data_resource_view,
            prepare_detailed_schedule_table_data
        )
        from backend.app.data_ingestion.mariadb_parser import load_jobs_planning_data
        from backend.app.scheduling.greedy_solver import greedy_schedule as run_greedy_solver
        from backend.app.scheduling.cpsat_solver import schedule_jobs as run_cpsat_solver
    except ImportError:
        from ...reporting.chart_generator import (
            prepare_gantt_data_priority_view, 
            prepare_gantt_data_resource_view,
            prepare_detailed_schedule_table_data
        )
        from ...data_ingestion.mariadb_parser import load_jobs_planning_data
        from ...scheduling.greedy_solver import greedy_schedule as run_greedy_solver
        from ...scheduling.cpsat_solver import schedule_jobs as run_cpsat_solver

logger = logging.getLogger(__name__)
router = APIRouter()

def normalize_schedule_format(schedule_output: Dict[str, List]) -> Dict[str, List]:
    """
    Normalize schedule output to simple 3-tuple format: (job_id, start_epoch, end_epoch)
    
    Args:
        schedule_output: Schedule from solver (can be 3-tuples or 5-tuples)
        
    Returns:
        Normalized schedule with 3-tuples
    """
    normalized = {}
    for machine, jobs in schedule_output.items():
        normalized[machine] = []
        for job_tuple in jobs:
            if len(job_tuple) >= 3:
                # Extract only the first 3 elements (job_id, start, end)
                normalized_tuple = (job_tuple[0], job_tuple[1], job_tuple[2])
                normalized[machine].append(normalized_tuple)
                logger.debug(f"Normalized job {job_tuple[0]} on {machine}: start={job_tuple[1]}, end={job_tuple[2]}")
    return normalized

# A placeholder for actual data loading and scheduling logic
# In a real app, this would be more sophisticated, perhaps a dependency
async def get_schedule_and_job_data(solver_type: str = "cpsat"):
    """ 
    Function to load job data and run the selected scheduler.
    
    Args:
        solver_type: The type of solver to use ("greedy" or "cpsat")
    
    Returns:
        A tuple of (schedule_output, jobs_data)
    """
    try:
        # 1. Load data using MariaDB parser
        # This requires DB connection and might be slow for an API call if not cached/pre-run.
        # For now, we assume it's feasible for demonstration.
        jobs_data, machines_data, setup_times_data = load_jobs_planning_data()
        
        # Extract machine names from jobs_data using rsc_code instead of RSC_MACHINE
        # This assumes jobs have rsc_code field which identifies the machine
        machine_names_list = list(set(m['rsc_code'] for m in jobs_data if m.get('rsc_code')))
        
        if not machine_names_list:
            # Fallback or default if no machines found from jobs
            machine_names_list = [m['MachineName_v'] for m in machines_data] if machines_data else ["DefaultMachine"]

        logger.info(f"Using '{solver_type}' solver to schedule {len(jobs_data)} jobs on {len(machine_names_list)} machines")
        
        # 2. Run selected scheduling algorithm
        schedule_output = None
        if solver_type.lower() == "cpsat":
            # Run CP-SAT solver with a reasonable time limit
            schedule_output_dict = run_cpsat_solver(jobs_data, machine_names_list, setup_times_data, enforce_sequence=True, time_limit_seconds=300)
            
            # Check if we got a valid result from CP-SAT
            if not schedule_output_dict or schedule_output_dict.get('_metadata', {}).get('status') not in ['OPTIMAL', 'FEASIBLE']:
                logger.warning(f"CP-SAT solver could not find a solution: {schedule_output_dict.get('_metadata', {}).get('message', 'Unknown error')}")
                # Fall back to greedy if CP-SAT fails
                logger.info("Falling back to greedy solver")
                schedule_output = run_greedy_solver(jobs_data, machine_names_list, setup_times_data)
            else:
                logger.info(f"CP-SAT solver found a solution with status: {schedule_output_dict['_metadata']['status']}")
                
                # Convert to simple format expected by optimized chart_generator
                # Format: {machine: [(job_id, start_epoch, end_epoch), ...]}
                schedule_output = {}
                for job_id, details in schedule_output_dict.items():
                    if job_id == '_metadata':
                        continue  # Skip metadata entry
                    
                    machine = details['machine']
                    if machine not in schedule_output:
                        schedule_output[machine] = []
                    
                    # Simple tuple format for optimized chart generator
                    job_tuple = (
                        job_id,
                        details.get('start'),  # start_epoch
                        details.get('end')     # end_epoch
                    )
                    
                    schedule_output[machine].append(job_tuple)
                    logger.debug(f"Added job {job_id} to {machine}: start={details.get('start')}, end={details.get('end')}")
                
                logger.info(f"Converted CP-SAT result: {sum(len(tasks) for tasks in schedule_output.values())} scheduled tasks")
        else:
            # Fallback to greedy solver
            schedule_output = run_greedy_solver(jobs_data, machine_names_list, setup_times_data)
        
        if not schedule_output:
            logger.warning("No valid schedule output generated")
            return {}, jobs_data

        # Normalize schedule format to simple 3-tuples for optimized chart generator
        schedule_output = normalize_schedule_format(schedule_output)
        logger.info(f"Final normalized schedule: {sum(len(tasks) for tasks in schedule_output.values())} tasks")

        return schedule_output, jobs_data
    except Exception as e:
        logger.error(f"Error in get_schedule_and_job_data: {e}", exc_info=True)
        # Depending on how critical this is, you might re-raise or return empty data
        # For an API, it's often better to raise HTTPException
        raise HTTPException(status_code=500, detail=f"Failed to generate schedule: {str(e)}")

@router.get("/gantt/priority-view", response_model=List[Dict[str, Any]])
async def get_gantt_priority_data(
    solver: Optional[str] = Query("cpsat", description="Solver type to use (cpsat or greedy)")
):
    """
    Endpoint to get Gantt chart data, colored by priority.
    """
    data = await get_schedule_and_job_data(solver)
    schedule_output, jobs_input_data = data
    if not schedule_output:
        logger.warning("No schedule output available for Gantt chart (priority view).")
        return [] # Or raise HTTPException(status_code=404, detail="Schedule not found")
    
    chart_data = prepare_gantt_data_priority_view(schedule_output, jobs_input_data)
    if not chart_data:
        # This could happen if processing fails or results in no tasks
        logger.info("prepare_gantt_data_priority_view returned no data.")
    return chart_data

@router.get("/gantt/resource-view", response_model=List[Dict[str, Any]])
async def get_gantt_resource_data(
    solver: Optional[str] = Query("cpsat", description="Solver type to use (cpsat or greedy)")
):
    """
    Endpoint to get Gantt chart data, grouped by resource and colored by buffer status.
    """
    data = await get_schedule_and_job_data(solver)
    schedule_output, jobs_input_data = data
    if not schedule_output:
        logger.warning("No schedule output available for Gantt chart (resource view).")
        return []
        
    chart_data = prepare_gantt_data_resource_view(schedule_output, jobs_input_data)
    if not chart_data:
        logger.info("prepare_gantt_data_resource_view returned no data.")
    return chart_data

@router.get("/detailed-schedule", response_model=List[Dict[str, Any]])
async def get_detailed_schedule_table(
    solver: Optional[str] = Query("cpsat", description="Solver type to use (cpsat or greedy)")
):
    """
    Endpoint to get detailed schedule data for a table view.
    """
    data = await get_schedule_and_job_data(solver)
    schedule_output, jobs_input_data = data
    if not schedule_output or not jobs_input_data:
        logger.warning("No schedule or job input data available for detailed table.")
        return [] 
    
    table_data = prepare_detailed_schedule_table_data(schedule_output, jobs_input_data)
    if not table_data:
        logger.info("prepare_detailed_schedule_table_data returned no data.")
    return table_data

@router.get("/schedule-overview", response_model=Dict[str, Any])
async def get_schedule_overview(
    solver: Optional[str] = Query("cpsat", description="Solver type to use (cpsat or greedy)")
):
    """
    Endpoint to get schedule overview data including total jobs, date range, duration, and buffer status counts.
    """
    data = await get_schedule_and_job_data(solver)
    schedule_output, jobs_input_data = data
    
    if not schedule_output or not jobs_input_data:
        logger.warning("No schedule or job input data available for overview.")
        return {
            "total_jobs": 0,
            "date_range": "N/A",
            "total_duration": "0 hours",
            "records_displayed": 0,
            "buffer_status_counts": {
                "Late": 0,
                "Warning": 0,
                "Caution": 0,
                "OK": 0
            }
        }
    
    table_data = prepare_detailed_schedule_table_data(schedule_output, jobs_input_data)
    
    if not table_data:
        logger.info("prepare_detailed_schedule_table_data returned no data for overview.")
        return {
            "total_jobs": 0,
            "date_range": "N/A", 
            "total_duration": "0 hours",
            "records_displayed": 0,
            "buffer_status_counts": {
                "Late": 0,
                "Warning": 0,
                "Caution": 0,
                "OK": 0
            }
        }
    
    # Calculate overview statistics
    total_jobs = len(table_data)
    
    # Get date range from scheduled times
    start_times = []
    end_times = []
    
    for job in table_data:
        if job.get('scheduled_start_time_epoch'):
            start_times.append(job['scheduled_start_time_epoch'])
        if job.get('scheduled_end_time_epoch'):
            end_times.append(job['scheduled_end_time_epoch'])
    
    date_range = "N/A"
    total_duration = "0 hours"
    
    if start_times and end_times:
        from datetime import datetime
        
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
    
    # Count buffer statuses
    buffer_counts = {
        "Late": 0,
        "Warning": 0, 
        "Caution": 0,
        "OK": 0
    }
    
    for job in table_data:
        status = job.get('buffer_status', 'OK')
        if status in buffer_counts:
            buffer_counts[status] += 1
        else:
            buffer_counts['OK'] += 1  # Default to OK for unknown statuses
    
    return {
        "total_jobs": total_jobs,
        "date_range": date_range,
        "total_duration": total_duration,
        "records_displayed": total_jobs,
        "buffer_status_counts": buffer_counts
    }

@router.get("/data-quality-analysis", response_model=Dict[str, Any])
async def get_data_quality_analysis(
    solver: Optional[str] = Query("cpsat", description="Solver type to use (cpsat or greedy)")
):
    """
    Endpoint to analyze data quality issues in the schedule.
    """
    data = await get_schedule_and_job_data(solver)
    schedule_output, jobs_input_data = data
    
    if not schedule_output or not jobs_input_data:
        return {"error": "No schedule or job data available"}
    
    table_data = prepare_detailed_schedule_table_data(schedule_output, jobs_input_data)
    
    # Analyze data quality issues
    issues = {
        "unrealistic_buffers": [],
        "negative_buffers": [],
        "missing_lcd_dates": [],
        "summary": {}
    }
    
    for job in table_data:
        actual_buffer = job.get('actual_buffer_hours', 0)
        
        # Jobs with very large buffer times (indicate potential LCD date issues)
        if actual_buffer > 720:  # More than 30 days - likely data issue
            issues["unrealistic_buffers"].append({
                "job_id": job["job_id"],
                "buffer_hours": round(actual_buffer, 1),
                "buffer_days": round(actual_buffer / 24, 1),
                "scheduled_end": job["scheduled_end_time_str"],
                "lcd_date": job["lcd_date_str"],
                "recommendation": "Review LCD date - job completes too early"
            })
        
        # Jobs that are late (negative buffer)
        elif actual_buffer < 0:
            issues["negative_buffers"].append({
                "job_id": job["job_id"],
                "buffer_hours": round(actual_buffer, 1),
                "scheduled_end": job["scheduled_end_time_str"],
                "lcd_date": job["lcd_date_str"],
                "recommendation": "Job will finish late - expedite or adjust LCD date"
            })
        
        # Jobs missing LCD dates
        if not job.get('lcd_date_epoch'):
            issues["missing_lcd_dates"].append({
                "job_id": job["job_id"],
                "recommendation": "Add LCD date for proper planning"
            })
    
    # Summary statistics
    total_jobs = len(table_data)
    issues["summary"] = {
        "total_jobs_analyzed": total_jobs,
        "unrealistic_buffers_count": len(issues["unrealistic_buffers"]),
        "late_jobs_count": len(issues["negative_buffers"]),
        "missing_lcd_dates_count": len(issues["missing_lcd_dates"]),
        "data_quality_score": round(
            (total_jobs - len(issues["unrealistic_buffers"]) - len(issues["missing_lcd_dates"])) / total_jobs * 100, 1
        ) if total_jobs > 0 else 0,
        "recommendations": [
            "Review LCD dates for jobs with extremely large buffers (>30 days)",
            "Check if late jobs can be expedited",
            "Ensure all jobs have realistic due dates",
            "Consider adjusting scheduling algorithm to balance workload"
        ]
    }
    
    return issues
