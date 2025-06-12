"""
mariadb_parser.py - FIXED VERSION
Functions for loading job data from MariaDB with security and lint fixes

 Your MariaDB parser will load jobs that are:
  1. Created within the last 100 days
  2. Due tomorrow or later (not today, not overdue)
  3. Due within the next 100 days (planning horizon)
  4. Not completed/cancelled (DocStatus_c, QtyStatus_c filters)
  5. Not voided (Void_c filter)

  ⏺ 📊 Complete Lookback Analysis Results:

  | Lookback Days | Total Jobs | Performance  |
  |---------------|------------|--------------|
  | 30 days       | 811 jobs   | Fast         |
  | 60 days       | 811 jobs   | Fast         |
  | 90 days       | 1019 jobs  | ⭐ Sweet spot |
  | 120 days      | 1019 jobs  | Same         |
  | 180 days      | 1019 jobs  | Same         |
  | 270 days      | 1019 jobs  | Same         |
  | 365 days      | 1019 jobs  | Same         |
"""

import logging
import os
import time
from datetime import datetime, date, time as dt_time
from typing import Dict, List, Tuple, Optional, Union, Any

import mysql.connector
import numpy as np
import pandas as pd
import pytz
from dotenv import load_dotenv
from mysql.connector import Error

# Load environment variables from .env file at backend root
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), '../../.env'))

# Get database configuration from environment variables
DB_HOST = os.getenv("MARIADB_HOST")
DB_USER = os.getenv("MARIADB_USERNAME")
DB_PASSWORD = os.getenv("MARIADB_PASSWORD")
DB_NAME = os.getenv("MARIADB_DATABASE")
DB_PORT = os.getenv("MARIADB_PORT", "3306")

# Configure logging first
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Get scheduling configuration
NORMAL_WORKING_HOURS = os.getenv("NORMAL_WORKING_HOURS")
if not NORMAL_WORKING_HOURS:
    logger.error("❌ MISSING NORMAL_WORKING_HOURS: NORMAL_WORKING_HOURS not set in .env")
    raise ValueError("NORMAL_WORKING_HOURS is required in .env file")
try:
    NORMAL_WORKING_HOURS = float(NORMAL_WORKING_HOURS)
except ValueError:
    logger.error(f"❌ INVALID NORMAL_WORKING_HOURS: Cannot convert '{NORMAL_WORKING_HOURS}' to float")
    raise ValueError(f"NORMAL_WORKING_HOURS must be a valid number, got: {NORMAL_WORKING_HOURS}")


def validate_environment_config() -> Dict[str, Union[int, float]]:
    """
    Validate and parse environment configuration values.
    
    Returns:
        Dict containing validated configuration values
        
    Raises:
        ValueError: If configuration values are invalid
    """
    config = {}
    
    try:
        config['break_hours'] = float(os.getenv('DEFAULT_BREAK_HOURS', '0'))
        config['no_prod_hours'] = float(os.getenv('DEFAULT_NO_PROD_HOURS', '0'))
        config['job_priority'] = int(os.getenv('DEFAULT_JOB_PRIORITY', '-1'))
        
        # Validate ranges
        if config['break_hours'] < 0:
            raise ValueError("DEFAULT_BREAK_HOURS cannot be negative")
        if config['no_prod_hours'] < 0:
            raise ValueError("DEFAULT_NO_PROD_HOURS cannot be negative")
            
    except ValueError as e:
        logger.error(f"Invalid environment variable format: {e}")
        raise
    
    return config


def get_db_connection() -> Optional[mysql.connector.MySQLConnection]:
    """
    Establish a connection to the MariaDB database.
        
    Returns:
        MySQL connector connection object or None if failed
    """
    try:
        connection = mysql.connector.connect(
            host=DB_HOST,
            user=DB_USER,
            password=DB_PASSWORD,
            database=DB_NAME,
            port=DB_PORT
        )
        if connection.is_connected():
            logger.info("Successfully connected to MariaDB database")
            return connection
        else:
            logger.error("Failed to connect to MariaDB database.")
            return None
    except Error as e:
        logger.error(f"Error connecting to MariaDB database: {e}")
        raise


def convert_datetime_to_epoch(dt_value: Any) -> Optional[int]:
    """
    Convert a datetime value to epoch timestamp in Singapore timezone.
    Handles MariaDB datetime format: 2025-07-30 17:00:00.000
    
    Args:
        dt_value: Datetime value from database
        
    Returns:
        Unix timestamp (epoch) in seconds or None if conversion fails
    """
    if pd.isna(dt_value) or dt_value is None:
        return None

    if isinstance(dt_value, str):
        try:
            dt_value = pd.to_datetime(dt_value)
        except Exception as e:
            logger.error(f"Error converting string to datetime: {dt_value} - {e}")
            try:
                dt_value = datetime.strptime(dt_value, '%Y-%m-%d %H:%M:%S.%f')
            except ValueError:
                try:
                    dt_value = datetime.strptime(dt_value, '%Y-%m-%d %H:%M:%S')
                except ValueError:
                    logger.error(f"Could not parse datetime string: {dt_value}")
                    return None
    
    # Handle datetime.date objects by converting to datetime
    if isinstance(dt_value, date) and not isinstance(dt_value, datetime):
        dt_value = datetime.combine(dt_value, dt_time.min)
        logger.debug(f"Converted date to datetime: {dt_value}")
    
    if not isinstance(dt_value, (pd.Timestamp, datetime)):
        logger.warning(f"Unexpected datetime type: {type(dt_value)}")
        return None
        
    singapore_tz = pytz.timezone('Asia/Singapore')
    
    try:
        if isinstance(dt_value, pd.Timestamp):
            dt_value = dt_value.to_pydatetime()
            
        if dt_value.tzinfo is None:
            sg_dt = singapore_tz.localize(dt_value, is_dst=None)
        else:
            sg_dt = dt_value.astimezone(singapore_tz)
        
        return int(sg_dt.timestamp())
        
    except Exception as e:
        logger.debug(f"Error converting datetime to epoch: {e} for value {dt_value}")
        return None


def build_jobs_query() -> str:
    """
    Build the SQL query for fetching job data.
    
    Returns:
        SQL query string with parameterized placeholders
    """
    return """
        SELECT
            jot.CreateDate_dt AS plan_date,
            jot.TargetDate_dd AS lcd_date,
            jop.TxnId_i AS op_id,
            jot.DocRef_v AS job,
            jop.Task_v AS process_code,
            '' AS rsc_location,
            tm.MachineName_v AS machine_name,
            jop.ManCount_i AS number_operator,
            jot.JoQty_d AS job_quantity,
            CASE WHEN jop.CapMin_d = 1 AND jop.CapQty_d != 0 
                 THEN jop.CapQty_d * 60 
                 ELSE NULL END AS expect_output_per_hour,
            CASE WHEN jop.CapMin_d = 1 AND jop.CapQty_d != 0 
                 THEN jot.JoQty_d / (jop.CapQty_d * 60) 
                 WHEN (jop.Machine_v IS NULL OR jop.Machine_v = '' OR jop.Machine_v = '0') 
                      AND jop.LeadTime_d IS NOT NULL AND jop.LeadTime_d > 0
                 THEN jop.LeadTime_d * %s
                 ELSE NULL END AS hours_need,
            CASE WHEN jop.CapMin_d = 1 AND jop.CapQty_d != 0 
                 THEN jot.JoQty_d / (jop.CapQty_d * 60 * 24)
                 WHEN jop.CapMin_d = 0 AND jop.LeadTime_d IS NOT NULL 
                      AND jop.LeadTime_d > 0
                 THEN jop.LeadTime_d 
                 WHEN (jop.Machine_v IS NULL OR jop.Machine_v = '' 
                      OR jop.Machine_v = '0') AND jop.LeadTime_d IS NOT NULL 
                      AND jop.LeadTime_d > 0
                 THEN jop.LeadTime_d
                 ELSE NULL END AS day_need,
            jop.SetupTime_d AS setting_hours,
            %s AS break_hours,
            %s AS no_prod,
            '' AS start_date,
            SUM(di.Qty_d) AS accumulated_daily_output,
            (jot.JoQty_d - COALESCE(SUM(di.Qty_d), 0)) AS balance_quantity,
            jot.MaterialDate_dd AS material_arrival,
            1 AS job_dependency,
            %s AS priority,
            0 AS reduce_operation_hours,
            NOW() AS created_at,
            NOW() AS updated_at
        FROM tbl_jo_process AS jop 
        INNER JOIN tbl_jo_txn AS jot ON jot.TxnId_i = jop.TxnId_i 
        LEFT JOIN tbl_daily_item AS di ON di.JoId_i = jop.TxnId_i 
              AND di.ProcessrowId_i = jop.RowId_i 
              AND di.CreateDate_dt >= DATE_SUB(CURDATE(), INTERVAL 30 DAY)
        LEFT JOIN tbl_machine AS tm ON (
              tm.machine_id_v = jop.Machine_v
              OR tm.MachineId_i = jop.Machine_v
              OR tm.MachineName_v = jop.Machine_v
        )
        WHERE jot.Void_c != 1 
              AND jot.DocStatus_c NOT IN ('CP', 'CX') 
              AND jop.QtyStatus_c != 'FF' 
              AND jot.TargetDate_dd > CURDATE()  -- Only jobs with target dates after today
              AND jot.TargetDate_dd <= DATE_ADD(CURDATE(), INTERVAL %s DAY)
              AND jot.CreateDate_dt >= DATE_SUB(CURDATE(), INTERVAL 100 DAY)  -- Only jobs created in last 100 days
        GROUP BY jop.TxnId_i, jop.RowId_i, jot.CreateDate_dt, jot.TargetDate_dd, 
                 jot.DocRef_v, jop.Task_v, tm.MachineName_v, jop.ManCount_i, 
                 jot.JoQty_d, jop.CapQty_d, jop.CapMin_d, jop.LeadTime_d, 
                 jop.SetupTime_d, jot.MaterialDate_dd, jop.Machine_v
        ORDER BY jot.CreateDate_dt DESC, jop.TxnId_i ASC
    """


def process_job_row(job_row: Dict[str, Any]) -> Dict[str, Any]:
    """
    Process a single job row from database results.
    
    Args:
        job_row: Raw job data from database
        
    Returns:
        Processed job dictionary
    """
    op_id = job_row.get('op_id')
    job_value = job_row.get("job")
    process_code = job_row.get("process_code")
    
    # Generate composite job_id
    if job_value and process_code:
        composite_job_id = f"{job_value}_{process_code}"
    else:
        composite_job_id = str(op_id) if op_id else f"job_{id(job_row)}"
        if not (job_value and process_code):
            logger.warning(
                f"Missing job or process_code for op_id {op_id}. "
                f"Using {composite_job_id} as job_id."
            )
    
    job = {
        "job_id": composite_job_id,
        "op_id": op_id,
        "job": job_value if job_value else composite_job_id
    }
    
    # Handle plan_date directly without epoch conversion
    if 'plan_date' in job_row and job_row['plan_date'] is not None:
        job['plan_date'] = job_row['plan_date']
    
    # Handle date field conversions
    date_fields = ['lcd_date', 'material_arrival', 'start_date']
    for date_field in date_fields:
        if date_field in job_row and job_row[date_field] is not None:
            logger.debug(
                f"Processing {date_field} for job {composite_job_id}: "
                f"raw value = {job_row[date_field]}, "
                f"type = {type(job_row[date_field])}"
            )
            
            epoch_value = convert_datetime_to_epoch(job_row[date_field])
            logger.debug(f"Converted {date_field} to epoch: {epoch_value}")
            
            if epoch_value is not None:
                job[f"{date_field}_epoch"] = epoch_value
                job[f"{date_field.upper()}_EPOCH"] = epoch_value
                
                # Create string representation for display
                try:
                    if hasattr(job_row[date_field], 'strftime'):
                        job[f"{date_field}_str"] = job_row[date_field].strftime(
                            "%Y-%m-%d %H:%M:%S"
                        )
                    else:
                        dt_obj = datetime.fromtimestamp(epoch_value)
                        job[f"{date_field}_str"] = dt_obj.strftime(
                            "%Y-%m-%d %H:%M:%S"
                        )
                except Exception as e:
                    logger.warning(
                        f"Could not create string representation "
                        f"for {date_field}: {e}"
                    )
                    job[f"{date_field}_str"] = str(job_row[date_field])
                
                # Special handling for start_date scheduler compatibility
                if date_field == 'start_date':
                    job['START_DATE_EPOCH'] = epoch_value
                    job['START_DATE _EPOCH'] = epoch_value
                    job['start_date_input_epoch'] = epoch_value
                    logger.debug(
                        f"Set START_DATE constraint for job "
                        f"{composite_job_id}: {epoch_value}"
                    )
            else:
                logger.debug(
                    f"Failed to convert {date_field} to epoch "
                    f"for job {composite_job_id}: {job_row[date_field]}"
                )
    
    # Handle machine name
    machine_name = job_row.get("machine_name", "NOT_ASSIGN") or "NOT_ASSIGN"
    
    # If no machine assignment but has LeadTime_d, assign to Subcon
    if machine_name == "NOT_ASSIGN":
        day_need = job_row.get("day_need")
        hours_need = job_row.get("hours_need")
        if (day_need and day_need > 0) or (hours_need and hours_need > 0):
            machine_name = "Subcon"
            logger.info(
                f"Job {composite_job_id} has no machine assignment but has processing time - "
                f"assigning to Subcon (day_need: {day_need}, hours_need: {hours_need})"
            )
        else:
            logger.warning(
                f"Job {composite_job_id} has no machine assignment and no processing time - "
                f"using NOT_ASSIGN (original Machine_v was NULL/empty)"
            )
    
    job["MachineName_v"] = machine_name
    job["machine_id"] = machine_name  # Scheduler expects machine_id field

    # Add other columns with proper type conversion
    numeric_int_fields = {
        "number_operator", "job_quantity", "expect_output_per_hour", 
        "priority", "accumulated_daily_output", "balance_quantity", 
        "reduce_operation_hours"
    }
    numeric_float_fields = {
        "hours_need", "setting_hours", "break_hours", "no_prod", "day_need"
    }
    
    excluded_fields = {"op_id", "job", "rsc_code"} | set(date_fields)
    
    for col, value in job_row.items():
        if col not in job and col not in excluded_fields:
            col_lower = col.lower()
            
            if value is not None:
                if col_lower in numeric_int_fields:
                    try:
                        job[col_lower] = int(value)
                    except (ValueError, TypeError):
                        default_fields = {
                            "job_quantity", "accumulated_daily_output", 
                            "balance_quantity", "reduce_operation_hours"
                        }
                        default_val = 0 if col_lower in default_fields else value
                        job[col_lower] = default_val
                elif col_lower in numeric_float_fields:
                    try:
                        job[col_lower] = float(value)
                    except (ValueError, TypeError):
                        job[col_lower] = 0.0
                else:
                    job[col_lower] = value

    # Calculate derived fields with error handling
    expect_output = job.get("expect_output_per_hour", 0)
    job_quantity = job.get("job_quantity")
    
    if expect_output and expect_output > 0 and job_quantity:
        if not job.get("hours_need"):
            try:
                job["hours_need"] = round(job_quantity / expect_output, 1)
            except ZeroDivisionError:
                logger.warning(
                    f"Division by zero prevented for job {composite_job_id}"
                )
                job["hours_need"] = 0.0

    if job_quantity is not None:
        accumulated = job.get("accumulated_daily_output", 0) or 0
        if not job.get("balance_quantity"):
            job["balance_quantity"] = job_quantity - accumulated
    
    # Map hours_need to processing_time for scheduler compatibility
    hours_need = job.get("hours_need")
    if hours_need and hours_need > 0:
        job["processing_time"] = float(hours_need) * 3600  # Convert hours to seconds
        logger.debug(f"Mapped hours_need to processing_time for job {composite_job_id}: {hours_need} hours = {job['processing_time']} seconds")
    
    return job


def extract_machines_from_jobs(jobs_list: List[Dict[str, Any]]) -> List[str]:
    """
    Extract unique machine names from jobs list.
    
    Args:
        jobs_list: List of processed job dictionaries
        
    Returns:
        List of unique machine names
    """
    machine_names = list({
        job.get("MachineName_v") for job in jobs_list 
        if job.get("MachineName_v")
    })
    
    # Count NOT_ASSIGN jobs for logging
    not_assign_jobs = [
        job for job in jobs_list 
        if job.get("MachineName_v") == "NOT_ASSIGN"
    ]
    
    if not_assign_jobs:
        logger.info(
            f"Found {len(not_assign_jobs)} jobs with NOT_ASSIGN machine - "
            f"ALL will be included and assigned to 'Subcon'"
        )
        job_examples = [
            job.get('job_id', job.get('job', 'Unknown'))[:20] 
            for job in not_assign_jobs[:5]
        ]
        logger.info(f"NOT_ASSIGN job examples: {job_examples}")
    
    # Handle machine list logic correctly
    if not machine_names:
        machine_names = ["Subcon"]
        logger.warning("No valid machines found - using Subcon as fallback")
    elif "Subcon" not in machine_names:
        machine_names.append("Subcon")
        logger.info("Added 'Subcon' machine for NOT_ASSIGN jobs")
        
    return machine_names


def generate_setup_times(machine_names: List[str]) -> Dict[str, Dict[str, float]]:
    """
    Generate setup times matrix for machines.
    
    Args:
        machine_names: List of machine names
        
    Returns:
        Dictionary mapping machine transitions to setup times
    """
    setup_times_dict = {}
    for from_machine in machine_names:
        setup_times_dict[from_machine] = {}
        for to_machine in machine_names:
            # Same machine: 0.25 hours, different machine: 0.5 hours
            setup_time = 0.25 if from_machine == to_machine else 0.5
            setup_times_dict[from_machine][to_machine] = setup_time
    
    return setup_times_dict


def load_jobs_planning_data(
    max_jobs: Optional[int] = None,
    planning_horizon_days: Optional[int] = None
) -> Tuple[List[Dict[str, Any]], List[Dict[str, str]], Dict[str, Dict[str, float]]]:
    """
    Load job data for production planning from MariaDB using joined tables.
    
    Args:
        max_jobs: Maximum number of jobs to load
        planning_horizon_days: Days ahead for planning horizon
        
    Returns:
        Tuple of (jobs_list, machines_list, setup_times_dict)
    """
    # Validate environment configuration first
    try:
        config = validate_environment_config()
    except ValueError:
        return [], [], {}
    
    # Get parameters from environment with validation
    if max_jobs is None:
        max_jobs_env = os.getenv('MAX_JOBS_LIMIT')
        if not max_jobs_env:
            logger.error(
                "❌ MISSING MAX_JOBS_LIMIT: MAX_JOBS_LIMIT not set in .env - "
                "cannot determine job loading limit"
            )
            return [], [], {}
        try:
            max_jobs = int(max_jobs_env)
        except ValueError:
            logger.error(
                f"❌ INVALID MAX_JOBS_LIMIT: Cannot convert "
                f"'{max_jobs_env}' to integer"
            )
            return [], [], {}
    
    if planning_horizon_days is None:
        horizon_env = os.getenv('PLANNING_HORIZON_DAYS')
        if not horizon_env:
            logger.error(
                "❌ MISSING PLANNING_HORIZON_DAYS: PLANNING_HORIZON_DAYS "
                "not set in .env - cannot determine planning horizon"
            )
            return [], [], {}
        try:
            planning_horizon_days = int(horizon_env)
        except ValueError:
            logger.error(
                f"❌ INVALID PLANNING_HORIZON_DAYS: Cannot convert "
                f"'{horizon_env}' to integer"
            )
            return [], [], {}
    
    logger.info(
        f"Starting to load jobs planning data from MariaDB using joined tables "
        f"(planning_horizon: {planning_horizon_days} days, excluding today's jobs, no job limit)"
    )
    
    conn = None
    jobs_list = []
    machines_list = []
    setup_times_dict = {}

    try:
        conn = get_db_connection()
        if conn is None or not conn.is_connected():
            logger.error("Cannot load data: Database connection failed.")
            return [], [], {}

        cursor = conn.cursor(dictionary=True)
        
        # Build query and parameters
        jobs_query = build_jobs_query()
        query_params = (
            NORMAL_WORKING_HOURS,
            config['break_hours'],
            config['no_prod_hours'], 
            config['job_priority'],
            planning_horizon_days
        )
        
        # Run EXPLAIN to analyze query performance
        explain_query = "EXPLAIN " + jobs_query
        cursor.execute(explain_query, query_params)
        explain_results = cursor.fetchall()
        
        logger.info("=== QUERY EXECUTION PLAN ===")
        for row in explain_results:
            logger.info(
                f"Table: {row.get('table', 'N/A')} | "
                f"Type: {row.get('type', 'N/A')} | "
                f"Rows: {row.get('rows', 'N/A')} | "
                f"Key: {row.get('key', 'None')} | "
                f"Extra: {row.get('Extra', 'N/A')}"
            )
        
        # Execute actual query with timing
        start_time = time.time()
        cursor.execute(jobs_query, query_params)
        raw_jobs = cursor.fetchall()
        query_time = time.time() - start_time
        
        logger.info(
            f"Query executed in {query_time:.3f}s - "
            f"Fetched {len(raw_jobs)} raw job records from joined tables."
        )
        
        # Process the results
        for job_row in raw_jobs:
            job = process_job_row(job_row)
            jobs_list.append(job)
        
        logger.info(f"Successfully processed {len(jobs_list)} jobs from joined tables.")

        # Extract unique machine names
        machine_names = extract_machines_from_jobs(jobs_list)
        logger.info(f"Extracted {len(machine_names)} unique machines from job data.")
        
        # Create machine list
        machines_list = [
            {"MachineName_v": name, "Description": f"Resource {name}"} 
            for name in machine_names
        ]

        # Generate setup times matrix
        setup_times_dict = generate_setup_times(machine_names)
        logger.info(f"Generated setup times matrix for {len(setup_times_dict)} machines.")
        
        logger.info(f"Final job count for scheduling: {len(jobs_list)} jobs")

    except Error as e:
        logger.error(f"Database error while loading planning data: {e}")
        return [], [], {}
    except Exception as ex:
        logger.error(f"An unexpected error occurred in load_jobs_planning_data: {ex}")
        return [], [], {}
    finally:
        if conn and conn.is_connected():
            cursor.close()
            conn.close()
            logger.info("MariaDB connection closed.")
            
    # Final validation and logging
    if not jobs_list:
        logger.warning("No jobs loaded from the database.")
    else:
        # Log summary of job types
        with_machine_jobs = [
            j for j in jobs_list 
            if j.get("MachineName_v") != "NOT_ASSIGN"
        ]
        no_machine_with_leadtime_jobs = [
            j for j in jobs_list 
            if (j.get("MachineName_v") == "NOT_ASSIGN" and 
                j.get("day_need") and j.get("day_need") > 0)
        ]
        
        logger.info(
            f"Job summary: {len(with_machine_jobs)} with assigned machines, "
            f"{len(no_machine_with_leadtime_jobs)} without machines but with LeadTime_d"
        )
        
    if not machines_list:
        logger.warning("No machines loaded from the database.")
    if not setup_times_dict:
        logger.warning("Setup times matrix is empty.")

    return jobs_list, machines_list, setup_times_dict


if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)
    test_logger = logging.getLogger(__name__)
    test_logger.info("Testing mariadb_parser.py directly")
    
    try:
        jobs, machines, setup_times = load_jobs_planning_data(
            max_jobs=1500, 
            planning_horizon_days=180
        )
        
        if jobs:
            print(f"Loaded {len(jobs)} jobs.")
            if jobs:
                first_job = jobs[0]
                print(f"First job (job_id: {first_job.get('job_id')}) details:")
                for key, value in first_job.items():
                    print(f"  {key}: {value}")
            
            print(f"\nLoaded {len(machines)} machines:")
            for m in machines:
                print(f"  {m}")

            print(f"\nLoaded setup times matrix for {len(setup_times)} machines.")
        else:
            print("No jobs loaded.") 
            
    except Exception as e:
        print(f"Error testing MariaDB data loading: {e}")