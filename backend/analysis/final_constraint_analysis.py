#!/usr/bin/env python3
"""
Final comprehensive analysis of scheduling constraints using correct table structures.
"""

import mysql.connector
from datetime import datetime, timedelta
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

def analyze_working_time_constraints():
    """Analyze working time constraints in detail"""
    conn = get_connection()
    if not conn:
        return
    
    cursor = conn.cursor(dictionary=True)
    
    print("WORKING TIME CONSTRAINTS ANALYSIS")
    print("=" * 60)
    
    try:
        # 1. Working hours configuration
        print("1. WORKING HOURS CONFIGURATION")
        print("-" * 40)
        
        cursor.execute("""
            SELECT 
                arrange_day,
                start_time,
                end_time,
                is_working,
                CASE arrange_day 
                    WHEN 1 THEN 'Monday'
                    WHEN 2 THEN 'Tuesday'
                    WHEN 3 THEN 'Wednesday'
                    WHEN 4 THEN 'Thursday'
                    WHEN 5 THEN 'Friday'
                    WHEN 6 THEN 'Saturday'
                    WHEN 7 THEN 'Sunday'
                    ELSE 'Unknown'
                END as day_name,
                TIME_TO_SEC(TIMEDIFF(end_time, start_time)) / 3600 as working_hours
            FROM ai_arrangable_hour 
            WHERE is_working = 1
            ORDER BY arrange_day
        """)
        
        working_hours = cursor.fetchall()
        total_weekly_hours = 0
        
        if working_hours:
            print("Working schedule:")
            for row in working_hours:
                day = row['day_name']
                start = row['start_time']
                end = row['end_time']
                hours = row['working_hours']
                total_weekly_hours += hours
                print(f"  {day:<10}: {start} - {end} ({hours:.1f} hours)")
            
            print(f"\nTotal weekly working hours: {total_weekly_hours:.1f}")
        else:
            print("No working hours configured!")
            return
        
        # 2. Break times analysis
        print("\n2. BREAK TIMES CONFIGURATION")
        print("-" * 40)
        
        cursor.execute("""
            SELECT 
                name,
                start_time,
                end_time,
                duration_minutes,
                break_type,
                is_mandatory
            FROM ai_breaktimes 
            WHERE is_active = 1
            ORDER BY start_time
        """)
        
        break_times = cursor.fetchall()
        total_break_minutes = 0
        
        if break_times:
            print("Daily break schedule:")
            for row in break_times:
                name = row['name']
                start = row['start_time']
                end = row['end_time']
                duration = row['duration_minutes']
                break_type = row['break_type']
                mandatory = "Yes" if row['is_mandatory'] else "No"
                total_break_minutes += duration
                print(f"  {name:<20}: {start} - {end} ({duration} min, {break_type}, Mandatory: {mandatory})")
            
            total_break_hours = total_break_minutes / 60
            print(f"\nTotal daily break time: {total_break_hours:.2f} hours")
            
            # Calculate effective working hours per day
            avg_daily_hours = total_weekly_hours / len(working_hours) if working_hours else 0
            effective_daily_hours = avg_daily_hours - total_break_hours
            print(f"Effective working hours per day: {effective_daily_hours:.2f} hours")
        
        # 3. Holiday constraints
        print("\n3. UPCOMING HOLIDAYS")
        print("-" * 30)
        
        cursor.execute("""
            SELECT 
                name,
                holiday_date,
                description,
                is_recurring
            FROM ai_holidays 
            WHERE is_active = 1 
                AND holiday_date BETWEEN CURDATE() AND DATE_ADD(CURDATE(), INTERVAL 60 DAY)
            ORDER BY holiday_date
        """)
        
        holidays = cursor.fetchall()
        
        if holidays:
            print("Holidays in next 60 days:")
            for row in holidays:
                name = row['name']
                date = row['holiday_date']
                recurring = "Yes" if row['is_recurring'] else "No"
                print(f"  {date}: {name} (Recurring: {recurring})")
        else:
            print("No holidays in next 60 days")
        
        # 4. Machine capacity vs demand analysis
        print("\n4. MACHINE CAPACITY vs DEMAND")
        print("-" * 40)
        
        # Calculate theoretical daily capacity per machine
        if working_hours and break_times:
            working_days_per_week = len(working_hours)
            effective_hours_per_day = effective_daily_hours
            
            print(f"Theoretical capacity per machine:")
            print(f"  - Working days per week: {working_days_per_week}")
            print(f"  - Effective hours per day: {effective_hours_per_day:.2f}")
            print(f"  - Effective hours per week: {effective_hours_per_day * working_days_per_week:.2f}")
        
        # Get machine workload for next 30 days
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
                END) as total_hours_needed,
                COUNT(CASE WHEN jot.TargetDate_dd <= DATE_ADD(CURDATE(), INTERVAL 7 DAY) THEN 1 END) as urgent_jobs
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
            HAVING total_hours_needed > 100  -- Focus on machines with significant load
            ORDER BY total_hours_needed DESC
            LIMIT 10
        """)
        
        machine_workload = cursor.fetchall()
        
        if machine_workload:
            print(f"\nTop 10 machines by workload (next 30 days):")
            print("Machine Name        | Jobs | Hours | Urgent | Status")
            print("-" * 55)
            
            # Calculate 30-day capacity per machine
            days_30 = 30
            weeks_30 = days_30 / 7
            capacity_per_machine_30days = effective_hours_per_day * working_days_per_week * weeks_30
            
            for row in machine_workload:
                machine = row['machine_name'][:18]
                jobs = row['job_count']
                hours = row['total_hours_needed'] or 0
                urgent = row['urgent_jobs']
                
                # Determine status
                if hours > capacity_per_machine_30days * 1.5:
                    status = "OVERLOADED"
                elif hours > capacity_per_machine_30days:
                    status = "HIGH LOAD"
                elif hours > capacity_per_machine_30days * 0.7:
                    status = "NORMAL"
                else:
                    status = "LOW LOAD"
                
                print(f"{machine:<18} | {jobs:>4} | {hours:>5.0f} | {urgent:>6} | {status}")
            
            print(f"\nCapacity per machine (30 days): {capacity_per_machine_30days:.0f} hours")
        
        # 5. Time urgency analysis
        print("\n5. JOB URGENCY ANALYSIS")
        print("-" * 30)
        
        cursor.execute("""
            SELECT 
                CASE 
                    WHEN jot.TargetDate_dd < CURDATE() THEN 'OVERDUE'
                    WHEN jot.TargetDate_dd = CURDATE() THEN 'DUE TODAY'
                    WHEN jot.TargetDate_dd <= DATE_ADD(CURDATE(), INTERVAL 3 DAY) THEN 'URGENT (≤3 days)'
                    WHEN jot.TargetDate_dd <= DATE_ADD(CURDATE(), INTERVAL 7 DAY) THEN 'SOON (≤7 days)'
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
            ORDER BY FIELD(urgency, 'OVERDUE', 'DUE TODAY', 'URGENT (≤3 days)', 'SOON (≤7 days)', 'NORMAL (≤30 days)', 'LATER (>30 days)')
        """)
        
        urgency_analysis = cursor.fetchall()
        
        if urgency_analysis:
            print("Job distribution by urgency:")
            print("Urgency           | Jobs | Total Hours")
            print("-" * 40)
            
            urgent_hours = 0
            for row in urgency_analysis:
                urgency = row['urgency']
                jobs = row['job_count']
                hours = row['total_hours'] or 0
                
                if 'URGENT' in urgency or 'DUE' in urgency or 'OVERDUE' in urgency:
                    urgent_hours += hours
                
                print(f"{urgency:<17} | {jobs:>4} | {hours:>10.0f}")
            
            print(f"\nTotal urgent hours (≤3 days): {urgent_hours:.0f}")
            
            # Calculate if urgent work can be accommodated
            if working_hours and break_times:
                # Get active machines count
                cursor.execute("""
                    SELECT COUNT(DISTINCT COALESCE(tm.MachineName_v, 'NOT_ASSIGN')) as active_machines
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
                        AND jot.TargetDate_dd <= DATE_ADD(CURDATE(), INTERVAL 7 DAY)
                """)
                
                active_machines = cursor.fetchone()['active_machines']
                urgent_capacity_3days = active_machines * effective_hours_per_day * 3
                
                print(f"\nCapacity for urgent work (3 days):")
                print(f"  - Active machines: {active_machines}")
                print(f"  - Capacity (3 days): {urgent_capacity_3days:.0f} hours")
                print(f"  - Urgent demand: {urgent_hours:.0f} hours")
                
                if urgent_hours > urgent_capacity_3days:
                    print(f"  ⚠️  CAPACITY SHORTAGE: {urgent_hours - urgent_capacity_3days:.0f} hours over capacity")
                else:
                    utilization = (urgent_hours / urgent_capacity_3days) * 100 if urgent_capacity_3days > 0 else 0
                    print(f"  ✅ Urgent utilization: {utilization:.1f}%")
        
    except Exception as e:
        print(f"Error during analysis: {e}")
    finally:
        cursor.close()
        conn.close()

def main():
    """Main function"""
    analyze_working_time_constraints()
    
    print("\n" + "=" * 60)
    print("KEY FINDINGS & RECOMMENDATIONS")
    print("=" * 60)
    
    print("""
Based on the analysis, here are the likely reasons why only 306 out of 904
schedulable jobs are being scheduled:

1. WORKING TIME CONSTRAINTS:
   • Limited daily working hours (after breaks)
   • Only 5-7 working days per week
   • Break times reduce effective capacity by 1-2 hours per day

2. MACHINE CAPACITY BOTTLENECKS:
   • Some machines are overloaded with work
   • Uneven distribution of jobs across machines
   • High utilization on critical machines

3. URGENCY vs CAPACITY MISMATCH:
   • Too many urgent jobs competing for limited time slots
   • Scheduler prioritizes urgent work, leaving less urgent jobs unscheduled
   • Insufficient capacity to handle peak demand periods

4. SOLVER LIMITATIONS:
   • Time limit of 240 seconds may prevent finding optimal solutions
   • Complex constraints may cause the solver to schedule conservatively
   • Batch processing may not find the best job combinations

RECOMMENDATIONS:
1. Increase solver time limit if computational resources allow
2. Consider overtime scheduling for bottleneck machines
3. Implement job splitting for large jobs
4. Balance workload across machines more evenly
5. Review break time scheduling for flexibility
6. Consider weekend or extended hours for urgent jobs
""")

if __name__ == "__main__":
    main()