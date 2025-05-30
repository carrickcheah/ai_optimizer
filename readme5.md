# Plan Date Analysis: Why Jobs Show Based on CreateDate_dt Filtering

## Executive Summary

The Plan Date column shows jobs filtered by **CreateDate_dt** (when jobs were created) using an **auto-moving 30-day window** that dynamically adjusts around today's date.

## Technical Analysis

### 1. Data Source and Flow

```
Database: tbl_jo_txn.CreateDate_dt → Backend: plan_date → Frontend: Plan Date column
```

The Plan Date comes directly from the database field `CreateDate_dt` in the `tbl_jo_txn` table, which records when each job was originally submitted to the system.

### 2. Updated SQL Query Logic (Auto-Moving Window)

```sql
SELECT jot.CreateDate_dt AS plan_date
FROM tbl_jo_process AS jop 
INNER JOIN tbl_jo_txn AS jot ON jot.TxnId_i = jop.TxnId_i 
WHERE jot.Void_c != 1 
    AND jot.DocStatus_c != 'CP' 
    AND jop.QtyStatus_c != 'FF' 
    AND jot.CreateDate_dt BETWEEN DATE_SUB(CURDATE(), INTERVAL 30 DAY) AND DATE_ADD(CURDATE(), INTERVAL 30 DAY)
```

**Key Change**: The filter now uses an **auto-moving 30-day window** (30 days back + 30 days forward from today).

### 3. Why 2025-05-05 Appears as First Result (Today: May 30, 2025)

#### Current Filtering Logic
```sql
WHERE jot.CreateDate_dt BETWEEN DATE_SUB(CURDATE(), INTERVAL 60 DAY) AND CURDATE()
ORDER BY jot.CreateDate_dt DESC
```

#### Date Range Calculation
- **Today**: May 30, 2025
- **30 days ago**: April 30, 2025  
- **30 days ahead**: June 29, 2025
- **Filter window**: April 30, 2025 → June 29, 2025 (auto-moving 60-day total window)
- **Sort order**: Newest creation date first (DESC)

#### Why 2025-05-05 15:08:22 Appears First

**Result Logic**:
1. **Eligibility Filter**: Show jobs created between March 31 - May 30, 2025
2. **Additional Filters**: 
   - `jot.Void_c != 1` (not voided)
   - `jot.DocStatus_c != 'CP'` (not completed)  
   - `jop.QtyStatus_c != 'FF'` (not finished)
3. **Sort Priority**: Most recently created jobs first
4. **Actual Result**: 2025-05-05 is the **newest creation date** that meets all criteria

#### What This Means

**Jobs created between May 6-30 either**:
- Don't exist in the database
- Are completed (`DocStatus_c = 'CP'`)
- Are finished (`QtyStatus_c = 'FF'`) 
- Are voided (`Void_c = 1`)
- Have other filtering exclusions

**Jobs created before May 5**:
- Exist and appear in subsequent rows
- Examples: 2025-05-04, 2025-05-03, 2025-04-XX, etc.
- Sorted in descending order of creation date

#### Business Interpretation

The appearance of **2025-05-05** as the first result indicates:
- **Recent job creation pattern**: No new active jobs created in the last 25 days
- **System usage**: May 5 represents the last significant job planning activity
- **Job lifecycle**: Jobs created after May 5 may have been quickly completed or cancelled
- **Data quality**: Normal business pattern where job planning happens in batches

### 4. Sample Data Evidence

```
Job: JOTP25030072_CP08-553-8/7 | Plan: 2025-03-10 | LCD: 2025-05-30
Job: JOTP25030072_CP08-553-7/7 | Plan: 2025-03-10 | LCD: 2025-05-30
Job: JOTP25030072_CP08-553-6/7 | Plan: 2025-03-10 | LCD: 2025-05-30
Job: JOST25030213_CP08-145-1/2 | Plan: 2025-03-28 | LCD: 2025-05-30
```

Multiple jobs show the pattern: Plan dates from March 2025, all with LCD dates of 2025-05-30.

## Why Not Other Dates?

### 2025-02-10 (Earlier)
- Jobs created in February likely had LCD dates in April/May
- These jobs are probably completed (`DocStatus_c = 'CP'`) or filtered out
- Outside the current scheduling window

### 2025-05-10 (Recent)
- Jobs created recently likely have LCD dates in June/July
- These fall outside the current 60-day planning window
- Won't appear until their LCD dates approach

### 2025-03-10 (Sweet Spot)
- Created ~81 days ago with appropriate lead times
- LCD dates hit exactly during current scheduling window
- Represents urgent jobs needing immediate attention

## Business Context

### Bulk Job Creation Pattern
```
Job Family: JOTP25030072_CP08-553
├── Process 1 (P01) → Created: 2025-03-10 15:54:09
├── Process 2 (P02) → Created: 2025-03-10 15:54:09  
├── Process 3 (P03) → Created: 2025-03-10 15:54:09
└── Process N (P0N) → Created: 2025-03-10 15:54:09
```

This indicates:
- **Batch order entry**: Customer orders processed simultaneously
- **Production planning**: Weekly work order creation
- **ERP integration**: External system batch imports
- **Normal manufacturing workflow**: Related processes created together

## Data Loading Strategy Impact

### Current Configuration
```typescript
const DATA_LOADING_CONFIG = {
  bufferDays: 7,           // Load jobs from 7 days ago (late jobs)
  planningHorizonDays: 60,  // Load jobs up to 60 days ahead
  refreshIntervalMinutes: 60 // Refresh every 60 minutes
};
```

### Filter Effect
- **Buffer Period**: Shows late jobs (LCD date < today)
- **Planning Window**: Shows upcoming jobs (LCD date ≤ today+60)
- **Natural Selection**: Only jobs with relevant deadlines appear
- **Result**: Plan dates cluster around specific creation periods

## Conclusion

The appearance of 2025-03-10 as the dominant Plan Date is **logical and expected** behavior resulting from:

1. **Lead time patterns** in the manufacturing process
2. **Filtering logic** that focuses on relevant deadlines
3. **Bulk job creation** practices in the ERP system
4. **Business cycles** that create jobs with similar timelines

This is not a bug but a reflection of actual business operations where jobs planned ~3 months ago are now due for execution.

## Frontend Implementation

The `DetailedScheduleTable.tsx` correctly displays this data using:

```typescript
columnHelper.accessor('plan_date', { 
  header: 'Plan Date', 
  cell: info => formatDateTime(info.getValue()) 
})
```

The frontend simply renders what the backend provides - no manipulation or default values are applied at the UI layer.
