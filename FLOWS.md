# AI Optimizer - Workflow Documentation

## System Architecture Overview

The AI Optimizer is a comprehensive job scheduling system that combines machine learning optimization with production-grade scheduling algorithms. The system manages complex manufacturing job dependencies, machine assignments, and timing constraints.

## Core System Flows

### 1. Job Scheduling Flow

#### Data Input Stage
1. **Job Data Ingestion**
   - MariaDB parser extracts job data from production database
   - Jobs contain: family, sequence, process_name, processing_time, assigned_machine
   - Material arrival dates and dependencies are validated
   - Job families follow strict sequential order (1→2→3→4→5)

2. **Constraint Validation**
   - Sequence dependency checking ensures no steps are skipped
   - Machine availability validation prevents conflicts
   - Material arrival time constraints are enforced
   - Working hours and capacity limits are applied

#### Processing Stage
3. **Dependency Analysis**
   - Complex dependency manager analyzes job chains
   - Sequence gap detection prevents invalid scheduling
   - Emergency override system removed to ensure strict compliance
   - Complete dependency chain validation implemented

4. **Greedy Scheduling Algorithm**
   - Production-grade greedy solver processes jobs
   - Priority calculator determines job urgency
   - Time availability checker ensures feasible scheduling
   - Setup buffer management optimizes machine transitions

#### Output Stage
5. **Schedule Generation**
   - Optimized schedule created with validated constraints
   - Gantt chart visualization generated for frontend
   - Performance metrics and validation results provided
   - Schedule exported for production deployment

### 2. Frontend Workflow

#### User Interface Flow
1. **Authentication & Access**
   - User login through secure authentication system
   - Protected routes ensure proper access control
   - User profile management with role-based permissions

2. **Dashboard Navigation**
   - Main dashboard provides system overview
   - Multiple view modes: table data, Gantt charts, reports
   - Real-time data updates through context providers
   - Responsive design for various screen sizes

3. **Schedule Visualization**
   - Interactive Gantt chart display with job sequences
   - Detailed schedule tables with filtering capabilities
   - Resource utilization charts and analytics
   - Export functionality for schedule data

4. **Reporting & Analytics**
   - AI-generated comprehensive reports
   - Late job analysis and bottleneck identification
   - Performance metrics and trend analysis
   - Production optimization recommendations

### 3. Backend API Flow

#### Service Architecture
1. **FastAPI Application**
   - RESTful API endpoints for all system operations
   - Authentication middleware for secure access
   - Request validation and error handling
   - Automatic API documentation generation

2. **Endpoint Categories**
   - **Production Jobs**: CRUD operations for job data
   - **Scheduling**: Algorithm execution and results
   - **Reporting**: Analytics and performance metrics
   - **Logs**: System monitoring and debugging

3. **Data Processing Pipeline**
   - Asynchronous job processing for large datasets
   - Queue management for scheduling requests
   - Result caching for improved performance
   - Error recovery and retry mechanisms

### 4. PPO System Architecture (app3)

#### Simplified PPO Implementation
1. **Environment Design**
   - Action space: Select next task to schedule (not job-machine pairs)
   - State representation: task_ready, machine_busy, urgency_scores
   - Reward structure: +100 on-time, +50 early, -100 late per day
   - Constraint integration: sequence, machine, material, time

2. **Training Pipeline**
   - Curriculum learning: 6 stages (10→20→40→60→100→200+ jobs)
   - Performance gate: >80% success rate to progress
   - 100k timesteps per stage with PPO optimization
   - Action masking prevents invalid scheduling decisions

3. **Model Architecture**
   - Multi-layer perceptron: 256-128-64 neurons
   - Learning rate: 3e-4 with adaptive scheduling
   - Batch size: 64 for stable gradient updates
   - Policy and value networks with shared features

## Data Flow Patterns

### 1. Real-time Scheduling Updates
```
User Request → API Gateway → Scheduler Service → Database Update → Frontend Refresh
```

### 2. Batch Processing Flow
```
Scheduled Job → Data Ingestion → Validation → Algorithm Processing → Result Storage → Notification
```

### 3. Error Handling Flow
```
Error Detection → Logging → Recovery Attempt → Fallback Strategy → User Notification
```

## Integration Points

### 1. Database Integration
- **MariaDB**: Primary production data storage
- **Caching Layer**: Redis for performance optimization
- **Backup Systems**: Automated data protection
- **Migration Scripts**: Database schema management

### 2. External Services
- **Authentication**: Supabase integration for user management
- **Monitoring**: Comprehensive logging and metrics
- **Deployment**: Containerized services with Docker
- **CI/CD**: Automated testing and deployment pipeline

### 3. Machine Learning Integration
- **Model Training**: PPO algorithm with curriculum learning
- **Inference**: Real-time scheduling optimization
- **Model Versioning**: Track and deploy model updates
- **Performance Monitoring**: ML model accuracy tracking

## Configuration Management

### 1. Environment Configuration
- Production, staging, and development environments
- Environment-specific variables through .env files
- Configuration validation and error handling
- Secure credential management

### 2. Scheduling Parameters
- Working hours and overtime configurations
- Machine capacity and setup times
- Priority weights and urgency factors
- Performance thresholds and gates

### 3. System Settings
- Logging levels and output formats
- API rate limiting and timeouts
- Cache expiration and cleanup
- Backup schedules and retention

## Monitoring and Observability

### 1. System Metrics
- **Performance**: Response times, throughput, resource usage
- **Quality**: Success rates, error frequencies, accuracy metrics
- **Business**: On-time delivery, machine utilization, cost optimization

### 2. Health Checks
- Service availability monitoring
- Database connection health
- External dependency status
- Resource utilization alerts

### 3. Logging Strategy
- Structured logging with correlation IDs
- Error tracking and alerting
- Performance profiling data
- Audit trails for compliance

## Security Considerations

### 1. Authentication & Authorization
- Multi-factor authentication support
- Role-based access control (RBAC)
- Session management and timeout
- API key management for service-to-service

### 2. Data Protection
- Encryption at rest and in transit
- Personal data anonymization
- Audit logging for sensitive operations
- Regular security assessments

### 3. Infrastructure Security
- Network segmentation and firewalls
- Container security scanning
- Dependency vulnerability monitoring
- Regular security updates

## Deployment Architecture

### 1. Development Workflow
- Local development with uv and Python 3.12+
- Git flow with feature branches and code reviews
- Automated testing with pre-commit hooks
- Documentation updates with code changes

### 2. Production Deployment
- Containerized services with Docker
- Load balancing and auto-scaling
- Blue-green deployment strategy
- Rollback capabilities for issues

### 3. Monitoring & Maintenance
- Automated health checks and alerts
- Performance monitoring and optimization
- Regular backup verification
- Capacity planning and scaling

## Future Enhancements

### 1. Advanced Features
- Real-time collaborative scheduling
- Advanced analytics and forecasting
- Multi-objective optimization
- Dynamic constraint adjustment

### 2. Scalability Improvements
- Microservices architecture
- Event-driven processing
- Distributed computing support
- Cloud-native deployment

### 3. User Experience
- Mobile application development
- Advanced visualization options
- Customizable dashboards
- Integration with third-party tools