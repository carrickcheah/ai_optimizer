#!/usr/bin/env python3
"""
Generate complete dependency failures report
"""

import mysql.connector
import os
from dotenv import load_dotenv

load_dotenv()

def generate_dependency_report():
    # Database connection
    conn = mysql.connector.connect(
        host=os.getenv('MARIADB_HOST'),
        user=os.getenv('MARIADB_USERNAME'),
        password=os.getenv('MARIADB_PASSWORD'),
        database=os.getenv('MARIADB_DATABASE'),
        port=int(os.getenv('MARIADB_PORT', 3306))
    )
    
    cursor = conn.cursor()
    
    # Get all dependency failures
    cursor.execute("""
        WITH active_jobs AS (
            SELECT DISTINCT
                t.DocRef_v as job_number,
                p.Task_v as process_code,
                SUBSTRING_INDEX(p.Task_v, '-', 2) as job_family,
                CAST(SUBSTRING_INDEX(SUBSTRING_INDEX(p.Task_v, '-', -1), '/', 1) AS UNSIGNED) as step_number,
                CAST(SUBSTRING_INDEX(p.Task_v, '/', -1) AS UNSIGNED) as total_steps,
                t.TargetDate_dd as target_date,
                p.ProcessDescr_v as process_description,
                p.Machine_v as required_machine
            FROM nex_valiant.tbl_jo_process p
            JOIN nex_valiant.tbl_jo_txn t ON p.TxnId_i = t.TxnId_i
            WHERE p.Task_v REGEXP '^[A-Z]+[0-9]+-[0-9]+-[0-9]+/[0-9]+$'
              AND t.DocStatus_c NOT IN ('CL', 'VO', 'CN')
              AND t.Void_c = '0'
              AND t.TargetDate_dd >= CURDATE()
        )
        SELECT 
            aj.job_number,
            aj.process_code,
            aj.job_family,
            aj.step_number,
            aj.total_steps,
            aj.target_date,
            aj.process_description,
            aj.required_machine
        FROM active_jobs aj
        LEFT JOIN active_jobs prereq ON (
            aj.job_number = prereq.job_number 
            AND aj.job_family = prereq.job_family
            AND prereq.step_number = aj.step_number - 1
        )
        WHERE aj.step_number > 1
          AND prereq.job_number IS NULL
        ORDER BY aj.job_family, aj.job_number, aj.step_number
    """)
    
    failures = cursor.fetchall()
    
    # Generate report
    report = []
    report.append("# ALL JOBS THAT FAIL DUE TO DEPENDENCY ISSUES")
    report.append(f"**Generated**: {__import__('datetime').datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    report.append(f"**Total Dependency Failures**: {len(failures)}")
    report.append("")
    
    # Group by family
    families = {}
    for failure in failures:
        job_number, process_code, job_family, step_number, total_steps, target_date, process_desc, machine = failure
        if job_family not in families:
            families[job_family] = []
        families[job_family].append({
            'job_number': job_number,
            'process_code': process_code,
            'step_number': step_number,
            'total_steps': total_steps,
            'target_date': target_date,
            'process_desc': process_desc,
            'machine': machine
        })
    
    report.append("## SUMMARY BY JOB FAMILY")
    report.append("")
    report.append("| Job Family | Total Failures | Unique Jobs | Blocked Steps | Date Range |")
    report.append("|------------|----------------|-------------|---------------|------------|")
    
    # Sort families by number of failures
    sorted_families = sorted(families.items(), key=lambda x: len(x[1]), reverse=True)
    
    for family, family_failures in sorted_families:
        unique_jobs = len(set(f['job_number'] for f in family_failures))
        blocked_steps = sorted(set(f['step_number'] for f in family_failures))
        blocked_steps_str = ', '.join(map(str, blocked_steps))
        min_date = min(f['target_date'] for f in family_failures)
        max_date = max(f['target_date'] for f in family_failures)
        
        report.append(f"| {family} | {len(family_failures)} | {unique_jobs} | {blocked_steps_str} | {min_date} to {max_date} |")
    
    report.append("")
    report.append("## DETAILED FAILURE LIST")
    report.append("")
    report.append("| Job Number | Process Code | Family | Step | Missing Prerequisite | Target Date | Process Description | Machine |")
    report.append("|------------|--------------|--------|------|-------------------|-------------|-------------------|---------|")
    
    for failure in failures:
        job_number, process_code, job_family, step_number, total_steps, target_date, process_desc, machine = failure
        missing_prereq = f"Needs step {step_number-1}/{total_steps}"
        current_step = f"Step {step_number}/{total_steps}"
        
        # Clean up description and machine for display
        process_desc = (process_desc or '').replace('|', '\\|')[:50]
        machine = (machine or '').replace('|', '\\|')[:20]
        
        report.append(f"| {job_number} | {process_code} | {job_family} | {current_step} | {missing_prereq} | {target_date} | {process_desc} | {machine} |")
    
    # Close connection
    cursor.close()
    conn.close()
    
    return '\n'.join(report)

if __name__ == "__main__":
    report = generate_dependency_report()
    print(report)