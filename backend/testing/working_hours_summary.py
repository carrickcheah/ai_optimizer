#!/usr/bin/env python3
"""
Script to display a summary of the working hours configuration including breaks.
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

def calculate_working_hours(start_time, end_time, breaks):
    """Calculate actual working hours after subtracting breaks."""
    # Convert times to minutes since midnight for easier calculation
    def time_to_minutes(t):
        if isinstance(t, timedelta):
            return int(t.total_seconds() / 60)
        return t.hour * 60 + t.minute
    
    start_minutes = time_to_minutes(start_time)
    end_minutes = time_to_minutes(end_time)
    total_minutes = end_minutes - start_minutes
    
    # Subtract break times
    break_minutes = 0
    for b in breaks:
        break_start = time_to_minutes(b['start_time'])
        break_end = time_to_minutes(b['end_time'])
        
        # Only count breaks that fall within working hours
        if break_start >= start_minutes and break_end <= end_minutes:
            break_minutes += (break_end - break_start)
    
    working_minutes = total_minutes - break_minutes
    return working_minutes / 60.0  # Convert to hours

def main():
    """Main function to display working hours summary."""
    print("\n" + "#"*80)
    print("# WORKING HOURS CONFIGURATION SUMMARY")
    print(f"# Generated: {datetime.now(MALAYSIA_TZ).strftime('%Y-%m-%d %H:%M:%S %Z')}")
    print("#"*80)
    
    conn = get_db_connection()
    if not conn:
        return
    
    try:
        cursor = conn.cursor(dictionary=True)
        
        # Get working hours
        cursor.execute("""
        SELECT arrange_day, start_time, end_time, is_working
        FROM ai_arrangable_hour
        ORDER BY arrange_day
        """)
        working_hours = cursor.fetchall()
        
        # Get break times
        cursor.execute("""
        SELECT name, start_time, end_time, duration_minutes, is_mandatory
        FROM ai_breaktimes
        WHERE is_active = 1
        ORDER BY start_time
        """)
        breaks = cursor.fetchall()
        
        # Convert timedelta to time objects
        for b in breaks:
            if isinstance(b['start_time'], timedelta):
                total_seconds = int(b['start_time'].total_seconds())
                hours = total_seconds // 3600
                minutes = (total_seconds % 3600) // 60
                b['start_time'] = dt_time(hours, minutes)
            if isinstance(b['end_time'], timedelta):
                total_seconds = int(b['end_time'].total_seconds())
                hours = total_seconds // 3600
                minutes = (total_seconds % 3600) // 60
                b['end_time'] = dt_time(hours, minutes)
        
        print("\n## DAILY WORKING HOURS")
        print("-" * 80)
        
        day_names = {1: "Monday", 2: "Tuesday", 3: "Wednesday", 
                    4: "Thursday", 5: "Friday", 6: "Saturday", 7: "Sunday"}
        
        total_weekly_hours = 0
        
        for wh in working_hours:
            day_name = day_names.get(wh['arrange_day'], f"Day {wh['arrange_day']}")
            
            if wh['is_working']:
                # Convert timedelta to time if needed
                start_time = wh['start_time']
                end_time = wh['end_time']
                
                if isinstance(start_time, timedelta):
                    total_seconds = int(start_time.total_seconds())
                    hours = total_seconds // 3600
                    minutes = (total_seconds % 3600) // 60
                    start_time = dt_time(hours, minutes)
                
                if isinstance(end_time, timedelta):
                    total_seconds = int(end_time.total_seconds())
                    hours = total_seconds // 3600
                    minutes = (total_seconds % 3600) // 60
                    end_time = dt_time(hours, minutes)
                
                # Calculate working hours
                actual_hours = calculate_working_hours(start_time, end_time, breaks)
                total_weekly_hours += actual_hours
                
                print(f"{day_name:<12}: {start_time.strftime('%H:%M')} - {end_time.strftime('%H:%M')} "
                      f"({actual_hours:.1f} hours after breaks)")
            else:
                print(f"{day_name:<12}: Non-working day")
        
        print(f"\nTotal Weekly Working Hours: {total_weekly_hours:.1f} hours")
        
        print("\n## BREAK TIMES")
        print("-" * 80)
        for b in breaks:
            mandatory = "Mandatory" if b['is_mandatory'] else "Optional"
            print(f"- {b['name']:<20}: {b['start_time'].strftime('%H:%M')} - "
                  f"{b['end_time'].strftime('%H:%M')} ({b['duration_minutes']} min) [{mandatory}]")
        
        # Check environment variables
        print("\n## ENVIRONMENT CONFIGURATION")
        print("-" * 80)
        normal_hours = os.getenv("NORMAL_WORKING_HOURS", "Not set")
        ot_hours = os.getenv("OT_WORKING_HOURS", "Not set")
        print(f"NORMAL_WORKING_HOURS: {normal_hours}")
        print(f"OT_WORKING_HOURS: {ot_hours}")
        
        print("\n## SCHEDULING IMPLICATIONS")
        print("-" * 80)
        print("✓ Jobs will only be scheduled during the working hours shown above")
        print("✓ Break times will be avoided when scheduling jobs")
        print("✓ Jobs requiring more time than available in a day may span multiple days")
        print("✓ No jobs will be scheduled on Sundays")
        print("✓ Saturday has reduced hours (half day)")
        
        cursor.close()
        
    except Exception as e:
        print(f"Error: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    main()