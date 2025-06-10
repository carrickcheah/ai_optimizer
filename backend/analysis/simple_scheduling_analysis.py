#!/usr/bin/env python3
"""
Simple analysis script to identify constraints limiting job scheduling.
"""

import mysql.connector
from datetime import datetime
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Database configuration
DB_CONFIG = {
    'host': os.getenv("MARIADB_HOST", "localhost"),
    'user': os.getenv("MARIADB_USERNAME", "myuser"),
    'password': os.getenv("MARIADB_PASSWORD", "mypassword"),
    'database': os.getenv("MARIADB_DATABASE", "nex_valiant"),
    'port': int(os.getenv("MARIADB_PORT", "3306"))
}

def get_connection():
    """Get database connection"""
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        return conn
    except Exception as e:
        print(f"Database connection failed: {e}")
        return None

def main():
    """Main analysis function"""
    print("SCHEDULING CONSTRAINTS ANALYSIS")
    print("=" * 60)
    print(f"Database: {DB_CONFIG['host']}:{DB_CONFIG['port']}/{DB_CONFIG['database']}")
    print()
    
    conn = get_connection()
    if not conn:
        return
    
    cursor = conn.cursor(dictionary=True)
    
    try:
        # 1. Total jobs analysis
        print("1. TOTAL JOBS BREAKDOWN")
        print("-" * 30)
        
        cursor.execute("""
            SELECT COUNT(*) as total_jobs
            FROM tbl_jo_process jop 
            INNER JOIN tbl_jo_txn jot ON jot.TxnId_i = jop.TxnId_i 
        """)
        total = cursor.fetchone()['total_jobs']
        print(f"Total jobs in database: {total}")
        
        cursor.execute("""
            SELECT COUNT(*) as active_jobs
            FROM tbl_jo_process jop 
            INNER JOIN tbl_jo_txn jot ON jot.TxnId_i = jop.TxnId_i 
            WHERE jot.Void_c != 1 
                AND jot.DocStatus_c NOT IN ('CP', 'CX') 
                AND jop.QtyStatus_c != 'FF'
        """)
        active = cursor.fetchone()['active_jobs']
        print(f"Active jobs (not voided/completed/finished): {active}")
        
        cursor.execute("""
            SELECT COUNT(*) as horizon_jobs
            FROM tbl_jo_process jop 
            INNER JOIN tbl_jo_txn jot ON jot.TxnId_i = jop.TxnId_i 
            WHERE jot.Void_c != 1 
                AND jot.DocStatus_c NOT IN ('CP', 'CX') 
                AND jop.QtyStatus_c != 'FF' 
                AND jot.TargetDate_dd >= CURDATE()
                AND jot.TargetDate_dd <= DATE_ADD(CURDATE(), INTERVAL 180 DAY)
        """)
        horizon = cursor.fetchone()['horizon_jobs']
        print(f"Jobs within 180-day planning horizon: {horizon}")
        
        # 2. Machine assignment analysis
        print("\n2. MACHINE ASSIGNMENT ANALYSIS")
        print("-" * 40)
        
        cursor.execute("""
            SELECT 
                CASE 
                    WHEN jop.Machine_v IS NULL OR jop.Machine_v = '' OR jop.Machine_v = '0' THEN 'UNASSIGNED'
                    ELSE 'ASSIGNED'
                END as machine_status,
                COUNT(*) as job_count
            FROM tbl_jo_process jop 
            INNER JOIN tbl_jo_txn jot ON jot.TxnId_i = jop.TxnId_i 
            WHERE jot.Void_c != 1 
                AND jot.DocStatus_c NOT IN ('CP', 'CX') 
                AND jop.QtyStatus_c != 'FF' 
                AND jot.TargetDate_dd >= CURDATE()
                AND jot.TargetDate_dd <= DATE_ADD(CURDATE(), INTERVAL 180 DAY)
            GROUP BY machine_status
        """)
        
        for row in cursor.fetchall():
            print(f"  {row['machine_status']}: {row['job_count']} jobs")
        
        # 3. Lead time analysis
        print("\n3. LEAD TIME ANALYSIS")
        print("-" * 30)
        
        cursor.execute("""
            SELECT 
                CASE 
                    WHEN jop.LeadTime_d IS NULL OR jop.LeadTime_d = 0 THEN 'NO_LEADTIME'
                    WHEN jop.LeadTime_d > 0 THEN 'HAS_LEADTIME'
                END as leadtime_status,
                COUNT(*) as job_count,
                AVG(jop.LeadTime_d) as avg_leadtime
            FROM tbl_jo_process jop 
            INNER JOIN tbl_jo_txn jot ON jot.TxnId_i = jop.TxnId_i 
            WHERE jot.Void_c != 1 
                AND jot.DocStatus_c NOT IN ('CP', 'CX') 
                AND jop.QtyStatus_c != 'FF' 
                AND jot.TargetDate_dd >= CURDATE()
                AND jot.TargetDate_dd <= DATE_ADD(CURDATE(), INTERVAL 180 DAY)
            GROUP BY leadtime_status
        """)
        
        for row in cursor.fetchall():
            avg_lead = row['avg_leadtime'] if row['avg_leadtime'] else 0
            print(f"  {row['leadtime_status']}: {row['job_count']} jobs (avg: {avg_lead:.2f} days)")
        
        # 4. Schedulable jobs analysis (following mariadb_parser logic)
        print("\n4. SCHEDULABLE JOBS ANALYSIS")
        print("-" * 40)
        
        # Jobs that pass the scheduling filter
        cursor.execute("""
            SELECT COUNT(*) as schedulable_jobs
            FROM tbl_jo_process jop 
            INNER JOIN tbl_jo_txn jot ON jot.TxnId_i = jop.TxnId_i 
            LEFT JOIN tbl_machine tm ON (
                tm.machine_id_v = jop.Machine_v
                OR tm.MachineId_i = jop.Machine_v
                OR tm.MachineName_v = jop.Machine_v
            )
            WHERE jot.Void_c != 1 
                AND jot.DocStatus_c NOT IN ('CP', 'CX') 
                AND jop.QtyStatus_c != 'FF' 
                AND jot.TargetDate_dd >= CURDATE()
                AND jot.TargetDate_dd <= DATE_ADD(CURDATE(), INTERVAL 180 DAY)
                AND NOT (
                    (jop.Machine_v IS NULL OR jop.Machine_v = '' OR jop.Machine_v = '0' OR tm.MachineName_v IS NULL)
                    AND (jop.LeadTime_d IS NULL OR jop.LeadTime_d <= 0)
                )
        """)
        schedulable = cursor.fetchone()['schedulable_jobs']
        print(f"Jobs that would be schedulable: {schedulable}")
        
        # Jobs filtered out (NOT_ASSIGN without LeadTime)
        cursor.execute("""
            SELECT 
                COUNT(*) as filtered_jobs
            FROM tbl_jo_process jop 
            INNER JOIN tbl_jo_txn jot ON jot.TxnId_i = jop.TxnId_i 
            LEFT JOIN tbl_machine tm ON (
                tm.machine_id_v = jop.Machine_v
                OR tm.MachineId_i = jop.Machine_v
                OR tm.MachineName_v = jop.Machine_v
            )
            WHERE jot.Void_c != 1 
                AND jot.DocStatus_c NOT IN ('CP', 'CX') 
                AND jop.QtyStatus_c != 'FF' 
                AND jot.TargetDate_dd >= CURDATE()
                AND jot.TargetDate_dd <= DATE_ADD(CURDATE(), INTERVAL 180 DAY)
                AND (jop.Machine_v IS NULL OR jop.Machine_v = '' OR jop.Machine_v = '0' OR tm.MachineName_v IS NULL)
                AND (jop.LeadTime_d IS NULL OR jop.LeadTime_d <= 0)
        """)
        filtered = cursor.fetchone()['filtered_jobs']
        print(f"Jobs filtered out (no machine + no leadtime): {filtered}")
        
        # 5. Working hours table check
        print("\n5. WORKING HOURS CONSTRAINTS")
        print("-" * 40)
        
        cursor.execute("SHOW TABLES LIKE 'ai_arrangable_hour'")
        if cursor.fetchone():
            cursor.execute("SELECT COUNT(*) as count FROM ai_arrangable_hour")
            count = cursor.fetchone()['count']
            print(f"ai_arrangable_hour table exists with {count} records")
        else:
            print("ai_arrangable_hour table does not exist")
        
        cursor.execute("SHOW TABLES LIKE 'ai_holidays'")
        if cursor.fetchone():
            cursor.execute("SELECT COUNT(*) as count FROM ai_holidays WHERE holiday_date >= CURDATE()")
            count = cursor.fetchone()['count']
            print(f"ai_holidays table exists with {count} upcoming holidays")
        else:
            print("ai_holidays table does not exist")
        
        cursor.execute("SHOW TABLES LIKE 'ai_breaktimes'")
        if cursor.fetchone():
            cursor.execute("SELECT COUNT(*) as count FROM ai_breaktimes")
            count = cursor.fetchone()['count']
            print(f"ai_breaktimes table exists with {count} break records")
        else:
            print("ai_breaktimes table does not exist")
        
        print("\n" + "=" * 60)
        print("SUMMARY OF FINDINGS:")
        print("=" * 60)
        print(f"• Total jobs in horizon: {horizon}")
        print(f"• Schedulable jobs: {schedulable}")
        print(f"• Filtered jobs: {filtered}")
        print(f"• Gap (should investigate): {horizon - schedulable - filtered}")
        
        if schedulable < 306:
            print(f"\n⚠️  WARNING: Only {schedulable} jobs are schedulable, but system reports scheduling 306")
            print("   This suggests the scheduler might be processing different data or")
            print("   there might be additional filtering happening in the scheduler logic.")
        
    except Exception as e:
        print(f"Error during analysis: {e}")
    finally:
        cursor.close()
        conn.close()

if __name__ == "__main__":
    main()