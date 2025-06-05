#!/usr/bin/env python3

import sys
sys.path.append('/Users/carrickcheah/Project/ai_optimizer/backend')

from app.api.fastapi_app import get_db_connection_from_pool

try:
    with get_db_connection_from_pool() as conn:
        cursor = conn.cursor(dictionary=True)
        
        # Check break times
        cursor.execute('SELECT * FROM ai_breaktimes WHERE is_active = 1 ORDER BY start_time')
        breaktimes = cursor.fetchall()
        
        print('Active break times:')
        for bt in breaktimes:
            print(f'  {bt["name"]}: {bt["start_time"]} - {bt["end_time"]} (mandatory: {bt["is_mandatory"]})')
        
        cursor.close()
        
except Exception as e:
    print(f'Error: {e}')
    import traceback
    traceback.print_exc() 