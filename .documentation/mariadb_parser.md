# MariaDB Parser Documentation

## Configuration Variables
```python
DB_HOST = os.getenv("MARIADB_HOST")
DB_USER = os.getenv("MARIADB_USERNAME")
DB_PASSWORD = os.getenv("MARIADB_PASSWORD")
DB_NAME = os.getenv("MARIADB_DATABASE")
DB_PORT = os.getenv("MARIADB_PORT", "3306")
```

## Main Functions

### 1. `get_db_connection()`
- **Purpose**: Establishes connection to MariaDB
- **Returns**: MySQL connector connection object
- **Key Variables**:
  - `connection`: Database connection object

### 2. `convert_datetime_to_epoch(dt_value)`
- **Purpose**: Converts datetime to epoch timestamp (Singapore timezone)
- **Parameters**:
  - `dt_value`: Datetime value from database
- **Returns**: Unix timestamp in seconds (or None for invalid dates)
- **Handles**:
  - Multiple datetime formats
  - Timezone conversion to Singapore
  - Invalid/None dates

### 3. `load_jobs_planning_data()`
- **Purpose**: Load and process job data for scheduling
- **Returns**: Tuple of (jobs_list, machines_list, setup_times_dict)
- **Key Variables**:
  - `jobs_list`: List of job dictionaries
  - `machines_list`: List of machine dictionaries
  - `setup_times_dict`: Machine transition setup times

## Data Processing Logic

### Job Data Loading
1. Fetches all columns from `tbl_aa_job`
2. For each job:
   - Uses `op_id` as primary key
   - Processes date fields (epoch + string formats)
   - Converts numeric fields
   - Calculates derived fields

### Machine Processing
1. Extracts unique machines from `rsc_code`
2. Creates machine entries with:
   - `MachineName_v`: Machine code
   - `Description`: "Resource {code}"

### Setup Times Matrix
- **Same Machine**: 0.25 hours (15 min)
- **Different Machines**: 0.5 hours (30 min)

## Field Handling

### Special Fields
- **rsc_code**: Used for machine assignment
- **Date Fields** (converted to both formats):
  - lcd_date
  - material_arrival
  - start_date

### Excluded Fields
- created_at
- updated_at

## Error Handling
- Graceful database connection handling
- Logs warnings for missing/invalid data
- Returns empty collections on failure

## Main Execution
When run directly:
1. Loads job data
2. Displays first job details
3. Lists all machines
4. Includes error handling and logging

## Dependencies
- mysql-connector-python
- python-dotenv
- pytz
- pandas
- datetime