# CP-SAT Solver Implementation

## Overview
The CP-SAT (Constraint Programming - Satisfiability) solver is integrated into the AI Optimizer to handle production scheduling. It uses Google's OR-Tools CP-SAT solver to find optimal or near-optimal schedules based on various constraints.

## Key Components

### 1. Core Files
- `app/scheduling/cpsat_solver.py`: Main solver implementation
- `app/scheduling/greedy_solver.py`: Fallback greedy algorithm
- `app/api/endpoints/reporting_endpoints.py`: API endpoints
- `app/data_ingestion/mariadb_parser.py`: Data loading

### 2. Data Flow
```
Database → mariadb_parser → CP-SAT Solver → API Endpoints → Frontend
```

## API Endpoints

### 1. Gantt Chart - Priority View
- **Endpoint**: `GET /api/reports/gantt/priority-view`
- **Parameters**:
  - `solver`: `cpsat` (default) or `greedy`
- **Response**: List of tasks with priority-based coloring

### 2. Gantt Chart - Resource View
- **Endpoint**: `GET /api/reports/gantt/resource-view`
- **Parameters**:
  - `solver`: `cpsat` (default) or `greedy`
- **Response**: List of tasks grouped by resource

### 3. Detailed Schedule Table
- **Endpoint**: `GET /api/reports/detailed-schedule`
- **Parameters**:
  - `solver`: `cpsat` (default) or `greedy`
- **Response**: Detailed schedule data for tabular display

## Solver Features

### 1. CP-SAT Solver (`cpsat_solver.py`)
- Uses Google's OR-Tools CP-SAT
- Handles complex constraints:
  - Machine assignments
  - Setup times
  - Sequence constraints
  - Operator constraints
- Fallback to greedy solver if no solution found

### 2. Greedy Solver (`greedy_solver.py`)
- Fallback algorithm
- Faster but less optimal than CP-SAT
- Used when CP-SAT fails to find a solution

## Data Model

### Job Object
```python
{
    'op_id': str,           # Operation ID
    'job': str,              # Job name
    'rsc_code': str,         # Machine code
    'hours_need': float,     # Required hours
    'priority': int,         # Job priority (1-5)
    'setup_time': float,     # Setup time in hours
    'processing_time': float,# Processing time in hours
    'start_time': int,       # Start time (epoch)
    'end_time': int,        # End time (epoch)
    # ... additional fields
}
```

## Error Handling
- Returns empty list if no data available
- Falls back to greedy solver if CP-SAT fails
- Detailed error logging for debugging

## Performance
- CP-SAT time limit: 300 seconds (5 minutes)
- Handles up to several thousand jobs
- Memory efficient implementation

## Dependencies
- Python 3.8+
- ortools
- FastAPI
- pandas
- mysql-connector-python

## Development Notes
- Always test with both solvers
- Monitor memory usage with large datasets
- Check logs for solver status and warnings