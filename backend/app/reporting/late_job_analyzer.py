"""Late Job Analyzer - Identifies and reports jobs scheduled past their plan dates."""

import logging
from datetime import datetime
from typing import Dict, List, Any, Tuple
import pytz

logger = logging.getLogger(__name__)

class LateJobAnalyzer:
    """Analyzes scheduled jobs to identify those that are late relative to their plan dates."""
    
    @staticmethod
    def analyze_late_jobs(schedule: Dict[str, List[Tuple]], jobs: List[Dict[str, Any]], 
                         current_time: float = None) -> Dict[str, Any]:
        """
        Analyze scheduled jobs to identify late ones.
        
        Args:
            schedule: Dictionary with machine IDs as keys and scheduled jobs as values
            jobs: Original job list with plan_date information
            current_time: Current timestamp (defaults to now)
            
        Returns:
            Dictionary with late job analysis
        """
        if current_time is None:
            current_time = datetime.now().timestamp()
        
        # Create job lookup dictionary
        job_lookup = {job['job_id']: job for job in jobs}
        
        # Analyze scheduled jobs
        late_jobs = []
        on_time_jobs = []
        future_jobs = []
        
        malaysia_tz = pytz.timezone('Asia/Kuala_Lumpur')
        
        for machine, tasks in schedule.items():
            for task in tasks:
                job_id = task[0]
                start_time = task[1]
                end_time = task[2]
                
                # Skip segment jobs
                if '_seg' in job_id:
                    base_job_id = job_id.split('_seg')[0]
                else:
                    base_job_id = job_id
                
                job_data = job_lookup.get(base_job_id)
                if not job_data:
                    continue
                
                plan_date_epoch = job_data.get('plan_date_epoch')
                if not plan_date_epoch:
                    continue
                
                # Calculate lateness
                days_late = (start_time - plan_date_epoch) / 86400
                
                # Convert timestamps to readable dates
                start_dt = datetime.fromtimestamp(start_time, tz=malaysia_tz)
                plan_dt = datetime.fromtimestamp(plan_date_epoch, tz=malaysia_tz)
                
                job_info = {
                    'job_id': job_id,
                    'machine': machine,
                    'plan_date': plan_dt.strftime('%Y-%m-%d'),
                    'scheduled_start': start_dt.strftime('%Y-%m-%d %H:%M'),
                    'days_late': days_late,
                    'lcd_date': job_data.get('lcd_date'),
                    'priority': job_data.get('priority', 99)
                }
                
                if days_late > 0.1:  # More than 2.4 hours late
                    late_jobs.append(job_info)
                elif days_late < -0.1:  # Future scheduled
                    future_jobs.append(job_info)
                else:
                    on_time_jobs.append(job_info)
        
        # Sort late jobs by days late (most late first)
        late_jobs.sort(key=lambda x: x['days_late'], reverse=True)
        
        # Calculate statistics
        total_scheduled = sum(len(tasks) for tasks in schedule.values())
        
        # Generate summary
        summary = {
            'total_scheduled': total_scheduled,
            'late_jobs_count': len(late_jobs),
            'on_time_jobs_count': len(on_time_jobs),
            'future_jobs_count': len(future_jobs),
            'late_percentage': (len(late_jobs) / total_scheduled * 100) if total_scheduled > 0 else 0,
            'late_jobs': late_jobs,
            'worst_late_jobs': late_jobs[:10],  # Top 10 most late
            'analysis_timestamp': datetime.now(tz=malaysia_tz).strftime('%Y-%m-%d %H:%M:%S')
        }
        
        # Log summary
        logger.info(f"Late Job Analysis Summary:")
        logger.info(f"  Total scheduled jobs: {total_scheduled}")
        logger.info(f"  Late jobs: {len(late_jobs)} ({summary['late_percentage']:.1f}%)")
        logger.info(f"  On-time jobs: {len(on_time_jobs)}")
        logger.info(f"  Future scheduled: {len(future_jobs)}")
        
        if late_jobs:
            logger.warning(f"Top 5 most late jobs:")
            for job in late_jobs[:5]:
                logger.warning(f"  {job['job_id']}: {job['days_late']:.1f} days late "
                             f"(planned: {job['plan_date']}, scheduled: {job['scheduled_start']})")
        
        return summary
    
    @staticmethod
    def generate_late_job_report(summary: Dict[str, Any]) -> str:
        """
        Generate a formatted report of late jobs.
        
        Args:
            summary: Late job analysis summary
            
        Returns:
            Formatted report string
        """
        report = []
        report.append("=" * 80)
        report.append("LATE JOB ANALYSIS REPORT")
        report.append(f"Generated: {summary['analysis_timestamp']}")
        report.append("=" * 80)
        report.append("")
        
        # Summary statistics
        report.append("SUMMARY STATISTICS")
        report.append("-" * 40)
        report.append(f"Total Scheduled Jobs: {summary['total_scheduled']}")
        report.append(f"Late Jobs: {summary['late_jobs_count']} ({summary['late_percentage']:.1f}%)")
        report.append(f"On-Time Jobs: {summary['on_time_jobs_count']}")
        report.append(f"Future Scheduled: {summary['future_jobs_count']}")
        report.append("")
        
        # Worst late jobs
        if summary['worst_late_jobs']:
            report.append("TOP 10 MOST LATE JOBS")
            report.append("-" * 40)
            report.append(f"{'Job ID':<30} {'Days Late':>10} {'Plan Date':>12} {'Scheduled':>16}")
            report.append("-" * 70)
            
            for job in summary['worst_late_jobs']:
                report.append(f"{job['job_id']:<30} {job['days_late']:>10.1f} "
                            f"{job['plan_date']:>12} {job['scheduled_start']:>16}")
        
        report.append("")
        report.append("=" * 80)
        
        return "\n".join(report)