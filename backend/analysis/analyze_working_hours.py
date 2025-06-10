#!/usr/bin/env python3
"""
Detailed analysis of working hours constraints that might be limiting scheduling.
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

def analyze_working_hours():
    """Analyze working hours constraints in detail"""
    conn = get_connection()
    if not conn:
        return
    
    cursor = conn.cursor(dictionary=True)
    
    print("DETAILED WORKING HOURS ANALYSIS")
    print("=" * 60)
    
    try:
        # 1. ai_arrangable_hour table analysis
        print("1. WORKING HOURS SETUP (ai_arrangable_hour)")
        print("-" * 50)
        
        cursor.execute("SELECT * FROM ai_arrangable_hour ORDER BY working_day, start_time")
        working_hours = cursor.fetchall()
        
        if working_hours:
            print("Current working hours configuration:")
            for row in working_hours:
                machine = row.get('machine_name', 'ALL')
                day = row.get('working_day', 'Unknown')
                start = row.get('start_time', 'Unknown')
                end = row.get('end_time', 'Unknown')
                print(f"  {machine:<15} | {day:<10} | {start} - {end}")
        else:
            print("No working hours configured!")
        
        # 2. Holiday constraints
        print("\n2. HOLIDAY CONSTRAINTS (ai_holidays)")
        print("-" * 40)
        
        cursor.execute("""
            SELECT holiday_date, description 
            FROM ai_holidays 
            WHERE holiday_date BETWEEN CURDATE() AND DATE_ADD(CURDATE(), INTERVAL 30 DAY)
            ORDER BY holiday_date
        """)
        holidays = cursor.fetchall()
        
        if holidays:
            print("Upcoming holidays (next 30 days):")
            for row in holidays:
                print(f"  {row['holiday_date']}: {row['description']}")
        else:
            print("No holidays in next 30 days")
        
        # 3. Break time constraints
        print("\n3. BREAK TIME CONSTRAINTS (ai_breaktimes)")
        print("-" * 45)
        
        cursor.execute("SELECT * FROM ai_breaktimes ORDER BY start_time")
        breaktimes = cursor.fetchall()
        
        if breaktimes:
            print("Break time configuration:")
            for row in breaktimes:
                break_type = row.get('break_type', 'Unknown')
                start = row.get('start_time', 'Unknown')
                end = row.get('end_time', 'Unknown')
                print(f"  {break_type:<15} | {start} - {end}")
        else:
            print("No break times configured")
        
        # 4. Machine hours demand vs availability
        print("\n4. MACHINE WORKLOAD ANALYSIS")
        print("-" * 40)
        
        cursor.execute("""
            SELECT 
                COALESCE(tm.MachineName_v, 'NOT_ASSIGN') as machine_name,
                COUNT(*) as job_count,
                SUM(CASE 
                    WHEN jop.CapMin_d = 1 AND jop.CapQty_d != 0 
                    THEN jot.JoQty_d / (jop.CapQty_d * 60) 
                    WHEN jop.LeadTime_d IS NOT NULL AND jop.LeadTime_d > 0
                    THEN jop.LeadTime_d * 24
                    ELSE 8 
                END) as total_hours_needed
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
                AND jot.TargetDate_dd <= DATE_ADD(CURDATE(), INTERVAL 30 DAY)
            GROUP BY COALESCE(tm.MachineName_v, 'NOT_ASSIGN')
            HAVING total_hours_needed > 0
            ORDER BY total_hours_needed DESC
            LIMIT 15
        """)
        
        machine_workload = cursor.fetchall()
        
        if machine_workload:
            print("Top machines by workload (next 30 days):")
            print("Machine Name        | Jobs | Hours Needed")
            print("-" * 45)
            
            total_hours_all = 0
            for row in machine_workload:
                machine = row['machine_name'][:18]
                jobs = row['job_count']
                hours = row['total_hours_needed'] or 0
                total_hours_all += hours
                print(f"{machine:<18} | {jobs:>4} | {hours:>10.1f}")
            
            print(f"\nTotal hours needed (all machines): {total_hours_all:.1f}")
            
            # Calculate available hours assuming 8 hours/day, 5 days/week
            days_in_month = 30
            working_days = days_in_month * 5 / 7  # Assume 5-day work week
            hours_per_day = 8  # Base working hours
            
            # Get unique machines count
            cursor.execute("""
                SELECT COUNT(DISTINCT COALESCE(tm.MachineName_v, 'NOT_ASSIGN')) as unique_machines
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
                    AND jot.TargetDate_dd <= DATE_ADD(CURDATE(), INTERVAL 30 DAY)
            """)
            
            unique_machines = cursor.fetchone()['unique_machines']
            theoretical_capacity = unique_machines * working_days * hours_per_day
            
            print(f"\nCapacity Analysis (30 days):")
            print(f"• Active machines: {unique_machines}")
            print(f"• Working days: {working_days:.1f}")
            print(f"• Hours per day: {hours_per_day}")
            print(f"• Theoretical capacity: {theoretical_capacity:.1f} hours")
            
            if total_hours_all > theoretical_capacity:
                print(f"⚠️  OVERLOADED: Need {total_hours_all:.1f} hours but only {theoretical_capacity:.1f} available")
                print(f"   Overload factor: {total_hours_all/theoretical_capacity:.2f}x")
            else:
                utilization = (total_hours_all / theoretical_capacity) * 100
                print(f"✅ Capacity utilization: {utilization:.1f}%")
        
        # 5. Jobs by urgency and hours needed
        print("\n5. JOB URGENCY vs HOURS NEEDED")
        print("-" * 40)
        
        cursor.execute("""
            SELECT 
                CASE 
                    WHEN jot.TargetDate_dd <= DATE_ADD(CURDATE(), INTERVAL 7 DAY) THEN 'URGENT (≤7 days)'
                    WHEN jot.TargetDate_dd <= DATE_ADD(CURDATE(), INTERVAL 30 DAY) THEN 'NORMAL (≤30 days)'
                    ELSE 'LATER (>30 days)'
                END as urgency,
                COUNT(*) as job_count,
                SUM(CASE 
                    WHEN jop.CapMin_d = 1 AND jop.CapQty_d != 0 
                    THEN jot.JoQty_d / (jop.CapQty_d * 60) 
                    WHEN jop.LeadTime_d IS NOT NULL AND jop.LeadTime_d > 0
                    THEN jop.LeadTime_d * 24
                    ELSE 8 
                END) as total_hours
            FROM tbl_jo_process jop 
            INNER JOIN tbl_jo_txn jot ON jot.TxnId_i = jop.TxnId_i 
            WHERE jot.Void_c != 1 
                AND jot.DocStatus_c NOT IN ('CP', 'CX') 
                AND jop.QtyStatus_c != 'FF' 
                AND jot.TargetDate_dd >= CURDATE()
                AND jot.TargetDate_dd <= DATE_ADD(CURDATE(), INTERVAL 180 DAY)
            GROUP BY urgency
            ORDER BY FIELD(urgency, 'URGENT (≤7 days)', 'NORMAL (≤30 days)', 'LATER (>30 days)')
        """)
        
        urgency_analysis = cursor.fetchall()
        
        if urgency_analysis:
            print("Job distribution by urgency:")
            for row in urgency_analysis:
                urgency = row['urgency']
                jobs = row['job_count']
                hours = row['total_hours'] or 0
                avg_hours = hours / jobs if jobs > 0 else 0
                print(f"  {urgency:<20} | {jobs:>4} jobs | {hours:>8.1f} total hrs | {avg_hours:>6.1f} avg hrs")
        
    except Exception as e:
        print(f"Error during analysis: {e}")
    finally:
        cursor.close()
        conn.close()

def main():
    """Main function"""
    analyze_working_hours()
    
    print("\n" + "=" * 60)
    print("KEY INSIGHTS:")
    print("=" * 60)
    print("This analysis helps identify why only 306 out of 904 schedulable jobs")
    print("are being scheduled. Key factors to investigate:")
    print()
    print("1. Working Hours Constraints:")
    print("   - Limited working hours per day/week")
    print("   - Machine-specific availability windows")
    print("   - Break times reducing effective capacity")
    print()
    print("2. Capacity vs Demand:")
    print("   - Total hours needed vs available capacity")
    print("   - Machine utilization rates")
    print("   - Bottleneck machines")
    print()
    print("3. Scheduling Algorithm Limitations:")
    print("   - Solver time limits (240 seconds)")
    print("   - Optimization constraints")
    print("   - Batch size limitations")

if __name__ == "__main__":
    main()