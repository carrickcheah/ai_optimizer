# Prepares data for textual reports 

# production_report_generator.py
"""Production-grade report generator for manufacturing schedules."""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Union
import pytz

logger = logging.getLogger(__name__)
SG_TIMEZONE = pytz.timezone('Asia/Singapore')

class ProductionReportGenerator:
    """Generates comprehensive production reports from schedule data."""
    
    def __init__(self, timezone: str = 'Asia/Singapore'):
        self.timezone = pytz.timezone(timezone)
    
    def generate_summary_report(self, schedule: Dict[str, Any], jobs_data: List[Dict]) -> Dict[str, Any]:
        """Generate executive summary report."""
        if not self._validate_inputs(schedule, jobs_data):
            raise ValueError("Invalid schedule or jobs data provided")
        
        total_jobs = len(jobs_data)
        scheduled_jobs = self._count_scheduled_jobs(schedule)
        
        return {
            'report_type': 'summary',
            'generated_at': datetime.now(self.timezone).isoformat(),
            'metrics': {
                'total_jobs': total_jobs,
                'scheduled_jobs': scheduled_jobs,
                'scheduling_rate': round((scheduled_jobs / total_jobs * 100), 2) if total_jobs > 0 else 0,
                'machines_utilized': len(schedule.keys()) if schedule else 0
            },
            'status': 'success'
        }
    
    def generate_efficiency_report(self, schedule: Dict[str, Any], jobs_data: List[Dict]) -> Dict[str, Any]:
        """Generate production efficiency analysis."""
        if not self._validate_inputs(schedule, jobs_data):
            raise ValueError("Invalid schedule or jobs data provided")
        
        machine_utilization = self._calculate_machine_utilization(schedule)
        priority_distribution = self._analyze_priority_distribution(jobs_data)
        
        return {
            'report_type': 'efficiency',
            'generated_at': datetime.now(self.timezone).isoformat(),
            'machine_utilization': machine_utilization,
            'priority_distribution': priority_distribution,
            'recommendations': self._generate_recommendations(machine_utilization),
            'status': 'success'
        }
    
    def generate_constraint_report(self, schedule: Dict[str, Any], jobs_data: List[Dict]) -> Dict[str, Any]:
        """Generate constraint violation analysis."""
        if not self._validate_inputs(schedule, jobs_data):
            raise ValueError("Invalid schedule or jobs data provided")
        
        violations = self._analyze_constraint_violations(schedule, jobs_data)
        
        return {
            'report_type': 'constraints',
            'generated_at': datetime.now(self.timezone).isoformat(),
            'violations': violations,
            'total_violations': sum(len(v) for v in violations.values()),
            'status': 'success'
        }
    
    def _validate_inputs(self, schedule: Any, jobs_data: Any) -> bool:
        """Validate input data structure."""
        if not isinstance(schedule, dict):
            logger.error("Schedule must be a dictionary")
            return False
        
        if not isinstance(jobs_data, list):
            logger.error("Jobs data must be a list")
            return False
        
        return True
    
    def _count_scheduled_jobs(self, schedule: Dict[str, Any]) -> int:
        """Count total scheduled jobs across all machines."""
        count = 0
        for machine_jobs in schedule.values():
            if isinstance(machine_jobs, list):
                count += len(machine_jobs)
        return count
    
    def _calculate_machine_utilization(self, schedule: Dict[str, Any]) -> Dict[str, float]:
        """Calculate utilization percentage for each machine."""
        utilization = {}
        
        for machine, jobs in schedule.items():
            if not isinstance(jobs, list) or not jobs:
                utilization[machine] = 0.0
                continue
            
            total_time = 0
            for job in jobs:
                if len(job) >= 3 and isinstance(job[1], (int, float)) and isinstance(job[2], (int, float)):
                    total_time += (job[2] - job[1])  # end - start
            
            # Convert to hours and calculate percentage (assuming 24h day)
            hours = total_time / 3600
            utilization[machine] = round(min(hours / 24 * 100, 100), 2)
        
        return utilization
    
    def _analyze_priority_distribution(self, jobs_data: List[Dict]) -> Dict[str, int]:
        """Analyze distribution of job priorities."""
        distribution = {'1': 0, '2': 0, '3': 0, '4': 0, '5': 0}
        
        for job in jobs_data:
            priority = str(job.get('priority', '3'))
            if priority in distribution:
                distribution[priority] += 1
        
        return distribution
    
    def _generate_recommendations(self, utilization: Dict[str, float]) -> List[str]:
        """Generate optimization recommendations."""
        recommendations = []
        
        high_util_machines = [m for m, u in utilization.items() if u > 90]
        low_util_machines = [m for m, u in utilization.items() if u < 50]
        
        if high_util_machines:
            recommendations.append(f"Consider load balancing for high-utilization machines: {', '.join(high_util_machines)}")
        
        if low_util_machines:
            recommendations.append(f"Optimize scheduling for under-utilized machines: {', '.join(low_util_machines)}")
        
        return recommendations
    
    def _analyze_constraint_violations(self, schedule: Dict[str, Any], jobs_data: List[Dict]) -> Dict[str, List[str]]:
        """Analyze schedule for constraint violations."""
        violations = {
            'start_date': [],
            'due_date': [],
            'sequence': []
        }
        
        # Create lookup for scheduled times
        scheduled_times = {}
        for machine, jobs in schedule.items():
            for job in jobs:
                if len(job) >= 3:
                    job_id = job[0]
                    scheduled_times[job_id] = {'start': job[1], 'end': job[2]}
        
        # Check violations
        for job in jobs_data:
            job_id = job.get('job_id')
            if not job_id or job_id not in scheduled_times:
                continue
            
            scheduled = scheduled_times[job_id]
            
            # Check start date constraints
            if 'start_date_epoch' in job and job['start_date_epoch']:
                required_start = job['start_date_epoch']
                actual_start = scheduled['start']
                if actual_start < required_start - 3600:  # 1 hour tolerance
                    violations['start_date'].append(job_id)
            
            # Check due date constraints
            if 'lcd_date_epoch' in job and job['lcd_date_epoch']:
                due_date = job['lcd_date_epoch']
                actual_end = scheduled['end']
                if actual_end > due_date:
                    violations['due_date'].append(job_id)
        
        return violations 