## Application Bootstrap






### Elements

    1.Single Responsibility Principle:
        main.py has one job: start the application
        This makes the codebase more maintainable and easier to reason about

    2.Separation of Concerns:
        Configuration (environment, logging, middleware)
        Application setup (FastAPI instance, routers)
        Business logic (in separate modules)
        API endpoints (in router files)

    3.Testing:
        Easier to test when components are decoupled
        Can create test clients without starting the full application
        Can mock components independently

    4.Scalability:
        As your application grows, you can add more routers and components without cluttering the entry point
        Teams can work on different parts of the application simultaneously

### Knowledge Base

    1. What Belongs in main.py:
        Minimal Configuration:
            Environment variable loading
            Logging setup
            Database connection setup (or import from config)

    2. Application Initialization:
            FastAPI/FastAPI app instance
            Include routers
            Add middleware
            Add exception handlers
       
    3.Server Startup (in if __name__ == "__main__": block)

        What Should NOT Be in main.py:
        Business logic
        Database models
        API route handlers
        Complex configuration
        Utility functions

### AI Optimizer Logic Overview

    Here's how the AI Optimizer works:

    Core Functionality
    The AI Optimizer is a production scheduling system that helps optimize job scheduling across machines with the following key features:

    1. Multiple Solver Support:

    - CP-SAT Solver: Uses Google's CP-SAT constraint programming solver for optimal scheduling

    - Greedy Solver: A faster but potentially less optimal heuristic-based scheduler.

    2. Key Components:

        - Job Management:
        Tracks jobs with properties like priority, processing time, setup time, and dependencies
        Handles job sequences and dependencies between processes

        - Resource Allocation:
        Allocates jobs to machines based on resource constraints
        Manages operator availability and machine capabilities

        - Time Management:
        Handles due dates (LCD - Latest Completion Date)
        Manages material arrival times
        Calculates buffer times between job completion and deadlines

    3. Optimization Features:
        - Urgent Job Handling:
        Reduces non-productive time (setup, breaks) for late jobs
        Can reduce non-productive time by 50% or 100% for critical jobs

        - Buffer Management:
        Calculates buffer time between job completion and deadline
        Categorizes jobs based on buffer status (Late, Critical, Warning, Caution, OK)

        - Scheduling Constraints:
        Enforces sequence dependencies between jobs
        Respects machine capabilities and availability
        Handles operator constraints

        - Visualization:
        Provides Gantt chart views:
        Priority View: Jobs colored by priority level
        Resource View: Grouped by machine/resource


### API Endpoints

    The system exposes several API endpoints:

    Production Jobs Management:
        GET /api/production-jobs/: List all jobs
        GET /api/production-jobs/{id}: Get job details
        POST /api/production-jobs/: Create new job
        PUT /api/production-jobs/{id}: Update job

    Reporting:
        GET /api/charts/gantt-priority-view: Get Gantt chart data (priority view)
        GET /api/charts/gantt-resource-view: Get Gantt chart data (resource view)
        GET /api/reports/detailed-schedule-table: Get detailed schedule data

    System:
        GET /api/health: Health check
        GET /api/machines: List available machines



### Data Flow

    1. Data Ingestion:
        Pulls job data from MariaDB database
        Processes and enriches job information

    2. Scheduling:
        Applies optimization algorithms (CP-SAT or Greedy)
        Handles constraints and dependencies
        Applies urgent job handling if needed

    3. Output:
        Generates optimized schedules
        Provides data for visualization
        Calculates performance metrics

    The system is designed to help production planners optimize their schedules, reduce delays, and better utilize resources.



### Job Number Generation Logic

    1. Database Table Structure:
        The system uses joined tables (`tbl_jo_process`, `tbl_jo_txn`, `tbl_daily_item`) in MariaDB to provide job information with calculated fields and real-time production data.

    2. Auto-incrementing Primary Key:
    The op_id is an auto-incrementing integer field in the database.
    When a new job is inserted, the database automatically generates the next available op_id.

    3. Job Creation Process:
        When a new job is created via the /production-jobs/ POST endpoint:
            The system establishes a database connection.
            It executes an INSERT query without specifying op_id.
            After insertion, it retrieves the generated ID using cursor.lastrowid.
            This ID is returned to the client as the unique job number.

    4. Key Code Snippet:        
        cursor.execute(query, data)
        conn.commit()
        new_job_id = cursor.lastrowid  # This gets the auto-generated op_id

    5. Uniqueness Guarantee:
        The database ensures each op_id is unique.
        The auto-increment feature prevents duplicates.


    6. Job Retrieval:
        Jobs can be retrieved using their op_id via the /production-jobs/{job_id} GET endpoint.
        The system returns job details including the auto-generated op_id.


    7. Job Updates:
        Existing jobs can be updated using their op_id via the /production-jobs/{job_id} PUT endpoint.
        The op_id remains constant throughout the job's lifecycle.

    
    This approach is reliable and follows standard database practices for generating unique identifiers, ensuring each job has a distinct identifier throughout the system.



## Or-tools logic

    1. Create a Dedicated Scheduling Module

    app/
    ├── scheduling/
    │   ├── __init__.py
    │   ├── models.py          # Pydantic models for input/output
    │   ├── ortools_solver.py  # Your OR-Tools implementation
    │   └── service.py         # Business logic/service layer


    2. Implementation Example. app/scheduling/ortools_solver.py


        from ortools.sat.python import cp_model

        def solve_scheduling_problem(jobs, machines, setup_times):
            """OR-Tools CP-SAT solver implementation."""
            model = cp_model.CpModel()
            
            # Your OR-Tools implementation here
            # ...
            
            return {
                "schedule": optimized_schedule,
                "status": solver.StatusName(solver.StatusValue(status)),
                "objective": solver.ObjectiveValue() if has_objective else None
            }

### Before pass to or-tools
        
    Data Loading (mariadb_parser.py):
        - Changed the job data structure to use "op_id" as the key identifier
        - Updated logging and debug output

    Time Utilities (time_utils.py):
        - Updated all logging references to use "op_id" instead of "unique_job_id"
        - Changed function parameters and variable references

    Scheduling Logic:
        - Updated greedy_solver.py, cpsat_solver.py, and setup_buffer.py
        - Changed all function signatures and references to use "op_id"
        - Updated extraction functions for job family and process numbers

    Reporting:
        - Updated chart_generator.py to use "op_id" in all data processing
        - Changed reporting_endpoints.py to reference the new field name
    
    Utilities and Debugging:
        - Updated check_job_data.py to look for "op_id"
        - Fixed urgent_handling.py logging to use the new field name
        




























