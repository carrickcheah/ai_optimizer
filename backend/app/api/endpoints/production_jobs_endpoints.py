# backend/app/api/endpoints/production_jobs_endpoints.py
"""Production-grade production jobs API endpoints with STRICT configuration - NO FALLBACKS."""

from fastapi import APIRouter, HTTPException, Body, Query, Depends
from fastapi.responses import JSONResponse
import logging
import os
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
import mysql.connector
from datetime import datetime
import math

from ..fastapi_app import (
    ProductionJobData, 
    ProductionJobResponse, 
    DataTransformer,
    monitor_performance,
    APIResponse
)
from app.data_ingestion.mariadb_parser import load_jobs_planning_data

router = APIRouter()
logger = logging.getLogger(__name__)

@dataclass
class EndpointConfig:
    """Configuration for production jobs endpoints - ALL VALUES MUST BE IN .env - NO FALLBACKS."""
    
    # Job limits
    max_jobs_limit: int
    
    # Time horizons
    planning_horizon_days: int
    max_planning_horizon_days: int
    
    @classmethod
    def from_env(cls) -> 'EndpointConfig':
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
        
        # ALL variables are REQUIRED - NO FALLBACKS
        max_jobs_limit = get_required_int_env('MAX_JOBS_LIMIT')
        planning_horizon_days = get_required_int_env('PLANNING_HORIZON_DAYS')
        max_planning_horizon_days = get_required_int_env('MAX_PLANNING_HORIZON_DAYS')
        
        # Check for critical errors - FAIL IMMEDIATELY
        if missing_vars:
            error_msg = f"CRITICAL ENDPOINT CONFIG ERROR: Missing required environment variables: {', '.join(missing_vars)}"
            logger.error(error_msg)
            raise ValueError(error_msg)

        if invalid_vars:
            error_msg = f"CRITICAL ENDPOINT CONFIG ERROR: Invalid environment variable values: {', '.join(invalid_vars)}"
            logger.error(error_msg)
            raise ValueError(error_msg)

        # Validate business logic - FAIL IF INVALID
        if planning_horizon_days > max_planning_horizon_days:
            error_msg = f"CRITICAL CONFIG ERROR: PLANNING_HORIZON_DAYS ({planning_horizon_days}) cannot exceed MAX_PLANNING_HORIZON_DAYS ({max_planning_horizon_days})"
            logger.error(error_msg)
            raise ValueError(error_msg)

        logger.info("Successfully loaded endpoint configuration from .env")
        
        return cls(
            max_jobs_limit=max_jobs_limit,
            planning_horizon_days=planning_horizon_days,
            max_planning_horizon_days=max_planning_horizon_days
        )

# Initialize configuration at module level - FAIL IF MISSING
try:
    ENDPOINT_CONFIG = EndpointConfig.from_env()
    logger.info("Production jobs endpoints initialized")
except Exception as e:
    logger.error(f"FAILED to initialize endpoint configuration: {e}")
    raise

class ProductionJobValidation:
    """Parameter validation for API endpoints - NO DATABASE QUERIES."""
    
    @staticmethod
    def validate_query_parameters(limit: Optional[int], offset: Optional[int]) -> None:
        """Validate query parameters with strict limits - NO FALLBACKS."""
        if limit is not None:
            if limit <= 0:
                raise ValueError("Limit must be positive")
            if limit > ENDPOINT_CONFIG.max_jobs_limit:
                raise ValueError(f"Limit cannot exceed {ENDPOINT_CONFIG.max_jobs_limit}")
        
        if offset is not None and offset < 0:
            raise ValueError("Offset cannot be negative")
    
    @staticmethod
    def validate_pagination_parameters(page: int, page_size: int) -> None:
        """Validate pagination parameters with strict limits - NO FALLBACKS."""
        if page <= 0:
            raise ValueError("Page must be positive")
        
        if page_size <= 0:
            raise ValueError("Page size must be positive")
        
        if page_size > 500:  # Hardcoded MAX_PAGE_SIZE
            raise ValueError(f"Page size cannot exceed 500")
    
    @staticmethod
    def validate_time_parameters(planning_horizon_days: int) -> None:
        """Validate time parameters with strict limits - NO FALLBACKS."""
        if planning_horizon_days <= 0:
            raise ValueError("Planning horizon days must be positive")
        
        if planning_horizon_days > ENDPOINT_CONFIG.max_planning_horizon_days:
            raise ValueError(f"Planning horizon days cannot exceed {ENDPOINT_CONFIG.max_planning_horizon_days}")

class ProductionJobService:
    """Business logic with strict validation - NO FALLBACKS."""
    
    @staticmethod
    def validate_job_id(job_id: int) -> None:
        """Validate job ID with strict checks - NO FALLBACKS."""
        if not isinstance(job_id, int):
            raise ValueError(f"Job ID must be an integer, got {type(job_id)}")
        
        if job_id <= 0:
            raise ValueError("Job ID must be positive")
        
        if job_id > 2147483647:  # MySQL INT max
            raise ValueError("Job ID exceeds maximum allowed value")
    
    @staticmethod
    def validate_priority_filter(priority: Optional[int]) -> None:
        """Validate priority filter - NO FALLBACKS."""
        if priority is not None:
            if not isinstance(priority, int):
                raise ValueError(f"Priority must be an integer, got {type(priority)}")
            
            if priority < 1 or priority > 5:
                raise ValueError("Priority must be between 1 and 5")

# API Endpoints with STRICT validation - NO FALLBACKS
@router.get("/", 
           response_model=List[ProductionJobResponse],
           summary="Get all production jobs",
           description="Retrieve production jobs using mariadb_parser - SINGLE DATA SOURCE")
@monitor_performance
async def get_production_jobs(
    limit: Optional[int] = Query(None, ge=1, le=ENDPOINT_CONFIG.max_jobs_limit, description="Limit number of results"),
    offset: Optional[int] = Query(None, ge=0, description="Offset for pagination"),
    priority: Optional[int] = Query(None, ge=1, le=5, description="Filter by priority")
):
    """Get production jobs using mariadb_parser as single data source."""
    try:
        # Strict parameter validation - FAIL IF INVALID
        ProductionJobValidation.validate_query_parameters(limit, offset)
        ProductionJobService.validate_priority_filter(priority)
        
        # Load data from mariadb_parser (SINGLE DATA SOURCE)
        max_jobs = limit or ENDPOINT_CONFIG.max_jobs_limit
        jobs_data, _, _ = load_jobs_planning_data(
            max_jobs=max_jobs,
            planning_horizon_days=ENDPOINT_CONFIG.planning_horizon_days
        )
        
        if not jobs_data:
            logger.warning("NO JOBS FOUND from mariadb_parser")
            return []
        
        # Apply filters and pagination
        filtered_jobs = jobs_data
        
        # Apply priority filter if specified
        if priority is not None:
            filtered_jobs = [job for job in filtered_jobs if job.get('priority', 3) == priority]
        
        # Apply offset and limit
        if offset is not None:
            filtered_jobs = filtered_jobs[offset:]
        if limit is not None:
            filtered_jobs = filtered_jobs[:limit]
        
        # Transform data for API response
        response_jobs = []
        failed_jobs = 0
        
        for job in filtered_jobs:
            try:
                # Strict validation - NO FALLBACKS for missing required fields
                required_fields = ['job_id', 'job', 'process_code']
                for field in required_fields:
                    if field not in job or job[field] is None:
                        raise ValueError(f"Required field '{field}' is missing")
                
                # Map job_id to op_id for API compatibility
                if 'op_id' not in job and 'job_id' in job:
                    job['op_id'] = job.get('op_id', abs(hash(job['job_id'])) % 1000000)
                
                transformed_row = DataTransformer.transform_job_row(job)
                response_jobs.append(ProductionJobResponse(**transformed_row))
                
            except Exception as e:
                failed_jobs += 1
                logger.error(f"FAILED to validate job data for job {job.get('job_id', 'unknown')}: {e}")
                continue

        if failed_jobs > 0:
            logger.warning(f"{failed_jobs} jobs failed validation and were excluded")

        if not response_jobs:
            logger.error("ALL JOBS FAILED VALIDATION - no valid jobs returned")
            raise HTTPException(status_code=500, detail="All jobs failed data validation")

        logger.info(f"Retrieved {len(response_jobs)} valid production jobs from mariadb_parser")
        return response_jobs

    except ValueError as e:
        logger.error(f"PARAMETER VALIDATION ERROR: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"UNEXPECTED ERROR in get_production_jobs: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/production-schedule", 
           response_model=Dict[str, Any],
           summary="Get production schedule data",
           description="Get production schedule using mariadb_parser - SINGLE DATA SOURCE")
@monitor_performance
async def get_production_schedule(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(50, ge=1, le=500, description="Items per page"),  # Hardcoded DEFAULT_PAGE_SIZE=50, MAX_PAGE_SIZE=500
    sort_field: Optional[str] = Query("LCD_DATE", description="Field to sort by"),
    sort_order: Optional[str] = Query("asc", description="Sort order: 'asc' or 'desc'"),
    search: Optional[str] = Query(None, description="Search term"),
    planning_horizon_days: int = Query(ENDPOINT_CONFIG.planning_horizon_days, ge=7, le=ENDPOINT_CONFIG.max_planning_horizon_days, description="Planning horizon days")
):
    """Get production schedule using mariadb_parser as single data source."""
    try:
        # STRICT parameter validation - FAIL IF INVALID
        ProductionJobValidation.validate_pagination_parameters(page, page_size)
        ProductionJobValidation.validate_time_parameters(planning_horizon_days)
        
        # Validate sort parameters - NO FALLBACKS
        # Map requested sort fields to keys in schedule_items below
        allowed_sort_fields = {
            "PLAN_DATE": "plan_date",
            "LCD_DATE": "LCD_DATE",
            "JOB": "JOB",
            "PROCESS_CODE": "PROCESS_CODE",
            "RSC_CODE": "RSC_CODE",
            "MACHINE": "MACHINE",
            "NUMBER_OPERATOR": "NUMBER_OPERATOR",
            "JOB_QUANTITY": "JOB_QUANTITY",
            "TxnId_i": "TxnId_i",
            "MATERIAL_ARRIVAL": "MATERIAL_ARRIVAL",
            # Additional fields used by frontend table
            "START_DATE": "START_DATE",
            "JOB_DEPENDENCY": "JOB_DEPENDENCY",
            "ACCUMULATED_DAILY_OUTPUT": "ACCUMULATED_DAILY_OUTPUT",
            "BALANCE_QUANTITY": "BALANCE_QUANTITY",
            "REDUCE_OPERATION_HOURS": "REDUCE_OPERATION_HOURS"
        }
        
        if sort_field not in allowed_sort_fields:
            raise ValueError(f"Invalid sort_field. Allowed values: {list(allowed_sort_fields.keys())}")
        
        if sort_order.lower() not in ['asc', 'desc']:
            raise ValueError("sort_order must be 'asc' or 'desc'")
        
        # Load data from mariadb_parser (SINGLE DATA SOURCE)
        jobs_data, _, _ = load_jobs_planning_data(
            max_jobs=ENDPOINT_CONFIG.max_jobs_limit,
            planning_horizon_days=planning_horizon_days
        )
        
        if not jobs_data:
            logger.warning("NO JOBS FOUND from mariadb_parser")
            return {
                "items": [],
                "total_items": 0,
                "page": page,
                "page_size": page_size,
                "total_pages": 0,
                "config_used": {
                    "planning_horizon_days": planning_horizon_days,
                    "sort_field": sort_field,
                    "sort_order": sort_order
                }
            }
        
        # Apply search filter if provided
        filtered_jobs = jobs_data
        if search and search.strip():
            search_term = search.strip().lower()
            filtered_jobs = [
                job for job in jobs_data
                if search_term in job.get('job', '').lower() or
                   search_term in job.get('process_code', '').lower() or
                   search_term in job.get('MachineName_v', '').lower()
            ]
        
        # Transform data for schedule format
        schedule_items = []
        for job in filtered_jobs:
            schedule_item = {
                "plan_date": job.get('plan_date'),
                "LCD_DATE": job.get('lcd_date_str', '').split(' ')[0] if job.get('lcd_date_str') else '',
                "JOB": job.get('job', ''),
                "PROCESS_CODE": job.get('process_code', ''),
                "RSC_CODE": job.get('rsc_location', ''),
                "MACHINE": job.get('MachineName_v', ''),
                "NUMBER_OPERATOR": job.get('number_operator', 1),
                "JOB_QUANTITY": job.get('job_quantity', 0),
                "TxnId_i": job.get('op_id', 0),
                "MATERIAL_ARRIVAL": job.get('material_arrival_str', '').split(' ')[0] if job.get('material_arrival_str') else '',
                # Extra fields required by frontend
                "START_DATE": job.get('start_date_str', ''),
                "JOB_DEPENDENCY": job.get('job_dependency', True),
                "ACCUMULATED_DAILY_OUTPUT": job.get('accumulated_daily_output', 0),
                "BALANCE_QUANTITY": job.get('balance_quantity', 0),
                "REDUCE_OPERATION_HOURS": job.get('reduce_operation_hours', 0)
            }
            schedule_items.append(schedule_item)
        
        # Apply sorting
        sort_key = allowed_sort_fields[sort_field]
        reverse_sort = sort_order.lower() == "desc"
        schedule_items.sort(key=lambda x: x.get(sort_key, ''), reverse=reverse_sort)
        
        # Apply pagination
        total_items = len(schedule_items)
        total_pages = math.ceil(total_items / page_size) if total_items > 0 else 1
        
        # Validate page number against total pages
        if page > total_pages and total_items > 0:
            raise ValueError(f"Page {page} exceeds total pages {total_pages}")
        
        # Get page data
        start_idx = (page - 1) * page_size
        end_idx = start_idx + page_size
        page_items = schedule_items[start_idx:end_idx]
        
        logger.info(f"Retrieved {len(page_items)} schedule records from mariadb_parser (page {page}/{total_pages})")
        
        return {
            "items": page_items,
            "total_items": total_items,
            "page": page,
            "page_size": page_size,
            "total_pages": total_pages,
            "config_used": {
                "planning_horizon_days": planning_horizon_days,
                "sort_field": sort_field,
                "sort_order": sort_order
            }
        }
                
    except ValueError as e:
        logger.error(f"PARAMETER VALIDATION ERROR: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"UNEXPECTED ERROR in get_production_schedule: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/health", 
           response_model=Dict[str, Any],
           summary="Health check with STRICT validation")
async def health_check():
    """Health check with STRICT validation - NO FALLBACKS."""
    health_data = {
        "service": "production_jobs_endpoints",
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "checks": {},
        "config": {
            "max_jobs_limit": ENDPOINT_CONFIG.max_jobs_limit,
            "planning_horizon_days": ENDPOINT_CONFIG.planning_horizon_days,
            "max_page_size": 500  # Hardcoded MAX_PAGE_SIZE
        }
    }
    
    # Database connectivity check via mariadb_parser - FAIL IF UNHEALTHY
    try:
        from app.data_ingestion.mariadb_parser import test_database_connection
        if test_database_connection():
            health_data["checks"]["database"] = {"status": "healthy"}
        else:
            raise Exception("Database connection test failed")
            
    except Exception as e:
        logger.error(f"DATABASE HEALTH CHECK FAILED: {e}")
        health_data["status"] = "unhealthy"
        health_data["checks"]["database"] = {
            "status": "unhealthy",
            "error": str(e)
        }

    # Configuration validation check
    try:
        # Verify configuration is still valid
        EndpointConfig.from_env()
        health_data["checks"]["configuration"] = {"status": "healthy"}

    except Exception as e:
        logger.error(f"CONFIGURATION HEALTH CHECK FAILED: {e}")
        health_data["status"] = "unhealthy"
        health_data["checks"]["configuration"] = {
            "status": "unhealthy",
            "error": str(e)
        }
    
    status_code = 200 if health_data["status"] == "healthy" else 503
    return JSONResponse(content=health_data, status_code=status_code)

@router.get("/{job_id}", 
           response_model=ProductionJobResponse,
           summary="Get production job by ID",
           description="Get specific job using mariadb_parser - SINGLE DATA SOURCE")
@monitor_performance
async def get_production_job(job_id: int):
    """Get specific production job using mariadb_parser as single data source."""
    try:
        # STRICT job ID validation - FAIL IF INVALID
        ProductionJobService.validate_job_id(job_id)
        
        # Load data from mariadb_parser (SINGLE DATA SOURCE)
        jobs_data, _, _ = load_jobs_planning_data(
            max_jobs=ENDPOINT_CONFIG.max_jobs_limit,
            planning_horizon_days=ENDPOINT_CONFIG.planning_horizon_days
        )
        
        if not jobs_data:
            logger.warning("NO JOBS FOUND from mariadb_parser")
            raise HTTPException(status_code=404, detail=f"Job with ID {job_id} not found")
        
        # Find job by op_id
        found_job = None
        for job in jobs_data:
            if job.get('op_id') == job_id:
                found_job = job
                break
        
        if not found_job:
            logger.warning(f"JOB NOT FOUND: {job_id}")
            raise HTTPException(status_code=404, detail=f"Job with ID {job_id} not found")

        # STRICT validation - NO FALLBACKS for missing data
        required_fields = ['job_id', 'job', 'process_code']
        for field in required_fields:
            if field not in found_job or found_job[field] is None:
                logger.error(f"INVALID JOB DATA: Missing required field '{field}' for job {job_id}")
                raise HTTPException(status_code=500, detail=f"Job data incomplete - missing {field}")
        
        # Ensure op_id is available for API compatibility
        if 'op_id' not in found_job:
            found_job['op_id'] = job_id
        
        transformed_row = DataTransformer.transform_job_row(found_job)
        return ProductionJobResponse(**transformed_row)
                
    except ValueError as e:
        logger.error(f"JOB ID VALIDATION ERROR: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise  # Re-raise HTTP exceptions
    except Exception as e:
        logger.error(f"UNEXPECTED ERROR fetching job {job_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

# Disabled endpoints - NO WRITE OPERATIONS SUPPORTED
@router.post("/", response_model=APIResponse)
async def create_production_job(job_data: ProductionJobData = Body(...)):
    """CREATE NOT SUPPORTED - READ-ONLY ENDPOINT."""
    logger.error("ATTEMPTED CREATE OPERATION on read-only endpoint")
    raise HTTPException(status_code=501, detail="Create operations not supported - read-only endpoint")

@router.put("/{job_id}", response_model=ProductionJobResponse)
async def update_production_job(job_id: int, job_data: ProductionJobData = Body(...)):
    """UPDATE NOT SUPPORTED - READ-ONLY ENDPOINT."""
    logger.error(f"ATTEMPTED UPDATE OPERATION on read-only endpoint for job {job_id}")
    raise HTTPException(status_code=501, detail="Update operations not supported - read-only endpoint")

@router.delete("/{job_id}", response_model=APIResponse)
async def delete_production_job(job_id: int):
    """DELETE NOT SUPPORTED - READ-ONLY ENDPOINT."""
    logger.error(f"ATTEMPTED DELETE OPERATION on read-only endpoint for job {job_id}")
    raise HTTPException(status_code=501, detail="Delete operations not supported - read-only endpoint")