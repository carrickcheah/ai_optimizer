#!/usr/bin/env python3
"""
Script to check the current working hours configuration in the database.
This will help diagnose why jobs are being scheduled at 11:33 PM instead of during normal working hours.
"""

import os
import sys
from datetime import datetime, timedelta, time as dt_time
import mysql.connector
import pytz
from dotenv import load_dotenv

# Add the backend directory to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Load environment variables
load_dotenv()

# Get database configuration
DB_HOST = os.getenv("MARIADB_HOST")
DB_USER = os.getenv("MARIADB_USERNAME") 
DB_PASSWORD = os.getenv("MARIADB_PASSWORD")
DB_NAME = os.getenv("MARIADB_DATABASE")
DB_PORT = os.getenv("MARIADB_PORT", "3306")

MALAYSIA_TZ = pytz.timezone('Asia/Kuala_Lumpur')

def get_db_connection():
    """Get database connection."""
    try:
        connection = mysql.connector.connect(
            host=DB_HOST,
            user=DB_USER,
            password=DB_PASSWORD,
            database=DB_NAME,
            port=DB_PORT
        )
        return connection
    except Exception as e:
        print(f"Error connecting to database: {e}")
        return None

def timedelta_to_time(td):
    """Convert timedelta to time object."""
    if isinstance(td, timedelta):
        total_seconds = int(td.total_seconds())
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        seconds = total_seconds % 60
        return dt_time(hours, minutes, seconds)
    elif isinstance(td, dt_time):
        return td
    else:
        return td

def check_arrangable_hours():
    """Check the ai_arrangable_hour table for working hours configuration."""
    print("\n" + "="*80)
    print("CHECKING WORKING HOURS CONFIGURATION (ai_arrangable_hour)")
    print("="*80)
    
    conn = get_db_connection()
    if not conn:
        return
    
    try:
        cursor = conn.cursor(dictionary=True)
        
        # Query all arrangable hours
        query = """
        SELECT id, arrange_day, start_time, end_time, is_working, created_at, updated_at
        FROM ai_arrangable_hour 
        ORDER BY arrange_day, start_time
        """
        
        cursor.execute(query)
        hours = cursor.fetchall()
        
        if not hours:
            print("WARNING: No working hours found in ai_arrangable_hour table!")
            return
        
        # Group by day for better display
        days_map = {
            1: "Monday",
            2: "Tuesday", 
            3: "Wednesday",
            4: "Thursday",
            5: "Friday",
            6: "Saturday",
            7: "Sunday"
        }
        
        # Process and display data
        table_data = []
        for hour in hours:
            day_name = days_map.get(hour['arrange_day'], f"Day {hour['arrange_day']}")
            start_time = timedelta_to_time(hour['start_time'])
            end_time = timedelta_to_time(hour['end_time'])
            
            table_data.append([
                hour['id'],
                day_name,
                hour['arrange_day'],
                start_time.strftime("%H:%M:%S"),
                end_time.strftime("%H:%M:%S"),
                "✓ Working" if hour['is_working'] else "✗ Not Working",
                hour['created_at'],
                hour['updated_at']
            ])
        
        # Display header
        print(f"\n{'ID':<4} {'Day Name':<12} {'Day #':<6} {'Start Time':<12} {'End Time':<12} {'Status':<15} {'Created':<20} {'Updated':<20}")
        print("-" * 120)
        
        # Display data
        for row in table_data:
            print(f"{row[0]:<4} {row[1]:<12} {row[2]:<6} {row[3]:<12} {row[4]:<12} {row[5]:<15} {str(row[6]):<20} {str(row[7]):<20}")
        
        # Check for missing days
        configured_days = set(h['arrange_day'] for h in hours)
        all_days = set(range(1, 8))
        missing_days = all_days - configured_days
        
        if missing_days:
            print(f"\nWARNING: Missing configuration for days: {sorted(missing_days)}")
            for day in sorted(missing_days):
                print(f"  - {days_map.get(day, f'Day {day}')}")
        
        # Check for non-working days
        non_working = [h for h in hours if not h['is_working']]
        if non_working:
            print(f"\nWARNING: Found {len(non_working)} non-working periods:")
            for h in non_working:
                day_name = days_map.get(h['arrange_day'], f"Day {h['arrange_day']}")
                print(f"  - {day_name}: {h['start_time']} - {h['end_time']}")
        
        cursor.close()
        
    except Exception as e:
        print(f"Error querying arrangable hours: {e}")
    finally:
        conn.close()

def check_holidays():
    """Check the ai_holidays table for holidays affecting today."""
    print("\n" + "="*80)
    print("CHECKING HOLIDAYS (ai_holidays)")
    print("="*80)
    
    conn = get_db_connection()
    if not conn:
        return
    
    try:
        cursor = conn.cursor(dictionary=True)
        
        # Get today's date and upcoming dates
        today = datetime.now(MALAYSIA_TZ).date()
        next_week = today + timedelta(days=7)
        
        # Query holidays
        query = """
        SELECT id, name, description, holiday_date, month_day, is_recurring, 
               scope, location, country_code, is_active
        FROM ai_holidays 
        WHERE is_active = 1
        ORDER BY holiday_date, month_day
        """
        
        cursor.execute(query)
        holidays = cursor.fetchall()
        
        if not holidays:
            print("No active holidays found in ai_holidays table.")
            return
        
        # Separate specific date holidays and recurring holidays
        specific_holidays = []
        recurring_holidays = []
        
        for holiday in holidays:
            if holiday['holiday_date']:
                specific_holidays.append(holiday)
            elif holiday['month_day'] and holiday['is_recurring']:
                recurring_holidays.append(holiday)
        
        # Display specific date holidays
        if specific_holidays:
            print(f"\nSpecific Date Holidays ({len(specific_holidays)} found):")
            table_data = []
            for h in specific_holidays:
                is_today = h['holiday_date'] == today
                is_upcoming = today <= h['holiday_date'] <= next_week
                status = "TODAY!" if is_today else ("This Week" if is_upcoming else "")
                
                table_data.append([
                    h['id'],
                    h['name'],
                    h['holiday_date'].strftime("%Y-%m-%d"),
                    h['scope'],
                    h['location'] or "All",
                    status
                ])
            
            # Display header
            print(f"\n{'ID':<4} {'Name':<30} {'Date':<12} {'Scope':<10} {'Location':<15} {'Status':<10}")
            print("-" * 85)
            
            # Display data
            for row in table_data:
                print(f"{row[0]:<4} {row[1]:<30} {row[2]:<12} {row[3]:<10} {row[4]:<15} {row[5]:<10}")
        
        # Display recurring holidays
        if recurring_holidays:
            print(f"\nRecurring Holidays ({len(recurring_holidays)} found):")
            table_data = []
            for h in recurring_holidays:
                # Check if this recurring holiday affects today
                if h['month_day']:
                    try:
                        month, day = map(int, h['month_day'].split('-'))
                        if today.month == month and today.day == day:
                            status = "TODAY!"
                        else:
                            status = f"Every {month:02d}-{day:02d}"
                    except:
                        status = "Invalid Format"
                else:
                    status = "No Date"
                
                table_data.append([
                    h['id'],
                    h['name'],
                    h['month_day'] or "N/A",
                    h['scope'],
                    h['location'] or "All",
                    status
                ])
            
            # Display header
            print(f"\n{'ID':<4} {'Name':<30} {'Month-Day':<12} {'Scope':<10} {'Location':<15} {'Status':<15}")
            print("-" * 90)
            
            # Display data
            for row in table_data:
                print(f"{row[0]:<4} {row[1]:<30} {row[2]:<12} {row[3]:<10} {row[4]:<15} {row[5]:<15}")
        
        # Check if today is a holiday
        today_is_holiday = False
        for h in specific_holidays:
            if h['holiday_date'] == today:
                print(f"\n⚠️  TODAY IS A HOLIDAY: {h['name']}")
                today_is_holiday = True
        
        for h in recurring_holidays:
            if h['month_day']:
                try:
                    month, day = map(int, h['month_day'].split('-'))
                    if today.month == month and today.day == day:
                        print(f"\n⚠️  TODAY IS A RECURRING HOLIDAY: {h['name']}")
                        today_is_holiday = True
                except:
                    pass
        
        if not today_is_holiday:
            print(f"\n✓ Today ({today.strftime('%Y-%m-%d')}) is NOT a holiday.")
        
        cursor.close()
        
    except Exception as e:
        print(f"Error querying holidays: {e}")
    finally:
        conn.close()

def check_break_times():
    """Check the ai_breaktimes table for break periods."""
    print("\n" + "="*80)
    print("CHECKING BREAK TIMES (ai_breaktimes)")
    print("="*80)
    
    conn = get_db_connection()
    if not conn:
        return
    
    try:
        cursor = conn.cursor(dictionary=True)
        
        # Query break times
        query = """
        SELECT id, name, description, start_time, end_time, duration_minutes, 
               break_type, is_paid, is_mandatory, is_active
        FROM ai_breaktimes 
        WHERE is_active = 1
        ORDER BY start_time
        """
        
        cursor.execute(query)
        breaktimes = cursor.fetchall()
        
        if not breaktimes:
            print("No active break times found in ai_breaktimes table.")
            return
        
        print(f"\nActive Break Times ({len(breaktimes)} found):")
        table_data = []
        
        for b in breaktimes:
            start_time = timedelta_to_time(b['start_time'])
            end_time = timedelta_to_time(b['end_time'])
            
            table_data.append([
                b['id'],
                b['name'],
                start_time.strftime("%H:%M:%S"),
                end_time.strftime("%H:%M:%S"),
                b['duration_minutes'],
                b['break_type'],
                "✓" if b['is_mandatory'] else "✗",
                "✓" if b['is_paid'] else "✗"
            ])
        
        # Display header
        print(f"\n{'ID':<4} {'Name':<20} {'Start':<10} {'End':<10} {'Duration':<12} {'Type':<15} {'Mandatory':<10} {'Paid':<6}")
        print("-" * 95)
        
        # Display data
        for row in table_data:
            print(f"{row[0]:<4} {row[1]:<20} {row[2]:<10} {row[3]:<10} {row[4]:<12} {row[5]:<15} {row[6]:<10} {row[7]:<6}")
        
        cursor.close()
        
    except Exception as e:
        print(f"Error querying break times: {e}")
    finally:
        conn.close()

def analyze_scheduling_window():
    """Analyze when jobs can be scheduled based on working hours."""
    print("\n" + "="*80)
    print("ANALYZING SCHEDULING WINDOWS")
    print("="*80)
    
    now = datetime.now(MALAYSIA_TZ)
    print(f"\nCurrent time in Kuala Lumpur: {now.strftime('%Y-%m-%d %H:%M:%S %Z')}")
    print(f"Day of week: {now.strftime('%A')} (Day {now.weekday() + 1})")
    
    # Check if jobs scheduled at 23:33 would be within working hours
    late_time = now.replace(hour=23, minute=33, second=0)
    print(f"\nChecking if 23:33 (11:33 PM) is within working hours...")
    
    # Import time availability checker
    try:
        from app.scheduling.time_availability import TimeAvailabilityManager
        checker = TimeAvailabilityManager.get_instance()
        
        is_available = checker.is_time_available_for_scheduling(late_time)
        print(f"Is 23:33 available for scheduling: {'YES' if is_available else 'NO'}")
        
        # Check working hours for today
        working_periods = checker.get_working_hours_for_date(now)
        if working_periods:
            print(f"\nWorking periods for today ({now.strftime('%A')}):")
            for start, end in working_periods:
                print(f"  - {start.strftime('%H:%M:%S')} to {end.strftime('%H:%M:%S')}")
        else:
            print(f"\nNO WORKING PERIODS found for today ({now.strftime('%A')})!")
        
        # Find next available slot
        print("\nFinding next available time slot from now...")
        next_slot = checker.get_next_available_datetime(now, 1.0)  # 1 hour job
        if next_slot:
            print(f"Next available slot: {next_slot.strftime('%Y-%m-%d %H:%M:%S %Z')}")
        else:
            print("WARNING: No available slots found!")
            
    except Exception as e:
        print(f"Error using time availability checker: {e}")

def main():
    """Main function to run all checks."""
    print("\n" + "#"*80)
    print("# WORKING HOURS CONFIGURATION DIAGNOSTIC")
    print(f"# Run time: {datetime.now(MALAYSIA_TZ).strftime('%Y-%m-%d %H:%M:%S %Z')}")
    print("#"*80)
    
    # Check database connection first
    conn = get_db_connection()
    if not conn:
        print("\nERROR: Cannot connect to database. Check your .env configuration.")
        return
    conn.close()
    
    # Run all checks
    check_arrangable_hours()
    check_holidays()
    check_break_times()
    analyze_scheduling_window()
    
    print("\n" + "#"*80)
    print("# DIAGNOSTIC COMPLETE")
    print("#"*80)

if __name__ == "__main__":
    main()