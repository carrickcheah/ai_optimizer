#!/usr/bin/env python3
"""
Check the actual structure of working hours and constraint tables.
"""

import mysql.connector
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

def check_table_structure():
    """Check the structure of constraint tables"""
    conn = get_connection()
    if not conn:
        return
    
    cursor = conn.cursor(dictionary=True)
    
    print("TABLE STRUCTURE ANALYSIS")
    print("=" * 60)
    
    # List of tables to check
    tables_to_check = [
        'ai_arrangable_hour',
        'ai_holidays', 
        'ai_breaktimes',
        'tbl_machine',
        'tbl_jo_process',
        'tbl_jo_txn'
    ]
    
    try:
        for table in tables_to_check:
            print(f"\n{table.upper()}")
            print("-" * len(table))
            
            # Check if table exists
            cursor.execute(f"SHOW TABLES LIKE '{table}'")
            if not cursor.fetchone():
                print(f"❌ Table {table} does not exist")
                continue
            
            # Get table structure
            cursor.execute(f"DESCRIBE {table}")
            columns = cursor.fetchall()
            
            print("Columns:")
            for col in columns:
                field = col['Field']
                data_type = col['Type']
                null = "NULL" if col['Null'] == 'YES' else "NOT NULL"
                key = f" ({col['Key']})" if col['Key'] else ""
                default = f" DEFAULT {col['Default']}" if col['Default'] is not None else ""
                print(f"  {field:<20} {data_type:<20} {null}{key}{default}")
            
            # Get sample data (first 3 rows)
            cursor.execute(f"SELECT * FROM {table} LIMIT 3")
            sample_data = cursor.fetchall()
            
            if sample_data:
                print("\nSample data:")
                for i, row in enumerate(sample_data, 1):
                    print(f"  Row {i}:")
                    for key, value in row.items():
                        print(f"    {key}: {value}")
            else:
                print("\nNo data in table")
        
        # Check for other potential constraint tables
        print("\n\nOTHER CONSTRAINT TABLES SEARCH")
        print("-" * 40)
        
        cursor.execute("SHOW TABLES")
        all_tables = [row['Tables_in_nex_valiant'] for row in cursor.fetchall()]
        
        constraint_keywords = ['hour', 'time', 'shift', 'break', 'holiday', 'calendar', 'schedule', 'availability']
        
        potential_tables = []
        for table in all_tables:
            for keyword in constraint_keywords:
                if keyword.lower() in table.lower():
                    potential_tables.append(table)
                    break
        
        if potential_tables:
            print("Potential constraint-related tables found:")
            for table in potential_tables:
                print(f"  - {table}")
        else:
            print("No additional constraint-related tables found")
        
    except Exception as e:
        print(f"Error checking table structure: {e}")
    finally:
        cursor.close()
        conn.close()

def main():
    """Main function"""
    check_table_structure()

if __name__ == "__main__":
    main()