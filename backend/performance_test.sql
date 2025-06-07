-- Performance Testing - Before/After Index Comparison

-- Enable query timing
SET profiling = 1;

-- Test 1: Simple JOIN performance
SELECT COUNT(*) as simple_join_count
FROM tbl_jo_process AS jop 
INNER JOIN tbl_jo_txn AS jot ON jot.TxnId_i = jop.TxnId_i 
WHERE jot.Void_c != 1 
  AND jot.TargetDate_dd >= CURDATE() 
  AND jot.TargetDate_dd <= DATE_ADD(CURDATE(), INTERVAL 60 DAY);

-- Test 2: Full complex query (simplified to avoid syntax issues)
SELECT COUNT(*) as full_query_count
FROM tbl_jo_process AS jop 
INNER JOIN tbl_jo_txn AS jot ON jot.TxnId_i = jop.TxnId_i 
LEFT JOIN tbl_daily_item AS di ON di.JoId_i = jop.TxnId_i 
WHERE jot.Void_c != 1 
  AND jot.TargetDate_dd >= CURDATE() 
  AND jot.TargetDate_dd <= DATE_ADD(CURDATE(), INTERVAL 60 DAY)
  AND jop.QtyStatus_c != 'FF';

-- Show timing results
SHOW PROFILES;

-- Show current indexes being used
SHOW INDEX FROM tbl_jo_txn WHERE Key_name LIKE 'idx_%';
SHOW INDEX FROM tbl_jo_process WHERE Key_name LIKE 'idx_%';
SHOW INDEX FROM tbl_machine WHERE Key_name LIKE 'idx_%';