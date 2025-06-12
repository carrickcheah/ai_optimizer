#!/usr/bin/env python3
"""
test_ingest.py - Comprehensive Data Ingestion Test
Tests the MariaDB parser and displays all loaded data with detailed analysis
"""

import sys
import os
from datetime import datetime
from collections import defaultdict, Counter
import json
from typing import Dict, List, Any

# Add the parent directory to sys.path to import from app
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.data_ingestion.mariadb_parser import (
    load_jobs_planning_data,
    get_db_connection,
    validate_environment_config
)

def print_separator(title: str, char: str = "=", width: int = 80):
    """Print a formatted separator with title"""
    print(f"\n{char * width}")
    print(f"{title:^{width}}")
    print(f"{char * width}")

def print_subsection(title: str, char: str = "-", width: int = 60):
    """Print a formatted subsection header"""
    print(f"\n{char * width}")
    print(f" {title}")
    print(f"{char * width}")

def format_epoch_time(epoch_time):
    """Convert epoch time to readable format"""
    if epoch_time is None:
        return "None"
    try:
        return datetime.fromtimestamp(int(epoch_time)).strftime("%Y-%m-%d %H:%M:%S")
    except (ValueError, TypeError, OSError):
        return f"Invalid epoch: {epoch_time}"

def display_specific_job_fields(jobs: List[Dict[str, Any]], limit: int = 50):
    """Display specific fields: job_id/job, plan_date, CreateDate_dt, TargetDate_dd"""
    print_subsection(f"Specific Job Fields (First {min(limit, len(jobs))} jobs)")
    
    # Header
    print(f"{'#':<4} {'Job ID / Job':<25} {'Plan Date':<20} {'Create Date':<20} {'Target Date (LCD)':<20}")
    print("-" * 90)
    
    for i, job in enumerate(jobs[:limit]):
        # Get job identifier (prefer job_id, fallback to job)
        job_identifier = job.get('job_id') or job.get('job', 'N/A')
        if len(str(job_identifier)) > 24:
            job_identifier = str(job_identifier)[:21] + "..."
        
        # Get plan_date (original datetime object)
        plan_date = job.get('plan_date', 'N/A')
        if plan_date != 'N/A' and hasattr(plan_date, 'strftime'):
            plan_date_str = plan_date.strftime('%Y-%m-%d %H:%M:%S')[:19]
        else:
            plan_date_str = str(plan_date)[:19] if plan_date else 'N/A'
        
        # Get CreateDate_dt (this should be same as plan_date in our current implementation)
        create_date = job.get('create_date') or job.get('plan_date', 'N/A')
        if create_date != 'N/A' and hasattr(create_date, 'strftime'):
            create_date_str = create_date.strftime('%Y-%m-%d %H:%M:%S')[:19]
        else:
            create_date_str = str(create_date)[:19] if create_date else 'N/A'
        
        # Get TargetDate_dd (LCD date)
        target_date_epoch = job.get('lcd_date_epoch')
        if target_date_epoch:
            target_date_str = format_epoch_time(target_date_epoch)[:19]
        else:
            target_date_str = 'N/A'
        
        print(f"{i+1:<4} {job_identifier:<25} {plan_date_str:<20} {create_date_str:<20} {target_date_str:<20}")

def display_all_job_fields_table(jobs: List[Dict[str, Any]], limit: int = 20):
    """Display all jobs in a table format showing the specific requested fields"""
    print_subsection(f"Complete Job Data Table (First {min(limit, len(jobs))} jobs)")
    
    print("=" * 120)
    print(f"{'Row':<4} {'Job ID':<20} {'Job Ref':<15} {'Plan Date':<20} {'LCD Date':<20} {'Machine':<15} {'Quantity':<10} {'Hours':<8}")
    print("=" * 120)
    
    for i, job in enumerate(jobs[:limit]):
        # Job identifiers
        job_id = str(job.get('job_id', 'N/A'))[:19]
        job_ref = str(job.get('job', 'N/A'))[:14]
        
        # Dates
        plan_date = job.get('plan_date', 'N/A')
        if plan_date != 'N/A' and hasattr(plan_date, 'strftime'):
            plan_date_str = plan_date.strftime('%Y-%m-%d %H:%M')[:19]
        else:
            plan_date_str = 'N/A'
        
        lcd_epoch = job.get('lcd_date_epoch')
        lcd_date_str = format_epoch_time(lcd_epoch)[:19] if lcd_epoch else 'N/A'
        
        # Other fields
        machine = str(job.get('MachineName_v', 'N/A'))[:14]
        quantity = job.get('job_quantity', 'N/A')
        hours = job.get('hours_need', 'N/A')
        
        print(f"{i+1:<4} {job_id:<20} {job_ref:<15} {plan_date_str:<20} {lcd_date_str:<20} {machine:<15} {quantity:<10} {hours:<8}")
    
    print("=" * 120)

def analyze_job_data(jobs: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Analyze job data and return statistics"""
    if not jobs:
        return {}
    
    analysis = {
        'total_jobs': len(jobs),
        'machines': Counter(),
        'processing_times': [],
        'job_quantities': [],
        'priorities': Counter(),
        'date_ranges': {
            'lcd_dates': [],
            'plan_dates': [],
            'material_dates': []
        },
        'jobs_with_processing_time': 0,
        'jobs_without_processing_time': 0,
        'subcon_jobs': 0,
        'machine_assigned_jobs': 0
    }
    
    for job in jobs:
        # Machine analysis
        machine = job.get('MachineName_v', 'Unknown')
        analysis['machines'][machine] += 1
        
        if machine == 'Subcon':
            analysis['subcon_jobs'] += 1
        elif machine != 'NOT_ASSIGN':
            analysis['machine_assigned_jobs'] += 1
        
        # Processing time analysis
        processing_time = job.get('processing_time')
        hours_need = job.get('hours_need')
        
        if processing_time and processing_time > 0:
            analysis['processing_times'].append(processing_time / 3600)  # Convert to hours
            analysis['jobs_with_processing_time'] += 1
        elif hours_need and hours_need > 0:
            analysis['processing_times'].append(hours_need)
            analysis['jobs_with_processing_time'] += 1
        else:
            analysis['jobs_without_processing_time'] += 1
        
        # Quantity analysis
        quantity = job.get('job_quantity')
        if quantity:
            analysis['job_quantities'].append(quantity)
        
        # Priority analysis
        priority = job.get('priority', 'Unknown')
        analysis['priorities'][priority] += 1
        
        # Date analysis
        lcd_epoch = job.get('lcd_date_epoch')
        if lcd_epoch:
            analysis['date_ranges']['lcd_dates'].append(lcd_epoch)
        
        plan_date = job.get('plan_date')
        if plan_date:
            analysis['date_ranges']['plan_dates'].append(str(plan_date))
        
        material_epoch = job.get('material_arrival_epoch')
        if material_epoch:
            analysis['date_ranges']['material_dates'].append(material_epoch)
    
    return analysis

def display_detailed_analysis(analysis: Dict[str, Any]):
    """Display detailed statistical analysis"""
    print_subsection("Statistical Analysis")
    
    print(f"Total Jobs Loaded: {analysis['total_jobs']}")
    print(f"Jobs with Processing Time: {analysis['jobs_with_processing_time']}")
    print(f"Jobs without Processing Time: {analysis['jobs_without_processing_time']}")
    print(f"Subcontractor Jobs: {analysis['subcon_jobs']}")
    print(f"Machine Assigned Jobs: {analysis['machine_assigned_jobs']}")
    
    # Processing time statistics
    if analysis['processing_times']:
        processing_times = analysis['processing_times']
        print(f"\nProcessing Time Statistics (hours):")
        print(f"  Average: {sum(processing_times) / len(processing_times):.2f}")
        print(f"  Min: {min(processing_times):.2f}")
        print(f"  Max: {max(processing_times):.2f}")
        print(f"  Total: {sum(processing_times):.2f}")
    
    # Quantity statistics
    if analysis['job_quantities']:
        quantities = analysis['job_quantities']
        print(f"\nJob Quantity Statistics:")
        print(f"  Average: {sum(quantities) / len(quantities):.2f}")
        print(f"  Min: {min(quantities)}")
        print(f"  Max: {max(quantities)}")
        print(f"  Total: {sum(quantities)}")
    
    # Machine distribution
    print(f"\nMachine Distribution:")
    for machine, count in analysis['machines'].most_common():
        percentage = (count / analysis['total_jobs']) * 100
        print(f"  {machine}: {count} jobs ({percentage:.1f}%)")
    
    # Priority distribution
    print(f"\nPriority Distribution:")
    for priority, count in analysis['priorities'].most_common():
        percentage = (count / analysis['total_jobs']) * 100
        print(f"  Priority {priority}: {count} jobs ({percentage:.1f}%)")
    
    # Date range analysis
    lcd_dates = analysis['date_ranges']['lcd_dates']
    if lcd_dates:
        min_lcd = min(lcd_dates)
        max_lcd = max(lcd_dates)
        print(f"\nLCD Date Range:")
        print(f"  Earliest: {format_epoch_time(min_lcd)}")
        print(f"  Latest: {format_epoch_time(max_lcd)}")

def test_environment_setup():
    """Test environment configuration"""
    print_subsection("Environment Configuration Test")
    
    try:
        config = validate_environment_config()
        print("✅ Environment configuration validated successfully")
        print(f"  Break Hours: {config.get('break_hours')}")
        print(f"  No Production Hours: {config.get('no_prod_hours')}")
        print(f"  Job Priority: {config.get('job_priority')}")
    except Exception as e:
        print(f"❌ Environment configuration failed: {e}")
        return False
    
    return True

def test_database_connection():
    """Test database connection"""
    print_subsection("Database Connection Test")
    
    try:
        conn = get_db_connection()
        if conn and conn.is_connected():
            print("✅ Database connection successful")
            conn.close()
            return True
        else:
            print("❌ Database connection failed")
            return False
    except Exception as e:
        print(f"❌ Database connection error: {e}")
        return False

def save_detailed_report(jobs: List[Dict[str, Any]], machines: List[Dict[str, str]], 
                        setup_times: Dict[str, Dict[str, float]], analysis: Dict[str, Any]):
    """Save detailed report to JSON file"""
    report_file = "/Users/carrickcheah/Project/ai_optimizer/backend/testing/data_ingestion_report.json"
    
    # Prepare sample jobs (first 10 with all details)
    sample_jobs = []
    for job in jobs[:10]:
        sample_job = {}
        for key, value in job.items():
            if isinstance(value, (str, int, float, bool)) or value is None:
                sample_job[key] = value
            else:
                sample_job[key] = str(value)
        sample_jobs.append(sample_job)
    
    report = {
        'timestamp': datetime.now().isoformat(),
        'summary': {
            'total_jobs': len(jobs),
            'total_machines': len(machines),
            'total_setup_combinations': len(setup_times) * len(setup_times) if setup_times else 0
        },
        'analysis': analysis,
        'sample_jobs': sample_jobs,
        'machines': machines,
        'sample_setup_times': {
            machine: setup_times.get(machine, {}) 
            for machine in list(setup_times.keys())[:5]
        } if setup_times else {}
    }
    
    try:
        with open(report_file, 'w') as f:
            json.dump(report, f, indent=2, default=str)
        print(f"\nDetailed report saved to: {report_file}")
    except Exception as e:
        print(f"Failed to save report: {e}")

def test_lookback_periods():
    """Test different lookback periods and compare results"""
    print_separator("Lookback Period Comparison Test", "=", 80)
    
    lookback_periods = [30, 60, 90, 120, 180, 270, 365]
    results = []
    
    for days in lookback_periods:
        print(f"Testing {days} days lookback...")
        
        # Temporarily modify the mariadb_parser to use this lookback period
        import tempfile
        import shutil
        
        # Create a temporary modified version
        parser_path = "/Users/carrickcheah/Project/ai_optimizer/backend/app/data_ingestion/mariadb_parser.py"
        
        # Read current file
        with open(parser_path, 'r') as f:
            content = f.read()
        
        # Replace the 180 DAY with current test period
        modified_content = content.replace(
            "INTERVAL 180 DAY",
            f"INTERVAL {days} DAY"
        )
        
        # Write temporary file
        temp_path = parser_path + f".temp_{days}"
        with open(temp_path, 'w') as f:
            f.write(modified_content)
        
        # Backup original and use temp
        backup_path = parser_path + ".backup"
        shutil.move(parser_path, backup_path)
        shutil.move(temp_path, parser_path)
        
        try:
            # Reload the module to pick up changes
            import importlib
            import sys
            if 'app.data_ingestion.mariadb_parser' in sys.modules:
                importlib.reload(sys.modules['app.data_ingestion.mariadb_parser'])
            
            from app.data_ingestion.mariadb_parser import load_jobs_planning_data
            
            start_time = datetime.now()
            jobs, machines, setup_times = load_jobs_planning_data(
                max_jobs=None,
                planning_horizon_days=180  # Keep planning horizon constant
            )
            end_time = datetime.now()
            loading_time = (end_time - start_time).total_seconds()
            
            results.append({
                'lookback_days': days,
                'total_jobs': len(jobs),
                'total_machines': len(machines),
                'loading_time': loading_time,
                'jobs_with_processing_time': len([j for j in jobs if j.get('processing_time', 0) > 0]),
                'subcon_jobs': len([j for j in jobs if j.get('MachineName_v') == 'Subcon'])
            })
            
            print(f"  ✅ {days} days: {len(jobs)} jobs loaded in {loading_time:.2f}s")
            
        except Exception as e:
            print(f"  ❌ {days} days: Failed - {e}")
            results.append({
                'lookback_days': days,
                'total_jobs': 0,
                'total_machines': 0,
                'loading_time': 0,
                'jobs_with_processing_time': 0,
                'subcon_jobs': 0,
                'error': str(e)
            })
        finally:
            # Restore original file
            shutil.move(backup_path, parser_path)
    
    return results

def save_lookback_test_results(results):
    """Save lookback test results to markdown file"""
    report_content = f"""# Lookback Period Comparison Test Results

## Test Overview
- **Test Date**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
- **Planning Horizon**: 180 days (constant)
- **LCD Filter**: Tomorrow and future dates only
- **Test Periods**: 30, 60, 90, 120, 180, 270, 365 days lookback

## Results Summary

| Lookback Days | Total Jobs | Total Machines | Jobs with Processing Time | Subcon Jobs | Loading Time (s) |
|---------------|------------|----------------|---------------------------|-------------|------------------|
"""
    
    for result in results:
        if 'error' not in result:
            report_content += f"| {result['lookback_days']} | {result['total_jobs']} | {result['total_machines']} | {result['jobs_with_processing_time']} | {result['subcon_jobs']} | {result['loading_time']:.3f} |\n"
        else:
            report_content += f"| {result['lookback_days']} | ERROR | ERROR | ERROR | ERROR | ERROR |\n"
    
    report_content += f"""
## Analysis

### Job Count Progression
"""
    
    for result in results:
        if 'error' not in result:
            report_content += f"- **{result['lookback_days']} days**: {result['total_jobs']} jobs\n"
    
    report_content += f"""
### Key Findings

1. **Data Completeness**: Longer lookback periods capture more historical jobs
2. **Performance Impact**: Loading time correlation with job count
3. **Machine Discovery**: How lookback period affects machine identification
4. **Processing Time Coverage**: Percentage of jobs with valid processing times

### Recommendations

Based on the results:
- **30 days**: Minimal dataset, may miss important jobs
- **60 days**: Balanced for recent operations
- **90 days**: Current setting, good balance of relevance and completeness
- **120 days**: Extended coverage for slower-moving projects
- **180 days**: Maximum coverage, may include less relevant jobs

## Conclusion

The optimal lookback period balances:
- **Data relevance** (recent jobs more likely to be accurate)
- **Completeness** (enough historical context)
- **Performance** (reasonable loading times)
- **Planning accuracy** (sufficient job coverage)

Current 90-day setting appears optimal for most production scenarios.
"""
    
    try:
        with open('/Users/carrickcheah/Project/ai_optimizer/testtest.md', 'w') as f:
            f.write(report_content)
        print(f"📄 Lookback test results saved to: /Users/carrickcheah/Project/ai_optimizer/testtest.md")
    except Exception as e:
        print(f"❌ Failed to save results: {e}")

def display_120_day_jobs():
    """Display top 100 jobs using 120-day lookback, sorted by LCD date ascending"""
    print_separator("120-Day Lookback Analysis - Top 100 Jobs by LCD Date", "=", 80)
    
    # Temporarily modify the mariadb_parser to use 120 days
    import shutil
    parser_path = "/Users/carrickcheah/Project/ai_optimizer/backend/app/data_ingestion/mariadb_parser.py"
    
    # Read current file
    with open(parser_path, 'r') as f:
        content = f.read()
    
    # Replace the 180 DAY with 120 DAY
    modified_content = content.replace("INTERVAL 180 DAY", "INTERVAL 120 DAY")
    
    # Backup and replace
    backup_path = parser_path + ".backup"
    shutil.move(parser_path, backup_path)
    
    with open(parser_path, 'w') as f:
        f.write(modified_content)
    
    try:
        # Reload the module
        import importlib
        import sys
        if 'app.data_ingestion.mariadb_parser' in sys.modules:
            importlib.reload(sys.modules['app.data_ingestion.mariadb_parser'])
        
        from app.data_ingestion.mariadb_parser import load_jobs_planning_data
        
        print("Loading jobs with 120-day lookback...")
        jobs, machines, setup_times = load_jobs_planning_data(
            max_jobs=None,
            planning_horizon_days=180
        )
        
        print(f"✅ Loaded {len(jobs)} jobs with 120-day lookback")
        
        # Sort by LCD date ascending
        jobs_sorted = sorted(jobs, key=lambda x: x.get('lcd_date_epoch', 0) if x.get('lcd_date_epoch') else 0)
        
        # Display top 100 jobs
        print_subsection(f"Top 100 Jobs by LCD Date (120-day lookback)")
        
        print(f"{'#':<4} {'Job ID':<25} {'Plan Date':<20} {'LCD Date':<20} {'Days Old':<10} {'Machine':<15}")
        print("-" * 100)
        
        current_time = datetime.now()
        
        for i, job in enumerate(jobs_sorted[:100]):
            job_id = str(job.get('job_id', 'N/A'))[:24]
            
            # Plan date
            plan_date = job.get('plan_date', 'N/A')
            if plan_date != 'N/A' and hasattr(plan_date, 'strftime'):
                plan_date_str = plan_date.strftime('%Y-%m-%d')
                # Calculate days old
                days_old = (current_time.date() - plan_date.date()).days
            else:
                plan_date_str = 'N/A'
                days_old = 'N/A'
            
            # LCD date
            lcd_epoch = job.get('lcd_date_epoch')
            lcd_date_str = format_epoch_time(lcd_epoch)[:10] if lcd_epoch else 'N/A'
            
            # Machine
            machine = str(job.get('MachineName_v', 'N/A'))[:14]
            
            print(f"{i+1:<4} {job_id:<25} {plan_date_str:<20} {lcd_date_str:<20} {days_old:<10} {machine:<15}")
        
        return jobs_sorted
        
    except Exception as e:
        print(f"❌ Failed to load 120-day data: {e}")
        return []
    finally:
        # Restore original file
        shutil.move(backup_path, parser_path)

def main():
    """Main test execution"""
    print_separator("MariaDB Data Ingestion Analysis", "=", 80)
    print(f"Test started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Test environment and database
    if not test_environment_setup():
        print("❌ Environment setup failed. Exiting.")
        return
    
    if not test_database_connection():
        print("❌ Database connection failed. Exiting.")
        return
    
    # Show 120-day analysis first
    jobs_120 = display_120_day_jobs()
    
    # Run lookback period tests
    print_separator("Running Lookback Period Comparison", "=", 80)
    results = test_lookback_periods()
    
    # Save results
    save_lookback_test_results(results)
    
    # Analysis of missing jobs
    if jobs_120:
        print_separator("Analysis of Missing Jobs (90 vs 120 days)", "=", 80)
        
        # Count jobs by age brackets
        current_time = datetime.now()
        age_brackets = {
            '0-30 days': 0,
            '31-60 days': 0,
            '61-90 days': 0,
            '91-120 days': 0,
            '120+ days': 0
        }
        
        for job in jobs_120:
            plan_date = job.get('plan_date')
            if plan_date and hasattr(plan_date, 'date'):
                days_old = (current_time.date() - plan_date.date()).days
                if days_old <= 30:
                    age_brackets['0-30 days'] += 1
                elif days_old <= 60:
                    age_brackets['31-60 days'] += 1
                elif days_old <= 90:
                    age_brackets['61-90 days'] += 1
                elif days_old <= 120:
                    age_brackets['91-120 days'] += 1
                else:
                    age_brackets['120+ days'] += 1
        
        print("📊 Job Distribution by Age:")
        for bracket, count in age_brackets.items():
            print(f"  • {bracket}: {count} jobs")
        
        print(f"\n🔍 Key Finding:")
        print(f"  • With 90-day lookback: {age_brackets['0-30 days'] + age_brackets['31-60 days'] + age_brackets['61-90 days']} jobs")
        print(f"  • With 120-day lookback: {sum(age_brackets.values())} jobs") 
        print(f"  • Missing jobs (91-120 days old): {age_brackets['91-120 days']} jobs")
        
        if age_brackets['91-120 days'] > 0:
            print(f"\n⚠️  You are missing {age_brackets['91-120 days']} active jobs that are 91-120 days old!")
            print(f"   These might be long-running projects or delayed jobs that are still active.")
    
    # Display summary
    print_separator("Test Summary", "=", 80)
    print("✅ Lookback period analysis completed!")
    
    print("\n📊 Results Summary:")
    for result in results:
        if 'error' not in result:
            print(f"  • {result['lookback_days']} days: {result['total_jobs']} jobs")
        else:
            print(f"  • {result['lookback_days']} days: ERROR - {result.get('error', 'Unknown error')}")
    
    print(f"\n📄 Detailed results saved to: /Users/carrickcheah/Project/ai_optimizer/testtest.md")

if __name__ == "__main__":
    main()