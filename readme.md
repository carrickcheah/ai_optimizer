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




