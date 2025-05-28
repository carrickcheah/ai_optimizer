###############################################
# mariadb_parser.py - FIXED VERSION
# Functions for loading job data from MariaDB
###############################################

import pandas as pd
import numpy as np
import logging
import os
from datetime import datetime
import pytz
from dotenv import load_dotenv
import mysql.connector
from mysql.connector import Error

# Load environment variables from .env file
load_dotenv()

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
        logger.error(f"Error converting datetime to epoch: {e} for value {dt_value}")
        return None
        
def load_jobs_planning_data():
    """
    Load job data for production planning from MariaDB.
        
    Returns:
        Tuple of (jobs_list, machines_list, setup_times_dict) where:
            jobs_list (list): List of job dictionaries.
            machines_list (list): List of available machine dictionaries.
            setup_times_dict (dict): Dictionary mapping machine transitions to setup times.
    """
    logger.info("Starting to load jobs planning data from MariaDB")
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

        # Get existing columns
        columns_query = "SHOW COLUMNS FROM tbl_aa_job"
        cursor.execute(columns_query)
        existing_columns = [column['Field'] for column in cursor.fetchall()]
        logger.info(f"Found {len(existing_columns)} columns in tbl_aa_job table")

        # FIX: Create case-insensitive column lookup once
        columns_lower = {col.lower(): col for col in existing_columns}
        
        jobs_query = "SELECT * FROM tbl_aa_job"
        cursor.execute(jobs_query)
        raw_jobs = cursor.fetchall()
        logger.info(f"Fetched {len(raw_jobs)} raw job records from database.")

        # Validate required fields
        id_field = 'op_id'
        if id_field not in existing_columns:
            raise ValueError(f"Required column '{id_field}' not found in tbl_aa_job table")
        
        # FIX: Use the case-insensitive lookup
        has_rsc_code = 'rsc_code' in columns_lower
        has_job_field = 'job' in columns_lower
        has_process_code = 'process_code' in columns_lower
        
        # Log all columns for debugging
        logger.info(f"Available columns: {existing_columns}")
        
        date_fields = ['lcd_date', 'material_arrival', 'start_date']

        for job_row in raw_jobs:
            op_id = job_row.get(id_field)
            job_value = job_row.get("job") if has_job_field else None
            process_code = job_row.get("process_code") if has_process_code else None
            
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
            
            # FIX: Simplified date field handling - avoid redundant storage
            for date_field in date_fields:
                if date_field in job_row and job_row[date_field] is not None:
                    epoch_value = convert_datetime_to_epoch(job_row[date_field])
                    if epoch_value is not None:
                        job[f"{date_field}_epoch"] = epoch_value
                        job[f"{date_field.upper()}_EPOCH"] = epoch_value  # For backward compatibility
                        
                        # Store formatted string for display purposes only
                        if hasattr(job_row[date_field], 'strftime'):
                            job[f"{date_field}_str"] = job_row[date_field].strftime("%Y-%m-%d %H:%M:%S")
                        # DO NOT store the original datetime object to avoid 2025 date confusion
                        
                        # Special handling for start_date to ensure scheduler compatibility
                        if date_field == 'start_date':
                            # Create all possible variants that the scheduler might look for
                            job['START_DATE_EPOCH'] = epoch_value
                            job['START_DATE _EPOCH'] = epoch_value  # Handle space variant
                            job['start_date_input_epoch'] = epoch_value
                            logger.debug(f"Set START_DATE constraint for job {composite_job_id}: {epoch_value}")
            
            # Handle resource code
            job["rsc_code"] = job_row.get("rsc_code", "DEFAULT") if has_rsc_code else "DEFAULT"

            # Add other columns with proper type conversion
            numeric_int_fields = {"number_operator", "job_quantity", "expect_output_per_hour", 
                                "priority", "accumulated_daily_output", "balance_quantity", "reduce_operation_hours"}
            numeric_float_fields = {"hours_need", "setting_hours", "break_hours", "no_prod", "bal_hr"}
            
            for col in existing_columns:
                if col not in job and col not in [id_field, "job", "rsc_code"] + date_fields:
                    value = job_row.get(col)
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

            # Calculate derived fields
            if job.get("expect_output_per_hour", 0) > 0 and job.get("job_quantity"):
                job["hours_need"] = round(job["job_quantity"] / job["expect_output_per_hour"], 1)

            if job.get("job_quantity") is not None:
                accumulated = job.get("accumulated_daily_output", 0) or 0
                job["balance_quantity"] = job["job_quantity"] - accumulated
            
            jobs_list.append(job)
        
        logger.info(f"Successfully processed {len(jobs_list)} jobs from database.")

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

        # FIX: Generate setup times using consistent machine identifiers
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
        jobs, machines, setup_times = load_jobs_planning_data()
        
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