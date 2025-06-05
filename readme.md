## Project Architecture Overview
    services/ai_optimizer/
    ├── frontend/                    # React/TypeScript frontend
    │   ├── src/
    │   │   ├── components/         # UI components (Gantt charts, tables, forms)
    │   │   ├── App.tsx            # Main React app
    │   │   └── config.ts          # Frontend configuration
    │   ├── package.json           # npm dependencies (React, Vite, TailwindCSS)
    │   ├── vite.config.js         # Vite build configuration
    │   └── tailwind.config.js     # TailwindCSS styling
    │
    ├── backend/                     # Python FastAPI backend
    │   ├── app/
    │   │   ├── main.py            # FastAPI application entry point
    │   │   ├── api/               # REST API endpoints
    │   │   │   └── endpoints/     # Route handlers
    │   │   ├── core/              # Core application logic
    │   │   ├── scheduling/        # Optimization algorithms
    │   │   │   ├── cpsat_solver.py      # Google OR-Tools CP-SAT solver
    │   │   │   ├── greedy_solver.py     # Greedy scheduling algorithm
    │   │   │   ├── setup_buffer.py      # Setup time calculations
    │   │   │   └── urgent_handling.py   # Priority job handling
    │   │   ├── data_ingestion/    # Database connectors
    │   │   │   └── mariadb_parser.py    # MariaDB data loader
    │   │   ├── reporting/         # Report generation
    │   │   └── utils/             # Utility functions
    │   └── Makefile              # Development commands
    │
    ├── documentation/              # Project documentation
    ├── pyproject.toml             # Python dependencies (uv managed)
    ├── package.json              # Root stylelint config
    └── run_dev.sh               # Development bootstrap script




## Technology Stack

    Backend:
    FastAPI - REST API framework
    Google OR-Tools - Optimization engine (CP-SAT solver)
    MySQL Connector - MariaDB database integration
    pandas/numpy - Data processing
    uvicorn - ASGI server
    Frontend:
    React 19 - UI framework
    TypeScript - Type safety
    Vite - Build tool
    TailwindCSS - Styling
    Plotly.js - Data visualization (Gantt charts)
    React Router - Navigation





## Core Application Flow

    Data Pipeline:
    MariaDB ingestion → mariadb_parser.py extracts job data
    Data transformation → Converts to optimization format
    Scheduling algorithms → CP-SAT/Greedy solvers optimize
    API endpoints → Serve optimized schedules
    Frontend visualization → Gantt charts & tables

    Optimization Engine:
    CP-SAT Solver → Google OR-Tools constraint programming
    Greedy Solver → Fast heuristic for large datasets
    Setup buffer management → Machine changeover times
    Priority handling → Urgent job scheduling

    Key API Endpoints:
    /api/production-jobs/ → Job management & optimization
    /api/reports/ → Schedule reporting & analytics
    / → Health check endpoint







Problems in the three files:

  cpsat_solver.py:

  - Line 50: time_limit_seconds: int = 120 - Hardcoded solver timeout
  - Line 52: max_jobs_limit: int = 1000 - Hardcoded job processing limit
  - Line 53: planning_horizon_days: int = 60 - Hardcoded planning horizon
  - Line 310: return max(horizon, 24*7) - Hardcoded minimum horizon (1 week)
  - Line 330: setup_times_dict[from_machine][to_machine] = 0.25 if from_machine == to_machine else 0.5 - Hardcoded
   setup times
  - Line 635: grace_period_hours = 24 - Hardcoded grace period for late jobs
  - Line 706: solver.parameters.num_search_workers = min(os.cpu_count() or 4, 8) - Hardcoded max workers limit

  fastapi_app.py:

  - Lines 45-46: host: os.getenv("MARIADB_HOST", "localhost"), port: int(os.getenv("MARIADB_PORT", "3306")) -
  Hardcoded database fallbacks
  - Lines 62-64: pool_name="ai_optimizer_pool", pool_size=10, pool_reset_session=True - Hardcoded connection pool
  settings
  - Lines 125-133: Multiple hardcoded default values in ProductionJobData model (number_operator=1, priority=3,
  etc.)
  - Lines 299-302: Hardcoded fallback machine data when no machines found in database
  - Line 290: INTERVAL 30 DAY - Hardcoded date range in SQL query

  mariadb_parser.py:

  - Line 17: dotenv_path=os.path.join(os.path.dirname(__file__), '../../../../.env') - Hardcoded relative path to
  .env file
  - Line 24: DB_PORT = os.getenv("MARIADB_PORT", "3306") - Hardcoded default port
  - Line 330: 0.25 if from_machine == to_machine else 0.5 - Hardcoded setup times in algorithm
  - Line 180: INTERVAL %s DAY placeholders but hardcoded SQL structure
  - Lines 162-164: Hardcoded default values (1 AS break_hours, 8 AS no_prod, 3 AS priority)

  Main risks for real data integration:
  - Fixed timeouts may not suit production workloads
  - Database fallbacks could connect to wrong environment
  - Business logic parameters hardcoded instead of configurable
  - Static machine data overrides real database content
  - Algorithm parameters can't be tuned for different scenarios
