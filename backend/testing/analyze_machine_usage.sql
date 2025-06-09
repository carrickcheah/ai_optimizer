-- Check machine assignment distribution for jobs in scheduler scope
SELECT 
    jop.Machine_v as machine_name,
    COUNT(*) as job_count,
    SUM(jop.CycleTime_d + jop.SetupTime_d) as total_hours_needed,
    COUNT(*) * 100.0 / (SELECT COUNT(*) FROM tbl_jo_txn jot2 
                        JOIN tbl_jo_process jop2 ON jot2.TxnId_i = jop2.TxnId_i
                        WHERE jot2.Void_c != 1 
                        AND jot2.DocStatus_c NOT IN ('CP', 'CX') 
                        AND jop2.QtyStatus_c != 'FF' 
                        AND jot2.TargetDate_dd >= CURDATE()
                        AND jot2.TargetDate_dd <= DATE_ADD(CURDATE(), INTERVAL 14 DAY)
                        AND jop2.Machine_v IS NOT NULL 
                        AND jop2.Machine_v != '') as percentage
FROM tbl_jo_txn jot
JOIN tbl_jo_process jop ON jot.TxnId_i = jop.TxnId_i
WHERE jot.Void_c != 1 
    AND jot.DocStatus_c NOT IN ('CP', 'CX') 
    AND jop.QtyStatus_c != 'FF' 
    AND jot.TargetDate_dd >= CURDATE()
    AND jot.TargetDate_dd <= DATE_ADD(CURDATE(), INTERVAL 14 DAY)
    AND jop.Machine_v IS NOT NULL 
    AND jop.Machine_v != ''
GROUP BY jop.Machine_v
ORDER BY total_hours_needed DESC
LIMIT 10;