-- Performance Comparison: Before vs After Indexes

-- === CURRENT PERFORMANCE (WITH INDEXES) ===
SET profiling = 1;

SELECT COUNT(*) as with_indexes_count
FROM tbl_jo_process AS jop 
INNER JOIN tbl_jo_txn AS jot ON jot.TxnId_i = jop.TxnId_i 
LEFT JOIN tbl_daily_item AS di ON di.JoId_i = jop.TxnId_i 
WHERE jot.Void_c != 1 
  AND jot.TargetDate_dd >= CURDATE() 
  AND jot.TargetDate_dd <= DATE_ADD(CURDATE(), INTERVAL 60 DAY)
  AND jop.QtyStatus_c != 'FF';

-- === SIMULATE BEFORE (DROP ONE KEY INDEX) ===
DROP INDEX idx_jo_txn_target_date ON tbl_jo_txn;

SELECT COUNT(*) as without_key_index_count
FROM tbl_jo_process AS jop 
INNER JOIN tbl_jo_txn AS jot ON jot.TxnId_i = jop.TxnId_i 
LEFT JOIN tbl_daily_item AS di ON di.JoId_i = jop.TxnId_i 
WHERE jot.Void_c != 1 
  AND jot.TargetDate_dd >= CURDATE() 
  AND jot.TargetDate_dd <= DATE_ADD(CURDATE(), INTERVAL 60 DAY)
  AND jop.QtyStatus_c != 'FF';

-- === RESTORE THE INDEX ===
CREATE INDEX idx_jo_txn_target_date ON tbl_jo_txn(TargetDate_dd);

-- Show timing comparison
SHOW PROFILES;

-- Clear profiling
SET profiling = 0;