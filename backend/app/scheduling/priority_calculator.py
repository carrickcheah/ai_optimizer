"""
priority_calculator.py - Enhanced Priority Calculation System
Implements LCD-based urgency scoring and dependency chain analysis
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Tuple, Optional

logger = logging.getLogger(__name__)


class PriorityCalculator:
    """Enhanced priority calculation for LCD-based urgency and dependency chains."""
    
    @staticmethod
    def calculate_lcd_urgency_score(job: Dict[str, Any], current_time: float) -> float:
        """
        Calculate urgency score based on LCD date proximity.
        
        Returns:
            float: Higher score = more urgent (0-1000)
                  1000+ = overdue jobs
                  100-999 = urgent (days until LCD)
                  0-99 = normal priority
        """
        lcd_date = job.get('lcd_date_epoch')
        
        if not lcd_date:
            return 0  # No LCD date = lowest priority
        
        days_until_lcd = (lcd_date - current_time) / 86400
        
        if days_until_lcd <= 0:
            # Job is overdue - highest priority
            days_overdue = abs(days_until_lcd)
            return 1000 + days_overdue
        elif days_until_lcd <= 7:
            # Critical urgency: 1 week or less
            return 900 + (7 - days_until_lcd) * 10
        elif days_until_lcd <= 30:
            # High urgency: 1 month or less  
            return 500 + (30 - days_until_lcd) * 10
        elif days_until_lcd <= 90:
            # Medium urgency: 3 months or less
            return 100 + (90 - days_until_lcd) * 2
        else:
            # Low urgency: more than 3 months
            return max(0, 100 - days_until_lcd * 0.1)
    
    @staticmethod
    def calculate_comprehensive_priority(job: Dict[str, Any], current_time: float, 
                                       chain_info: Optional[Dict] = None) -> float:
        """
        Calculate comprehensive priority score combining multiple factors.
        
        Args:
            job: Job dictionary
            current_time: Current timestamp
            chain_info: Optional dependency chain information
            
        Returns:
            float: Priority score (higher = more urgent)
        """
        # Base LCD urgency (0-1000+)
        lcd_urgency = PriorityCalculator.calculate_lcd_urgency_score(job, current_time)
        
        # Plan date factor (jobs past plan date get boost)
        plan_date_factor = 1.0
        plan_date = job.get('plan_date_epoch')
        if plan_date and plan_date < current_time:
            days_overdue = (current_time - plan_date) / 86400
            plan_date_factor = 1.0 + (days_overdue * 0.1)  # 10% boost per overdue day
        
        # Chain completion factor (massive boost for jobs that must start soon for chain completion)
        chain_factor = 1.0
        if chain_info:
            # Apply critical urgency boost for chain completion requirements
            critical_urgency_boost = chain_info.get('critical_urgency_boost', 1.0)
            chain_completion_critical = chain_info.get('chain_completion_critical', False)
            
            if chain_completion_critical:
                chain_factor = critical_urgency_boost
                logger.info(f"🚨 Chain completion boost applied to {job.get('job_id', 'unknown')}: "
                          f"{critical_urgency_boost}x multiplier (must start by required date)")
            else:
                remaining_processes = chain_info.get('remaining_processes', 1)
                is_critical = chain_info.get('is_critical', False)
                
                if is_critical and remaining_processes > 1:
                    chain_factor = 1.0 + (remaining_processes * 0.1)  # Standard boost for critical chains
        
        # Buffer status factor (late jobs get significant boost)
        buffer_factor = 1.0
        buffer_status = job.get('buffer_status', '')
        if buffer_status == 'Late':
            buffer_factor = 2.0
        elif buffer_status == 'Warning':
            buffer_factor = 1.5
        elif buffer_status == 'Caution':
            buffer_factor = 1.2
        
        # Original priority field (lower number = higher priority)
        original_priority = job.get('priority', 99)
        priority_factor = max(0.1, (100 - original_priority) / 100)  # Invert and normalize
        
        # Combine all factors
        final_score = (
            lcd_urgency * 
            plan_date_factor * 
            chain_factor * 
            buffer_factor * 
            priority_factor
        )
        
        return final_score
    
    @staticmethod
    def sort_jobs_by_enhanced_priority(jobs: List[Dict[str, Any]], current_time: float,
                                     chain_analysis: Optional[Dict] = None) -> List[Dict[str, Any]]:
        """
        Sort jobs using enhanced priority calculation.
        
        Args:
            jobs: List of job dictionaries
            current_time: Current timestamp
            chain_analysis: Optional chain analysis results
            
        Returns:
            List of jobs sorted by priority (most urgent first)
        """
        def priority_key(job):
            job_id = job.get('job_id', '')
            chain_info = chain_analysis.get(job_id) if chain_analysis else None
            priority = PriorityCalculator.calculate_comprehensive_priority(job, current_time, chain_info)
            return -priority  # Negative for descending sort (highest priority first)
        
        sorted_jobs = sorted(jobs, key=priority_key)
        
        # Log top priorities for debugging
        logger.info("Enhanced priority analysis (top 10 jobs):")
        for i, job in enumerate(sorted_jobs[:10]):
            job_id = job.get('job_id', 'unknown')
            lcd_date = job.get('lcd_date_epoch')
            lcd_str = datetime.fromtimestamp(lcd_date).strftime('%Y-%m-%d') if lcd_date else 'None'
            buffer_status = job.get('buffer_status', 'None')
            
            chain_info = chain_analysis.get(job_id) if chain_analysis else None
            priority = PriorityCalculator.calculate_comprehensive_priority(job, current_time, chain_info)
            
            logger.info(f"  {i+1}. {job_id}: Priority={priority:.1f}, LCD={lcd_str}, Buffer={buffer_status}")
        
        return sorted_jobs
    
    @staticmethod
    def analyze_family_urgency(family_jobs: List[Tuple], current_time: float) -> Dict[str, float]:
        """
        Analyze urgency for entire job families to prioritize family scheduling order.
        
        Args:
            family_jobs: List of (process_num, job_id, job_item) tuples
            current_time: Current timestamp
            
        Returns:
            Dict with family analysis metrics
        """
        if not family_jobs:
            return {'urgency': 0, 'is_critical': False}
        
        # Get all LCD dates in the family
        lcd_dates = []
        for _, _, job_item in family_jobs:
            lcd_date = job_item.get('lcd_date_epoch')
            if lcd_date:
                lcd_dates.append(lcd_date)
        
        if not lcd_dates:
            return {'urgency': 0, 'is_critical': False}
        
        # Use earliest LCD date as family urgency
        earliest_lcd = min(lcd_dates)
        days_until_lcd = (earliest_lcd - current_time) / 86400
        
        # Family is critical if any job is due within 30 days
        is_critical = days_until_lcd <= 30
        
        # Calculate family urgency score
        urgency = PriorityCalculator.calculate_lcd_urgency_score(
            {'lcd_date_epoch': earliest_lcd}, current_time
        )
        
        return {
            'urgency': urgency,
            'is_critical': is_critical,
            'days_until_lcd': days_until_lcd,
            'earliest_lcd': earliest_lcd,
            'total_processes': len(family_jobs)
        }