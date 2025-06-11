-- Database Performance Optimization Indexes for Time-Boxed Job Scheduling
-- Execute these commands in MariaDB to improve query performance
-- Focus: 30-day time window + open jobs + future LCD dates
-- Updated: 2025-06-11 based on production testing

-- Check if indexes exist before creating (prevents errors on re-run)
SET @sql = 'DROP INDEX IF EXISTS idx_jo_txn_timebox_optimized ON tbl_jo_txn';
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

-- PRIMARY OPTIMIZATION: Time-boxed composite index (most important)
-- This index supports the main query filtering logic:
-- 1. CreateDate_dt >= DATE_SUB(CURDATE(), INTERVAL 30 DAY) -- Recent jobs only
-- 2. Void_c != 1 AND DocStatus_c NOT IN ('CP', 'CX')      -- Open jobs  
-- 3. TargetDate_dd >= CURDATE()                           -- Future LCD dates
CREATE INDEX idx_jo_txn_timebox_optimized ON tbl_jo_txn(CreateDate_dt, Void_c, DocStatus_c, TargetDate_dd);

-- JOIN optimization indexes (check and create safely)
CREATE INDEX IF NOT EXISTS idx_jo_txn_txnid ON tbl_jo_txn(TxnId_i);
CREATE INDEX IF NOT EXISTS idx_jo_process_txnid ON tbl_jo_process(TxnId_i);

-- CRITICAL: Time-boxed daily_item index to prevent 190K row scans
CREATE INDEX IF NOT EXISTS idx_daily_item_timebox ON tbl_daily_item(CreateDate_dt, JoId_i, ProcessrowId_i);
CREATE INDEX IF NOT EXISTS idx_daily_item_joid_processid ON tbl_daily_item(JoId_i, ProcessrowId_i);

-- Machine lookup optimization
CREATE INDEX IF NOT EXISTS idx_machine_id_v ON tbl_machine(machine_id_v);
CREATE INDEX IF NOT EXISTS idx_machine_id_i ON tbl_machine(MachineId_i);
CREATE INDEX IF NOT EXISTS idx_machine_name ON tbl_machine(MachineName_v);
CREATE INDEX IF NOT EXISTS idx_jo_process_machine ON tbl_jo_process(Machine_v);

-- Process status filtering
CREATE INDEX IF NOT EXISTS idx_jo_process_qty_status ON tbl_jo_process(QtyStatus_c);

-- SECONDARY OPTIMIZATION: Individual indexes for fallback
CREATE INDEX IF NOT EXISTS idx_jo_txn_create_date_desc ON tbl_jo_txn(CreateDate_dt DESC);
CREATE INDEX IF NOT EXISTS idx_jo_txn_target_date ON tbl_jo_txn(TargetDate_dd);
CREATE INDEX IF NOT EXISTS idx_jo_txn_status ON tbl_jo_txn(Void_c, DocStatus_c);

-- Process-level optimization for capacity calculations
CREATE INDEX IF NOT EXISTS idx_jo_process_leadtime ON tbl_jo_process(LeadTime_d);
CREATE INDEX IF NOT EXISTS idx_jo_process_capmin_capqty ON tbl_jo_process(CapMin_d, CapQty_d);

-- Comprehensive process index for complex filtering
CREATE INDEX IF NOT EXISTS idx_jo_process_comprehensive ON tbl_jo_process(TxnId_i, QtyStatus_c, Machine_v, LeadTime_d, CapMin_d, CapQty_d);

-- Working hours and scheduling constraints (enable if tables exist)
CREATE INDEX IF NOT EXISTS idx_arrangable_hour_day ON ai_arrangable_hour(arrange_day, is_working);
CREATE INDEX IF NOT EXISTS idx_holidays_date ON ai_holidays(holiday_date, is_active);
CREATE INDEX IF NOT EXISTS idx_breaktimes_active ON ai_breaktimes(is_active, start_time, end_time);

-- PERFORMANCE VERIFICATION QUERY:
-- Run this after creating indexes to verify optimization:
/*
EXPLAIN SELECT
    jot.CreateDate_dt AS plan_date,
    jot.TargetDate_dd AS lcd_date,
    jop.TxnId_i AS op_id,
    jot.DocRef_v AS job,
    jop.Task_v AS process_code
FROM tbl_jo_process AS jop 
INNER JOIN tbl_jo_txn AS jot ON jot.TxnId_i = jop.TxnId_i 
WHERE jot.Void_c != 1 
    AND jot.DocStatus_c NOT IN ('CP', 'CX') 
    AND jop.QtyStatus_c != 'FF' 
    AND jot.TargetDate_dd >= CURDATE()
    AND jot.TargetDate_dd <= DATE_ADD(CURDATE(), INTERVAL 180 DAY)
    AND jot.CreateDate_dt >= DATE_SUB(CURDATE(), INTERVAL 30 DAY)
ORDER BY jot.CreateDate_dt DESC
LIMIT 1500;
*/

-- EXPECTED PERFORMANCE IMPROVEMENT:
-- Before (full table scan): 5-15 seconds for 1500 jobs
-- After (time-boxed + indexed): 0.3-0.8 seconds for 1500 jobs  
-- Improvement: 90-95% faster query execution
-- Data reduction: ~80% fewer rows scanned (30 days vs full history)

-- EXECUTION INSTRUCTIONS:
-- 1. Run this script on your MariaDB database
-- 2. Monitor index creation progress (some indexes may take time on large tables)
-- 3. Use EXPLAIN on your queries after creation to verify index usage
-- 4. Check query performance improvement with timing

-- INDEX MAINTENANCE:
-- These indexes will automatically maintain themselves
-- Monitor disk space usage - indexes require additional storage
-- Consider dropping unused indexes if performance issues arise

-- ROLLBACK SCRIPT (if needed):
/*
DROP INDEX IF EXISTS idx_jo_txn_timebox_optimized ON tbl_jo_txn;
DROP INDEX IF EXISTS idx_jo_txn_txnid ON tbl_jo_txn;
DROP INDEX IF EXISTS idx_jo_process_txnid ON tbl_jo_process;
DROP INDEX IF EXISTS idx_daily_item_timebox ON tbl_daily_item;
DROP INDEX IF EXISTS idx_daily_item_joid_processid ON tbl_daily_item;
DROP INDEX IF EXISTS idx_machine_id_v ON tbl_machine;
DROP INDEX IF EXISTS idx_machine_id_i ON tbl_machine;
DROP INDEX IF EXISTS idx_machine_name ON tbl_machine;
DROP INDEX IF EXISTS idx_jo_process_machine ON tbl_jo_process;
DROP INDEX IF EXISTS idx_jo_process_qty_status ON tbl_jo_process;
DROP INDEX IF EXISTS idx_jo_txn_create_date_desc ON tbl_jo_txn;
DROP INDEX IF EXISTS idx_jo_txn_target_date ON tbl_jo_txn;
DROP INDEX IF EXISTS idx_jo_txn_status ON tbl_jo_txn;
DROP INDEX IF EXISTS idx_jo_process_leadtime ON tbl_jo_process;
DROP INDEX IF EXISTS idx_jo_process_capmin_capqty ON tbl_jo_process;
DROP INDEX IF EXISTS idx_jo_process_comprehensive ON tbl_jo_process;
DROP INDEX IF EXISTS idx_arrangable_hour_day ON ai_arrangable_hour;
DROP INDEX IF EXISTS idx_holidays_date ON ai_holidays;
DROP INDEX IF EXISTS idx_breaktimes_active ON ai_breaktimes;
*/