#!/usr/bin/env python3
"""
Comprehensive analysis script to identify constraints limiting job scheduling.
Analyzing why only 306 out of 999 jobs are being scheduled.
"""

import mysql.connector
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import os
from dotenv import load_dotenv
import logging

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

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
        logger.error(f"Database connection failed: {e}")
        return None

def analyze_job_distribution():
    """Analyze the distribution of jobs by machine type and constraints"""
    conn = get_connection()
    if not conn:
        return
    
    cursor = conn.cursor(dictionary=True)
    
    print("=" * 80)
    print("JOB DISTRIBUTION ANALYSIS")
    print("=" * 80)
    
    try:
        # Total jobs in the system
        cursor.execute("""
            SELECT COUNT(*) as total_jobs
            FROM tbl_jo_process jop 
            INNER JOIN tbl_jo_txn jot ON jot.TxnId_i = jop.TxnId_i 
            WHERE jot.Void_c != 1 
                AND jot.DocStatus_c NOT IN ('CP', 'CX') 
                AND jop.QtyStatus_c != 'FF'
        """)
        total_jobs = cursor.fetchone()['total_jobs']
        print(f"Total jobs in system: {total_jobs}")
        
        # Jobs within planning horizon
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
        horizon_jobs = cursor.fetchone()['horizon_jobs']
        print(f"Jobs within planning horizon (180 days): {horizon_jobs}")
        
        # Analyze machine assignments
        cursor.execute("""
            SELECT 
                CASE 
                    WHEN jop.Machine_v IS NULL OR jop.Machine_v = '' OR jop.Machine_v = '0' THEN 'UNASSIGNED'
                    WHEN tm.MachineName_v IS NULL THEN 'NOT_ASSIGN'
                    ELSE 'ASSIGNED'
                END as machine_status,
                COUNT(*) as job_count,
                AVG(CASE WHEN jop.CapMin_d = 1 AND jop.CapQty_d != 0 
                         THEN jot.JoQty_d / (jop.CapQty_d * 60) 
                         ELSE NULL END) as avg_hours_need,
                AVG(jop.LeadTime_d) as avg_leadtime_days
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
            GROUP BY machine_status
            ORDER BY job_count DESC
        """)
        
        machine_distribution = cursor.fetchall()
        print("\nMachine Assignment Distribution:")
        print("-" * 60)
        for row in machine_distribution:
            print(f"{row['machine_status']:<12}: {row['job_count']:>6} jobs | "
                  f"Avg Hours: {row['avg_hours_need']:.2f if row['avg_hours_need'] else 'N/A':>8} | "
                  f"Avg LeadTime: {row['avg_leadtime_days']:.2f if row['avg_leadtime_days'] else 'N/A':>8} days")
        
        # Analyze jobs by lead time availability
        cursor.execute("""
            SELECT 
                CASE 
                    WHEN jop.LeadTime_d IS NULL OR jop.LeadTime_d <= 0 THEN 'NO_LEADTIME'
                    WHEN jop.LeadTime_d > 0 AND jop.LeadTime_d <= 1 THEN 'SHORT_LEADTIME'
                    WHEN jop.LeadTime_d > 1 AND jop.LeadTime_d <= 7 THEN 'MEDIUM_LEADTIME'
                    ELSE 'LONG_LEADTIME'
                END as leadtime_category,
                COUNT(*) as job_count
            FROM tbl_jo_process jop 
            INNER JOIN tbl_jo_txn jot ON jot.TxnId_i = jop.TxnId_i 
            WHERE jot.Void_c != 1 
                AND jot.DocStatus_c NOT IN ('CP', 'CX') 
                AND jop.QtyStatus_c != 'FF' 
                AND jot.TargetDate_dd >= CURDATE()
                AND jot.TargetDate_dd <= DATE_ADD(CURDATE(), INTERVAL 180 DAY)
            GROUP BY leadtime_category
            ORDER BY job_count DESC
        """)
        
        leadtime_distribution = cursor.fetchall()
        print("\nLead Time Distribution:")
        print("-" * 40)
        for row in leadtime_distribution:
            print(f"{row['leadtime_category']:<16}: {row['job_count']:>6} jobs")
        
    except Exception as e:
        logger.error(f"Error analyzing job distribution: {e}")
    finally:
        cursor.close()
        conn.close()

def analyze_working_hours_constraints():
    """Analyze working hours and time availability constraints"""
    conn = get_connection()
    if not conn:
        return
    
    cursor = conn.cursor(dictionary=True)
    
    print("\n" + "=" * 80)
    print("WORKING HOURS CONSTRAINTS ANALYSIS")
    print("=" * 80)
    
    try:
        # Check if ai_arrangable_hour table exists
        cursor.execute("SHOW TABLES LIKE 'ai_arrangable_hour'")
        if cursor.fetchone():
            cursor.execute("SELECT COUNT(*) as count FROM ai_arrangable_hour")
            arrangeble_count = cursor.fetchone()['count']
            print(f"ai_arrangable_hour table exists with {arrangeble_count} records")
            
            if arrangeble_count > 0:
                cursor.execute("""
                    SELECT machine_name, working_day, start_time, end_time, COUNT(*) as schedule_count
                    FROM ai_arrangable_hour 
                    GROUP BY machine_name, working_day, start_time, end_time
                    ORDER BY machine_name, working_day
                    LIMIT 10
                """)
                sample_hours = cursor.fetchall()
                print("\nSample working hours:")
                for row in sample_hours:
                    print(f"  {row['machine_name']}: {row['working_day']} {row['start_time']}-{row['end_time']} ({row['schedule_count']} entries)")
        else:
            print("ai_arrangable_hour table does not exist")
        
        # Check if ai_holidays table exists
        cursor.execute("SHOW TABLES LIKE 'ai_holidays'")
        if cursor.fetchone():
            cursor.execute("SELECT COUNT(*) as count FROM ai_holidays WHERE holiday_date >= CURDATE()")
            holidays_count = cursor.fetchone()['count']
            print(f"\nai_holidays table exists with {holidays_count} upcoming holidays")
            
            if holidays_count > 0:
                cursor.execute("""
                    SELECT holiday_date, description 
                    FROM ai_holidays 
                    WHERE holiday_date >= CURDATE() 
                    ORDER BY holiday_date 
                    LIMIT 5
                """)
                upcoming_holidays = cursor.fetchall()
                print("Upcoming holidays:")
                for row in upcoming_holidays:
                    print(f"  {row['holiday_date']}: {row['description']}")
        else:
            print("ai_holidays table does not exist")
        
        # Check if ai_breaktimes table exists
        cursor.execute("SHOW TABLES LIKE 'ai_breaktimes'")
        if cursor.fetchone():
            cursor.execute("SELECT COUNT(*) as count FROM ai_breaktimes")
            breaktimes_count = cursor.fetchone()['count']
            print(f"\nai_breaktimes table exists with {breaktimes_count} break time records")
            
            if breaktimes_count > 0:
                cursor.execute("""
                    SELECT break_type, start_time, end_time, COUNT(*) as break_count
                    FROM ai_breaktimes 
                    GROUP BY break_type, start_time, end_time
                    ORDER BY break_type, start_time
                    LIMIT 10
                """)
                sample_breaks = cursor.fetchall()
                print("Sample break times:")
                for row in sample_breaks:
                    print(f"  {row['break_type']}: {row['start_time']}-{row['end_time']} ({row['break_count']} entries)")
        else:
            print("ai_breaktimes table does not exist")
            
    except Exception as e:
        logger.error(f"Error analyzing working hours constraints: {e}")
    finally:
        cursor.close()
        conn.close()

def analyze_machine_capacity():
    """Analyze machine capacity and availability"""
    conn = get_connection()
    if not conn:
        return
    
    cursor = conn.cursor(dictionary=True)
    
    print("\n" + "=" * 80)
    print("MACHINE CAPACITY ANALYSIS")
    print("=" * 80)
    
    try:
        # Get all machines
        cursor.execute("SELECT COUNT(*) as total_machines FROM tbl_machine")
        total_machines = cursor.fetchone()['total_machines']
        print(f"Total machines in system: {total_machines}")
        
        # Get machine utilization
        cursor.execute("""
            SELECT 
                tm.MachineName_v,
                COUNT(jop.TxnId_i) as assigned_jobs,
                SUM(CASE WHEN jop.CapMin_d = 1 AND jop.CapQty_d != 0 
                         THEN jot.JoQty_d / (jop.CapQty_d * 60) 
                         ELSE jop.LeadTime_d * 24 END) as total_hours_needed
            FROM tbl_machine tm
            LEFT JOIN tbl_jo_process jop ON (
                tm.machine_id_v = jop.Machine_v
                OR tm.MachineId_i = jop.Machine_v
                OR tm.MachineName_v = jop.Machine_v
            )
            LEFT JOIN tbl_jo_txn jot ON jot.TxnId_i = jop.TxnId_i 
            WHERE (jop.TxnId_i IS NULL OR (
                jot.Void_c != 1 
                AND jot.DocStatus_c NOT IN ('CP', 'CX') 
                AND jop.QtyStatus_c != 'FF' 
                AND jot.TargetDate_dd >= CURDATE()
                AND jot.TargetDate_dd <= DATE_ADD(CURDATE(), INTERVAL 180 DAY)
            ))
            GROUP BY tm.MachineName_v
            ORDER BY assigned_jobs DESC
            LIMIT 15
        """)
        
        machine_utilization = cursor.fetchall()
        print("\nTop 15 Machines by Job Assignment:")
        print("-" * 60)
        for row in machine_utilization:
            hours_needed = row['total_hours_needed'] or 0
            print(f"{row['MachineName_v']:<25}: {row['assigned_jobs']:>4} jobs | {hours_needed:>8.1f} hours needed")
        
        # Check for machines with no jobs
        cursor.execute("""
            SELECT COUNT(*) as unused_machines
            FROM tbl_machine tm
            LEFT JOIN tbl_jo_process jop ON (
                tm.machine_id_v = jop.Machine_v
                OR tm.MachineId_i = jop.Machine_v
                OR tm.MachineName_v = jop.Machine_v
            )
            LEFT JOIN tbl_jo_txn jot ON jot.TxnId_i = jop.TxnId_i 
            WHERE jop.TxnId_i IS NULL OR (
                jot.Void_c = 1 
                OR jot.DocStatus_c IN ('CP', 'CX') 
                OR jop.QtyStatus_c = 'FF'
            )
            GROUP BY tm.MachineName_v
            HAVING COUNT(CASE WHEN jot.Void_c != 1 
                              AND jot.DocStatus_c NOT IN ('CP', 'CX') 
                              AND jop.QtyStatus_c != 'FF' 
                              AND jot.TargetDate_dd >= CURDATE()
                              AND jot.TargetDate_dd <= DATE_ADD(CURDATE(), INTERVAL 180 DAY)
                         THEN 1 END) = 0
        """)
        unused_machines = cursor.fetchone()['unused_machines']
        print(f"\nMachines with no active jobs: {unused_machines}")
        
    except Exception as e:
        logger.error(f"Error analyzing machine capacity: {e}")
    finally:
        cursor.close()
        conn.close()

def analyze_time_constraints():
    """Analyze time-related constraints affecting scheduling"""
    conn = get_connection()
    if not conn:
        return
    
    cursor = conn.cursor(dictionary=True)
    
    print("\n" + "=" * 80)
    print("TIME CONSTRAINTS ANALYSIS")
    print("=" * 80)
    
    try:
        # Jobs by urgency (based on target date)
        cursor.execute("""
            SELECT 
                CASE 
                    WHEN jot.TargetDate_dd < CURDATE() THEN 'OVERDUE'
                    WHEN jot.TargetDate_dd = CURDATE() THEN 'DUE_TODAY'
                    WHEN jot.TargetDate_dd <= DATE_ADD(CURDATE(), INTERVAL 7 DAY) THEN 'DUE_THIS_WEEK'
                    WHEN jot.TargetDate_dd <= DATE_ADD(CURDATE(), INTERVAL 30 DAY) THEN 'DUE_THIS_MONTH'
                    ELSE 'DUE_LATER'
                END as urgency,
                COUNT(*) as job_count,
                AVG(CASE WHEN jop.CapMin_d = 1 AND jop.CapQty_d != 0 
                         THEN jot.JoQty_d / (jop.CapQty_d * 60) 
                         ELSE jop.LeadTime_d * 24 END) as avg_hours_needed
            FROM tbl_jo_process jop 
            INNER JOIN tbl_jo_txn jot ON jot.TxnId_i = jop.TxnId_i 
            WHERE jot.Void_c != 1 
                AND jot.DocStatus_c NOT IN ('CP', 'CX') 
                AND jop.QtyStatus_c != 'FF' 
                AND jot.TargetDate_dd >= CURDATE()
                AND jot.TargetDate_dd <= DATE_ADD(CURDATE(), INTERVAL 180 DAY)
            GROUP BY urgency
            ORDER BY FIELD(urgency, 'OVERDUE', 'DUE_TODAY', 'DUE_THIS_WEEK', 'DUE_THIS_MONTH', 'DUE_LATER')
        """)
        
        urgency_analysis = cursor.fetchall()
        print("Jobs by Urgency:")
        print("-" * 50)
        for row in urgency_analysis:
            avg_hours = row['avg_hours_needed'] or 0
            print(f"{row['urgency']:<15}: {row['job_count']:>6} jobs | Avg Hours: {avg_hours:>6.1f}")
        
        # Material availability constraints
        cursor.execute("""
            SELECT 
                CASE 
                    WHEN jot.MaterialDate_dd IS NULL THEN 'NO_MATERIAL_DATE'
                    WHEN jot.MaterialDate_dd > CURDATE() THEN 'MATERIAL_PENDING'
                    WHEN jot.MaterialDate_dd <= CURDATE() THEN 'MATERIAL_AVAILABLE'
                END as material_status,
                COUNT(*) as job_count
            FROM tbl_jo_process jop 
            INNER JOIN tbl_jo_txn jot ON jot.TxnId_i = jop.TxnId_i 
            WHERE jot.Void_c != 1 
                AND jot.DocStatus_c NOT IN ('CP', 'CX') 
                AND jop.QtyStatus_c != 'FF' 
                AND jot.TargetDate_dd >= CURDATE()
                AND jot.TargetDate_dd <= DATE_ADD(CURDATE(), INTERVAL 180 DAY)
            GROUP BY material_status
            ORDER BY job_count DESC
        """)
        
        material_analysis = cursor.fetchall()
        print("\nMaterial Availability:")
        print("-" * 30)
        for row in material_analysis:
            print(f"{row['material_status']:<18}: {row['job_count']:>6} jobs")
        
    except Exception as e:
        logger.error(f"Error analyzing time constraints: {e}")
    finally:
        cursor.close()
        conn.close()

def analyze_scheduling_filters():
    """Analyze which jobs are being filtered out during scheduling"""
    conn = get_connection()
    if not conn:
        return
    
    cursor = conn.cursor(dictionary=True)
    
    print("\n" + "=" * 80)
    print("SCHEDULING FILTER ANALYSIS")
    print("=" * 80)
    
    try:
        # Jobs that would be included in scheduling (matching the mariadb_parser logic)
        cursor.execute("""
            SELECT 
                COUNT(*) as schedulable_jobs
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
        
        schedulable_jobs = cursor.fetchone()['schedulable_jobs']
        print(f"Jobs that pass scheduling filters: {schedulable_jobs}")
        
        # Jobs that would be filtered out
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
                AND (
                    (jop.Machine_v IS NULL OR jop.Machine_v = '' OR jop.Machine_v = '0' OR tm.MachineName_v IS NULL)
                    AND (jop.LeadTime_d IS NULL OR jop.LeadTime_d <= 0)
                )
        """)
        
        filtered_jobs = cursor.fetchone()['filtered_jobs']
        print(f"Jobs filtered out (NO_ASSIGN without LeadTime): {filtered_jobs}")
        
        # Detailed breakdown of filter reasons
        cursor.execute("""
            SELECT 
                CASE 
                    WHEN jot.Void_c = 1 THEN 'VOIDED'
                    WHEN jot.DocStatus_c IN ('CP', 'CX') THEN 'COMPLETED/CANCELLED'
                    WHEN jop.QtyStatus_c = 'FF' THEN 'FULLY_FINISHED'
                    WHEN jot.TargetDate_dd < CURDATE() THEN 'PAST_DUE'
                    WHEN jot.TargetDate_dd > DATE_ADD(CURDATE(), INTERVAL 180 DAY) THEN 'BEYOND_HORIZON'
                    WHEN (jop.Machine_v IS NULL OR jop.Machine_v = '' OR jop.Machine_v = '0') AND (jop.LeadTime_d IS NULL OR jop.LeadTime_d <= 0) THEN 'NO_MACHINE_NO_LEADTIME'
                    ELSE 'SCHEDULABLE'
                END as filter_reason,
                COUNT(*) as job_count
            FROM tbl_jo_process jop 
            INNER JOIN tbl_jo_txn jot ON jot.TxnId_i = jop.TxnId_i 
            GROUP BY filter_reason
            ORDER BY job_count DESC
        """)
        
        filter_breakdown = cursor.fetchall()
        print("\nDetailed Filter Breakdown:")
        print("-" * 50)
        for row in filter_breakdown:
            print(f"{row['filter_reason']:<25}: {row['job_count']:>6} jobs")
        
    except Exception as e:
        logger.error(f"Error analyzing scheduling filters: {e}")
    finally:
        cursor.close()
        conn.close()

def main():
    """Main analysis function"""
    print("COMPREHENSIVE SCHEDULING CONSTRAINTS ANALYSIS")
    print("=" * 80)
    print(f"Analysis started at: {datetime.now()}")
    print(f"Database: {DB_CONFIG['host']}:{DB_CONFIG['port']}/{DB_CONFIG['database']}")
    
    # Run all analyses
    analyze_job_distribution()
    analyze_working_hours_constraints()
    analyze_machine_capacity()
    analyze_time_constraints()
    analyze_scheduling_filters()
    
    print("\n" + "=" * 80)
    print("ANALYSIS COMPLETE")
    print("=" * 80)

if __name__ == "__main__":
    main()