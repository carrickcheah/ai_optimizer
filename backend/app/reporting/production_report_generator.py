# production_report_generator.py
"""Production-grade report generator for manufacturing schedules with strict .env configuration."""

import logging
import os
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Union, Tuple
from dataclasses import dataclass
from functools import lru_cache
import pytz

logger = logging.getLogger(__name__)

@dataclass
class ReportConfig:
    """Configuration class for report generation settings - all values must be loaded from .env."""
    
    # Time and scheduling configuration
    normal_working_hours: float
    ot_working_hours: float
    emergency_ot_hours: float
    grace_period_hours: float
    
    # Buffer thresholds
    buffer_critical_hours: float
    buffer_warning_hours: float
    buffer_caution_hours: float
    
    # Utilization thresholds
    high_utilization_threshold: float
    low_utilization_threshold: float
    
    # Tolerance settings
    start_date_tolerance_hours: float
    
    # Timezone
    timezone: str
    
    @classmethod
    def from_env(cls) -> 'ReportConfig':
        """Create configuration from environment variables with strict validation."""
        missing_vars = []
        invalid_vars = []
        
        def get_required_float_env(key: str) -> Optional[float]:
            """Get required float environment variable with strict validation."""
            value = os.getenv(key)
            if value is None:
                missing_vars.append(key)
                return None
            
            try:
                return float(value)
            except (ValueError, TypeError):
                invalid_vars.append(f"{key}={value}")
                return None
        
        def get_required_str_env(key: str) -> Optional[str]:
            """Get required string environment variable."""
            value = os.getenv(key)
            if value is None:
                missing_vars.append(key)
                return None
            return value.strip()
        
        # Load all required configuration
        normal_working_hours = get_required_float_env('NORMAL_WORKING_HOURS')
        ot_working_hours = get_required_float_env('OT_WORKING_HOURS')
        emergency_ot_hours = get_required_float_env('EMERGENCY_OT_HOURS')
        grace_period_hours = get_required_float_env('GRACE_PERIOD_HOURS')
        
        buffer_critical_hours = get_required_float_env('CHART_BUFFER_CRITICAL_HOURS')
        buffer_warning_hours = get_required_float_env('CHART_BUFFER_WARNING_HOURS')
        buffer_caution_hours = get_required_float_env('CHART_BUFFER_CAUTION_HOURS')
        
        # Additional thresholds (with fallback to common values but log if missing)
        high_util_threshold = os.getenv('HIGH_UTILIZATION_THRESHOLD')
        if high_util_threshold is None:
            logger.warning("HIGH_UTILIZATION_THRESHOLD not set in .env, using 90.0")
            high_util_threshold = 90.0
        else:
            try:
                high_util_threshold = float(high_util_threshold)
            except (ValueError, TypeError):
                invalid_vars.append(f"HIGH_UTILIZATION_THRESHOLD={high_util_threshold}")
                high_util_threshold = 90.0
        
        low_util_threshold = os.getenv('LOW_UTILIZATION_THRESHOLD')
        if low_util_threshold is None:
            logger.warning("LOW_UTILIZATION_THRESHOLD not set in .env, using 50.0")
            low_util_threshold = 50.0
        else:
            try:
                low_util_threshold = float(low_util_threshold)
            except (ValueError, TypeError):
                invalid_vars.append(f"LOW_UTILIZATION_THRESHOLD={low_util_threshold}")
                low_util_threshold = 50.0
        
        start_tolerance = os.getenv('START_DATE_TOLERANCE_HOURS')
        if start_tolerance is None:
            logger.warning("START_DATE_TOLERANCE_HOURS not set in .env, using 1.0")
            start_tolerance = 1.0
        else:
            try:
                start_tolerance = float(start_tolerance)
            except (ValueError, TypeError):
                invalid_vars.append(f"START_DATE_TOLERANCE_HOURS={start_tolerance}")
                start_tolerance = 1.0
        
        timezone_str = get_required_str_env('TIMEZONE') or 'Asia/Kuala_Lumpur'
        if timezone_str == 'Asia/Kuala_Lumpur' and os.getenv('TIMEZONE') is None:
            logger.warning("TIMEZONE not set in .env, using 'Asia/Kuala_Lumpur'")
        
        # Check for critical errors
        if missing_vars:
            error_msg = f"❌ CRITICAL CONFIG ERROR: Missing required environment variables: {', '.join(missing_vars)}"
            logger.error(error_msg)
            raise ValueError(error_msg)
        
        if invalid_vars:
            error_msg = f"❌ CRITICAL CONFIG ERROR: Invalid environment variable values: {', '.join(invalid_vars)}"
            logger.error(error_msg)
            raise ValueError(error_msg)
        
        # Validate timezone
        try:
            pytz.timezone(timezone_str)
        except pytz.exceptions.UnknownTimeZoneError:
            error_msg = f"❌ CRITICAL CONFIG ERROR: Unknown timezone: {timezone_str}"
            logger.error(error_msg)
            raise ValueError(error_msg)
        
        logger.info(f"✅ Successfully loaded report configuration from .env")
        
        return cls(
            normal_working_hours=normal_working_hours,
            ot_working_hours=ot_working_hours,
            emergency_ot_hours=emergency_ot_hours,
            grace_period_hours=grace_period_hours,
            buffer_critical_hours=buffer_critical_hours,
            buffer_warning_hours=buffer_warning_hours,
            buffer_caution_hours=buffer_caution_hours,
            high_utilization_threshold=high_util_threshold,
            low_utilization_threshold=low_util_threshold,
            start_date_tolerance_hours=start_tolerance,
            timezone=timezone_str
        )


class ProductionReportGenerator:
    """Generates comprehensive production reports from schedule data with strict configuration."""
    
    def __init__(self, config: Optional[ReportConfig] = None):
        try:
            self.config = config or ReportConfig.from_env()
            self.timezone = pytz.timezone(self.config.timezone)
            logger.info(f"✅ ProductionReportGenerator initialized with timezone: {self.config.timezone}")
        except Exception as e:
            logger.error(f"❌ FAILED to initialize ProductionReportGenerator: {e}")
            raise
    
    def generate_summary_report(self, schedule: Dict[str, Any], jobs_data: List[Dict]) -> Dict[str, Any]:
        """Generate executive summary report with comprehensive metrics."""
        validation_errors = self._validate_inputs(schedule, jobs_data)
        if validation_errors:
            error_msg = f"Input validation failed: {'; '.join(validation_errors)}"
            logger.error(f"❌ SUMMARY REPORT FAILED: {error_msg}")
            raise ValueError(error_msg)
        
        try:
            total_jobs = len(jobs_data)
            scheduled_jobs = self._count_scheduled_jobs(schedule)
            machines_active = len([m for m, jobs in schedule.items() if jobs])
            
            # Calculate timing metrics
            timing_metrics = self._calculate_timing_metrics(schedule, jobs_data)
            buffer_analysis = self._analyze_buffer_status(schedule, jobs_data)
            
            report = {
                'report_type': 'summary',
                'generated_at': datetime.now(self.timezone).isoformat(),
                'config_snapshot': {
                    'working_hours': self.config.normal_working_hours,
                    'ot_hours': self.config.ot_working_hours,
                    'emergency_hours': self.config.emergency_ot_hours,
                    'buffer_thresholds': {
                        'critical': self.config.buffer_critical_hours,
                        'warning': self.config.buffer_warning_hours,
                        'caution': self.config.buffer_caution_hours
                    }
                },
                'metrics': {
                    'total_jobs': total_jobs,
                    'scheduled_jobs': scheduled_jobs,
                    'unscheduled_jobs': total_jobs - scheduled_jobs,
                    'scheduling_rate': round((scheduled_jobs / total_jobs * 100), 2) if total_jobs > 0 else 0,
                    'machines_total': len(schedule.keys()) if schedule else 0,
                    'machines_active': machines_active,
                    'machine_utilization_rate': round(machines_active / len(schedule) * 100, 2) if schedule else 0
                },
                'timing_analysis': timing_metrics,
                'buffer_status': buffer_analysis,
                'status': 'success'
            }
            
            logger.info(f"✅ Generated summary report: {scheduled_jobs}/{total_jobs} jobs scheduled ({report['metrics']['scheduling_rate']}%)")
            return report
            
        except Exception as e:
            logger.error(f"❌ FAILED to generate summary report: {e}")
            raise
    
    def generate_efficiency_report(self, schedule: Dict[str, Any], jobs_data: List[Dict]) -> Dict[str, Any]:
        """Generate production efficiency analysis with configurable thresholds."""
        validation_errors = self._validate_inputs(schedule, jobs_data)
        if validation_errors:
            error_msg = f"Input validation failed: {'; '.join(validation_errors)}"
            logger.error(f"❌ EFFICIENCY REPORT FAILED: {error_msg}")
            raise ValueError(error_msg)
        
        try:
            machine_utilization = self._calculate_machine_utilization(schedule)
            priority_distribution = self._analyze_priority_distribution(jobs_data)
            efficiency_metrics = self._calculate_efficiency_metrics(schedule, jobs_data)
            
            report = {
                'report_type': 'efficiency',
                'generated_at': datetime.now(self.timezone).isoformat(),
                'machine_utilization': machine_utilization,
                'priority_distribution': priority_distribution,
                'efficiency_metrics': efficiency_metrics,
                'recommendations': self._generate_recommendations(machine_utilization),
                'thresholds_used': {
                    'high_utilization': self.config.high_utilization_threshold,
                    'low_utilization': self.config.low_utilization_threshold
                },
                'status': 'success'
            }
            
            logger.info(f"✅ Generated efficiency report with {len(machine_utilization)} machines analyzed")
            return report
            
        except Exception as e:
            logger.error(f"❌ FAILED to generate efficiency report: {e}")
            raise
    
    def generate_constraint_report(self, schedule: Dict[str, Any], jobs_data: List[Dict]) -> Dict[str, Any]:
        """Generate constraint violation analysis with configurable tolerances."""
        validation_errors = self._validate_inputs(schedule, jobs_data)
        if validation_errors:
            error_msg = f"Input validation failed: {'; '.join(validation_errors)}"
            logger.error(f"❌ CONSTRAINT REPORT FAILED: {error_msg}")
            raise ValueError(error_msg)
        
        try:
            violations = self._analyze_constraint_violations(schedule, jobs_data)
            critical_issues = self._identify_critical_issues(violations)
            
            total_violations = sum(len(v) for v in violations.values())
            
            report = {
                'report_type': 'constraints',
                'generated_at': datetime.now(self.timezone).isoformat(),
                'violations': violations,
                'critical_issues': critical_issues,
                'total_violations': total_violations,
                'tolerance_settings': {
                    'start_date_tolerance_hours': self.config.start_date_tolerance_hours,
                    'grace_period_hours': self.config.grace_period_hours
                },
                'status': 'success'
            }
            
            if total_violations > 0:
                logger.warning(f"⚠️ Generated constraint report: {total_violations} violations found")
            else:
                logger.info(f"✅ Generated constraint report: No violations found")
                
            return report
            
        except Exception as e:
            logger.error(f"❌ FAILED to generate constraint report: {e}")
            raise
    
    def _validate_inputs(self, schedule: Any, jobs_data: Any) -> List[str]:
        """Validate input data structure with detailed error messages."""
        errors = []
        
        if not isinstance(schedule, dict):
            errors.append(f"Schedule must be a dictionary, got {type(schedule).__name__}")
        
        if not isinstance(jobs_data, list):
            errors.append(f"Jobs data must be a list, got {type(jobs_data).__name__}")
        
        if isinstance(schedule, dict):
            for machine, jobs in schedule.items():
                if not isinstance(jobs, list):
                    errors.append(f"Jobs for machine '{machine}' must be a list, got {type(jobs).__name__}")
                else:
                    for i, job in enumerate(jobs):
                        if not isinstance(job, (list, tuple)) or len(job) < 3:
                            errors.append(f"Job {i} for machine '{machine}' must be tuple/list with at least 3 elements")
                        elif len(job) >= 3:
                            start_time, end_time = job[1], job[2]
                            if not isinstance(start_time, (int, float)) or not isinstance(end_time, (int, float)):
                                errors.append(f"Job {i} for machine '{machine}' has invalid timestamp types")
                            elif end_time <= start_time:
                                errors.append(f"Job {i} for machine '{machine}' has invalid timing: end <= start")
        
        if isinstance(jobs_data, list):
            for i, job in enumerate(jobs_data):
                if not isinstance(job, dict):
                    errors.append(f"Job {i} must be a dictionary, got {type(job).__name__}")
                elif 'job_id' not in job:
                    errors.append(f"Job {i} missing required 'job_id' field")
        
        return errors
    
    def _count_scheduled_jobs(self, schedule: Dict[str, Any]) -> int:
        """Count total scheduled jobs across all machines."""
        count = 0
        for machine_jobs in schedule.values():
            if isinstance(machine_jobs, list):
                count += len(machine_jobs)
        return count
    
    def _calculate_machine_utilization(self, schedule: Dict[str, Any]) -> Dict[str, float]:
        """Calculate utilization percentage for each machine based on configured working hours."""
        utilization = {}
        daily_seconds = self.config.normal_working_hours * 3600
        
        for machine, jobs in schedule.items():
            if not isinstance(jobs, list) or not jobs:
                utilization[machine] = 0.0
                continue
            
            total_time = 0
            valid_jobs = 0
            
            for job in jobs:
                if len(job) >= 3 and isinstance(job[1], (int, float)) and isinstance(job[2], (int, float)):
                    job_duration = job[2] - job[1]  # end - start
                    if job_duration > 0:  # Only count valid durations
                        total_time += job_duration
                        valid_jobs += 1
            
            if valid_jobs == 0:
                utilization[machine] = 0.0
            else:
                # Calculate percentage based on configured working hours
                utilization_pct = min((total_time / daily_seconds) * 100, 100)
                utilization[machine] = round(utilization_pct, 2)
        
        return utilization
    
    def _analyze_priority_distribution(self, jobs_data: List[Dict]) -> Dict[str, int]:
        """Analyze distribution of job priorities."""
        distribution = {'1': 0, '2': 0, '3': 0, '4': 0, '5': 0, 'unknown': 0}
        
        for job in jobs_data:
            priority = str(job.get('priority', 'unknown'))
            if priority in distribution:
                distribution[priority] += 1
            else:
                distribution['unknown'] += 1
        
        return distribution
    
    def _calculate_timing_metrics(self, schedule: Dict[str, Any], jobs_data: List[Dict]) -> Dict[str, Any]:
        """Calculate comprehensive timing metrics."""
        # Create lookup for scheduled times
        scheduled_times = {}
        for machine, jobs in schedule.items():
            for job in jobs:
                if len(job) >= 3:
                    job_id = job[0]
                    scheduled_times[job_id] = {'start': job[1], 'end': job[2], 'machine': machine}
        
        total_scheduled_duration = 0
        jobs_with_timing = 0
        earliest_start = None
        latest_end = None
        
        for job_id, timing in scheduled_times.items():
            duration = timing['end'] - timing['start']
            if duration > 0:
                total_scheduled_duration += duration
                jobs_with_timing += 1
                
                if earliest_start is None or timing['start'] < earliest_start:
                    earliest_start = timing['start']
                if latest_end is None or timing['end'] > latest_end:
                    latest_end = timing['end']
        
        avg_job_duration = (total_scheduled_duration / jobs_with_timing / 3600) if jobs_with_timing > 0 else 0
        schedule_span_hours = ((latest_end - earliest_start) / 3600) if earliest_start and latest_end else 0
        
        return {
            'total_scheduled_hours': round(total_scheduled_duration / 3600, 2),
            'average_job_duration_hours': round(avg_job_duration, 2),
            'schedule_span_hours': round(schedule_span_hours, 2),
            'jobs_with_valid_timing': jobs_with_timing,
            'schedule_start': datetime.fromtimestamp(earliest_start, self.timezone).isoformat() if earliest_start else None,
            'schedule_end': datetime.fromtimestamp(latest_end, self.timezone).isoformat() if latest_end else None
        }
    
    def _analyze_buffer_status(self, schedule: Dict[str, Any], jobs_data: List[Dict]) -> Dict[str, int]:
        """Analyze buffer status distribution using configured thresholds."""
        # Create lookup for scheduled times
        scheduled_times = {}
        for machine, jobs in schedule.items():
            for job in jobs:
                if len(job) >= 3:
                    job_id = job[0]
                    scheduled_times[job_id] = job[2]  # end time
        
        # Create lookup for due dates
        job_due_dates = {job.get('job_id'): job.get('lcd_date_epoch') for job in jobs_data if job.get('job_id') and job.get('lcd_date_epoch')}
        
        buffer_counts = {'Late': 0, 'Critical': 0, 'Warning': 0, 'Caution': 0, 'OK': 0, 'Unknown': 0}
        
        for job_id, end_time in scheduled_times.items():
            due_date = job_due_dates.get(job_id)
            if due_date:
                buffer_hours = (due_date - end_time) / 3600
                status = self._determine_buffer_status(buffer_hours)
                buffer_counts[status] += 1
            else:
                buffer_counts['Unknown'] += 1
        
        return buffer_counts
    
    def _determine_buffer_status(self, buffer_hours: float) -> str:
        """Determine buffer status based on configured thresholds."""
        if buffer_hours < 0:
            return "Late"
        elif buffer_hours < self.config.buffer_critical_hours:
            return "Critical"
        elif buffer_hours < self.config.buffer_warning_hours:
            return "Warning"
        elif buffer_hours < self.config.buffer_caution_hours:
            return "Caution"
        else:
            return "OK"
    
    def _calculate_efficiency_metrics(self, schedule: Dict[str, Any], jobs_data: List[Dict]) -> Dict[str, Any]:
        """Calculate detailed efficiency metrics."""
        machine_utilization = self._calculate_machine_utilization(schedule)
        
        high_util_machines = [m for m, u in machine_utilization.items() if u >= self.config.high_utilization_threshold]
        low_util_machines = [m for m, u in machine_utilization.items() if u <= self.config.low_utilization_threshold]
        optimal_machines = [m for m, u in machine_utilization.items() if self.config.low_utilization_threshold < u < self.config.high_utilization_threshold]
        
        avg_utilization = sum(machine_utilization.values()) / len(machine_utilization) if machine_utilization else 0
        
        return {
            'average_utilization': round(avg_utilization, 2),
            'high_utilization_count': len(high_util_machines),
            'low_utilization_count': len(low_util_machines),
            'optimal_utilization_count': len(optimal_machines),
            'utilization_distribution': {
                'high': high_util_machines,
                'optimal': optimal_machines,
                'low': low_util_machines
            }
        }
    
    def _generate_recommendations(self, utilization: Dict[str, float]) -> List[str]:
        """Generate optimization recommendations based on configured thresholds."""
        recommendations = []
        
        high_util_machines = [m for m, u in utilization.items() if u >= self.config.high_utilization_threshold]
        low_util_machines = [m for m, u in utilization.items() if u <= self.config.low_utilization_threshold]
        
        if high_util_machines:
            recommendations.append(f"⚠️ HIGH UTILIZATION ALERT: {len(high_util_machines)} machines above {self.config.high_utilization_threshold}% threshold: {', '.join(high_util_machines[:5])}" + ("..." if len(high_util_machines) > 5 else ""))
        
        if low_util_machines:
            recommendations.append(f"📊 LOW UTILIZATION: {len(low_util_machines)} machines below {self.config.low_utilization_threshold}% threshold: {', '.join(low_util_machines[:5])}" + ("..." if len(low_util_machines) > 5 else ""))
        
        if not high_util_machines and not low_util_machines:
            recommendations.append("✅ All machines operating within optimal utilization ranges")
        
        # Add specific recommendations based on patterns
        if len(high_util_machines) > len(low_util_machines) * 2:
            recommendations.append("🔄 Consider redistributing workload from high-utilization to low-utilization machines")
        
        return recommendations
    
    def _analyze_constraint_violations(self, schedule: Dict[str, Any], jobs_data: List[Dict]) -> Dict[str, List[str]]:
        """Analyze schedule for constraint violations using configured tolerances."""
        violations = {
            'start_date': [],
            'due_date': [],
            'timing': [],
            'buffer': []
        }
        
        # Create lookup for scheduled times
        scheduled_times = {}
        for machine, jobs in schedule.items():
            for job in jobs:
                if len(job) >= 3:
                    job_id = job[0]
                    scheduled_times[job_id] = {'start': job[1], 'end': job[2], 'machine': machine}
        
        tolerance_seconds = self.config.start_date_tolerance_hours * 3600
        grace_period_seconds = self.config.grace_period_hours * 3600
        
        for job in jobs_data:
            job_id = job.get('job_id')
            if not job_id or job_id not in scheduled_times:
                continue
            
            scheduled = scheduled_times[job_id]
            
            # Check start date constraints
            if job.get('start_date_epoch'):
                required_start = job['start_date_epoch']
                actual_start = scheduled['start']
                if actual_start < (required_start - tolerance_seconds):
                    violations['start_date'].append(f"{job_id} (early by {round((required_start - actual_start) / 3600, 1)}h)")
            
            # Check due date constraints
            if job.get('lcd_date_epoch'):
                due_date = job['lcd_date_epoch']
                actual_end = scheduled['end']
                if actual_end > due_date:
                    violations['due_date'].append(f"{job_id} (late by {round((actual_end - due_date) / 3600, 1)}h)")
            
            # Check timing logic
            if scheduled['end'] <= scheduled['start']:
                violations['timing'].append(f"{job_id} (invalid timing: end <= start)")
            
            # Check critical buffer violations
            if job.get('lcd_date_epoch'):
                buffer_hours = (job['lcd_date_epoch'] - scheduled['end']) / 3600
                if buffer_hours < 0:
                    violations['buffer'].append(f"{job_id} (late by {abs(round(buffer_hours, 1))}h)")
                elif buffer_hours < self.config.buffer_critical_hours:
                    violations['buffer'].append(f"{job_id} (critical buffer: {round(buffer_hours, 1)}h)")
        
        return violations
    
    def _identify_critical_issues(self, violations: Dict[str, List[str]]) -> List[str]:
        """Identify the most critical issues requiring immediate attention."""
        critical_issues = []
        
        # Due date violations are most critical
        if violations['due_date']:
            critical_issues.append(f"🚨 CRITICAL: {len(violations['due_date'])} jobs will miss due dates")
        
        # Buffer violations indicate potential problems
        if violations['buffer']:
            critical_issues.append(f"⚠️ WARNING: {len(violations['buffer'])} jobs have insufficient buffer time")
        
        # Timing violations indicate schedule corruption
        if violations['timing']:
            critical_issues.append(f"❌ ERROR: {len(violations['timing'])} jobs have invalid timing")
        
        # Start date violations may indicate constraint issues
        if violations['start_date']:
            critical_issues.append(f"📅 NOTICE: {len(violations['start_date'])} jobs violate start date constraints")
        
        return critical_issues