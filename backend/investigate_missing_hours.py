#!/usr/bin/env python3

import os, sys
sys.path.append('.')
from app.data_ingestion.mariadb_parser import get_db_connection
import mysql.connector

# The 6 problematic job IDs
problematic_jobs = [
    'JOAW25060037_CD11-026-9/6',
    'JOST25050164_CP08-259-5/4', 
    'JOST25050055_CP08-086-4/4',
    'JOST25050054_CP08-085-4/4',
    'JOAW25050031_CD11-026-9/6',
    'JOAW25040171_CP08-071-3/3'
]

print('Analyzing the 6 jobs with missing hours_need data...')
print('=' * 60)

conn = get_db_connection()
if conn:
    cursor = conn.cursor(dictionary=True)
    
    # Check the raw data for these specific jobs
    for job_id in problematic_jobs:
        job_parts = job_id.split('_')
        if len(job_parts) >= 2:
            job_ref = job_parts[0]  # e.g., JOAW25060037
            process_code = job_parts[1]  # e.g., CD11-026-9/6
            
            query = '''
            SELECT 
                jot.DocRef_v as job_ref,
                jop.Task_v as process_code,
                jop.CapMin_d,
                jop.CapQty_d, 
                jop.LeadTime_d,
                jop.Machine_v,
                jot.JoQty_d,
                -- The exact hours_need calculation from the main query
                CASE WHEN jop.CapMin_d = 1 AND jop.CapQty_d != 0 
                     THEN jot.JoQty_d / (jop.CapQty_d * 60) 
                     WHEN (jop.Machine_v IS NULL OR jop.Machine_v = '' OR jop.Machine_v = '0') 
                          AND jop.LeadTime_d IS NOT NULL AND jop.LeadTime_d > 0
                     THEN jop.LeadTime_d * 17.5
                     ELSE NULL END AS calculated_hours_need
            FROM tbl_jo_process AS jop 
            INNER JOIN tbl_jo_txn AS jot ON jot.TxnId_i = jop.TxnId_i 
            WHERE jot.DocRef_v = %s AND jop.Task_v = %s
            '''
            
            try:
                cursor.execute(query, (job_ref, process_code))
                results = cursor.fetchall()
                
                print(f'Job: {job_id}')
                if results:
                    for row in results:
                        print(f'  DocRef_v: {row["job_ref"]}')
                        print(f'  Task_v: {row["process_code"]}')
                        print(f'  CapMin_d: {row["CapMin_d"]}')
                        print(f'  CapQty_d: {row["CapQty_d"]}')
                        print(f'  LeadTime_d: {row["LeadTime_d"]}')
                        print(f'  Machine_v: {row["Machine_v"]}')
                        print(f'  JoQty_d: {row["JoQty_d"]}')
                        print(f'  calculated_hours_need: {row["calculated_hours_need"]}')
                        
                        # Analyze why hours_need is NULL
                        capmin = row['CapMin_d']
                        capqty = row['CapQty_d']
                        leadtime = row['LeadTime_d']
                        machine = row['Machine_v']
                        
                        print(f'  Analysis:')
                        condition1 = capmin == 1 and capqty != 0
                        machine_empty = machine in [None, '', '0']
                        leadtime_valid = leadtime is not None and leadtime > 0
                        condition2 = machine_empty and leadtime_valid
                        
                        print(f'    - Condition 1 (CapMin_d=1 AND CapQty_d!=0): CapMin_d={capmin}, CapQty_d={capqty} -> {condition1}')
                        print(f'    - Condition 2 (No Machine AND LeadTime_d>0): Machine empty={machine_empty}, LeadTime_d={leadtime}, LeadTime_d>0={leadtime_valid}')
                        print(f'    - Overall Condition 2: {condition2}')
                        
                        if not condition1 and not condition2:
                            print(f'    - REASON: Neither condition met -> hours_need = NULL')
                        elif condition1:
                            print(f'    - Using Condition 1: JoQty_d / (CapQty_d * 60)')
                        elif condition2:  
                            print(f'    - Using Condition 2: LeadTime_d * 17.5')
                            
                else:
                    print(f'  No data found for job {job_ref} with process {process_code}')
                print()
                
            except Exception as e:
                print(f'  Error querying job {job_id}: {e}')
                print()
    
    conn.close()
else:
    print('Failed to connect to database')