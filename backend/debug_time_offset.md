# Debug Report: 1-Hour Time Offset Issue (6:30 AM → 7:30 AM)

## Issue Summary
Jobs are being scheduled at 7:30 AM instead of the expected 6:30 AM, despite database showing working hours start at 06:30:00.

## Analysis of Potential Root Causes

### 1. Time Zone Issues
**Location**: `/Users/carrickcheah/Project/ai_optimizer/backend/app/utils/time_utils.py` lines 15-16, 24-25

```python
SINGAPORE_TZ = timezone(timedelta(hours=8))  # UTC+8
REFERENCE_TIME = initialize_reference_time()  # Uses SINGAPORE_TZ
```

**Issue**: If the system clock or database is in a different timezone than Singapore (UTC+8), there could be timezone conversion errors causing the 1-hour offset.

### 2. Setup Time Addition
**Location**: `/Users/carrickcheah/Project/ai_optimizer/backend/app/scheduling/cpsat_solver.py` lines 369-376

```python
setup_time = job_item.get('setup_time') or job_item.get('setting_hours', 0)
if setup_time:
    try:
        if 'setup_time' in job_item:
            total_hours += float(setup_time) / 3600  # Convert seconds to hours
        else:
            total_hours += float(setup_time)  # Already in hours
```

**Issue**: If `setup_time` is being incorrectly interpreted (e.g., 3600 seconds = 1 hour being added to job duration), this could cause jobs to start later than expected.

### 3. Working Hours Time Conversion
**Location**: `/Users/carrickcheah/Project/ai_optimizer/backend/app/scheduling/cpsat_solver.py` lines 573-574

```python
start_hour = start_time.hour + start_time.minute / 60.0
end_hour = end_time.hour + end_time.minute / 60.0
```

**Issue**: The conversion from database time (06:30:00) to decimal hours (6.5) appears correct, but there might be an issue in how this is applied.

### 4. Time Availability Adjustment
**Location**: `/Users/carrickcheah/Project/ai_optimizer/backend/app/scheduling/cpsat_solver.py` lines 850-867

```python
if not is_time_available(start_epoch, end_epoch):
    # Find next available slot
    next_available_start = get_next_available_slot(start_epoch, duration_hours)
    if next_available_start:
        new_start_epoch = next_available_start
        start_epoch = new_start_epoch
```

**Issue**: The post-processing step that checks time availability and adjusts times might be pushing jobs forward by 1 hour if there's a discrepancy between the CP-SAT constraint logic and the time availability checker.

### 5. Break Time Interference
**Location**: `/Users/carrickcheah/Project/ai_optimizer/backend/app/scheduling/time_availability.py` lines 227-249

The time availability checker also considers break times, which could push jobs forward if there's a break period at 6:30 AM.

## Debugging Steps Required

1. **Check Database Working Hours**: Verify the exact `start_time` and `end_time` values in `ai_arrangable_hour` table
2. **Check Time Zone Configuration**: Verify system timezone vs Singapore timezone
3. **Check Setup Time Values**: Look for jobs with `setup_time` or `setting_hours` values
4. **Check Break Time Configuration**: Verify `ai_breaktimes` table for any conflicts at 6:30 AM
5. **Add Debug Logging**: Add logs to track the exact time conversions through the pipeline

## Immediate Investigation Needed

1. **Working Hours Database Query**:
```sql
SELECT arrange_day, start_time, end_time, is_working 
FROM ai_arrangable_hour 
WHERE is_working = 1 
ORDER BY arrange_day, start_time;
```

2. **Break Times Database Query**:
```sql
SELECT name, start_time, end_time, is_active 
FROM ai_breaktimes 
WHERE is_active = 1 
ORDER BY start_time;
```

3. **Check for Setup Times in Job Data**:
Look for jobs with non-zero `setup_time` or `setting_hours` values that might be adding 1 hour to the schedule.

## Most Likely Cause
Based on the code analysis, the most likely cause is either:
1. **Time zone conversion error** between the database timezone and Singapore timezone
2. **Setup time addition** where 1 hour (3600 seconds) is being added to job durations
3. **Time availability post-processing** pushing jobs forward due to a discrepancy in time checking logic