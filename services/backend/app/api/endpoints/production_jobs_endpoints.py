# services/ai_optimizer/backend/app/api/endpoints/production_jobs_endpoints.py
"""Production-grade production jobs API endpoints with optimized performance and error handling."""

from fastapi import APIRouter, HTTPException, Body, Query, Depends
from fastapi.responses import JSONResponse
import logging
from typing import List, Dict, Any, Optional
import mysql.connector
from datetime import datetime
import math # Added for math.ceil

from ..fastapi_app import (
    ProductionJobData, 
    ProductionJobResponse, 
    DataTransformer,
    get_db_connection_from_pool,
    monitor_performance,
    APIResponse
)

router = APIRouter()
logger = logging.getLogger(__name__)

# Database Queries - Centralized and optimized
class ProductionJobQueries:
    """Centralized database queries for production jobs."""
    
    @staticmethod
    def get_base_select_query() -> str:
        """Base SELECT query for production jobs."""
        return """
        SELECT
            op_id, created_at AS plan_date, lcd_date, job, process_code, 
            rsc_location, rsc_code, job_dependency, number_operator, 
            job_quantity, expect_output_per_hour, hours_need, day_need, 
            setting_hours, break_hours, no_prod, priority,
            material_arrival, start_date, reduce_operation_hours,
            created_at, updated_at
        FROM tbl_aa_job
        """
    
    @staticmethod
    def get_all_jobs_query(limit: Optional[int] = None, offset: Optional[int] = None) -> str:
        """Query to get all jobs with optional pagination."""
        query = ProductionJobQueries.get_base_select_query()
        query += " ORDER BY created_at DESC, op_id DESC"
        
        if limit:
            query += f" LIMIT {limit}"
            if offset:
                query += f" OFFSET {offset}"
        
        return query
    
    @staticmethod
    def get_job_by_id_query() -> str:
        """Query to get a specific job by ID."""
        return ProductionJobQueries.get_base_select_query() + " WHERE op_id = %s"
    
    @staticmethod
    def insert_job_query() -> str:
        """Query to insert a new production job."""
        return """
        INSERT INTO tbl_aa_job (
            lcd_date, job, process_code, rsc_location, rsc_code,
            job_dependency, number_operator, job_quantity, expect_output_per_hour,
            hours_need, day_need, setting_hours, break_hours, no_prod, priority,
            material_arrival, start_date, reduce_operation_hours, created_at, updated_at
        ) VALUES (
            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 
            %s, %s, %s, %s, %s, %s, %s, %s, NOW(), NOW()
        )
        """
    
    @staticmethod
    def update_job_query() -> str:
        """Query to update an existing production job."""
        return """
        UPDATE tbl_aa_job SET
            lcd_date = %s, job = %s, process_code = %s, rsc_location = %s, rsc_code = %s,
            job_dependency = %s, number_operator = %s, job_quantity = %s, 
            expect_output_per_hour = %s, hours_need = %s, day_need = %s, 
            setting_hours = %s, break_hours = %s, no_prod = %s, priority = %s,
            material_arrival = %s, start_date = %s, reduce_operation_hours = %s,
            updated_at = NOW()
        WHERE op_id = %s
        """
    
    @staticmethod
    def delete_job_query() -> str:
        """Query to delete a production job."""
        return "DELETE FROM tbl_aa_job WHERE op_id = %s"

# Service Layer
class ProductionJobService:
    """Business logic layer for production jobs."""
    
    @staticmethod
    def prepare_job_data(job_data: ProductionJobData) -> tuple:
        """Prepare job data for database insertion/update."""
        return (
            job_data.lcd_date, job_data.job, job_data.process_code, 
            job_data.rsc_location, job_data.rsc_code, job_data.job_dependency,
            job_data.number_operator, job_data.job_quantity, job_data.expect_output_per_hour,
            job_data.hours_need, job_data.day_need, job_data.setting_hours, 
            job_data.break_hours, job_data.no_prod, job_data.priority,
            job_data.material_arrival, job_data.start_date, job_data.reduce_operation_hours
        )
    
    @staticmethod
    def validate_job_exists(cursor, job_id: int) -> bool:
        """Check if a job exists in the database."""
        cursor.execute("SELECT 1 FROM tbl_aa_job WHERE op_id = %s", (job_id,))
        return cursor.fetchone() is not None

# API Endpoints
@router.get("/", 
           response_model=List[ProductionJobResponse],
           summary="Get all production jobs",
           description="Retrieve all production jobs with optional pagination")
@monitor_performance
async def get_production_jobs(
    limit: Optional[int] = Query(None, ge=1, le=1000, description="Limit number of results"),
    offset: Optional[int] = Query(None, ge=0, description="Offset for pagination"),
    priority: Optional[int] = Query(None, ge=1, le=5, description="Filter by priority")
):
    """Get all production jobs with optional filtering and pagination."""
    with get_db_connection_from_pool() as conn:
        cursor = conn.cursor(dictionary=True)
        
        try:
            # Build query with optional filters
            query = ProductionJobQueries.get_all_jobs_query(limit, offset)
            params = []
            
            # Add priority filter if specified
            if priority:
                query = query.replace("ORDER BY", "WHERE priority = %s ORDER BY")
                params.append(priority)
            
            cursor.execute(query, params)
            jobs_from_db = cursor.fetchall()
            
            # Transform and validate data
            response_jobs = []
            for job_row in jobs_from_db:
                try:
                    transformed_row = DataTransformer.transform_job_row(job_row)
                    response_jobs.append(ProductionJobResponse(**transformed_row))
                except Exception as e:
                    logger.error(f"Error validating job data for op_id {job_row.get('op_id')}: {e}")
                    continue  # Skip invalid jobs rather than fail entire request
            
            logger.info(f"Retrieved {len(response_jobs)} production jobs")
            return response_jobs
            
        except mysql.connector.Error as e:
            logger.error(f"Database error fetching jobs: {e}")
            raise HTTPException(status_code=500, detail="Failed to fetch production jobs")
        finally:
            cursor.close()

@router.get("/production-schedule", 
           response_model=Dict[str, Any],
           summary="Get production schedule data",
           description="Get production schedule from joined tables with pagination, sorting, and search")
@monitor_performance
async def get_production_schedule(
    page: int = Query(1, ge=1, description="Page number for pagination"),
    page_size: int = Query(50, ge=1, le=500, description="Number of items per page"),
    sort_field: Optional[str] = Query("LCD_DATE", description="Field to sort by (e.g., LCD_DATE, JOB, PROCESS_CODE)"),
    sort_order: Optional[str] = Query("asc", description="Sort order: 'asc' or 'desc'"),
    search: Optional[str] = Query(None, description="Search term for JOB, PROCESS_CODE, RSC_CODE, RSC_LOCATION")
):
    """Get production schedule data with pagination, sorting, and search."""
    with get_db_connection_from_pool() as conn:
        cursor = conn.cursor(dictionary=True)
        
        # Define allowed sortable columns to prevent SQL injection and map to SQL expressions if needed
        allowed_sort_fields = {
            "LCD_DATE": "jot.TargetDate_dd",
            "JOB": "jot.DocRef_v",
            "PROCESS_CODE": "jop.Task_v",
            "RSC_LOCATION": "RSC_LOCATION", # This is an alias from the SELECT
            "RSC_CODE": "jop.Machine_v",
            "NUMBER_OPERATOR": "jop.ManCount_i",
            "JOB_QUANTITY": "jot.JoQty_d",
            "EXPECT_OUTPUT_PER_HOUR": "EXPECT_OUTPUT_PER_HOUR", # Alias
            "HOURS_NEED": "HOURS_NEED", # Alias
            "DAY_NEED": "DAY_NEED", # Alias
            "SETTING_HOURS": "jop.SetupTime_d",
            "START_DATE": "START_DATE", # Alias
            "ACCUMULATED_DAILY_OUTPUT": "di.Qty_d", # careful with alias vs direct field with LEFT JOIN nulls
            "BALANCE_QUANTITY": "BALANCE_QUANTITY", # Alias
            "TxnId_i": "jop.TxnId_i",
            "MATERIAL_ARRIVAL": "MATERIAL_ARRIVAL", #Alias
            "PRIORITY": "PRIORITY" #Alias
        }

        sql_sort_field = allowed_sort_fields.get(sort_field, "jot.TargetDate_dd") # Default sort
        sql_sort_order = "DESC" if sort_order and sort_order.lower() == "desc" else "ASC"

        params = []
        search_conditions = ""
        if search:
            search_term_like = f"%{search.lower()}%"
            search_conditions = """
            AND (
                LOWER(jot.DocRef_v) LIKE %s OR 
                LOWER(jop.Task_v) LIKE %s OR 
                LOWER(jop.Machine_v) LIKE %s OR
                LOWER('' AS RSC_LOCATION) LIKE %s 
            )
            """
             # For aliased RSC_LOCATION, direct SQL search is tricky without subquery or if it's always ''.
             # If RSC_LOCATION can have actual values from a field, replace LOWER('' AS RSC_LOCATION) LIKE %s
             # with LOWER(actual_field_for_RSC_LOCATION) LIKE %s
            params.extend([search_term_like, search_term_like, search_term_like, search_term_like])

        try:
            base_select_fields = """ \n                jot.TargetDate_dd AS LCD_DATE, \
                jot.DocRef_v AS JOB, \
                jop.Task_v AS PROCESS_CODE, \
                '' AS RSC_LOCATION, \
                jop.Machine_v AS RSC_CODE, \
                jop.ManCount_i AS NUMBER_OPERATOR, \
                jot.JoQty_d AS JOB_QUANTITY, \
                CASE WHEN jop.CapMin_d = 1 AND jop.CapQty_d != 0 \
                     THEN jop.CapQty_d * 60 \
                     ELSE NULL END AS EXPECT_OUTPUT_PER_HOUR,\
                CASE WHEN jop.CapMin_d = 1 AND jop.CapQty_d != 0 \
                     THEN jot.JoQty_d / (jop.CapQty_d * 60) \
                     ELSE NULL END AS HOURS_NEED,\
                CASE WHEN jop.CapMin_d = 1 AND jop.CapQty_d != 0 \
                     THEN jot.JoQty_d / (jop.CapQty_d * 60 * 24)\
                     WHEN jop.CapMin_d = 0 AND jop.LeadTime_d != 0 \
                     THEN jop.LeadTime_d \
                     ELSE NULL END AS DAY_NEED,\
                jop.SetupTime_d AS SETTING_HOURS, \
                1 AS BREAK_HOURS, \
                8 AS NO_PROD, \
                '' AS START_DATE, \
                di.Qty_d AS ACCUMULATED_DAILY_OUTPUT, \
                (jot.JoQty_d - COALESCE(di.Qty_d, 0)) AS BALANCE_QUANTITY, \
                jop.TxnId_i,\
                '' AS MATERIAL_ARRIVAL,\
                1 AS JOB_DEPENDENCY,\
                3 AS PRIORITY,\
                0 AS REDUCE_OPERATION_HOURS
            """
            from_join_clauses = """ \n            FROM tbl_jo_process AS jop \
            INNER JOIN tbl_jo_txn AS jot ON jot.TxnId_i = jop.TxnId_i \
            LEFT JOIN tbl_daily_item AS di ON di.JoId_i = jop.TxnId_i AND di.ProcessrowId_i = jop.RowId_i
            """
            base_where_clauses = """ \n            WHERE jot.Void_c != 1 \
                AND jot.DocStatus_c != 'CP' \
                AND jop.QtyStatus_c != 'FF' \
                AND jot.TargetDate_dd BETWEEN DATE_SUB(CURDATE(), INTERVAL 10 DAY) AND DATE_ADD(CURDATE(), INTERVAL 60 DAY)
            """

            # Count query
            count_query = f"SELECT COUNT(*) as total_items {from_join_clauses} {base_where_clauses} {search_conditions}"
            cursor.execute(count_query, tuple(params)) # Use a copy of params for count query
            total_items_result = cursor.fetchone()
            total_items = total_items_result['total_items'] if total_items_result else 0
            total_pages = math.ceil(total_items / page_size) if total_items > 0 else 1

            # Data query with pagination, sorting, and search
            order_by_clause = f"ORDER BY {sql_sort_field} {sql_sort_order}"
            offset = (page - 1) * page_size
            
            data_query_params = list(params) # Create a new list for data query params
            data_query_params.extend([page_size, offset])

            data_query = f""" \n            SELECT {base_select_fields}
            {from_join_clauses}
            {base_where_clauses}
            {search_conditions}
            {order_by_clause}
            LIMIT %s OFFSET %s
            """            
            cursor.execute(data_query, tuple(data_query_params))
            results = cursor.fetchall()
            
            logger.info(f"Retrieved {len(results)} production schedule records for page {page}/{total_pages}, sort: {sql_sort_field} {sql_sort_order}, search: '{search}'")
            
            return {
                "items": results,
                "total_items": total_items,
                "page": page,
                "page_size": page_size,
                "total_pages": total_pages
            }
            
        except mysql.connector.Error as e:
            logger.error(f"Database error fetching production schedule: {e}")
            raise HTTPException(status_code=500, detail="Failed to fetch production schedule")
        finally:
            cursor.close()

@router.get("/{job_id}", 
           response_model=ProductionJobResponse,
           summary="Get production job by ID",
           description="Retrieve a specific production job by its ID")
@monitor_performance
async def get_production_job(job_id: int):
    """Get a specific production job by ID."""
    if job_id <= 0:
        raise HTTPException(status_code=400, detail="Job ID must be positive")
    
    with get_db_connection_from_pool() as conn:
        cursor = conn.cursor(dictionary=True)
        
        try:
            cursor.execute(ProductionJobQueries.get_job_by_id_query(), (job_id,))
            job_row = cursor.fetchone()
            
            if not job_row:
                raise HTTPException(status_code=404, detail=f"Job with ID {job_id} not found")
            
            transformed_row = DataTransformer.transform_job_row(job_row)
            return ProductionJobResponse(**transformed_row)
            
        except mysql.connector.Error as e:
            logger.error(f"Database error fetching job {job_id}: {e}")
            raise HTTPException(status_code=500, detail="Failed to fetch job")
        finally:
            cursor.close()

@router.post("/",
            response_model=APIResponse,
            summary="Create new production job",
            description="Create a new production job with validation")
@monitor_performance
async def create_production_job(job_data: ProductionJobData = Body(...)):
    """Create a new production job with comprehensive validation."""
    with get_db_connection_from_pool() as conn:
        cursor = conn.cursor()
        
        try:
            # Check for duplicate job
            cursor.execute(
                "SELECT op_id FROM tbl_aa_job WHERE job = %s AND process_code = %s",
                (job_data.job, job_data.process_code)
            )
            if cursor.fetchone():
                raise HTTPException(
                    status_code=409, 
                    detail=f"Job {job_data.job} with process {job_data.process_code} already exists"
                )
            
            # Insert new job
            data = ProductionJobService.prepare_job_data(job_data)
            cursor.execute(ProductionJobQueries.insert_job_query(), data)
            conn.commit()
            
            new_job_id = cursor.lastrowid
            logger.info(f"Successfully created job with ID: {new_job_id}")
            
            return APIResponse(
                success=True,
                message="Production job created successfully",
                data={
                    "job_id": new_job_id,
                    "job": job_data.job,
                    "process_code": job_data.process_code
                }
            )
            
        except mysql.connector.Error as e:
            conn.rollback()
            logger.error(f"Database error creating job: {e}")
            raise HTTPException(status_code=500, detail="Failed to create production job")
        except HTTPException:
            conn.rollback()
            raise
        finally:
            cursor.close()

@router.put("/{job_id}", 
           response_model=ProductionJobResponse,
           summary="Update production job",
           description="Update an existing production job")
@monitor_performance
async def update_production_job(job_id: int, job_data: ProductionJobData = Body(...)):
    """Update an existing production job."""
    if job_id <= 0:
        raise HTTPException(status_code=400, detail="Job ID must be positive")
    
    with get_db_connection_from_pool() as conn:
        cursor = conn.cursor(dictionary=True)
        
        try:
            # Check if job exists
            if not ProductionJobService.validate_job_exists(cursor, job_id):
                raise HTTPException(status_code=404, detail=f"Job with ID {job_id} not found")
            
            # Update job
            data = ProductionJobService.prepare_job_data(job_data) + (job_id,)
            cursor.execute(ProductionJobQueries.update_job_query(), data)
            conn.commit()
            
            logger.info(f"Successfully updated job with ID: {job_id}")
            
            # Fetch and return updated job
            cursor.execute(ProductionJobQueries.get_job_by_id_query(), (job_id,))
            updated_job_row = cursor.fetchone()
            
            if not updated_job_row:
                raise HTTPException(status_code=500, detail="Failed to retrieve job after update")
            
            transformed_row = DataTransformer.transform_job_row(updated_job_row)
            return ProductionJobResponse(**transformed_row)
            
        except mysql.connector.Error as e:
            conn.rollback()
            logger.error(f"Database error updating job {job_id}: {e}")
            raise HTTPException(status_code=500, detail="Failed to update production job")
        except HTTPException:
            conn.rollback()
            raise
        finally:
            cursor.close()

@router.delete("/{job_id}",
              response_model=APIResponse,
              summary="Delete production job",
              description="Delete a production job by ID")
@monitor_performance
async def delete_production_job(job_id: int):
    """Delete a production job by ID."""
    if job_id <= 0:
        raise HTTPException(status_code=400, detail="Job ID must be positive")
    
    with get_db_connection_from_pool() as conn:
        cursor = conn.cursor()
        
        try:
            # Check if job exists
            if not ProductionJobService.validate_job_exists(cursor, job_id):
                raise HTTPException(status_code=404, detail=f"Job with ID {job_id} not found")
            
            # Delete job
            cursor.execute(ProductionJobQueries.delete_job_query(), (job_id,))
            conn.commit()
            
            if cursor.rowcount == 0:
                raise HTTPException(status_code=404, detail=f"Job with ID {job_id} not found")
            
            logger.info(f"Successfully deleted job with ID: {job_id}")
            
            return APIResponse(
                success=True,
                message=f"Production job {job_id} deleted successfully",
                data={"deleted_job_id": job_id}
            )
            
        except mysql.connector.Error as e:
            conn.rollback()
            logger.error(f"Database error deleting job {job_id}: {e}")
            raise HTTPException(status_code=500, detail="Failed to delete production job")
        except HTTPException:
            conn.rollback()
            raise
        finally:
            cursor.close()

@router.get("/stats/summary",
           response_model=Dict[str, Any],
           summary="Get production jobs statistics",
           description="Get summary statistics for production jobs")
@monitor_performance
async def get_production_jobs_stats():
    """Get summary statistics for production jobs."""
    with get_db_connection_from_pool() as conn:
        cursor = conn.cursor(dictionary=True)
        
        try:
            # Get various statistics in one query
            cursor.execute("""
                SELECT 
                    COUNT(*) as total_jobs,
                    COUNT(DISTINCT rsc_code) as unique_machines,
                    AVG(hours_need) as avg_hours_needed,
                    SUM(job_quantity) as total_quantity,
                    COUNT(CASE WHEN priority = 1 THEN 1 END) as high_priority_jobs,
                    COUNT(CASE WHEN priority >= 4 THEN 1 END) as low_priority_jobs,
                    MIN(created_at) as oldest_job,
                    MAX(created_at) as newest_job
                FROM tbl_aa_job
            """)
            
            stats = cursor.fetchone()
            
            if stats:
                # Format dates
                for date_field in ['oldest_job', 'newest_job']:
                    if stats[date_field]:
                        stats[date_field] = stats[date_field].isoformat()
                
                # Round averages
                if stats['avg_hours_needed']:
                    stats['avg_hours_needed'] = round(float(stats['avg_hours_needed']), 2)
            
            return stats or {}
            
        except mysql.connector.Error as e:
            logger.error(f"Database error fetching job statistics: {e}")
            raise HTTPException(status_code=500, detail="Failed to fetch job statistics")
        finally:
            cursor.close() 