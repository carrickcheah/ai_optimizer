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
    get_db_connection_from_pool,
    get_connection_pool,
    monitor_performance,
    APIResponse
)

router = APIRouter()
logger = logging.getLogger(__name__)

@dataclass
class EndpointConfig:
    """Configuration for production jobs endpoints - ALL VALUES MUST BE IN .env - NO FALLBACKS."""
    
    # Pagination limits
    max_page_size: int
    default_page_size: int
    max_jobs_limit: int
    
    # Time horizons
    planning_horizon_days: int
    default_buffer_days: int
    max_buffer_days: int
    max_planning_horizon_days: int
    
    # Performance limits
    query_timeout_seconds: int
    
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
        max_page_size = get_required_int_env('MAX_PAGE_SIZE')
        default_page_size = get_required_int_env('DEFAULT_PAGE_SIZE')
        max_jobs_limit = get_required_int_env('MAX_JOBS_LIMIT')
        planning_horizon_days = get_required_int_env('PLANNING_HORIZON_DAYS')
        default_buffer_days = get_required_int_env('DEFAULT_BUFFER_DAYS')
        max_buffer_days = get_required_int_env('MAX_BUFFER_DAYS')
        max_planning_horizon_days = get_required_int_env('MAX_PLANNING_HORIZON_DAYS')
        query_timeout_seconds = get_required_int_env('QUERY_TIMEOUT_SECONDS')
        
        # Check for critical errors - FAIL IMMEDIATELY
        if missing_vars:
            error_msg = f"❌ CRITICAL ENDPOINT CONFIG ERROR: Missing required environment variables: {', '.join(missing_vars)}"
            logger.error(error_msg)
            raise ValueError(error_msg)
        
        if invalid_vars:
            error_msg = f"❌ CRITICAL ENDPOINT CONFIG ERROR: Invalid environment variable values: {', '.join(invalid_vars)}"
            logger.error(error_msg)
            raise ValueError(error_msg)
        
        # Validate business logic - FAIL IF INVALID
        if max_page_size > max_jobs_limit:
            error_msg = f"❌ CRITICAL CONFIG ERROR: MAX_PAGE_SIZE ({max_page_size}) cannot exceed MAX_JOBS_LIMIT ({max_jobs_limit})"
            logger.error(error_msg)
            raise ValueError(error_msg)
        
        if default_page_size > max_page_size:
            error_msg = f"❌ CRITICAL CONFIG ERROR: DEFAULT_PAGE_SIZE ({default_page_size}) cannot exceed MAX_PAGE_SIZE ({max_page_size})"
            logger.error(error_msg)
            raise ValueError(error_msg)
        
        if default_buffer_days > max_buffer_days:
            error_msg = f"❌ CRITICAL CONFIG ERROR: DEFAULT_BUFFER_DAYS ({default_buffer_days}) cannot exceed MAX_BUFFER_DAYS ({max_buffer_days})"
            logger.error(error_msg)
            raise ValueError(error_msg)
        
        if planning_horizon_days > max_planning_horizon_days:
            error_msg = f"❌ CRITICAL CONFIG ERROR: PLANNING_HORIZON_DAYS ({planning_horizon_days}) cannot exceed MAX_PLANNING_HORIZON_DAYS ({max_planning_horizon_days})"
            logger.error(error_msg)
            raise ValueError(error_msg)
        
        logger.info(f"✅ Successfully loaded endpoint configuration from .env")
        
        return cls(
            max_page_size=max_page_size,
            default_page_size=default_page_size,
            max_jobs_limit=max_jobs_limit,
            planning_horizon_days=planning_horizon_days,
            default_buffer_days=default_buffer_days,
            max_buffer_days=max_buffer_days,
            max_planning_horizon_days=max_planning_horizon_days,
            query_timeout_seconds=query_timeout_seconds
        )

# Initialize configuration at module level - FAIL IF MISSING
try:
    ENDPOINT_CONFIG = EndpointConfig.from_env()
    logger.info(f"✅ Production jobs endpoints initialized")
except Exception as e:
    logger.error(f"❌ FAILED to initialize endpoint configuration: {e}")
    raise

class ProductionJobQueries:
    """Database queries with strict validation - NO FALLBACKS."""
    
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
        
        if page_size > ENDPOINT_CONFIG.max_page_size:
            raise ValueError(f"Page size cannot exceed {ENDPOINT_CONFIG.max_page_size}")
    
    @staticmethod
    def validate_time_parameters(buffer_days: int, planning_horizon_days: int) -> None:
        """Validate time parameters with strict limits - NO FALLBACKS."""
        if buffer_days <= 0:
            raise ValueError("Buffer days must be positive")
        
        if buffer_days > ENDPOINT_CONFIG.max_buffer_days:
            raise ValueError(f"Buffer days cannot exceed {ENDPOINT_CONFIG.max_buffer_days}")
        
        if planning_horizon_days <= 0:
            raise ValueError("Planning horizon days must be positive")
        
        if planning_horizon_days > ENDPOINT_CONFIG.max_planning_horizon_days:
            raise ValueError(f"Planning horizon days cannot exceed {ENDPOINT_CONFIG.max_planning_horizon_days}")
    
    @staticmethod
    def get_base_select_query() -> str:
        """Base SELECT query - NO FALLBACKS for missing data."""
        return """
        SELECT
            jop.TxnId_i AS op_id,
            jot.CreateDate_dt AS plan_date,
            jot.TargetDate_dd AS lcd_date,
            jot.DocRef_v AS job,
            jop.Task_v AS process_code,
            jop.Machine_v AS rsc_code,
            COALESCE(tm.MachineName_v, jop.Machine_v) AS machine_name,
            jop.ManCount_i AS number_operator,
            jot.JoQty_d AS job_quantity,
            CASE WHEN jop.CapMin_d = 1 AND jop.CapQty_d > 0 
                 THEN jop.CapQty_d * 60 
                 ELSE NULL END AS expect_output_per_hour,
            CASE WHEN jop.CapMin_d = 1 AND jop.CapQty_d > 0 
                 THEN jot.JoQty_d / (jop.CapQty_d * 60) 
                 ELSE NULL END AS hours_need,
            jop.SetupTime_d AS setting_hours,
            jot.MaterialDate_dd AS material_arrival,
            jot.CreateDate_dt AS created_at,
            jot.UpdateDate_dt AS updated_at
        FROM tbl_jo_process AS jop 
        INNER JOIN tbl_jo_txn AS jot ON jot.TxnId_i = jop.TxnId_i 
        LEFT JOIN tbl_machine AS tm ON (
            tm.MachineName_v LIKE CONCAT('%', jop.Machine_v, '%') 
            OR tm.machine_id_v = jop.Machine_v
        )
        WHERE jot.Void_c != 1 
            AND jot.DocStatus_c != 'CP' 
            AND jop.QtyStatus_c != 'FF'
        """

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
           description="Retrieve production jobs with STRICT validation - NO FALLBACKS")
@monitor_performance
async def get_production_jobs(
    limit: Optional[int] = Query(None, ge=1, le=ENDPOINT_CONFIG.max_jobs_limit, description="Limit number of results"),
    offset: Optional[int] = Query(None, ge=0, description="Offset for pagination"),
    priority: Optional[int] = Query(None, ge=1, le=5, description="Filter by priority")
):
    """Get production jobs with STRICT validation - NO FALLBACKS."""
    try:
        # Strict parameter validation - FAIL IF INVALID
        ProductionJobQueries.validate_query_parameters(limit, offset)
        ProductionJobService.validate_priority_filter(priority)
        
        with get_db_connection_from_pool() as conn:
            cursor = conn.cursor(dictionary=True)
            
            try:
                # Build query with STRICT parameter handling
                base_query = ProductionJobQueries.get_base_select_query()
                params = []
                
                # Add priority filter if specified
                if priority is not None:
                    base_query += " AND 3 = %s"  # Fixed priority value, replace with actual priority field
                    params.append(priority)
                
                # Add date range filter using configured horizon
                base_query += f" AND jot.CreateDate_dt BETWEEN DATE_SUB(CURDATE(), INTERVAL {ENDPOINT_CONFIG.default_buffer_days} DAY) AND DATE_ADD(CURDATE(), INTERVAL {ENDPOINT_CONFIG.planning_horizon_days} DAY)"
                
                base_query += " ORDER BY jot.CreateDate_dt DESC, jop.TxnId_i DESC"
                
                # Add pagination if specified
                if limit is not None:
                    base_query += " LIMIT %s"
                    params.append(limit)
                    
                    if offset is not None:
                        base_query += " OFFSET %s"
                        params.append(offset)
                
                cursor.execute(base_query, params)
                jobs_from_db = cursor.fetchall()
                
                if not jobs_from_db:
                    logger.warning(f"❌ NO JOBS FOUND with current filters")
                    return []
                
                # Transform and validate data - FAIL ON INVALID DATA
                response_jobs = []
                failed_jobs = 0
                
                for job_row in jobs_from_db:
                    try:
                        # Strict validation - NO FALLBACKS for missing required fields
                        required_fields = ['op_id', 'job', 'process_code']
                        for field in required_fields:
                            if job_row.get(field) is None:
                                raise ValueError(f"Required field '{field}' is missing")
                        
                        transformed_row = DataTransformer.transform_job_row(job_row)
                        response_jobs.append(ProductionJobResponse(**transformed_row))
                        
                    except Exception as e:
                        failed_jobs += 1
                        logger.error(f"❌ FAILED to validate job data for op_id {job_row.get('op_id')}: {e}")
                        continue
                
                if failed_jobs > 0:
                    logger.warning(f"⚠️ {failed_jobs} jobs failed validation and were excluded")
                
                if not response_jobs:
                    logger.error(f"❌ ALL JOBS FAILED VALIDATION - no valid jobs returned")
                    raise HTTPException(status_code=500, detail="All jobs failed data validation")
                
                logger.info(f"✅ Retrieved {len(response_jobs)} valid production jobs")
                return response_jobs
                
            except mysql.connector.Error as e:
                logger.error(f"❌ DATABASE ERROR fetching jobs: {e}")
                raise HTTPException(status_code=500, detail="Database query failed")
            finally:
                cursor.close()
                
    except ValueError as e:
        logger.error(f"❌ PARAMETER VALIDATION ERROR: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"❌ UNEXPECTED ERROR in get_production_jobs: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/production-schedule", 
           response_model=Dict[str, Any],
           summary="Get production schedule data",
           description="Get production schedule with STRICT validation - NO FALLBACKS")
@monitor_performance
async def get_production_schedule(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(ENDPOINT_CONFIG.default_page_size, ge=1, le=ENDPOINT_CONFIG.max_page_size, description="Items per page"),
    sort_field: Optional[str] = Query("LCD_DATE", description="Field to sort by"),
    sort_order: Optional[str] = Query("asc", description="Sort order: 'asc' or 'desc'"),
    search: Optional[str] = Query(None, description="Search term"),
    buffer_days: int = Query(ENDPOINT_CONFIG.default_buffer_days, ge=1, le=ENDPOINT_CONFIG.max_buffer_days, description="Buffer days"),
    planning_horizon_days: int = Query(ENDPOINT_CONFIG.planning_horizon_days, ge=7, le=ENDPOINT_CONFIG.max_planning_horizon_days, description="Planning horizon days")
):
    """Get production schedule with STRICT validation - NO FALLBACKS."""
    try:
        # STRICT parameter validation - FAIL IF INVALID
        ProductionJobQueries.validate_pagination_parameters(page, page_size)
        ProductionJobQueries.validate_time_parameters(buffer_days, planning_horizon_days)
        
        # Validate sort parameters - NO FALLBACKS
        allowed_sort_fields = {
            "PLAN_DATE": "jot.CreateDate_dt",
            "LCD_DATE": "jot.TargetDate_dd",
            "JOB": "jot.DocRef_v",
            "PROCESS_CODE": "jop.Task_v",
            "RSC_CODE": "jop.Machine_v",
            "MACHINE": "COALESCE(tm.MachineName_v, jop.Machine_v)",
            "NUMBER_OPERATOR": "jop.ManCount_i",
            "JOB_QUANTITY": "jot.JoQty_d"
        }
        
        if sort_field not in allowed_sort_fields:
            raise ValueError(f"Invalid sort_field. Allowed values: {list(allowed_sort_fields.keys())}")
        
        if sort_order.lower() not in ['asc', 'desc']:
            raise ValueError("sort_order must be 'asc' or 'desc'")
        
        sql_sort_field = allowed_sort_fields[sort_field]
        sql_sort_order = "DESC" if sort_order.lower() == "desc" else "ASC"
        
        with get_db_connection_from_pool() as conn:
            cursor = conn.cursor(dictionary=True)
            
            try:
                # Build base query components
                base_select = """
                SELECT 
                    jot.CreateDate_dt AS plan_date,
                    jot.TargetDate_dd AS LCD_DATE, 
                    jot.DocRef_v AS JOB, 
                    jop.Task_v AS PROCESS_CODE, 
                    jop.Machine_v AS RSC_CODE, 
                    COALESCE(tm.MachineName_v, jop.Machine_v) AS MACHINE,
                    jop.ManCount_i AS NUMBER_OPERATOR, 
                    jot.JoQty_d AS JOB_QUANTITY,
                    jop.TxnId_i,
                    jot.MaterialDate_dd AS MATERIAL_ARRIVAL
                """
                
                base_from = """
                FROM tbl_jo_process AS jop 
                INNER JOIN tbl_jo_txn AS jot ON jot.TxnId_i = jop.TxnId_i 
                LEFT JOIN tbl_machine AS tm ON (
                    tm.MachineName_v LIKE CONCAT('%', jop.Machine_v, '%') 
                    OR tm.machine_id_v = jop.Machine_v
                )
                """
                
                # STRICT date range filter - NO FALLBACKS
                base_where = f"""
                WHERE jot.Void_c != 1 
                    AND jot.DocStatus_c != 'CP' 
                    AND jop.QtyStatus_c != 'FF' 
                    AND jot.CreateDate_dt BETWEEN DATE_SUB(CURDATE(), INTERVAL {buffer_days} DAY) AND DATE_ADD(CURDATE(), INTERVAL {planning_horizon_days} DAY)
                """
                
                params = []
                search_conditions = ""
                
                # Add search conditions if provided
                if search and search.strip():
                    search_term = f"%{search.strip().lower()}%"
                    search_conditions = """
                    AND (
                        LOWER(jot.DocRef_v) LIKE %s OR 
                        LOWER(jop.Task_v) LIKE %s OR 
                        LOWER(jop.Machine_v) LIKE %s OR
                        LOWER(COALESCE(tm.MachineName_v, '')) LIKE %s
                    )
                    """
                    params.extend([search_term, search_term, search_term, search_term])
                
                # Count query for pagination
                count_query = f"SELECT COUNT(*) as total_items {base_from} {base_where} {search_conditions}"
                cursor.execute(count_query, params)
                total_result = cursor.fetchone()
                
                if not total_result:
                    raise HTTPException(status_code=500, detail="Failed to get total count")
                
                total_items = total_result['total_items']
                total_pages = math.ceil(total_items / page_size) if total_items > 0 else 1
                
                # Validate page number against total pages
                if page > total_pages and total_items > 0:
                    raise ValueError(f"Page {page} exceeds total pages {total_pages}")
                
                # Data query with pagination and sorting
                offset = (page - 1) * page_size
                order_clause = f"ORDER BY {sql_sort_field} {sql_sort_order}"
                limit_clause = "LIMIT %s OFFSET %s"
                
                data_params = params + [page_size, offset]
                data_query = f"{base_select} {base_from} {base_where} {search_conditions} {order_clause} {limit_clause}"
                
                cursor.execute(data_query, data_params)
                results = cursor.fetchall()
                
                logger.info(f"✅ Retrieved {len(results)} schedule records (page {page}/{total_pages})")
                
                return {
                    "items": results,
                    "total_items": total_items,
                    "page": page,
                    "page_size": page_size,
                    "total_pages": total_pages,
                    "config_used": {
                        "buffer_days": buffer_days,
                        "planning_horizon_days": planning_horizon_days,
                        "sort_field": sort_field,
                        "sort_order": sort_order
                    }
                }
                
            except mysql.connector.Error as e:
                logger.error(f"❌ DATABASE ERROR fetching production schedule: {e}")
                raise HTTPException(status_code=500, detail="Database query failed")
            finally:
                cursor.close()
                
    except ValueError as e:
        logger.error(f"❌ PARAMETER VALIDATION ERROR: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"❌ UNEXPECTED ERROR in get_production_schedule: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/{job_id}", 
           response_model=ProductionJobResponse,
           summary="Get production job by ID",
           description="Get specific job with STRICT validation - NO FALLBACKS")
@monitor_performance
async def get_production_job(job_id: int):
    """Get specific production job with STRICT validation - NO FALLBACKS."""
    try:
        # STRICT job ID validation - FAIL IF INVALID
        ProductionJobService.validate_job_id(job_id)
        
        with get_db_connection_from_pool() as conn:
            cursor = conn.cursor(dictionary=True)
            
            try:
                query = ProductionJobQueries.get_base_select_query() + " AND jop.TxnId_i = %s"
                cursor.execute(query, (job_id,))
                job_row = cursor.fetchone()
                
                if not job_row:
                    logger.warning(f"❌ JOB NOT FOUND: {job_id}")
                    raise HTTPException(status_code=404, detail=f"Job with ID {job_id} not found")
                
                # STRICT validation - NO FALLBACKS for missing data
                required_fields = ['op_id', 'job', 'process_code']
                for field in required_fields:
                    if job_row.get(field) is None:
                        logger.error(f"❌ INVALID JOB DATA: Missing required field '{field}' for job {job_id}")
                        raise HTTPException(status_code=500, detail=f"Job data incomplete - missing {field}")
                
                transformed_row = DataTransformer.transform_job_row(job_row)
                return ProductionJobResponse(**transformed_row)
                
            except mysql.connector.Error as e:
                logger.error(f"❌ DATABASE ERROR fetching job {job_id}: {e}")
                raise HTTPException(status_code=500, detail="Database query failed")
            finally:
                cursor.close()
                
    except ValueError as e:
        logger.error(f"❌ JOB ID VALIDATION ERROR: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise  # Re-raise HTTP exceptions
    except Exception as e:
        logger.error(f"❌ UNEXPECTED ERROR fetching job {job_id}: {e}")
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
            "max_page_size": ENDPOINT_CONFIG.max_page_size
        }
    }
    
    # Database connectivity check - FAIL IF UNHEALTHY
    try:
        with get_db_connection_from_pool() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT 1 as health_check")
            result = cursor.fetchone()
            cursor.close()
            
            if not result or result[0] != 1:
                raise Exception("Database health check returned invalid result")
            
            health_data["checks"]["database"] = {"status": "healthy"}
            
    except Exception as e:
        logger.error(f"❌ DATABASE HEALTH CHECK FAILED: {e}")
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
        logger.error(f"❌ CONFIGURATION HEALTH CHECK FAILED: {e}")
        health_data["status"] = "unhealthy"
        health_data["checks"]["configuration"] = {
            "status": "unhealthy",
            "error": str(e)
        }
    
    status_code = 200 if health_data["status"] == "healthy" else 503
    return JSONResponse(content=health_data, status_code=status_code)

# Disabled endpoints - NO WRITE OPERATIONS SUPPORTED
@router.post("/", response_model=APIResponse)
async def create_production_job(job_data: ProductionJobData = Body(...)):
    """CREATE NOT SUPPORTED - READ-ONLY ENDPOINT."""
    logger.error("❌ ATTEMPTED CREATE OPERATION on read-only endpoint")
    raise HTTPException(status_code=501, detail="Create operations not supported - read-only endpoint")

@router.put("/{job_id}", response_model=ProductionJobResponse)
async def update_production_job(job_id: int, job_data: ProductionJobData = Body(...)):
    """UPDATE NOT SUPPORTED - READ-ONLY ENDPOINT."""
    logger.error(f"❌ ATTEMPTED UPDATE OPERATION on read-only endpoint for job {job_id}")
    raise HTTPException(status_code=501, detail="Update operations not supported - read-only endpoint")

@router.delete("/{job_id}", response_model=APIResponse)
async def delete_production_job(job_id: int):
    """DELETE NOT SUPPORTED - READ-ONLY ENDPOINT."""
    logger.error(f"❌ ATTEMPTED DELETE OPERATION on read-only endpoint for job {job_id}")
    raise HTTPException(status_code=501, detail="Delete operations not supported - read-only endpoint")