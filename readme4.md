# AI Optimizer: Data Pipeline and System Analysis

## Project Overview

The AI Optimizer is a production scheduling system that uses Operations Research (OR-Tools) and machine learning techniques to optimize job scheduling in manufacturing environments. This document provides a comprehensive analysis of the current system architecture, data pipeline requirements, and recommendations for improvement.

## Current System Architecture

### Existing Components

#### 1. Data Ingestion (Basic)
- **mariadb_parser.py**: Handles database connection and raw data extraction
- Loads jobs, machines, and setup times from MariaDB
- Basic SQL queries to fetch production job data

#### 2. Minimal Transformation
- Date/time conversion (epoch to datetime and vice versa)
- Field normalization in `normalize_job_fields()`
- Basic data type conversions (string to float/int)

#### 3. Limited Validation
- `validate_job_data()` checks for required fields
- `validate_timestamp()` ensures reasonable timestamp values
- Basic type checking

#### 4. Optimization Engines
- **CP-SAT Solver**: Advanced constraint programming optimization
- **Greedy Solver**: Fast heuristic scheduling algorithm
- Both solvers work with cleaned data to generate optimal schedules

### System Logs Analysis

From the provided logs, the system shows:
- **73 tasks successfully scheduled**
- **27 tasks unscheduled** due to various constraints
- Jobs scheduled across multiple machines (52, 58, 64, 65, etc.)
- Time slots from 2025-05-31 00:40 to 22:40
- Some jobs cannot be scheduled due to "unmet dependencies"

## Data Pipeline Assessment

### ✅ What Currently Exists
1. **Basic Ingestion**: MariaDB connection and data extraction
2. **Minimal Transformation**: Date conversions and field normalization
3. **Basic Validation**: Required field checks and type validation

### ❌ Missing Critical Components

#### 1. Data Quality Assessment
- No systematic data profiling
- No comprehensive missing value analysis
- No outlier detection
- No data quality scoring/reporting

#### 2. Robust Data Cleaning
- No systematic missing value handling
- No duplicate detection/removal
- No standardized error handling
- No data consistency checks

#### 3. Comprehensive Transformation
- No feature engineering pipeline
- No business rule validation
- No data enrichment (derived metrics)
- No standardization framework

#### 4. Monitoring & Observability
- No data quality metrics tracking
- No pipeline performance monitoring
- No alerting for data issues
- No data lineage tracking

## Missing Value Handling Strategy

### Manufacturing Data Missing Value Patterns

#### Critical Fields (Cannot be missing)
- `job_id`, `rsc_code` (machine assignment)
- `job_quantity`, `process_code`

#### Time-sensitive Fields
- `lcd_date` (due dates)
- `start_date`, `material_arrival`
- `hours_need`, processing times

#### Operational Fields
- `number_operator`, `priority`
- `setting_hours`, `break_hours`
- `expect_output_per_hour`

### Recommended Missing Value Strategies

#### Strategy 1: Business Rule-Based Imputation
**For Processing Times** (`hours_need`, `expect_output_per_hour`):
- Use historical averages by machine type and process code
- Fallback to industry standards or equipment specifications
- Consider job quantity as a factor

**For Operational Parameters**:
- `number_operator`: Default to 1, check machine capacity
- `priority`: Default to 3 (medium), escalate if due date is soon
- `setting_hours`: Use machine-specific historical averages
- `break_hours`: Standard company policy (e.g., 1 hour per 8-hour shift)

#### Strategy 2: Contextual Imputation
**For Due Dates** (`lcd_date`):
- Calculate from job creation date + historical lead time
- Consider customer priority or job family urgency
- Use business calendar (exclude weekends/holidays)

**For Start Dates**:
- Use earliest possible start (after material arrival)
- Consider machine availability and sequence dependencies
- Default to "ASAP" scheduling

#### Strategy 3: Machine Learning-Based Imputation
- Predict `expect_output_per_hour` based on machine type, process code, and job characteristics
- Use clustering to find similar jobs and impute missing values
- Time series analysis for seasonal patterns in processing times

#### Strategy 4: Escalation and Flagging
**When to Flag for Manual Review**:
- Missing critical fields that affect safety or quality
- Inconsistent data (start_date after due_date)
- Values outside reasonable bounds (processing time > 1000 hours)

### Implementation Framework

#### Tier 1: Immediate Fixes (High Confidence)
- Use deterministic rules based on business logic
- Apply company standards and policies
- Use exact historical matches when available

#### Tier 2: Statistical Imputation (Medium Confidence)
- Historical averages by machine/process combinations
- Regression-based predictions using related fields
- Time-based patterns (seasonal adjustments)

#### Tier 3: Estimation with Uncertainty (Low Confidence)
- Industry benchmarks when no historical data exists
- Conservative estimates with wider safety margins
- Flag for future data collection improvement

#### Tier 4: Cannot Impute (Requires Intervention)
- Critical missing fields that affect safety/compliance
- Completely new job types with no reference data
- Data that requires external input (customer specifications)

## Machine Learning System Classification

### System Type: Operations Research (OR) + ML Hybrid

#### Why It's Considered an ML System
1. **Intelligent Decision Making**: Automatically learns optimal schedules from data
2. **Data-Driven Optimization**: Uses historical production data to inform scheduling decisions
3. **Pattern Recognition**: Identifies optimal job sequencing and resource allocation patterns

#### ML System Maturity Level: Basic ML System (Level 2/5)

**Current Capabilities**:
- Automated decision-making algorithms
- Data ingestion and basic preprocessing
- Model deployment (via FastAPI)
- Basic constraint optimization

**Missing for Advanced ML System**:
- No model training/retraining pipelines
- No performance monitoring and drift detection
- No A/B testing framework
- Limited feedback loops for continuous improvement

#### Industry Classification
- **Prescriptive Analytics** (tells you what to do)
- **Decision Support Systems** with ML components
- **AI-Powered Operations Research**
- **Intelligent Manufacturing Systems**

## Data Loading Strategy for Continuous Scheduling

### Recommended Approach: Rolling Window Based on LCD_DATE (Deadline)

Load jobs where:
```sql
lcd_date BETWEEN (TODAY - buffer_days) AND (TODAY + planning_horizon_days)
```

**Suggested Parameters**:
- `buffer_days`: 3-7 days (for late jobs that still need scheduling)
- `planning_horizon_days`: 30-90 days (depending on production lead times)

### Why LCD_DATE is Optimal

1. **Business Logic Alignment**: Scheduling is fundamentally about meeting deadlines
2. **Optimization Performance**: Keeps problem size manageable for OR-Tools
3. **Practical Scheduling Needs**: Production managers need visibility on upcoming deadlines

### Dynamic Loading Strategy

#### Refresh Frequency
1. **Real-time Updates** (Every 15-30 minutes):
   - New job arrivals
   - Status changes (started, completed, cancelled)
   - Priority changes or rush orders

2. **Daily Full Refresh** (Every night):
   - Complete data reload with updated horizons
   - Clean up completed/cancelled jobs
   - Recalculate planning windows

3. **Weekly Deep Clean**:
   - Archive old completed jobs
   - Update historical performance data
   - Adjust planning horizon based on performance metrics

#### Job Categories to Include
1. **Urgent/Late Jobs**: `lcd_date < TODAY` (overdue jobs)
2. **Current Planning Window**: `lcd_date BETWEEN TODAY AND (TODAY + planning_horizon)`
3. **Buffer for Flexibility**: `lcd_date BETWEEN (TODAY - grace_period) AND TODAY`

#### Job Categories to Exclude
1. **Far Future Jobs**: `lcd_date > (TODAY + planning_horizon)`
2. **Completed Jobs**: Status = Completed or Delivered
3. **Very Old Jobs**: `lcd_date < (TODAY - max_late_days)`

## Job Completion Tracking

### Current Elegant Solution: Quantity-Based Completion

The system uses `daily_output` and `job_quantity` fields to determine completion:

```
If accumulated_daily_output >= job_quantity 
Then job status = COMPLETED
```

### Three Status Model: PLANNED → IN_PROGRESS → COMPLETED

#### Status Transition Logic
- **PLANNED**: Job scheduled but production hasn't started (`accumulated_daily_output = 0`)
- **IN_PROGRESS**: Production started but not finished (`0 < accumulated_daily_output < job_quantity`)
- **COMPLETED**: Target quantity reached (`accumulated_daily_output >= job_quantity`)

### Advantages of Quantity-Based Completion
1. **More Accurate**: Better than time-based tracking
2. **Automatic Detection**: No manual status updates needed
3. **Progress Tracking**: Built-in completion percentage calculation
4. **Business Reality**: Reflects actual value delivery

### Automatic Status Update Logic
```sql
-- Daily process to update job statuses
UPDATE jobs SET status = 'IN_PROGRESS' 
WHERE accumulated_daily_output > 0 AND accumulated_daily_output < job_quantity;

UPDATE jobs SET status = 'COMPLETED' 
WHERE accumulated_daily_output >= job_quantity;
```

## Scheduling Time Window Management

### Core Principle: Never Modify Past Schedules

**Schedule Creation Rule**:
```
Schedule start date = MAX(TODAY, job.earliest_possible_start_date)
```

### Why This Approach is Critical

1. **Historical Data Integrity**: Past schedules represent actual planning decisions
2. **Operational Reality**: Past work has already been executed
3. **Performance Measurement**: Need original schedules to measure accuracy
4. **Compliance**: Audit trails must show original planning decisions

### Data Loading for Optimization
```sql
SELECT * FROM jobs 
WHERE lcd_date >= TODAY 
  AND status IN ('PLANNED', 'IN_PROGRESS') 
  AND scheduled_start_date >= TODAY
```

### Exception Handling
- **Delayed Jobs**: Reschedule past-due PLANNED jobs to start TODAY
- **In-Progress Jobs**: Don't change start times, adjust remaining work only
- **Emergency Changes**: Schedule rush orders for TODAY or ASAP
- **Equipment Issues**: Reschedule affected future work only

## Recommended Implementation Roadmap

### Phase 1: Data Pipeline Foundation (Immediate - 2 weeks)
1. **Missing Value Handling**:
   - Implement business rule-based imputation
   - Add data quality confidence scoring
   - Create missing value handling framework

2. **Enhanced Database Schema**:
   ```sql
   ALTER TABLE tbl_aa_job ADD COLUMN status ENUM('PLANNED', 'IN_PROGRESS', 'COMPLETED') DEFAULT 'PLANNED';
   ALTER TABLE tbl_aa_job ADD COLUMN data_quality_score DECIMAL(3,2) DEFAULT 1.00;
   ALTER TABLE tbl_aa_job ADD COLUMN imputation_flags JSON;
   ```

3. **Automatic Status Updates**:
   - Daily process to update job statuses based on daily_output
   - Integration with scheduling system

### Phase 2: Data Quality Framework (1-2 months)
1. **Data Profiling**:
   - Systematic analysis of data completeness
   - Outlier detection for processing times
   - Data consistency validation

2. **Monitoring Dashboard**:
   - Data quality metrics visualization
   - Missing value patterns analysis
   - Schedule performance tracking

3. **Alerting System**:
   - Real-time alerts for critical missing data
   - Daily data quality reports
   - Exception handling procedures

### Phase 3: Advanced Features (3-6 months)
1. **Machine Learning Enhancements**:
   - Predictive processing time models
   - Demand forecasting integration
   - Performance-based parameter tuning

2. **Real-time Integration**:
   - Live production data feeds
   - Dynamic schedule adjustments
   - IoT sensor integration planning

3. **Advanced Analytics**:
   - Schedule vs. actual performance analysis
   - Continuous improvement recommendations
   - Predictive maintenance integration

## Performance Monitoring Framework

### Key Metrics to Track

#### Data Quality Metrics
- **Completeness Rate**: Percentage of non-missing values by field
- **Accuracy Score**: Validation success rate
- **Timeliness**: Data freshness and update frequency
- **Consistency**: Cross-field validation success rate

#### Scheduling Performance
- **Schedule Adherence**: Actual vs. planned start/end times
- **Job Completion Rate**: Percentage of jobs completed on time
- **Resource Utilization**: Machine and operator efficiency
- **Schedule Stability**: Frequency of emergency reschedules

#### System Performance
- **Solver Runtime**: Time to generate optimal schedules
- **Data Processing Time**: Pipeline execution duration
- **System Availability**: Uptime and reliability metrics
- **User Adoption**: Status update frequency and accuracy

### Continuous Improvement Process

1. **Weekly Performance Reviews**:
   - Analyze schedule vs. actual performance
   - Identify data quality issues
   - Review optimization effectiveness

2. **Monthly System Optimization**:
   - Tune solver parameters based on performance
   - Update missing value imputation rules
   - Refine data loading strategies

3. **Quarterly Strategic Assessment**:
   - Evaluate system ROI and business impact
   - Plan infrastructure improvements
   - Update machine learning models

## Conclusion

The AI Optimizer project has a solid foundation as an ML-powered scheduling system, but requires significant enhancement to become a production-ready data pipeline. The current 20% pipeline completion needs to be expanded to include robust data quality management, comprehensive missing value handling, and continuous performance monitoring.

Key priorities:
1. **Immediate**: Implement missing value handling strategies
2. **Short-term**: Build data quality monitoring framework
3. **Medium-term**: Add advanced ML features and real-time integration
4. **Long-term**: Develop predictive capabilities and autonomous optimization

The quantity-based job completion tracking and forward-only scheduling principles are excellent design decisions that provide a strong foundation for the enhanced system architecture.

---

*This analysis represents the current state and recommended evolution path for the AI Optimizer project as of May 31, 2025.*