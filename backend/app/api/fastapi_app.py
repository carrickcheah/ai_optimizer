"""Production-grade FastAPI application core with optimized models and utilities."""

from fastapi import APIRouter, HTTPException, Depends, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, validator
from typing import Optional, List, Dict, Any, Union
import mysql.connector
from mysql.connector import pooling
import logging
from datetime import datetime
from contextlib import contextmanager
import asyncio
import time
from functools import wraps
import os
from dotenv import load_dotenv

try:
    from app.data_ingestion.mariadb_parser import get_db_connection
except ImportError:
    # Fallback for different import contexts
    try:
        from backend.app.data_ingestion.mariadb_parser import get_db_connection
    except ImportError:
        from ..data_ingestion.mariadb_parser import get_db_connection

logger = logging.getLogger(__name__)

# Create API router
router = APIRouter()

# Connection Pool Configuration
DB_POOL = None

def get_connection_pool():
    """Initialize database connection pool for production-grade performance."""
    global DB_POOL
    if DB_POOL is None:
        try:
            # Load environment variables from project root
            load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), '../../../.env'))
            
            # Use environment variables directly for connection pool
            config = {
                'host': os.getenv("MARIADB_HOST", "localhost"),
                'port': int(os.getenv("MARIADB_PORT", "3306")),
                'user': os.getenv("MARIADB_USERNAME"),
                'password': os.getenv("MARIADB_PASSWORD"),
                'database': os.getenv("MARIADB_DATABASE"),
                'charset': 'utf8mb4',
                'collation': 'utf8mb4_unicode_ci',
                'use_unicode': True,
                'autocommit': False
            }
            
            # Validate required parameters
            if not all([config['user'], config['password'], config['database']]):
                raise ValueError("Missing required database credentials in environment variables")
            
            # Create connection pool
            DB_POOL = pooling.MySQLConnectionPool(
                pool_name="ai_optimizer_pool",
                pool_size=10,
                pool_reset_session=True,
                **config
            )
            logger.info("Database connection pool initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize connection pool: {e}")
            DB_POOL = None
    return DB_POOL

@contextmanager
def get_db_connection_from_pool():
    """Context manager for database connections with automatic cleanup."""
    connection = None
    try:
        pool = get_connection_pool()
        if pool:
            connection = pool.get_connection()
        else:
            # Fallback to direct connection
            connection = get_db_connection()
        
        yield connection
    except mysql.connector.Error as e:
        if connection:
            connection.rollback()
        logger.error(f"Database error: {e}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
    except Exception as e:
        if connection:
            connection.rollback()
        logger.error(f"Unexpected error: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")
    finally:
        if connection and connection.is_connected():
            connection.close()

# Performance monitoring decorator
def monitor_performance(func):
    """Decorator to monitor API endpoint performance."""
    @wraps(func)
    async def wrapper(*args, **kwargs):
        start_time = time.time()
        try:
            result = await func(*args, **kwargs)
            duration = time.time() - start_time
            logger.info(f"{func.__name__} completed in {duration:.3f}s")
            return result
        except Exception as e:
            duration = time.time() - start_time
            logger.error(f"{func.__name__} failed after {duration:.3f}s: {e}")
            raise
    return wrapper

# Enhanced Pydantic Models with Validation
class ProductionJobData(BaseModel):
    """Production job input model with comprehensive validation."""
    lcd_date: Optional[str] = Field(None, description="Latest completion date")
    job: str = Field(..., min_length=1, max_length=50, description="Job identifier")
    process_code: str = Field(..., min_length=1, max_length=20, description="Process code")
    rsc_location: str = Field(..., min_length=1, max_length=10, description="Resource location")
    MachineName_v: str = Field(..., min_length=1, max_length=50, description="Machine name")
    number_operator: int = Field(default=1, ge=1, le=10, description="Number of operators")
    job_quantity: int = Field(..., ge=1, le=1000000, description="Job quantity")
    expect_output_per_hour: int = Field(..., ge=1, le=10000, description="Expected output per hour")
    hours_need: float = Field(..., ge=0.1, le=1000.0, description="Hours needed")
    day_need: float = Field(default=0, ge=0, le=365, description="Days needed")
    setting_hours: float = Field(default=1, ge=0, le=24, description="Setup hours")
    break_hours: float = Field(default=1, ge=0, le=24, description="Break hours")
    no_prod: float = Field(default=8, ge=0, le=24, description="Non-production hours")
    priority: int = Field(default=3, ge=1, le=5, description="Job priority (1=highest, 5=lowest)")
    job_dependency: bool = Field(default=True, description="Has job dependencies")
    material_arrival: Optional[str] = Field(None, description="Material arrival date")
    start_date: Optional[str] = Field(None, description="Job start date")
    reduce_operation_hours: int = Field(default=0, ge=0, le=24, description="Reduced operation hours")
    
    @validator('lcd_date', 'material_arrival', 'start_date')
    def validate_dates(cls, v):
        """Validate date strings are in proper format."""
        if v is not None and v.strip():
            try:
                # Try parsing common date formats
                for fmt in ['%Y-%m-%d', '%Y-%m-%d %H:%M:%S', '%d/%m/%Y', '%d/%m/%Y %H:%M']:
                    try:
                        datetime.strptime(v.strip(), fmt)
                        return v.strip()
                    except ValueError:
                        continue
                raise ValueError("Invalid date format")
            except Exception:
                raise ValueError(f"Invalid date format: {v}")
        return v
    
    @validator('job', 'process_code')
    def validate_identifiers(cls, v):
        """Validate job and process code format."""
        if not v or not v.strip():
            raise ValueError("Cannot be empty")
        # Basic sanitization
        return v.strip().upper()
    
    class Config:
        """Pydantic configuration."""
        json_schema_extra = {
            "example": {
                "job": "J/O-03",
                "process_code": "CD02-P01",
                "rsc_location": "VM",
                "MachineName_v": "TW01-Wire Machine",
                "job_quantity": 1000,
                "expect_output_per_hour": 10,
                "hours_need": 100.0,
                "priority": 3
            }
        }

class ProductionJobResponse(BaseModel):
    """Production job response model with proper typing."""
    op_id: int
    plan_date: Optional[datetime] = None
    lcd_date: Optional[datetime] = None
    job: str
    process_code: str
    rsc_location: str
    MachineName_v: str
    machine: Optional[str] = None
    job_dependency: bool
    number_operator: int
    job_quantity: int
    expect_output_per_hour: int
    hours_need: float
    setting_hours: float
    break_hours: float
    no_prod: float
    priority: int
    material_arrival: Optional[datetime] = None
    start_date: Optional[datetime] = None
    reduce_operation_hours: int = 0
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    
    class Config:
        """Pydantic configuration."""
        from_attributes = True
        json_encoders = {
            datetime: lambda v: v.isoformat() if v else None
        }

class MachineResponse(BaseModel):
    """Machine response model."""
    machine_name: str = Field(..., alias="MachineName_v")
    location: str = Field(..., alias="rsc_location")
    status: str = Field(default="active")
    capacity: Optional[int] = Field(default=1)
    
    class Config:
        """Pydantic configuration."""
        populate_by_name = True

class APIResponse(BaseModel):
    """Standard API response wrapper."""
    success: bool
    message: str
    data: Optional[Any] = None
    errors: Optional[List[str]] = None
    timestamp: datetime = Field(default_factory=datetime.now)

# Data Transformation Utilities
class DataTransformer:
    """Centralized data transformation utilities."""
    
    @staticmethod
    def transform_job_row(row: Dict[str, Any]) -> Dict[str, Any]:
        """Transform raw database row to standardized format."""
        if not row:
            return {}
        
        # Convert boolean fields
        if 'job_dependency' in row:
            row['job_dependency'] = bool(row.get('job_dependency', False))
        
        # Convert integer fields
        int_fields = ['job_quantity', 'expect_output_per_hour', 'hours_need', 
                     'number_operator', 'priority', 'reduce_operation_hours']
        for field in int_fields:
            if field in row and row[field] is not None:
                try:
                    row[field] = int(float(row[field]))  # Handle decimals from DB
                except (ValueError, TypeError):
                    logger.warning(f"Could not convert {field} to int: {row[field]}")
                    row[field] = 0
        
        # Convert float fields
        float_fields = ['setting_hours', 'break_hours', 'no_prod', 'day_need']
        for field in float_fields:
            if field in row and row[field] is not None:
                try:
                    row[field] = float(row[field])
                except (ValueError, TypeError):
                    logger.warning(f"Could not convert {field} to float: {row[field]}")
                    row[field] = 0.0
        
        return row

# Enhanced Endpoints with Production Features
@router.get("/machines", 
           response_model=List[MachineResponse],
           summary="Get all machines",
           description="Retrieve list of all available machines with their locations")
@monitor_performance
async def get_machines():
    """Get list of all available machines with enhanced error handling."""
    with get_db_connection_from_pool() as conn:
        cursor = conn.cursor(dictionary=True)
        
        try:
            # Primary query - get machines from jobs
            cursor.execute("""
                SELECT DISTINCT 
                    jop.Machine_v as MachineName_v, 
                    '' as rsc_location,
                    'active' as status,
                    1 as capacity
                FROM tbl_jo_process AS jop 
                INNER JOIN tbl_jo_txn AS jot ON jot.TxnId_i = jop.TxnId_i 
                WHERE jot.Void_c != 1 
                    AND jot.DocStatus_c != 'CP' 
                    AND jop.QtyStatus_c != 'FF' 
                    AND jot.CreateDate_dt BETWEEN DATE_SUB(CURDATE(), INTERVAL 30 DAY) AND DATE_ADD(CURDATE(), INTERVAL 30 DAY)
                ORDER BY jop.Machine_v
            """)
            
            machines = cursor.fetchall()
            
            # Fallback if no machines found
            if not machines:
                logger.warning("No machines found in job table, using defaults")
                machines = [
                    {"MachineName_v": "TW01", "rsc_location": "VM", "status": "active", "capacity": 1},
                    {"MachineName_v": "TW02", "rsc_location": "TR", "status": "active", "capacity": 1}
                ]
            
            logger.info(f"Retrieved {len(machines)} machines")
            return [MachineResponse(**machine) for machine in machines]
            
        except mysql.connector.Error as e:
            logger.error(f"Database error fetching machines: {e}")
            raise HTTPException(status_code=500, detail="Failed to fetch machines")
        finally:
            cursor.close()

# Export components
__all__ = ["router", "ProductionJobData", "ProductionJobResponse", "DataTransformer", 
           "get_db_connection_from_pool", "monitor_performance", "APIResponse"]