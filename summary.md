### AI Optimizer: Backend and Frontend System Summary

#### What it is
End-to-end production scheduling and reporting system:
- **Backend**: FastAPI service that loads jobs from MariaDB, generates schedules (greedy solver with chain/OT logic), exposes reporting endpoints, and streams AI reports via an LLM adapter.
- **Frontend**: React + Router app with auth and a data cache that renders Gantt charts, a detailed schedule table, and an AI-generated report (SSE).

### Backend architecture (FastAPI)
- Entry: `backend/main.py`
  - Loads `.env`, validates config via `AppConfig`, initializes CORS.
  - Validates DB availability and `ProductionReportGenerator` on boot.
  - Mounts routers under `/api`.
- Routers:
  - `app/api/fastapi_app.py`: shared router primitives, MySQL pool (`pooling.MySQLConnectionPool`), Pydantic models, `get_db_connection_from_pool()`.
  - `app/api/endpoints/production_jobs_endpoints.py` (prefix `/api/production-jobs`):
    - GET `/` → strict-validated list of jobs via `load_jobs_planning_data` with limit/offset/priority filters.
    - GET `/production-schedule` → paginated schedule-style table (sorting/search) powered by same data source.
    - GET `/{job_id}` → fetch single job by `op_id`-mapped id.
    - All write endpoints disabled (501) — read-only API.
    - Strict `.env` requirements: `MAX_JOBS_LIMIT`, `PLANNING_HORIZON_DAYS`, `MAX_PLANNING_HORIZON_DAYS`.
  - `app/api/endpoints/reporting_endpoints.py` (prefix `/api/reports`):
    - GET `/gantt/priority-view` and `/gantt/resource-view` → transforms schedule+jobs to Gantt datasets.
    - GET `/detailed-schedule` → detailed table ready for frontend.
    - GET `/schedule-overview` → span, hours, buffer-status counts.
    - GET `/data-quality-analysis` → flags unrealistic/negative/missing buffer data and scores quality.
    - GET `/late-jobs-analysis` → plan-date lateness analysis.
  - `app/api/endpoints/ai_report_endpoints.py` (prefix `/api/reports`):
    - POST `/ai-report` → non-streaming LLM report with cached frontend data as input.
    - POST `/ai-report-stream` → SSE streaming LLM report (DeepSeek-like API), incremental chunks back to UI.
  - `app/api/endpoints/logs_endpoints.py` (prefix `/api/logs`):
    - GET `/recent` → tail and parse `app.log` with simple split parsing.

### Data ingestion (MariaDB)
- `app/data_ingestion/mariadb_parser.py`:
  - Reads DB creds from `.env` (`MARIADB_*`), validates `NORMAL_WORKING_HOURS`.
  - Query constraints (joined tables):
    - Not voided/cancelled; due date > today and <= horizon days; created in last 100 days; material already arrived.
  - Returns `(jobs_list, machines_list, setup_times_dict)`:
    - Jobs: normalized ids (`job_id` composite), epoch conversions, defaults, derived `processing_time` (hours_need → seconds).
    - Machines: deduped from jobs; ensures `'Subcon'` when needed.
    - Setup times: symmetric 0.25h same-machine, 0.5h cross-machine.

### Scheduling core
- Orchestrator: `app/reporting/schedule_orchestrator.py`
  - Loads data via `load_jobs_planning_data(max_jobs, planning_horizon_days)`.
  - Runs `greedy_solver.greedy_schedule()`, validates + normalizes schedule tuples `(job_id, start, end, [priority, meta])`.
  - Exposed via `get_schedule_and_job_data(solver='greedy')` used by reporting endpoints.
- Greedy solver: `app/scheduling/greedy_solver.py`
  - Strict env config (working hours/OT, search horizons, buffers, setup times; some are hardcoded).
  - Preemptive scheduling: calculates end time minute-by-minute wrt working-hour availability (via `time_availability` if present), so tasks pause during breaks and resume.
  - Prioritization:
    - LCD-based urgency with boosts for jobs late vs plan date; chain completion urgency (from `chain_analyzer`); buffer-status weighting.
  - Chain/dependency handling:
    - `dependency_manager` derives sequences from DB table `ai_job_sequences` if present, otherwise infers from job ids.
    - Families grouped and scheduled honoring sequence; ultra-critical chain jobs may preempt machine queues.
  - Special handling: `NOT_ASSIGN` → schedule on pseudo machine `Subcon` bucket; true `SUBCONTRACTOR` jobs timed but not machine-competing.
- Utilities:
  - `scheduler_utils.py`: extraction/parsing, normalization, batch validators, schedule metrics, CP-SAT → greedy format converter.
  - `priority_calculator.py`: composable priority score; `chain_analyzer.py`: family urgency + required start time logic.

### Reporting and chart generation
- `app/reporting/chart_generator.py`:
  - Validates inputs; buffer thresholds fixed (Critical 8h, Warning 24h, Caution 72h).
  - Generates two Gantt datasets:
    - Priority view: color by buffer status; `SUBCONTRACTOR` shown gray with special label.
    - Resource view: machine-name mapping via DB lookup for readability.
  - Detailed schedule table builder: strict timestamp formatting, buffer computation, sortable by LCD.
- `app/reporting/production_report_generator.py`:
  - Creates summary, efficiency, constraints reports; uses consistent buffer thresholds and utilization cutoffs.
- `app/reporting/late_job_analyzer.py`:
  - Identifies jobs late vs plan date; builds human-readable analysis text.

### API surface (selected)
- Health/config:
  - GET `/` → service banner.
  - GET `/health` → DB + configuration checks.
  - GET `/config` → sanitized runtime config.
- Production jobs: `/api/production-jobs`
  - GET `/` → list; `limit, offset, priority`.
  - GET `/production-schedule` → paginated/sorted table; `page, page_size, sort_field, sort_order, search, planning_horizon_days`.
  - GET `/{job_id}` → details by `op_id` mapping.
- Reporting: `/api/reports`
  - GET `/gantt/priority-view`, `/gantt/resource-view`.
  - GET `/detailed-schedule`, `/schedule-overview`, `/data-quality-analysis`, `/late-jobs-analysis`.
  - POST `/ai-report`, POST `/ai-report-stream` (SSE).
- Logs: `/api/logs/recent?lines=100`.

### Configuration and environment
- Required DB vars: `MARIADB_HOST`, `MARIADB_USERNAME`, `MARIADB_PASSWORD`, `MARIADB_DATABASE`, `MARIADB_PORT`.
- Scheduling/reporting critical:
  - `MAX_JOBS_LIMIT`, `PLANNING_HORIZON_DAYS`, `MAX_PLANNING_HORIZON_DAYS`.
  - `NORMAL_WORKING_HOURS`, `OT_WORKING_HOURS`, `EMERGENCY_OT_HOURS`.
  - Many thresholds are hardcoded in code to reduce config drift.
- CORS, PORT/HOST, LOG_LEVEL etc via `AppConfig` with strict casting and safe defaults.

### Frontend architecture (React)
- Entry: `frontend/src/App.tsx` with `AuthProvider`, `DataCacheProvider`, `ProtectedRoute`.
- Main routes:
  - `/` and `/page/ai_optimizer` → `Dashboard` with “Refresh All Data” that clears cache then triggers data pulls (via context’s `refreshData`).
  - `/data` and `/table_data` → table view.
  - `/schedule-table` → detailed schedule table.
  - `/gantt-chart` → jobs allocation (priority view) Gantt chart.
  - `/resource-chart` → machine allocation (resource view) Gantt chart.
  - `/reports` → AI report page (streaming SSE from backend).
- AI Report page:
  - Consumes cached data: logs, detailed schedule, both Gantt datasets, overview.
  - Calls `POST /api/reports/ai-report-stream` with those caches; streams tokens to render a live report; falls back if stream lacks structure.
  - Derives metrics in-browser (completion/scheduling/unscheduled rates; buffer breakdown) for highlighted KPI cards.

### Data flow E2E
1) Frontend dashboard refresh → backend reporting endpoints call orchestrator → `load_jobs_planning_data()` → DB.
2) Greedy solver returns schedule dict; chart generator transforms to view models; table builder generates detailed rows.
3) Frontend caches all responses; pages render tables, charts; AI report streams analysis using the cached payload.

### Notable design choices
- Strict, fail-fast env validation in most modules; minimal silent fallbacks.
- Preemptive scheduling respects working hours and break times (minute-resolved stepping) when `time_availability` is present.
- Chain-aware prioritization with ultra-boosted urgency for required start dates to complete families.
- Separation of concerns: ingestion → schedule → transform → report → UI.

### Operational notes
- Logging: container-friendly stream + optional file handler (`app.log`) when not `PYTHONUNBUFFERED`.
- Docker: backend/frontend Dockerfiles; `docker-compose.backend.yml` present; `pyproject.toml` + `uv.lock` for Python deps.
- Tests: `backend/test_complex_dependencies.py` exists to validate dependency handling.

### Risks and gaps (actionable)
- If `.env` is incomplete, many endpoints fail fast by design. Ensure all required keys are set in deployment.
- `mariadb_parser` filters out jobs without material arrivals or with due dates today/past; may lead to “no jobs” in strict datasets. Confirm business rules.
- Time availability module assumed present for best results; fallback can reduce realism in preemptive timing.
- LLM integration expects DeepSeek-style API and keys; streaming path relies on external service availability.
- Machine mapping for resource view depends on DB content; missing mappings degrade labels to raw codes.

### Quick checklist to run locally
- Backend env: set DB and scheduling vars (see Config section). Start with `uvicorn main:app --reload` via `backend/main.py` or `make` if present.
- Frontend env: set `VITE_API_BASE_URL` to backend base (e.g. `http://localhost:8000/api`), then `npm run dev`.
- Load: visit Dashboard → Refresh All Data → open Gantt/Resource/Report pages.

### Suggested next improvements
- Add non-greedy solver option (CP-SAT/OR-Tools) behind a feature flag for complex plans; reuse `scheduler_utils` converter.
- Persist generated schedules to DB for audit/history; add idempotency on recomputations.
- Improve machine mapping table management and cache for resource view readability.
- Expand health checks: add solver warmup + time availability readiness endpoint.
- Parameterize chart/report thresholds via `.env` with safe defaults and central schema.


