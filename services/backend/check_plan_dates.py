#!/usr/bin/env python3
"""Script to check unique plan dates in the database"""

import sys
sys.path.append('.')

from app.utils.database import get_db_connection_from_pool

def check_plan_dates():
    """Check unique plan dates in database"""
    with get_db_connection_from_pool() as conn:
        cursor = conn.cursor(dictionary=True)
        
        # Check unique plan dates (CreateDate_dt)
        cursor.execute("""
            SELECT 
                DATE(jot.CreateDate_dt) as plan_date_only,
                COUNT(*) as job_count,
                MIN(jot.CreateDate_dt) as earliest_time,
                MAX(jot.CreateDate_dt) as latest_time
            FROM tbl_jo_process AS jop 
            INNER JOIN tbl_jo_txn AS jot ON jot.TxnId_i = jop.TxnId_i 
            WHERE jot.Void_c != 1 
                AND jot.DocStatus_c != 'CP' 
                AND jop.QtyStatus_c != 'FF' 
            GROUP BY DATE(jot.CreateDate_dt) 
            ORDER BY plan_date_only DESC 
            LIMIT 10
        """)
        
        results = cursor.fetchall()
        print("Plan Date Distribution:")
        print("=====================")
        for row in results:
            print(f"{row['plan_date_only']}: {row['job_count']} jobs (from {row['earliest_time']} to {row['latest_time']})")
        
        # Check some sample actual values
        cursor.execute("""
            SELECT 
                jot.CreateDate_dt as plan_date,
                jot.DocRef_v as job_name,
                jop.Task_v as process_code
            FROM tbl_jo_process AS jop 
            INNER JOIN tbl_jo_txn AS jot ON jot.TxnId_i = jop.TxnId_i 
            WHERE jot.Void_c != 1 
                AND jot.DocStatus_c != 'CP' 
                AND jop.QtyStatus_c != 'FF' 
            ORDER BY jot.CreateDate_dt DESC
            LIMIT 5
        """)
        
        samples = cursor.fetchall()
        print("\nSample Jobs:")
        print("============")
        for sample in samples:
            print(f"{sample['job_name']}_{sample['process_code']}: {sample['plan_date']}")

if __name__ == "__main__":
    check_plan_dates() 