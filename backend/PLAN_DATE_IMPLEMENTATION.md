# Plan Date Implementation - Job Scheduling Improvements

## Problem Statement
Jobs were being scheduled late even when entered early. For example, job JOST25050285 with plan_date 2025-05-30 was scheduled to start on 2025-06-20 (21 days late).

## Root Cause
The scheduler was ignoring plan_date and always starting from the current system time, causing jobs to be scheduled late unnecessarily.

## Implemented Solution

### 1. Plan Date Loading (mariadb_parser.py)
- Added plan_date_epoch conversion for all jobs
- Jobs now have both plan_date and plan_date_epoch fields

### 2. Urgency-Based Sorting (greedy_solver.py)
- Added `_sort_jobs_by_urgency()` method that considers:
  - Days overdue from plan_date 
  - Time ratio between overdue days and remaining time to LCD
  - Jobs past their plan_date get highest priority
- Replaced LCD-only sorting with urgency sorting in all scheduling methods

### 3. Plan Date Aware Scheduling (greedy_solver.py)
- Modified start time calculation: `start_time = max(machine_available, plan_date)`
- Added warnings when jobs are scheduled past their plan_date
- Applied to all job types: independent, dependency, subcontractor

### 4. Late Job Analysis (late_job_analyzer.py)
- Created analyzer to identify jobs scheduled past plan dates
- Provides statistics and detailed reports
- Added API endpoint: `/api/reports/late-jobs-analysis`

## Key Benefits

1. **Early Planning Rewarded**: Jobs entered early will be scheduled to start on their plan date
2. **Overdue Jobs Prioritized**: Jobs past their plan date are scheduled first
3. **Visibility**: Clear warnings and reports show which jobs are late
4. **Proactive Scheduling**: System no longer waits until last minute

## API Usage

```bash
# Check late jobs
curl "http://localhost:8000/api/reports/late-jobs-analysis"

# Response includes:
# - total_scheduled: Total jobs scheduled
# - late_jobs_count: Number of late jobs  
# - late_percentage: Percentage of jobs that are late
# - worst_late_jobs: Top 10 most delayed jobs
```

## Important Notes

1. The scheduler cannot schedule jobs in the past - if plan_date has passed, the job starts ASAP
2. All jobs are scheduled even if late (no jobs are skipped due to LCD constraints)
3. Plan date is a preference, not a hard constraint - machine availability still matters

## Future Enhancements

1. **Backward Scheduling**: Calculate optimal start time working backward from LCD date
2. **Buffer Management**: Add configurable buffer days based on job entry lead time
3. **Capacity Planning**: Show warnings when plan dates cannot be met due to capacity
4. **Plan Date Optimization**: Suggest better plan dates based on current workload