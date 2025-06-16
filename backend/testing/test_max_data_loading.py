#!/usr/bin/env python3
"""
Maximum Data Loading Performance Test
Tests MariaDB data loading with all available data (no limits)
"""

import time
import os
import sys
import psutil
import gc
import json
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional
import mysql.connector
from mysql.connector import Error

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from app.data_ingestion.mariadb_parser import (
        get_db_connection,
        test_database_connection
    )
except ImportError:
    from backend.app.data_ingestion.mariadb_parser import (
        get_db_connection,
        test_database_connection
    )

class MaxDataTester:
    def __init__(self):
        self.process = psutil.Process()
        
    def get_memory_usage(self) -> float:
        """Get current memory usage in MB"""
        return self.process.memory_info().rss / 1024 / 1024
    
    def count_available_data(self) -> Dict:
        """Count all available data in the database"""
        conn = get_db_connection()
        if not conn:
            return {"error": "Database connection failed"}
        
        cursor = conn.cursor(dictionary=True)
        counts = {}
        
        try:
            # Count total jobs
            cursor.execute("SELECT COUNT(*) as total FROM tbl_jo_txn WHERE Void_c != 1")
            counts['total_jobs'] = cursor.fetchone()['total']
            
            # Count jobs with positive quantity
            cursor.execute("""
                SELECT COUNT(DISTINCT jot.TxnId_i) as total 
                FROM tbl_jo_txn jot 
                JOIN tbl_jo_process jop ON jot.TxnId_i = jop.TxnId_i 
                WHERE jot.Void_c != 1 
                AND jot.DocStatus_c NOT IN ('CP', 'CX')
                AND jop.QtyStatus_c != 'FF'
                AND jot.JoQty_d > 0
            """)
            counts['jobs_with_quantity'] = cursor.fetchone()['total']
            
            # Count jobs within different time horizons
            today = datetime.now().date()
            horizons = [30, 60, 90, 180, 365]
            
            for days in horizons:
                end_date = today + timedelta(days=days)
                cursor.execute("""
                    SELECT COUNT(DISTINCT jot.TxnId_i) as total 
                    FROM tbl_jo_txn jot 
                    JOIN tbl_jo_process jop ON jot.TxnId_i = jop.TxnId_i 
                    WHERE jot.Void_c != 1 
                    AND jot.DocStatus_c NOT IN ('CP', 'CX')
                    AND jop.QtyStatus_c != 'FF'
                    AND jot.JoQty_d > 0 
                    AND jot.TargetDate_dd > %s 
                    AND jot.TargetDate_dd <= %s
                    AND jot.MaterialDate_dd IS NOT NULL 
                    AND jot.MaterialDate_dd <= %s
                """, (today, end_date, today))
                counts[f'jobs_{days}_days'] = cursor.fetchone()['total']
            
            # Count without any date restrictions
            cursor.execute("""
                SELECT COUNT(DISTINCT jot.TxnId_i) as total 
                FROM tbl_jo_txn jot 
                JOIN tbl_jo_process jop ON jot.TxnId_i = jop.TxnId_i 
                WHERE jot.Void_c != 1 
                AND jot.DocStatus_c NOT IN ('CP', 'CX')
                AND jop.QtyStatus_c != 'FF'
                AND jot.JoQty_d > 0
                AND jot.MaterialDate_dd IS NOT NULL
            """)
            counts['jobs_no_date_limit'] = cursor.fetchone()['total']
            
            # Count machines
            cursor.execute("SELECT COUNT(DISTINCT MachineName_v) as total FROM tbl_machine WHERE Void_c = 0")
            counts['total_machines'] = cursor.fetchone()['total']
            
            # Count setup times
            cursor.execute("SELECT COUNT(*) as total FROM ai_mcg_setup_time WHERE setup_time_minutes > 0")
            counts['setup_times'] = cursor.fetchone()['total']
            
            return counts
            
        except Error as e:
            return {"error": f"Query execution failed: {e}"}
        finally:
            cursor.close()
            conn.close()
    
    def load_all_data_custom(self, planning_horizon_days: Optional[int] = None) -> Dict:
        """Custom data loading without using the mariadb_parser"""
        gc.collect()
        start_memory = self.get_memory_usage()
        start_time = time.time()
        
        conn = get_db_connection()
        if not conn:
            return {"error": "Database connection failed"}
        
        cursor = conn.cursor(dictionary=True)
        
        try:
            # Build query with optional planning horizon
            today = datetime.now().date()
            
            # Use the exact query structure from mariadb_parser
            query = """
            SELECT 
                jot.DocRef_v as jot,
                jop.Task_v as jop,
                COALESCE(di.JoId_i, '') as di,
                jot.TargetDate_dd as rdd,
                jot.MaterialDate_dd as edd,
                jot.JoQty_d - COALESCE((
                    SELECT SUM(Qty_d) 
                    FROM tbl_daily_item 
                    WHERE JoId_i = jop.TxnId_i 
                    AND ProcessrowId_i = jop.RowId_i 
                    AND Void_c = 0
                ), 0) as qr,
                COALESCE(jop.Machine_v, '') as mcs,
                COALESCE(jop.Machine_v, '') as mcg,
                COALESCE(jop.LeadTime_d, 0) as tm,
                COALESCE(
                    CASE 
                        WHEN jop.CapMin_d > 0 AND jop.CapQty_d > 0 
                        THEN jop.CapMin_d / jop.CapQty_d * jot.JoQty_d / jop.ManCount_i
                        ELSE 0
                    END, 0
                ) as rcl
            FROM tbl_jo_process jop
            INNER JOIN tbl_jo_txn jot ON jot.TxnId_i = jop.TxnId_i
            LEFT JOIN tbl_daily_item di ON di.JoId_i = jop.TxnId_i AND di.ProcessrowId_i = jop.RowId_i AND di.Void_c = 0
            WHERE jot.Void_c != 1 
                AND jot.DocStatus_c NOT IN ('CP', 'CX')
                AND jop.QtyStatus_c != 'FF'
                AND jot.JoQty_d > 0
                AND jot.TargetDate_dd > %s
                AND jot.CreateDate_dt >= DATE_SUB(CURDATE(), INTERVAL 100 DAY)
                AND jot.MaterialDate_dd IS NOT NULL 
                AND jot.MaterialDate_dd <= %s
            """
            
            params = [today, today]
            
            if planning_horizon_days:
                end_date = today + timedelta(days=planning_horizon_days)
                query += " AND jot.TargetDate_dd <= %s"
                params.append(end_date)
            
            query += " ORDER BY jot.TargetDate_dd, jot.DocRef_v"
            
            # Execute query
            query_start = time.time()
            cursor.execute(query, params)
            raw_data = cursor.fetchall()
            query_time = time.time() - query_start
            
            # Process data
            jobs = []
            for row in raw_data:
                # Skip invalid jobs
                if row['qr'] is None or row['qr'] <= 0:
                    continue
                    
                job = {
                    'jot': row['jot'],
                    'jop': row['jop'],
                    'di': row['di'],
                    'rdd': row['rdd'],
                    'edd': row['edd'],
                    'qr': float(row['qr']),
                    'mcs': row['mcs'],
                    'mcg': row['mcg'],
                    'tm': float(row['tm']),
                    'rcl': float(row['rcl'])
                }
                jobs.append(job)
            
            # Load machines - use the actual structure
            cursor.execute("""
                SELECT DISTINCT 
                    MachineName_v as machine_id,
                    machine_id_v as line,
                    MachineName_v as description
                FROM tbl_machine 
                WHERE Void_c = 0
                ORDER BY machine_id_v, MachineName_v
            """)
            machines = cursor.fetchall()
            
            # Load setup times
            cursor.execute("""
                SELECT from_mcg, to_mcg, setup_time_minutes
                FROM ai_mcg_setup_time
                WHERE setup_time_minutes > 0
            """)
            setup_times = cursor.fetchall()
            
            end_time = time.time()
            end_memory = self.get_memory_usage()
            
            return {
                'status': 'success',
                'jobs_count': len(jobs),
                'raw_records': len(raw_data),
                'machines_count': len(machines),
                'setup_times_count': len(setup_times),
                'query_time': query_time,
                'total_time': end_time - start_time,
                'memory_used_mb': end_memory - start_memory,
                'peak_memory_mb': end_memory,
                'jobs_per_second': len(jobs) / (end_time - start_time) if end_time > start_time else 0,
                'data_size_mb': (sys.getsizeof(jobs) + sys.getsizeof(machines) + sys.getsizeof(setup_times)) / 1024 / 1024
            }
            
        except Exception as e:
            return {
                'status': 'error',
                'error': str(e),
                'time': time.time() - start_time
            }
        finally:
            cursor.close()
            conn.close()
    
    def run_max_data_tests(self) -> None:
        """Run comprehensive max data tests"""
        print("🚀 Starting Maximum Data Loading Performance Tests")
        print("=" * 60)
        
        # Test database connection
        print("\n1. Testing database connection...")
        if not test_database_connection():
            print("❌ Database connection failed!")
            return
        print("✅ Database connection successful")
        
        # Count available data
        print("\n2. Counting available data...")
        counts = self.count_available_data()
        if 'error' in counts:
            print(f"❌ Error counting data: {counts['error']}")
            return
        
        print("\n📊 Database Statistics:")
        for key, value in counts.items():
            print(f"   - {key}: {value:,}")
        
        # Test with different configurations
        print("\n3. Running performance tests...")
        
        test_configs = [
            {"name": "90 days horizon", "horizon": 90},
            {"name": "180 days horizon", "horizon": 180},
            {"name": "365 days horizon", "horizon": 365},
            {"name": "No time limit", "horizon": None}
        ]
        
        results = []
        
        for config in test_configs:
            print(f"\n   Testing: {config['name']}...")
            
            # Run test 3 times and average
            test_results = []
            for i in range(3):
                result = self.load_all_data_custom(config['horizon'])
                test_results.append(result)
                
                if result.get('status') == 'success':
                    print(f"      Run {i+1}: {result['jobs_count']:,} jobs in {result['total_time']:.2f}s")
                else:
                    print(f"      Run {i+1}: ❌ {result.get('error')}")
                
                time.sleep(0.5)
                gc.collect()
            
            # Calculate averages
            if all(r.get('status') == 'success' for r in test_results):
                avg_result = {
                    'config': config['name'],
                    'horizon_days': config['horizon'],
                    'jobs_count': test_results[0]['jobs_count'],
                    'avg_query_time': sum(r['query_time'] for r in test_results) / 3,
                    'avg_total_time': sum(r['total_time'] for r in test_results) / 3,
                    'avg_memory_mb': sum(r['memory_used_mb'] for r in test_results) / 3,
                    'avg_speed': sum(r['jobs_per_second'] for r in test_results) / 3,
                    'data_size_mb': test_results[0]['data_size_mb']
                }
                results.append(avg_result)
        
        # Generate report
        self.generate_max_data_report(counts, results)
    
    def generate_max_data_report(self, counts: Dict, results: List[Dict]) -> None:
        """Generate comprehensive report"""
        print("\n" + "=" * 60)
        print("MAXIMUM DATA LOADING PERFORMANCE REPORT")
        print("=" * 60)
        
        print("\n## Database Statistics")
        print(f"- Total Jobs in Database: {counts.get('total_jobs', 0):,}")
        print(f"- Jobs with Quantity > 0: {counts.get('jobs_with_quantity', 0):,}")
        print(f"- Active Machines: {counts.get('total_machines', 0):,}")
        print(f"- Setup Time Entries: {counts.get('setup_times', 0):,}")
        
        print("\n## Performance Results")
        print("\n| Configuration | Jobs Loaded | Query Time (s) | Total Time (s) | Memory (MB) | Speed (jobs/s) |")
        print("|---------------|-------------|----------------|----------------|-------------|----------------|")
        
        for r in results:
            print(f"| {r['config']:13} | {r['jobs_count']:11,} | {r['avg_query_time']:14.3f} | {r['avg_total_time']:14.3f} | {r['avg_memory_mb']:11.1f} | {r['avg_speed']:14.0f} |")
        
        print("\n## Key Findings")
        if results:
            max_jobs_result = max(results, key=lambda x: x['jobs_count'])
            print(f"- Maximum Jobs Loaded: {max_jobs_result['jobs_count']:,} ({max_jobs_result['config']})")
            print(f"- Best Query Performance: {min(r['avg_query_time'] for r in results):.3f}s")
            print(f"- Best Loading Speed: {max(r['avg_speed'] for r in results):,.0f} jobs/second")
            print(f"- Data Size in Memory: {max_jobs_result['data_size_mb']:.1f} MB for {max_jobs_result['jobs_count']:,} jobs")
            
            # Memory efficiency
            if max_jobs_result['jobs_count'] > 0:
                mb_per_1k_jobs = (max_jobs_result['data_size_mb'] / max_jobs_result['jobs_count']) * 1000
                print(f"- Memory Efficiency: {mb_per_1k_jobs:.2f} MB per 1,000 jobs")
        
        print("\n## Recommendations")
        if results and max_jobs_result['jobs_count'] > 10000:
            print("- ✅ System successfully handles large datasets (10K+ jobs)")
        elif results and max_jobs_result['jobs_count'] > 5000:
            print("- ⚠️ System handles medium datasets (5K-10K jobs)")
        else:
            print("- ℹ️ Limited data available in database for stress testing")
        
        if results and max_jobs_result['avg_speed'] > 1000:
            print("- ✅ Excellent loading performance maintained at scale")
        
        # Save detailed results
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"max_data_loading_results_{timestamp}.json"
        with open(filename, 'w') as f:
            json.dump({
                'counts': counts,
                'results': results,
                'timestamp': timestamp
            }, f, indent=2, default=str)
        print(f"\n📊 Detailed results saved to: {filename}")

def main():
    """Run maximum data loading tests"""
    tester = MaxDataTester()
    tester.run_max_data_tests()

if __name__ == "__main__":
    main()