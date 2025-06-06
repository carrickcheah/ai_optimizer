#!/usr/bin/env python3

from app.api.fastapi_app import get_db_connection_from_pool

try:
    with get_db_connection_from_pool() as conn:
        cursor = conn.cursor(dictionary=True)
        
        # Check shifts
        cursor.execute('SELECT * FROM ai_shifts WHERE is_active = 1')
        shifts = cursor.fetchall()
        print('Active shifts:')
        for shift in shifts:
            print(f'  ID: {shift["id"]}, Name: {shift["name"]}, Start: {shift["start_time"]}, End: {shift["end_time"]}, Working days: {shift["working_days"]}, Overnight: {shift["is_overnight"]}')
        
        if not shifts:
            print('❌ No active shifts found in database!')
            
        # Check if working hours are being enforced
        from app.scheduling.time_availability import time_checker
        from datetime import datetime
        
        # Test current time availability
        now = datetime.now().timestamp()
        test_end = now + 3600  # 1 hour from now
        
        availability = time_checker.is_time_available(now, test_end)
        print(f'Current time availability: {availability}')
        
        # Force cache refresh
        time_checker._refresh_cache_if_needed()
        print(f'Shifts cache: {time_checker._shifts_cache}')

except Exception as e:
    print(f'Error: {e}')
    import traceback
    traceback.print_exc() 