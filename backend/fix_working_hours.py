#!/usr/bin/env python3
"""
Script to fix the working hours configuration in the database.
This will update the end time from 23:59:59 to a more reasonable time like 18:00:00 (6 PM).
"""

import os
import sys
import mysql.connector
from dotenv import load_dotenv
from datetime import time

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

def update_working_hours():
    """Update working hours to more reasonable times."""
    print("\n" + "="*80)
    print("UPDATING WORKING HOURS CONFIGURATION")
    print("="*80)
    
    conn = get_db_connection()
    if not conn:
        return
    
    try:
        cursor = conn.cursor()
        
        # Define new working hours
        # Monday-Friday: 6:30 AM to 6:00 PM (11.5 hours)
        # Saturday: 6:30 AM to 1:00 PM (6.5 hours)
        # Sunday: Keep as non-working
        
        updates = [
            # Update Monday-Friday to end at 18:00:00 (6 PM)
            (time(18, 0, 0), 1),  # Monday
            (time(18, 0, 0), 2),  # Tuesday
            (time(18, 0, 0), 3),  # Wednesday
            (time(18, 0, 0), 4),  # Thursday
            (time(18, 0, 0), 5),  # Friday
            # Update Saturday to end at 13:00:00 (1 PM)
            (time(13, 0, 0), 6),  # Saturday
        ]
        
        for new_end_time, day_num in updates:
            update_query = """
            UPDATE ai_arrangable_hour 
            SET end_time = %s, updated_at = NOW()
            WHERE arrange_day = %s AND is_working = 1
            """
            
            cursor.execute(update_query, (new_end_time, day_num))
            affected_rows = cursor.rowcount
            
            day_names = {1: "Monday", 2: "Tuesday", 3: "Wednesday", 
                        4: "Thursday", 5: "Friday", 6: "Saturday", 7: "Sunday"}
            
            if affected_rows > 0:
                print(f"✓ Updated {day_names[day_num]} end time to {new_end_time}")
            else:
                print(f"✗ No working hours found for {day_names[day_num]}")
        
        # Commit the changes
        conn.commit()
        print("\n✓ Changes committed to database")
        
        # Show the updated configuration
        cursor.execute("""
        SELECT arrange_day, start_time, end_time, is_working
        FROM ai_arrangable_hour
        ORDER BY arrange_day
        """)
        
        print("\nUpdated Working Hours Configuration:")
        print("-" * 60)
        print(f"{'Day':<10} {'Start Time':<12} {'End Time':<12} {'Status':<10}")
        print("-" * 60)
        
        day_names = {1: "Monday", 2: "Tuesday", 3: "Wednesday", 
                    4: "Thursday", 5: "Friday", 6: "Saturday", 7: "Sunday"}
        
        for row in cursor.fetchall():
            day_name = day_names.get(row[0], f"Day {row[0]}")
            status = "Working" if row[3] else "Not Working"
            print(f"{day_name:<10} {str(row[1]):<12} {str(row[2]):<12} {status:<10}")
        
        cursor.close()
        
    except Exception as e:
        print(f"Error updating working hours: {e}")
        if conn:
            conn.rollback()
    finally:
        conn.close()

def main():
    """Main function."""
    print("\n" + "#"*80)
    print("# WORKING HOURS FIX SCRIPT")
    print("# This will update the working hours to more reasonable times:")
    print("# - Monday-Friday: 6:30 AM to 6:00 PM")
    print("# - Saturday: 6:30 AM to 1:00 PM")
    print("# - Sunday: Non-working (unchanged)")
    print("#"*80)
    
    response = input("\nDo you want to proceed with updating the working hours? (yes/no): ")
    
    if response.lower() in ['yes', 'y']:
        update_working_hours()
        print("\n✓ Working hours have been updated successfully!")
        print("Jobs should now be scheduled during normal business hours.")
    else:
        print("\nOperation cancelled.")

if __name__ == "__main__":
    main()