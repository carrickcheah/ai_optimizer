###############################################
# mariadb_parser.py - FIXED VERSION
# Functions for loading job data from MariaDB
###############################################

import pandas as pd
import numpy as np
import logging
import os
from datetime import datetime, date, time
import pytz
from dotenv import load_dotenv
import mysql.connector
from mysql.connector import Error

# Load environment variables from .env file at project root
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), '../../../../.env'))

# Get database configuration from environment variables
DB_HOST = os.getenv("MARIADB_HOST")
DB_USER = os.getenv("MARIADB_USERNAME")
DB_PASSWORD = os.getenv("MARIADB_PASSWORD")
DB_NAME = os.getenv("MARIADB_DATABASE")
DB_PORT = os.getenv("MARIADB_PORT", "3306")

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def get_db_connection():
    """
    Establish a connection to the MariaDB database.
        
    Returns:
        connection: MySQL connector connection object
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

def convert_datetime_to_epoch(dt_value):
    """
    Convert a datetime value to epoch timestamp in Singapore timezone.
    Handles MariaDB datetime format: 2025-07-30 17:00:00.000
    
    Args:
        dt_value: Datetime value from database
        
    Returns:
        int: Unix timestamp (epoch) in seconds
    """
    if pd.isna(dt_value) or dt_value is None:
        return None

    if isinstance(dt_value, str):
        try:
            dt_value = pd.to_datetime(dt_value)
        except Exception as e:
            logger.error(f"Error converting string to datetime object: {dt_value} - {e}")
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
        # Convert date to datetime at midnight
        dt_value = datetime.combine(dt_value, time.min)
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
        
def load_jobs_planning_data(max_jobs: int = 1000, buffer_days: int = 7, planning_horizon_days: int = 60):
    """
    Load job data for production planning from MariaDB using joined tables.
    
    Args:
        max_jobs: Maximum number of jobs to load (default: 1000)
        buffer_days: Days before today for late jobs (default: 7)
        planning_horizon_days: Days ahead for planning horizon (default: 60)
        
    Returns:
        Tuple of (jobs_list, machines_list, setup_times_dict) where:
            jobs_list (list): List of job dictionaries.
            machines_list (list): List of available machine dictionaries.
            setup_times_dict (dict): Dictionary mapping machine transitions to setup times.
    """
    logger.info(f"Starting to load jobs planning data from MariaDB using joined tables (max_jobs: {max_jobs})")
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

        # New complex SQL query joining three tables
        jobs_query = """
        SELECT
            jot.CreateDate_dt AS plan_date,
            jot.TargetDate_dd AS lcd_date,
            jop.TxnId_i AS op_id,
            jot.DocRef_v AS job,
            jop.Task_v AS process_code,
            '' AS rsc_location,
            jop.Machine_v AS rsc_code,
            jop.ManCount_i AS number_operator,
            jot.JoQty_d AS job_quantity,
            CASE WHEN jop.CapMin_d = 1 AND jop.CapQty_d != 0 
                 THEN jop.CapQty_d * 60 
                 ELSE NULL END AS expect_output_per_hour,
            CASE WHEN jop.CapMin_d = 1 AND jop.CapQty_d != 0 
                 THEN jot.JoQty_d / (jop.CapQty_d * 60) 
                 ELSE NULL END AS hours_need,
            CASE WHEN jop.CapMin_d = 1 AND jop.CapQty_d != 0 
                 THEN jot.JoQty_d / (jop.CapQty_d * 60 * 24)
                 WHEN jop.CapMin_d = 0 AND jop.LeadTime_d != 0 
                 THEN jop.LeadTime_d 
                 ELSE NULL END AS day_need,
            jop.SetupTime_d AS setting_hours,
            1 AS break_hours,
            8 AS no_prod,
            '' AS start_date,
            di.Qty_d AS accumulated_daily_output,
            (jot.JoQty_d - COALESCE(di.Qty_d, 0)) AS balance_quantity,
            jot.MaterialDate_dd AS material_arrival,
            1 AS job_dependency,
            3 AS priority,
            0 AS reduce_operation_hours,
            NOW() AS created_at,
            NOW() AS updated_at
        FROM tbl_jo_process AS jop 
        INNER JOIN tbl_jo_txn AS jot ON jot.TxnId_i = jop.TxnId_i 
        LEFT JOIN tbl_daily_item AS di ON di.JoId_i = jop.TxnId_i AND di.ProcessrowId_i = jop.RowId_i
        WHERE jot.Void_c != 1 
            AND jot.DocStatus_c != 'CP' 
            AND jop.QtyStatus_c != 'FF' 
            AND jot.CreateDate_dt BETWEEN DATE_SUB(CURDATE(), INTERVAL %s DAY) AND DATE_ADD(CURDATE(), INTERVAL %s DAY)
        ORDER BY jot.CreateDate_dt DESC, jop.TxnId_i ASC
        LIMIT %s
        """
        
        # Run EXPLAIN to analyze query performance
        explain_query = "EXPLAIN " + jobs_query
        cursor.execute(explain_query, (buffer_days, planning_horizon_days, max_jobs))
        explain_results = cursor.fetchall()
        
        logger.info("=== QUERY EXECUTION PLAN ===")
        for row in explain_results:
            logger.info(f"Table: {row.get('table', 'N/A')} | Type: {row.get('type', 'N/A')} | "
                       f"Rows: {row.get('rows', 'N/A')} | Key: {row.get('key', 'None')} | "
                       f"Extra: {row.get('Extra', 'N/A')}")
        
        # Execute actual query with timing
        import time
        start_time = time.time()
        cursor.execute(jobs_query, (buffer_days, planning_horizon_days, max_jobs))
        raw_jobs = cursor.fetchall()
        query_time = time.time() - start_time
        
        logger.info(f"Query executed in {query_time:.3f}s - Fetched {len(raw_jobs)} raw job records from joined tables (requested max: {max_jobs}).")
        
        # Process the results
        date_fields = ['lcd_date', 'material_arrival', 'start_date']

        for job_row in raw_jobs:
            op_id = job_row.get('op_id')
            job_value = job_row.get("job")
            process_code = job_row.get("process_code")
            
            # Generate composite job_id
            if job_value and process_code:
                composite_job_id = f"{job_value}_{process_code}"
            else:
                composite_job_id = str(op_id) if op_id else f"job_{len(jobs_list) + 1}"
                if not (job_value and process_code):
                    logger.warning(f"Missing job or process_code for op_id {op_id}. Using {composite_job_id} as job_id.")
            
            job = {
                "job_id": composite_job_id,
                "op_id": op_id,
                "job": job_value if job_value else composite_job_id
            }
            
            # Handle plan_date directly without epoch conversion
            if 'plan_date' in job_row and job_row['plan_date'] is not None:
                job['plan_date'] = job_row['plan_date']  # Store raw datetime value
            
            # Handle date field conversions
            for date_field in date_fields:
                if date_field in job_row and job_row[date_field] is not None:
                    # Debug: Log the raw value from database (reduced verbosity)
                    logger.debug(f"Processing {date_field} for job {composite_job_id}: raw value = {job_row[date_field]}, type = {type(job_row[date_field])}")
                    
                    epoch_value = convert_datetime_to_epoch(job_row[date_field])
                    logger.debug(f"Converted {date_field} to epoch: {epoch_value}")
                    
                    if epoch_value is not None:
                        job[f"{date_field}_epoch"] = epoch_value
                        job[f"{date_field.upper()}_EPOCH"] = epoch_value  # For backward compatibility
                        
                        # Always create the string representation for display
                        try:
                            if hasattr(job_row[date_field], 'strftime'):
                                # It's already a datetime object
                                job[f"{date_field}_str"] = job_row[date_field].strftime("%Y-%m-%d %H:%M:%S")
                            else:
                                # Convert from epoch to formatted string
                                dt_obj = datetime.fromtimestamp(epoch_value)
                                job[f"{date_field}_str"] = dt_obj.strftime("%Y-%m-%d %H:%M:%S")
                        except Exception as e:
                            logger.warning(f"Could not create string representation for {date_field}: {e}")
                            # Fallback: use the original value as string
                            job[f"{date_field}_str"] = str(job_row[date_field])
                        
                        # Special handling for start_date to ensure scheduler compatibility
                        if date_field == 'start_date':
                            job['START_DATE_EPOCH'] = epoch_value
                            job['START_DATE _EPOCH'] = epoch_value  # Handle space variant
                            job['start_date_input_epoch'] = epoch_value
                            logger.debug(f"Set START_DATE constraint for job {composite_job_id}: {epoch_value}")
                    else:
                        logger.debug(f"Failed to convert {date_field} to epoch for job {composite_job_id}: {job_row[date_field]}")  # Reduced from WARNING to DEBUG for empty values
            
            # Handle resource code
            job["rsc_code"] = job_row.get("rsc_code", "DEFAULT") or "DEFAULT"

            # Add other columns with proper type conversion
            numeric_int_fields = {"number_operator", "job_quantity", "expect_output_per_hour", 
                                "priority", "accumulated_daily_output", "balance_quantity", "reduce_operation_hours"}
            numeric_float_fields = {"hours_need", "setting_hours", "break_hours", "no_prod", "day_need"}
            
            for col, value in job_row.items():
                if col not in job and col not in ["op_id", "job", "rsc_code"] + date_fields:
                    col_lower = col.lower()
                    
                    if value is not None:
                        if col_lower in numeric_int_fields:
                            try:
                                job[col_lower] = int(value)
                            except (ValueError, TypeError):
                                default_val = 0 if col_lower in {"job_quantity", "accumulated_daily_output", "balance_quantity", "reduce_operation_hours"} else value
                                job[col_lower] = default_val
                        elif col_lower in numeric_float_fields:
                            try:
                                job[col_lower] = float(value)
                            except (ValueError, TypeError):
                                job[col_lower] = 0.0
                        else:
                            job[col_lower] = value

            # Calculate derived fields if needed
            if job.get("expect_output_per_hour", 0) and job.get("expect_output_per_hour") > 0 and job.get("job_quantity"):
                if not job.get("hours_need"):
                    job["hours_need"] = round(job["job_quantity"] / job["expect_output_per_hour"], 1)

            if job.get("job_quantity") is not None:
                accumulated = job.get("accumulated_daily_output", 0) or 0
                if not job.get("balance_quantity"):
                    job["balance_quantity"] = job["job_quantity"] - accumulated
            
            jobs_list.append(job)
        
        logger.info(f"Successfully processed {len(jobs_list)} jobs from joined tables.")

        # Extract unique machine codes
        machine_codes = list(set(
            job.get("rsc_code") for job in jobs_list 
            if job.get("rsc_code") and job.get("rsc_code") != "DEFAULT"
        ))
        
        if not machine_codes:
            machine_codes = ["DEFAULT"]
            
        logger.info(f"Extracted {len(machine_codes)} unique machines from job data.")
        
        # Create machine list
        machines_list = [
            {"MachineName_v": code, "Description": f"Resource {code}"} 
            for code in machine_codes
        ]

        # Generate setup times using consistent machine identifiers
        setup_times_dict = {}
        for from_machine in machine_codes:
            setup_times_dict[from_machine] = {}
            for to_machine in machine_codes:
                setup_times_dict[from_machine][to_machine] = 0.25 if from_machine == to_machine else 0.5

        logger.info(f"Generated setup times matrix for {len(setup_times_dict)} machines.")

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
            
    # Final validation
    if not jobs_list:
        logger.warning("No jobs loaded from the database.")
    if not machines_list:
        logger.warning("No machines loaded from the database.")
    if not setup_times_dict:
        logger.warning("Setup times matrix is empty.")

    return jobs_list, machines_list, setup_times_dict

if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)
    logger = logging.getLogger(__name__)
    logger.info("Testing mariadb_parser.py directly")
    
    try:
        jobs, machines, setup_times = load_jobs_planning_data(max_jobs=1000, buffer_days=7, planning_horizon_days=60)
        
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