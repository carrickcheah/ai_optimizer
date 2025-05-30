# Rolling Window Data Loading Strategy Implementation

## Overview

This document describes the implementation of the intelligent rolling window data loading strategy for the AI Optimizer job scheduling system, based on LCD_DATE (deadline) filtering.

## Implementation Details

### Core Strategy

The system now loads production jobs using a **rolling window based on LCD_DATE** instead of loading all jobs or using arbitrary date ranges.

### Key Components

#### 1. Production Schedule Endpoint Enhancement

**Endpoint**: `/production-jobs/production-schedule`

**New Parameters**:
- `buffer_days` (default: 7): Days before today for late jobs 
- `planning_horizon_days` (default: 60): Days ahead for planning horizon

**SQL Logic**:
```sql
WHERE jot.TargetDate_dd BETWEEN DATE_SUB(CURDATE(), INTERVAL {buffer_days} DAY) 
                           AND DATE_ADD(CURDATE(), INTERVAL {planning_horizon_days} DAY)
AND (
    (jot.TargetDate_dd < CURDATE() AND (jot.JoQty_d - COALESCE(di.Qty_d, 0)) > 0)
    OR jot.TargetDate_dd >= CURDATE()
)
```

#### 2. Job Categories Included

1. **Urgent/Late Jobs**: 
   - `lcd_date < TODAY` (overdue jobs)
   - Status: Not completed (has remaining quantity)
   
2. **Current Planning Window**:
   - `lcd_date BETWEEN TODAY AND (TODAY + planning_horizon_days)`
   - Status: Not started or in progress
   
3. **Buffer for Flexibility**:
   - `lcd_date BETWEEN (TODAY - buffer_days) AND TODAY`
   - Status: Not completed (recently overdue)

#### 3. Job Categories Excluded

1. **Far Future Jobs**: `lcd_date > (TODAY + planning_horizon_days)`
2. **Completed Jobs**: `DocStatus_c = 'CP'` or `QtyStatus_c = 'FF'`
3. **Very Old Jobs**: `lcd_date < (TODAY - buffer_days)`

### Adaptive Horizon Management

#### 1. Data Loading Statistics Endpoint

**Endpoint**: `/production-jobs/data-loading-stats`

**Provides**:
- Job distribution analysis
- Average lead time calculations  
- OR-Tools performance estimates
- Adaptive recommendations

#### 2. Recommendation Logic

Based on average lead times:
- ≤ 2 weeks → 6 weeks planning horizon
- ≤ 4 weeks → 12 weeks planning horizon  
- > 4 weeks → 16 weeks planning horizon

Buffer days = 30% of average lead time (min 3, max 14 days)

## Business Benefits

### 1. Performance Optimization
- **Reduced Problem Size**: Focuses on time-critical jobs only
- **OR-Tools Efficiency**: Keeps variables under 10,000 for optimal performance
- **Faster Response Times**: Smaller datasets = faster queries

### 2. Business Logic Alignment
- **Deadline-Focused**: Scheduling fundamentally about meeting deadlines
- **Urgency Prioritization**: Late jobs get immediate attention
- **Practical Horizons**: Production managers work in 4-12 week windows

### 3. Operational Benefits
- **Emergency Handling**: Rush orders can be accommodated
- **Resource Planning**: Appropriate visibility for capacity planning
- **Data Quality**: Reduces noise from irrelevant far-future jobs

## Configuration Examples

### Phase 1: Basic Implementation (Current)
```
buffer_days: 7
planning_horizon_days: 60
refresh: Manual/on-demand
```

### Phase 2: Enhanced Logic (Future)
```
buffer_days: Adaptive based on lead times
planning_horizon_days: Adaptive based on workload
refresh: Every 4 hours
priority_extension: Rush jobs beyond horizon
```

### Phase 3: Advanced Optimization (Future)
```
buffer_days: ML-predicted optimal
planning_horizon_days: Dynamic based on performance
refresh: Real-time based on job arrival patterns
```

## API Usage Examples

### Basic Usage
```bash
GET /production-jobs/production-schedule
# Uses defaults: buffer_days=7, planning_horizon_days=60
```

### Custom Window
```bash
GET /production-jobs/production-schedule?buffer_days=10&planning_horizon_days=90
# 10-day buffer, 90-day horizon
```

### Get Recommendations
```bash
GET /production-jobs/data-loading-stats
# Returns adaptive recommendations and performance metrics
```

## Response Format

### Production Schedule Response
```json
{
  "items": [...],
  "total_items": 250,
  "page": 1,
  "page_size": 50,
  "total_pages": 5,
  "data_loading_config": {
    "buffer_days": 7,
    "planning_horizon_days": 60,
    "date_range": {
      "start_date": "TODAY - 7 days",
      "end_date": "TODAY + 60 days"
    }
  }
}
```

### Statistics Response
```json
{
  "statistics": {
    "total_jobs": 1000,
    "active_jobs": 250,
    "overdue_jobs": 15,
    "avg_lead_time_days": 21.5,
    "job_distribution": {
      "next_30_days": 120,
      "next_60_days": 200,
      "next_90_days": 250
    }
  },
  "recommendations": {
    "buffer_days": 6,
    "planning_horizon_days": 84,
    "reasoning": {
      "buffer_logic": "Based on 28% of average lead time",
      "horizon_logic": "Based on 21.5 day average lead time"
    }
  },
  "or_tools_optimization": {
    "estimated_variables": 1250,
    "performance_level": "optimal",
    "solver_time_estimate": "< 30 seconds"
  }
}
```

## Monitoring and Maintenance

### Key Metrics to Track
1. **Schedule Quality**: Actual vs. planned performance
2. **System Performance**: Query response times, solver performance
3. **Data Coverage**: % of jobs within planning horizon
4. **Business Impact**: On-time delivery rates

### Warning Conditions
- OR-Tools variables > 10,000 (performance impact)
- Overdue jobs > 100 (planning issues)
- Average lead time > 60 days (process issues)

### Maintenance Tasks
- **Daily**: Monitor job distribution and performance
- **Weekly**: Review adaptive recommendations
- **Monthly**: Analyze schedule adherence and adjust horizons

## Testing

Use the provided test script:
```bash
python test_data_loading.py
```

This tests various parameter combinations and validates the statistical analysis functionality.

## Future Enhancements

1. **Real-time Refresh**: Automatic updates based on job arrival patterns
2. **Machine Learning**: Predictive horizon optimization
3. **Multi-facility Support**: Different horizons per facility
4. **Integration**: MES/ERP system data feeds
5. **Advanced Analytics**: Predictive completion estimates 