# __init__.py
"""Production-grade reporting module for AI Optimizer."""

__version__ = "1.0.0"
__author__ = "AI Optimizer Team"

# Import main classes for easy access
from .production_report_generator import ProductionReportGenerator
from .chart_generator import (
    prepare_gantt_data_priority_view,
    prepare_gantt_data_resource_view,
    prepare_detailed_schedule_table_data,
    format_display_date,
    extract_job_family,
    extract_process_number
)

__all__ = [
    'ProductionReportGenerator',
    'prepare_gantt_data_priority_view',
    'prepare_gantt_data_resource_view', 
    'prepare_detailed_schedule_table_data',
    'format_display_date',
    'extract_job_family',
    'extract_process_number'
] 