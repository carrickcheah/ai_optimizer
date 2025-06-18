# AI Optimizer - Production Planning System

A modern production scheduling and optimization system built with React and FastAPI, designed for manufacturing environments with complex job dependencies and resource constraints.

## 🏗️ Project Architecture

```
ai_optimizer/
├── frontend/                           # React/TypeScript frontend
│   ├── src/
│   │   ├── components/                 # UI components
│   │   │   ├── GanttChartDisplay.tsx   # Job timeline visualization
│   │   │   ├── resource_chart.tsx      # Resource-grouped view
│   │   │   └── ProductionJobsTable.tsx # Job management table
│   │   ├── contexts/                   # React contexts
│   │   │   └── DataCacheContext.tsx    # Frontend data caching
│   │   ├── hooks/                      # Custom React hooks
│   │   │   └── useWorkingHours.tsx     # Dynamic working hours
│   │   └── App.tsx                     # Main application
│   ├── package.json                    # Dependencies (React 19, Plotly.js)
│   └── vite.config.js                  # Vite build configuration
│
├── backend/                            # Python FastAPI backend
│   ├── app/
│   │   ├── api/endpoints/              # REST API endpoints
│   │   │   ├── reporting_endpoints.py  # Schedule reports & analytics
│   │   │   └── production_jobs_endpoints.py # Job management
│   │   ├── scheduling/                 # Scheduling engine
│   │   │   ├── greedy_solver.py        # Primary scheduling algorithm
│   │   │   ├── time_availability.py    # Working hours & breaks
│   │   │   └── scheduler_utils.py      # Utility functions
│   │   ├── data_ingestion/             # Database integration
│   │   │   └── mariadb_parser.py       # MariaDB data loading
│   │   ├── reporting/                  # Chart & report generation
│   │   │   ├── chart_generator.py      # Gantt chart data
│   │   │   └── production_report_generator.py # Analytics
│   │   └── config/                     # Configuration management
│   ├── testing/                        # Test scripts
│   ├── main.py                         # FastAPI application entry
│   └── .env                           # Environment configuration
│
├── CLAUDE.local.md                     # Development documentation
└── pyproject.toml                      # Python dependencies (uv managed)
```

## 🚀 Technology Stack

### Backend
- **FastAPI** - Modern REST API framework
- **Greedy Scheduling** - Efficient job scheduling with dependency enforcement
- **MariaDB** - Production database integration
- **Plotly.js** - Timeline visualization backend
- **uvicorn** - ASGI server

### Frontend
- **React 19** - Modern UI framework
- **TypeScript** - Type safety
- **Vite** - Fast build tool
- **Plotly.js** - Interactive Gantt charts and timelines
- **Bootstrap 5** - Responsive styling

### Database Schema
- **Core Tables**: `tbl_jo_txn`, `tbl_jo_process`, `tbl_machine`
- **Time Management**: `ai_arrangable_hour`, `ai_breaktimes`, `ai_holidays`
- **Configuration**: Dynamic working hours, break schedules, holiday handling

## 🎯 Key Features

### ✅ Production-Ready Scheduling
- **Dependency Enforcement**: All jobs (machine & subcontractor) follow process sequences (P1→P2→P3→P4)
- **Preemptive Scheduling**: Long jobs automatically pause during breaks and resume after
- **Working Hours Compliance**: Jobs respect 6:30 AM - 6:00 PM working hours from database
- **Break-Aware**: Automatic pause during lunch, tea, and dinner breaks
- **Holiday Support**: No scheduling on configured holidays

### ✅ Advanced Visualization
- **Merged Job Display**: Consolidated view of segmented jobs with gap visualization
- **Resource Grouping**: Machine-based timeline view
- **Real-time Updates**: Dynamic data loading and caching
- **Timeline Controls**: Multiple timeframe filters (1d, 7d, 14d, 1m, 3m, all)

### ✅ Data Integration
- **Dynamic Configuration**: All parameters loaded from database and .env
- **MariaDB Integration**: Production-grade database connectivity
- **Comprehensive Validation**: Strict data validation and error handling
- **Performance Optimization**: Efficient queries and data processing

## 🔧 Environment Configuration

### Required .env Variables
```bash
# Database Connection
MARIADB_HOST=localhost
MARIADB_USERNAME=myuser
MARIADB_PASSWORD=mypassword
MARIADB_DATABASE=nex_valiant
MARIADB_PORT=3306

# Scheduling Configuration
MAX_JOBS_LIMIT=1000
PLANNING_HORIZON_DAYS=180
DEFAULT_SOLVER_TYPE=greedy

# Working Hours
NORMAL_WORKING_HOURS=17.5
OT_WORKING_HOURS=19.5
EMERGENCY_OT_HOURS=22.0

# Server Configuration
PORT=8000
HOST=0.0.0.0
```

## 🏃‍♂️ Quick Start

### Backend Setup
```bash
cd backend
uv install
uv run uvicorn main:app --reload --port 8000
```

### Frontend Setup
```bash
cd frontend
npm install
npm run dev
```

### Health Check
```bash
curl http://localhost:8000/health
curl http://localhost:3000
```

## 📊 Core Application Flow

### Data Pipeline
1. **Data Ingestion**: MariaDB → `mariadb_parser.py` extracts job/machine data
2. **Job Categorization**: Dependencies analyzed, jobs sorted by priority
3. **Scheduling**: Greedy algorithm with preemptive time management
4. **API Layer**: REST endpoints serve optimized schedules
5. **Visualization**: React frontend displays interactive Gantt charts

### Scheduling Algorithm
- **Greedy Solver**: Single, reliable scheduling engine (CP-SAT removed)
- **Dependency Handling**: Process sequence enforcement for all job types
- **Time Management**: Working hours, breaks, holidays from database
- **Resource Optimization**: Machine availability and setup time consideration

## 🛠️ Key API Endpoints

### Schedule Management
- `GET /api/reports/schedule-overview` - Schedule summary and statistics
- `GET /api/production/gantt-priority-view` - Priority-based timeline
- `GET /api/production/gantt-resource-view` - Resource-grouped timeline
- `GET /api/production/detailed-schedule-table` - Comprehensive job data

### Configuration
- `GET /api/production/working-hours` - Dynamic working hours configuration
- `GET /health` - System health and component status

### Features
- **Solver Parameter**: `?solver=greedy` (default)
- **Job Limiting**: `?max_jobs=200` for performance
- **Time Filtering**: Frontend timeframe controls

## 🎨 Frontend Components

### Timeline Visualization
- **GanttChartDisplay.tsx**: Job-centric Gantt chart with merged segments
- **resource_chart.tsx**: Machine-centric resource view
- **Timeline Features**: Hover tooltips, gap visualization, dependency tracking

### Data Management
- **DataCacheContext**: Intelligent caching with refresh capabilities
- **useWorkingHours**: Dynamic working hours from backend API
- **Performance**: Debounced logging, optimized re-rendering

## 🧪 Testing & Development

### Component Testing
```bash
uv run python app/data_ingestion/mariadb_parser.py
uv run python app/scheduling/greedy_solver.py
uv run python testing/debug_deep_dive.py
```

### API Testing
```bash
curl -s "http://localhost:8000/api/reports/health"
curl -s "http://localhost:8000/api/reports/schedule-overview?solver=greedy"
```

### Database Verification
```bash
mysql -u myuser -pmypassword -h localhost -e "DESCRIBE ai_arrangable_hour" nex_valiant
mysql -u myuser -pmypassword -h localhost -e "SELECT * FROM ai_breaktimes LIMIT 5" nex_valiant
```

## 🏆 Recent Achievements

### Architecture Improvements
- **Simplified**: Greedy-only solver (1670+ lines of CP-SAT code removed)
- **Reliable**: No more solver timeouts or infeasible problems
- **Maintainable**: Single scheduling path, cleaner codebase
- **Performance**: Handles any number of jobs efficiently

### Feature Enhancements
- **Dependency Enforcement**: Fixed subcontractor job sequencing
- **Working Hours**: Dynamic configuration from database
- **Console Optimization**: Debounced logging for better development experience
- **Work Duration**: Machine-only calculation (excludes subcontractor hours)

### Data Quality
- **Validation**: Comprehensive input validation and error handling
- **Logging**: Structured logging with meaningful error messages
- **Monitoring**: Health checks and component status tracking

## 🔍 Troubleshooting

### Common Issues
1. **Database Connection**: Verify MariaDB credentials and server status
2. **Dependency Scheduling**: Check job categorization and process sequences
3. **Working Hours**: Validate `ai_arrangable_hour` table data
4. **Frontend Cache**: Use "Clear Cache" button for data refresh

### Debug Commands
```bash
# Check working hours
uv run python testing/check_working_hours.py

# Test scheduler
uv run python testing/test_greedy_deep_scan.py

# Database connectivity
uv run python app/data_ingestion/mariadb_parser.py
```

## 📈 Performance Metrics

- **Job Processing**: 200+ jobs scheduled in <2 seconds
- **Database Queries**: Optimized with proper indexing
- **Frontend Rendering**: Efficient React hooks and caching
- **Memory Usage**: Minimal footprint with cleanup routines

---

**Note**: This system is production-ready with comprehensive error handling, database integration, and real-time visualization capabilities. All hardcoded values have been replaced with environment-based configuration.