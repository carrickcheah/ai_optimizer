#!/usr/bin/env python3

import os, sys
sys.path.append('.')
from app.data_ingestion.mariadb_parser import get_db_connection
import mysql.connector

print('Checking machine assignments for the problematic jobs...')
print('=' * 60)

conn = get_db_connection()
if conn:
    cursor = conn.cursor(dictionary=True)
    
    # Check what machines 119 and 1 are
    machine_query = '''
    SELECT 
        machine_id_v,
        MachineId_i,
        MachineName_v,
        Description_v
    FROM tbl_machine 
    WHERE machine_id_v IN ('119', '1') OR MachineId_i IN (119, 1)
    '''
    
    try:
        cursor.execute(machine_query)
        machines = cursor.fetchall()
        
        print('Machine Details:')
        for machine in machines:
            print(f'  machine_id_v: {machine["machine_id_v"]}')
            print(f'  MachineId_i: {machine["MachineId_i"]}')
            print(f'  MachineName_v: {machine["MachineName_v"]}')
            print(f'  Description_v: {machine["Description_v"]}')
            print()
            
    except Exception as e:
        print(f'Error querying machines: {e}')
    
    # Now let's check if there are any jobs that DO get hours_need calculated
    # Let's look for jobs with CapMin_d=1 and CapQty_d!=0
    working_jobs_query = '''
    SELECT 
        jot.DocRef_v as job_ref,
        jop.Task_v as process_code,
        jop.CapMin_d,
        jop.CapQty_d, 
        jop.LeadTime_d,
        jop.Machine_v,
        jot.JoQty_d,
        CASE WHEN jop.CapMin_d = 1 AND jop.CapQty_d != 0 
             THEN jot.JoQty_d / (jop.CapQty_d * 60) 
             WHEN (jop.Machine_v IS NULL OR jop.Machine_v = '' OR jop.Machine_v = '0') 
                  AND jop.LeadTime_d IS NOT NULL AND jop.LeadTime_d > 0
             THEN jop.LeadTime_d * 17.5
             ELSE NULL END AS calculated_hours_need
    FROM tbl_jo_process AS jop 
    INNER JOIN tbl_jo_txn AS jot ON jot.TxnId_i = jop.TxnId_i 
    WHERE jot.Void_c != 1 
          AND jot.DocStatus_c NOT IN ('CP', 'CX') 
          AND jop.QtyStatus_c != 'FF' 
          AND jot.TargetDate_dd > CURDATE()
          AND jot.TargetDate_dd <= DATE_ADD(CURDATE(), INTERVAL 180 DAY)
          AND jot.CreateDate_dt >= DATE_SUB(CURDATE(), INTERVAL 100 DAY)
          AND jot.MaterialDate_dd IS NOT NULL
          AND jot.MaterialDate_dd <= CURDATE()
          AND (
              (jop.CapMin_d = 1 AND jop.CapQty_d != 0) OR
              ((jop.Machine_v IS NULL OR jop.Machine_v = '' OR jop.Machine_v = '0') 
               AND jop.LeadTime_d IS NOT NULL AND jop.LeadTime_d > 0)
          )
    LIMIT 10
    '''
    
    try:
        cursor.execute(working_jobs_query)
        working_jobs = cursor.fetchall()
        
        print(f'Sample of jobs that DO have hours_need calculated ({len(working_jobs)} found):')
        for job in working_jobs:
            print(f'  Job: {job["job_ref"]}_{job["process_code"]}')
            print(f'    CapMin_d: {job["CapMin_d"]}, CapQty_d: {job["CapQty_d"]}')
            print(f'    LeadTime_d: {job["LeadTime_d"]}, Machine_v: {job["Machine_v"]}')
            print(f'    calculated_hours_need: {job["calculated_hours_need"]}')
            print()
            
    except Exception as e:
        print(f'Error querying working jobs: {e}')
    
    conn.close()
else:
    print('Failed to connect to database')