Previously xxxxxxxx load from tbl_aa_job, but now I want change. Replace completely with sql query below:


    SELECT jot.TargetDate_dd AS LCD_DATE, jot.DocRef_v AS JOB, jop.Task_v AS PROCESS_CODE, '' AS RSC_LOCATION, jop.Machine_v AS RSC_CODE, jop.ManCount_i AS NUMBER_OPERATOR, jot.JoQty_d AS JOB_QUANTITY, CASE WHEN jop.CapMin_d = 1 AND jop.CapQty_d != 0 THEN jop.CapQty_d * 60 ELSE NULL END AS EXPECT_OUTPUT_PER_HOUR, CASE WHEN jop.CapMin_d = 1 AND jop.CapQty_d != 0 THEN jot.JoQty_d / (jop.CapQty_d * 60) ELSE NULL END AS HOURS_NEED, CASE WHEN jop.CapMin_d = 1 AND jop.CapQty_d != 0 THEN jot.JoQty_d / (jop.CapQty_d * 60 * 24) WHEN jop.CapMin_d = 0 AND jop.LeadTime_d != 0 THEN jop.LeadTime_d ELSE NULL END AS DAY_NEED, jop.SetupTime_d AS SETTING_HOURS, 1 AS BREAK_HOURS, 8 AS NO_PROD, '' AS START_DATE, di.Qty_d AS ACCUMULATED_DAILY_OUTPUT, (jot.JoQty_d - COALESCE(di.Qty_d, 0)) AS BALANCE_QUANTITY, jop.TxnId_i FROM tbl_jo_process AS jop INNER JOIN tbl_jo_txn AS jot ON jot.TxnId_i = jop.TxnId_i LEFT JOIN tbl_daily_item AS di ON di.JoId_i = jop.TxnId_i AND di.ProcessrowId_i = jop.RowId_i WHERE jot.Void_c != 1 AND jot.DocStatus_c != 'CP' AND jop.QtyStatus_c != 'FF' AND jot.TargetDate_dd BETWEEN DATE_SUB(CURDATE(), INTERVAL 5 DAY) AND DATE_ADD(CURDATE(), INTERVAL 60 DAY) ORDER BY jot.TargetDate_dd, jot.DocRef_v, jop.Task_v



Max load 50 row per page.

    #jobsTable th:nth-child(1) { width: 6%; }  /* LCD DATE */
    #jobsTable th:nth-child(2) { width: 5%; }  /* TXN ID */ (Replace with)
    #jobsTable th:nth-child(3) { width: 7%; }  /* START DATE */
    #jobsTable th:nth-child(4) { width: 7%; }  /* MATERIAL ARRIVAL */
    #jobsTable th:nth-child(5) { width: 6%; } /* JOB */ 
    #jobsTable th:nth-child(6) { width: 5%; }  /* PROCESS CODE */
    #jobsTable th:nth-child(7) { width: 4%; }  /* RSC LOCATION */
    #jobsTable th:nth-child(8) { width: 4%; }  /* RSC CODE */
    #jobsTable th:nth-child(9) { width: 4%; }  /* JOB DEPEND */
    #jobsTable th:nth-child(10) { width: 4%; } /* NUMBER OPERATOR */
    #jobsTable th:nth-child(11) { width: 4%; } /* JOB QUANTITY */
    #jobsTable th:nth-child(12) { width: 4%; } /* DAILY OUTPUT */
    #jobsTable th:nth-child(13) { width: 4%; }  /* BALANCE QUANTITY*/
    #jobsTable th:nth-child(14) { width: 4%; } /* HOURS NEED */
    #jobsTable th:nth-child(15) { width: 4%; } /* DAY NEED */ 
    #jobsTable th:nth-child(16) { width: 4%; } /* SETTING HOURS */
    #jobsTable th:nth-child(17) { width: 4%; } /* BREAK HOURS */
    #jobsTable th:nth-child(18) { width: 3%; } /* NO PROD */
    #jobsTable th:nth-child(19) { width: 3%; } /* PRIORITY */
    #jobsTable th:nth-child(20) { width: 3%; } /* REDUCE HRS */
    #jobsTable th:nth-child(21) { width: 11%; } /* ACTIONS */







