# AI Optimizer - Intelligent Job Scheduling System

A production-grade intelligent manufacturing job scheduling system that combines advanced algorithms with machine learning optimization to deliver efficient, constraint-aware scheduling solutions.

## System Overview

The AI Optimizer manages complex manufacturing workflows with strict dependency requirements, machine assignments, and timing constraints. Built with a modern microservices architecture, it provides real-time scheduling optimization, comprehensive analytics, and intuitive visualization tools.

### Key Features

**Advanced Scheduling Engine**
- Production-grade greedy scheduling algorithm with constraint validation
- Complex dependency management with strict sequence enforcement
- Machine assignment optimization with capacity management
- Material availability and timing constraint integration

**Machine Learning Integration**
- PPO-based reinforcement learning for schedule optimization
- Curriculum learning approach for improved training efficiency
- Real-time inference with sub-second response times
- Continuous model improvement through production feedback

**Comprehensive Visualization**
- Interactive Gantt charts with job sequence tracking
- Resource utilization analytics and bottleneck identification
- Real-time dashboard with performance metrics
- Export capabilities for schedule data and reports

**Production-Ready Architecture**
- RESTful API with FastAPI framework
- Containerized deployment with Docker
- Comprehensive logging and monitoring
- Secure authentication and role-based access control

## Architecture Components

### Backend Services (`/backend/`)

**Core Scheduling System**
- `greedy_solver.py`: Production-grade scheduling algorithm with constraint validation
- `dependency_manager.py`: Complex job dependency analysis and enforcement
- `priority_calculator.py`: Job prioritization with urgency scoring
- `time_availability.py`: Machine availability and capacity management

**API Layer**
- `fastapi_app.py`: Main application server with endpoint routing
- `endpoints/`: Modular API endpoints for different system functions
- `config/`: Environment configuration and parameter management

**Data Processing**
- `mariadb_parser.py`: Production database integration and data ingestion
- `reporting/`: Analytics, visualization, and performance reporting
- `utils/`: Shared utilities and helper functions

### Frontend Application (`/frontend/`)

**User Interface**
- React-based single-page application with TypeScript
- Responsive design with Tailwind CSS styling
- Interactive components for schedule visualization
- Real-time data updates through context providers

**Core Components**
- `GanttChartDisplay.tsx`: Interactive schedule visualization
- `DetailedScheduleTable.tsx`: Comprehensive job data tables
- Authentication system with protected routes
- Dashboard with multiple view modes and analytics

### Infrastructure

**Containerization**
- Docker containers for consistent deployment
- Docker Compose orchestration for multi-service setup
- Production-ready configurations with health checks

**Database Integration**
- MariaDB primary data storage with optimized queries
- Migration scripts for schema management
- Backup and recovery procedures

## Quick Start

### Prerequisites

- Python 3.12+ with uv package manager
- Node.js 18+ for frontend development
- Docker and Docker Compose for containerized deployment
- MariaDB for data storage

### Backend Setup

```bash
cd backend/
uv venv
source .venv/bin/activate
uv sync
uv run python main.py
```

### Frontend Setup

```bash
cd frontend/
npm install
npm run dev
```

### Docker Deployment

```bash
docker-compose up -d
```

## Configuration

### Environment Variables

Create `.env` files for each environment:

**Backend Configuration**
```env
# Database
DB_HOST=localhost
DB_PORT=3306
DB_NAME=scheduler_db
DB_USER=scheduler_user
DB_PASSWORD=secure_password

# Scheduling Parameters
NORMAL_WORKING_HOURS=8.0
OT_WORKING_HOURS=4.0
EMERGENCY_OT_HOURS=2.0
GRACE_PERIOD_HOURS=24

# System Settings
LOG_LEVEL=INFO
API_HOST=0.0.0.0
API_PORT=8000
```

**Frontend Configuration**
```env
REACT_APP_API_URL=http://localhost:8000
REACT_APP_AUTH_URL=your_supabase_url
REACT_APP_SUPABASE_KEY=your_supabase_key
```

## API Documentation

The system provides comprehensive API documentation through FastAPI's automatic documentation generation:

- **Interactive API Docs**: `http://localhost:8000/docs`
- **OpenAPI Schema**: `http://localhost:8000/openapi.json`

### Key Endpoints

**Production Jobs**
- `GET /api/jobs`: Retrieve job listings with filtering
- `POST /api/jobs/schedule`: Execute scheduling algorithm
- `GET /api/jobs/{job_id}`: Get specific job details

**Analytics & Reporting**
- `GET /api/reports/performance`: System performance metrics
- `GET /api/reports/bottlenecks`: Bottleneck analysis
- `POST /api/reports/generate`: Create custom reports

**System Management**
- `GET /api/health`: System health check
- `GET /api/logs`: Access system logs
- `POST /api/config/update`: Update system configuration

## Scheduling Algorithm

### Constraint Management

The system enforces strict constraints to ensure production validity:

**Sequence Dependencies**
- Job families must follow sequential order (1→2→3→4→5)
- No steps can be skipped in the production sequence
- Complete dependency chain validation prevents invalid scheduling

**Resource Constraints**
- Machine assignments respect capacity limitations
- Setup times and changeover requirements included
- Working hours and overtime rules enforced

**Timing Constraints**
- Material arrival dates respected
- Due dates and priority scheduling
- Buffer time management for realistic scheduling

### Performance Metrics

**Quality Indicators**
- 95% constraint satisfaction rate target
- 85% on-time delivery rate goal
- Sub-second inference time for 100+ job schedules

**Optimization Goals**
- Minimize total completion time
- Maximize machine utilization
- Reduce setup and changeover costs
- Optimize resource allocation

## Machine Learning Integration

### PPO System (app3)

**Architecture Design**
- Simplified action space: select next task to schedule
- State representation: task readiness, machine status, urgency scores
- Reward structure: time-based scoring with on-time bonuses

**Training Pipeline**
- Curriculum learning across 6 stages (10-200+ jobs)
- 100,000 timesteps per stage with performance gates
- Multi-layer perceptron with 256-128-64 architecture
- Action masking prevents invalid scheduling decisions

**Deployment**
- Real-time inference integration with scheduling engine
- Model versioning and A/B testing capabilities
- Performance monitoring and continuous improvement

## Development Standards

### Code Quality

**Python Development**
- Use uv package manager exclusively (no pip)
- Python 3.12+ with modern language features
- Type hints and comprehensive validation
- Ruff for formatting and linting

**Frontend Development**
- TypeScript for type safety
- React with functional components and hooks
- Tailwind CSS for consistent styling
- ESLint and Prettier for code quality

### Testing Standards

**Backend Testing**
- Comprehensive unit tests for all algorithms
- Integration tests for API endpoints
- Performance tests for scheduling algorithms
- Automated test cleanup (remove temp files)

**Frontend Testing**
- Component testing with React Testing Library
- End-to-end testing for critical user flows
- Performance testing for large datasets
- Accessibility testing compliance

### Git Workflow

**Branch Strategy**
- Feature branches for new development
- Code reviews required for all changes
- Automated testing before merge
- Descriptive commit messages with trailers

**Quality Gates**
- Pre-commit hooks for code formatting
- Automated testing pipeline
- Security scanning and dependency updates
- Documentation updates with code changes

## Monitoring & Observability

### System Metrics

**Performance Monitoring**
- API response times and throughput
- Database query performance
- Memory and CPU utilization
- Scheduling algorithm execution times

**Business Metrics**
- Schedule accuracy and constraint compliance
- On-time delivery rates
- Machine utilization efficiency
- Cost optimization achievements

### Health Monitoring

**Service Health**
- Automated health checks for all services
- Database connection monitoring
- External dependency status tracking
- Resource availability alerts

**Error Tracking**
- Comprehensive error logging with correlation IDs
- Exception tracking and alerting
- Performance profiling for bottleneck identification
- Audit trails for compliance and debugging

## Security

### Authentication & Authorization

**User Management**
- Secure authentication with Supabase integration
- Role-based access control (RBAC)
- Multi-factor authentication support
- Session management with automatic timeout

**API Security**
- JWT token validation for all endpoints
- API rate limiting and throttling
- Request validation and sanitization
- CORS configuration for cross-origin requests

### Data Protection

**Encryption**
- Data encryption at rest and in transit
- Secure credential management
- Personal data anonymization where applicable
- Regular security assessments and updates

**Compliance**
- Audit logging for sensitive operations
- Data retention policies
- Privacy protection measures
- Regular vulnerability scanning

## Deployment

### Production Deployment

**Infrastructure Requirements**
- Linux-based servers with Docker support
- Load balancer for high availability
- SSL certificates for secure communication
- Backup storage for data protection

**Deployment Process**
- Blue-green deployment strategy
- Automated rollback capabilities
- Health checks during deployment
- Zero-downtime updates

### Scaling Considerations

**Horizontal Scaling**
- Multiple backend service instances
- Load balancing across services
- Database connection pooling
- Caching layer for improved performance

**Performance Optimization**
- Database indexing and query optimization
- Application-level caching
- CDN for static assets
- Monitoring and alerting for performance issues

## Contributing

### Development Setup

1. Fork the repository and create a feature branch
2. Follow the development standards outlined above
3. Write comprehensive tests for new functionality
4. Update documentation for any changes
5. Submit pull request with detailed description

### Code Review Process

- All changes require peer review
- Automated testing must pass
- Documentation updates required
- Performance impact assessment
- Security review for sensitive changes

## Support & Documentation

### Getting Help

**Documentation**
- In-code documentation with detailed comments
- API documentation through FastAPI
- Architecture diagrams and flow charts
- Troubleshooting guides and FAQ

**Community Support**
- Issue tracking through GitHub
- Development discussions and planning
- Feature requests and feedback
- Security vulnerability reporting

### Maintenance

**Regular Updates**
- Dependency updates and security patches
- Performance optimization reviews
- Feature enhancements based on user feedback
- Documentation updates and improvements

**Monitoring**
- Automated monitoring and alerting
- Performance trend analysis
- Capacity planning and scaling
- Regular backup verification

---

**Project Status**: Production Ready
**Last Updated**: August 13, 2025
**Version**: 2.0.0
**License**: Proprietary