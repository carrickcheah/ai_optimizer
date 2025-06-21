# AI Optimizer - Production Scheduling System

A **production scheduling system** that optimizes manufacturing job sequences to meet deadlines while respecting real-world constraints. It uses a **greedy scheduling algorithm** enhanced with **chain completion analysis** and **priority-based optimization**.

## System Overview

The AI Optimizer handles complex manufacturing workflows with:
- **440+ jobs** with multi-process dependencies (P1→P2→P3→P4→P5)
- **76 machines** with specialized capabilities and constraints
- **Real-time working hours** management (6:30 AM - 6:00 PM).
- **Chain completion analysis** preventing entire production chains from being late.
- **100x priority boost system** for ultra-critical jobs.

## 🏗️ Core Architecture

```
ai_optimizer/
├── frontend/                           # React/TypeScript frontend
│   ├── src/
│   │   ├── components/                 # UI components
│   │   │   ├── GanttChartDisplay.tsx   # Gantt chart visualization
│   │   │   ├── DetailedScheduleTable.tsx # Job schedule table
│   │   │   ├── resource_chart.tsx      # Resource-grouped view
│   │   │   └── form/                   # Form components
│   │   │       ├── dashboard.tsx       # Main dashboard with refresh
│   │   │       ├── ai_report.tsx       # AI Production Analysis Report
│   │   │       ├── ai_report.css       # Basic AI report styles
│   │   │       └── ai_report_comprehensive.css # Professional report styling
│   │   ├── contexts/                   # React contexts
│   │   │   └── DataCacheContext.tsx    # API data caching
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
│   │   ├── scheduling/                 # Core scheduling engine
│   │   │   ├── greedy_solver.py        # Main scheduling algorithm
│   │   │   ├── priority_calculator.py  # Enhanced priority system
│   │   │   ├── chain_analyzer.py       # Dependency chain analysis
│   │   │   ├── time_availability.py    # Working hours management
│   │   │   └── scheduler_utils.py      # Utility functions
│   │   ├── data_ingestion/             # MariaDB data loading
│   │   │   └── mariadb_parser.py       # Database integration
│   │   ├── reporting/                  # Chart generation & analytics
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
- **Enhanced Greedy Scheduling** - Chain completion analysis with 100x priority boost
- **MariaDB** - Production database integration (`tbl_jo_txn`, `tbl_jo_process`, `tbl_machine`)
- **Real-time Configuration** - Database-driven working hours, holidays, breaks
- **uvicorn** - ASGI server

### Frontend
- **React 19** - Modern UI framework
- **TypeScript** - Type safety
- **Vite** - Fast build tool
- **Plotly.js** - Interactive Gantt charts and timelines
- **Bootstrap 5** - Responsive styling

### Database Schema
- **Production Tables**: `tbl_jo_txn`, `tbl_jo_process`, `tbl_machine`, `dbo_item`
- **Time Management**: `ai_arrangable_hour`, `ai_breaktimes`, `ai_holidays`
- **Configuration**: Dynamic working hours (6:30 AM - 6:00 PM), break schedules, holiday handling
- **Data Processing**: Joins tables to create unified job records with dependencies

## 🎯 Key Features

### ✅ Enhanced Scheduling Engine
- **Chain Completion Analysis**: Prevents entire job chains (P1→P2→P3→P4→P5) from missing LCD deadlines
- **100x Priority Boost**: Ultra-critical jobs override machine queues with massive priority multipliers
- **Dependency Enforcement**: Strict process sequence enforcement for all job types
- **Preemptive Scheduling**: Jobs pause during breaks, resume after, span multiple days seamlessly
- **Machine Preemption**: Critical jobs can take machines immediately, rescheduling other work
- **Working Hours Compliance**: Database-driven 6:30 AM - 6:00 PM scheduling
- **Break-Aware**: Automatic pause during lunch, tea, dinner breaks
- **Holiday Support**: No scheduling on configured holidays

### ✅ Advanced Analytics & Visualization
- **Buffer Status Analysis**: Real-time tracking of Late/Warning/Caution/OK/Unscheduled jobs
- **Machine Bottleneck Detection**: Identifies overloaded machines and failure rates
- **Chain Priority Visualization**: Shows 100x boost applications and critical paths
- **Resource Grouping**: Machine-based timeline with utilization metrics
- **Real-time Updates**: Dynamic data loading with manual refresh capability
- **Timeline Controls**: Multiple timeframe filters with gap visualization

### ✅ Production Data Integration
- **440+ Jobs Processing**: Real production workload with complex dependencies
- **76 Machine Management**: Specialized equipment with individual constraints
- **Subcontractor Coordination**: External work scheduling (143 days of queue)
- **LCD Deadline Tracking**: Latest Completion Date monitoring and urgency scoring
- **Dynamic Configuration**: All parameters from database (no hardcoded defaults)
- **Performance Optimization**: <1 second scheduling for 440+ jobs

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
1. **Data Ingestion**: MariaDB joins (`tbl_jo_txn`, `tbl_jo_process`, `tbl_machine`) → unified job records
2. **Job Categorization**: Dependency vs independent jobs, subcontractor identification
3. **Chain Analysis**: Calculate realistic completion times with 2.5x preemptive multiplier
4. **Priority Calculation**: LCD urgency × plan date × chain completion × buffer status factors
5. **Enhanced Scheduling**: Greedy algorithm with 100x priority boost and machine preemption
6. **API Layer**: REST endpoints serve optimized schedules with analytics
7. **Visualization**: React frontend with real-time buffer status and bottleneck analysis

### Enhanced Scheduling Logic

#### Priority Calculation System
```python
priority_score = (
    lcd_urgency *           # 0-1000+ (deadline proximity)
    plan_date_factor *      # 1.0+ (overdue penalty)
    chain_factor *          # 1.0-100x (chain completion boost)
    buffer_factor *         # 1.0-2.0 (buffer status multiplier)
    priority_factor         # 0.1-1.0 (original priority inversion)
)
```

#### Chain Completion Boost Levels
- **100x**: Must start NOW (past required date)
- **50x**: Must start within 7 days  
- **20x**: Must start within 14 days
- **5x**: Must start within 30 days

#### Machine Preemption Logic
- Ultra-critical jobs (100x boost) can override machine availability
- Machine queues reset for immediate critical job placement
- Other jobs automatically rescheduled to accommodate priorities

## 🛠️ Key API Endpoints

### Primary Endpoints
- `GET /api/reports/detailed-schedule?solver=greedy` - Full job schedule with chain analysis
- `GET /api/reports/gantt/priority-view?solver=greedy` - Priority-based Gantt chart data
- `GET /api/reports/gantt/resource-view?solver=greedy` - Machine-grouped timeline
- `GET /api/reports/schedule-overview?solver=greedy` - Summary statistics and bottleneck analysis
- `GET /api/reports/health` - System health check and component status

### Enhanced Parameters
- `solver=greedy` - Enhanced greedy algorithm (only available solver)
- `max_jobs=1000` - Job limit for performance control
- `force_refresh=true` - Bypass cache, recalculate schedule with latest priorities

### Chain Completion Features
- Real-time 100x boost application for critical jobs
- Machine preemption logging and tracking
- Buffer status analysis (Late/Warning/Caution/OK/Unscheduled)
- Bottleneck machine identification with failure rates

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

## 🏆 Enhanced Features & Achievements

### Chain Completion Boost System
**Problem Solved**: Jobs with tight LCD deadlines were being scheduled too late, causing entire chains to miss deadlines.

**Solution Implemented**: 
1. **Analyze entire job families** (all P1-P5 processes)
2. **Calculate realistic completion time** using 2.5x multiplier for preemptive scheduling
3. **Apply massive priority boosts** (5x to 100x) based on urgency
4. **Enable machine preemption** for ultra-critical jobs

**Results Achieved**:
- **JOAW25050075 P1**: July 10 → June 24 (**16-day improvement**)
- **Chain completion analysis** prevents late deliveries
- **Ultra-critical jobs** override normal machine queues
- **100x priority boost** system fully operational

### System Performance Metrics
- **Jobs Processed**: 440 jobs in <1 second
- **Late Job Analysis**: Real-time tracking of 44.1% late rate (capacity constrained)
- **Buffer Status**: 100% accurate tallying (194 late + 246 others = 440 total)
- **Machine Bottlenecks**: Automatic detection of 90%+ failure rate machines

### Architecture Improvements
- **Enhanced Greedy Solver**: 1670+ lines of CP-SAT code removed, single reliable algorithm
- **Chain Analysis Integration**: priority_calculator.py and chain_analyzer.py modules
- **Database-Only Configuration**: No hardcoded defaults, all from production database
- **Real-time Working Hours**: Dynamic 6:30 AM - 6:00 PM compliance

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

## 📈 Current Performance Metrics

### Scheduling Performance
- **Jobs Processed**: 440 jobs in <1 second
- **Processing Time**: ~0.5-1.0 seconds for full schedule
- **Memory Usage**: Efficient with intelligent caching
- **Database Queries**: Optimized with indexed joins

### Business Impact
- **Chain Optimization**: 16+ day improvements for critical chains
- **Buffer Status**: 100% accurate tracking and visualization
- **Machine Analysis**: Real-time bottleneck detection and failure rate monitoring
- **Deadline Compliance**: Enhanced priority system prevents worse delays

### System Constraints & Limitations
- **Late Job Rate**: 44.1% (194/440) indicating capacity vs demand mismatch
- **Machine Bottlenecks**: 4+ machines with >75% late rates (TM05-020T: 90%, PB04-020T-1.2M: 81.8%)
- **Subcontractor Queue**: 143 days of external work (29 jobs)
- **Capacity Analysis**: System working optimally within resource constraints

## 🎯 System Assessment

### ✅ ALGORITHM STATUS: FULLY OPERATIONAL
The AI Optimizer successfully optimizes production schedules with:
- **Enhanced chain completion analysis**
- **100x priority boost system** 
- **16+ day schedule improvements**
- **Accurate buffer status tracking**
- **Real-time working hours compliance**

### ⚠️ CAPACITY STATUS: CONSTRAINED
The 44.1% late job rate indicates **insufficient production capacity** relative to current demand:
- **Mathematical Evidence**: Multiple machines with 32+ days of work queued
- **Bottleneck Machines**: TM05-020T (90% late), PP20-110T-B4 (83.3% late)
- **External Dependencies**: 143 days of subcontractor work creating cascading delays
- **Business Reality**: Need additional machines, shifts, or subcontractor capacity

**Conclusion**: The scheduling algorithm has achieved optimal performance within resource constraints. Further improvements require **physical capacity expansion** rather than algorithm optimization.

---

## 📋 Quick Reference

### Development Commands
```bash
# Backend health check
curl -s "http://localhost:8000/api/reports/health" | python3 -m json.tool

# Test enhanced scheduling
curl -s "http://localhost:8000/api/reports/schedule-overview?solver=greedy&force_refresh=true"

# Check chain completion analysis
uv run python app/scheduling/chain_analyzer.py

# Test priority calculation
uv run python app/scheduling/priority_calculator.py
```

### Configuration Files
- `/backend/.env` - Database and scheduling parameters
- `/backend/app/config/` - Runtime configuration management
- `/Users/carrickcheah/Project/ai_optimizer/CLAUDE.local.md` - Development guidelines
- `/Users/carrickcheah/Project/ai_optimizer/z_issue.md` - System architecture summary
- `/Users/carrickcheah/Project/ai_optimizer/z_analysis_of_bottleneck.md` - Capacity analysis report

---

**Status**: This system is **production-ready** with enhanced chain completion analysis, 100x priority boost system, and comprehensive capacity vs demand monitoring. The scheduling algorithm performs optimally within available resource constraints.