"""
chain_analyzer.py - Dependency Chain Analysis
Analyzes complete job chains to optimize scheduling decisions
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Tuple, Optional
from collections import defaultdict

logger = logging.getLogger(__name__)

# Import dependency manager for complex dependencies
try:
    from .dependency_manager import get_dependency_manager
    COMPLEX_DEPENDENCIES_ENABLED = True
except ImportError:
    COMPLEX_DEPENDENCIES_ENABLED = False
    logger.warning("Complex dependency support not available - using sequential chain analysis")


class ChainAnalyzer:
    """Analyzer for dependency chains and critical path optimization."""
    
    @staticmethod
    def analyze_job_chains(job_families: Dict[str, List[Tuple]], current_time: float) -> Dict[str, Dict]:
        """
        Analyze all job chains to identify critical paths and timing requirements.
        
        Args:
            job_families: Dict of family -> [(process_num, job_id, job_item)]
            current_time: Current timestamp for urgency calculations
            
        Returns:
            Dict with chain analysis for each family
        """
        chain_analysis = {}
        
        for family, family_jobs in job_families.items():
            analysis = ChainAnalyzer._analyze_single_chain(family, family_jobs, current_time)
            chain_analysis[family] = analysis
            
            # Add individual job analysis with chain completion requirements
            for process_num, job_id, job_item in family_jobs:
                # Calculate remaining processes based on sequence position
                if COMPLEX_DEPENDENCIES_ENABLED:
                    dep_manager = get_dependency_manager()
                    _, process_code, _ = dep_manager.extract_process_info(job_id)
                    
                    # Get sequence position
                    seq_info = dep_manager.get_family_sequence_info(family)
                    if seq_info['exists']:
                        total_steps = seq_info['total_steps']
                        
                        # Count process occurrences to get current position
                        process_count = 0
                        for _, j_id, _ in family_jobs:
                            if j_id == job_id:
                                break
                            _, pc, _ = dep_manager.extract_process_info(j_id)
                            if pc == process_code:
                                process_count += 1
                        
                        occurrence = process_count + 1
                        current_position = dep_manager.get_sequence_position(family, process_code, occurrence)
                        remaining_processes = total_steps - current_position + 1 if current_position else 1
                    else:
                        # No sequence defined, use process number
                        remaining_processes = len([j for j in family_jobs if j[0] >= process_num])
                else:
                    remaining_processes = len([j for j in family_jobs if j[0] >= process_num])
                
                # Calculate remaining chain duration from this process
                remaining_duration = 0
                if COMPLEX_DEPENDENCIES_ENABLED and dep_manager:
                    # Calculate based on actual sequence
                    seq_info = dep_manager.get_family_sequence_info(family)
                    if seq_info['exists']:
                        # Find all jobs that come after this one in the sequence
                        _, process_code, _ = dep_manager.extract_process_info(job_id)
                        current_position = dep_manager.get_sequence_position(family, process_code, 1)  # Simplified for now
                        
                        if current_position:
                            for _, j_id, job in family_jobs:
                                _, pc, _ = dep_manager.extract_process_info(j_id)
                                job_position = dep_manager.get_sequence_position(family, pc, 1)
                                if job_position and job_position >= current_position:
                                    remaining_duration += job.get('processing_time', 3600) / 3600
                    else:
                        # Fallback to sequential
                        for p_num, _, job in family_jobs:
                            if p_num >= process_num:
                                remaining_duration += job.get('processing_time', 3600) / 3600
                else:
                    for p_num, _, job in family_jobs:
                        if p_num >= process_num:
                            remaining_duration += job.get('processing_time', 3600) / 3600  # Convert to hours
                
                # Calculate required start time for chain completion by LCD
                earliest_lcd = analysis['earliest_lcd']
                must_start_by = None
                critical_urgency_boost = 1.0
                
                if earliest_lcd and remaining_duration > 0:
                    # Realistic calendar days calculation (preemptive scheduling adds ~2.5x overhead)
                    realistic_remaining_days = (remaining_duration / 17.5) * 2.5
                    required_start_epoch = earliest_lcd - (realistic_remaining_days * 24 * 3600)
                    must_start_by = required_start_epoch
                    
                    # Calculate ultra-aggressive urgency boost for chain completion
                    days_until_must_start = (required_start_epoch - current_time) / 86400
                    if days_until_must_start <= 0:
                        critical_urgency_boost = 100.0  # Ultra-critical - already past required start
                    elif days_until_must_start <= 7:
                        critical_urgency_boost = 50.0  # Mega-urgent - must start within week
                    elif days_until_must_start <= 14:
                        critical_urgency_boost = 20.0  # Super-urgent - must start within 2 weeks
                    elif days_until_must_start <= 30:
                        critical_urgency_boost = 5.0   # Urgent - must start within month
                
                chain_analysis[job_id] = {
                    'family': family,
                    'process_num': process_num,
                    'remaining_processes': remaining_processes,
                    'remaining_duration_hours': remaining_duration,
                    'is_critical': analysis['is_critical'],
                    'chain_duration': analysis['total_duration'],
                    'earliest_lcd': analysis['earliest_lcd'],
                    'must_start_by': must_start_by,
                    'critical_urgency_boost': critical_urgency_boost,
                    'chain_completion_critical': critical_urgency_boost > 1.0
                }
        
        return chain_analysis
    
    @staticmethod
    def _analyze_single_chain(family: str, family_jobs: List[Tuple], current_time: float) -> Dict:
        """
        Analyze a single job chain for timing and criticality.
        
        Args:
            family: Family name
            family_jobs: List of (process_num, job_id, job_item) tuples
            
        Returns:
            Dict with chain analysis metrics
        """
        if not family_jobs:
            return {
                'total_duration': 0,
                'process_count': 0,
                'earliest_lcd': None,
                'latest_lcd': None,
                'is_critical': False,
                'bottleneck_processes': []
            }
        
        # Sort by process number
        sorted_jobs = sorted(family_jobs, key=lambda x: x[0])
        
        # Calculate total duration and find LCD dates
        total_duration = 0
        lcd_dates = []
        process_durations = []
        bottleneck_threshold = 0  # Will be calculated as > average duration
        
        for process_num, job_id, job_item in sorted_jobs:
            duration = job_item.get('processing_time', 3600) / 3600  # Convert to hours
            total_duration += duration
            process_durations.append((process_num, job_id, duration))
            
            lcd_date = job_item.get('lcd_date_epoch')
            if lcd_date:
                lcd_dates.append(lcd_date)
        
        # Find bottleneck processes (significantly longer than average)
        if process_durations:
            avg_duration = total_duration / len(process_durations)
            bottleneck_threshold = avg_duration * 2  # Processes 2x longer than average
            bottleneck_processes = [
                (pnum, jid) for pnum, jid, dur in process_durations 
                if dur > bottleneck_threshold
            ]
        else:
            bottleneck_processes = []
        
        # Determine criticality
        is_critical = False
        earliest_lcd = None
        latest_lcd = None
        
        if lcd_dates:
            earliest_lcd = min(lcd_dates)
            latest_lcd = max(lcd_dates)
            
            # Chain is critical if earliest LCD is within 60 days
            current_time = datetime.now().timestamp()
            days_until_earliest = (earliest_lcd - current_time) / 86400
            is_critical = days_until_earliest <= 60
        
        logger.info(f"Chain analysis for family '{family}': "
                   f"{len(sorted_jobs)} processes, {total_duration:.1f}h total, "
                   f"critical={is_critical}")
        
        return {
            'total_duration': total_duration,
            'process_count': len(sorted_jobs),
            'earliest_lcd': earliest_lcd,
            'latest_lcd': latest_lcd,
            'is_critical': is_critical,
            'bottleneck_processes': bottleneck_processes,
            'avg_process_duration': total_duration / len(sorted_jobs) if sorted_jobs else 0
        }
    
    @staticmethod
    def prioritize_families_by_urgency(job_families: Dict[str, List[Tuple]], 
                                     current_time: float) -> List[Tuple[str, float]]:
        """
        Prioritize job families by chain completion urgency for scheduling order.
        
        Args:
            job_families: Dict of family -> job list
            current_time: Current timestamp
            
        Returns:
            List of (family_name, urgency_score) sorted by urgency (most urgent first)
        """
        family_priorities = []
        
        for family, family_jobs in job_families.items():
            if not family_jobs:
                continue
            
            # Find most urgent LCD date and calculate total chain duration
            earliest_lcd = None
            total_chain_duration = 0
            
            for _, _, job_item in family_jobs:
                lcd_date = job_item.get('lcd_date_epoch')
                if lcd_date:
                    if earliest_lcd is None or lcd_date < earliest_lcd:
                        earliest_lcd = lcd_date
                
                # Add to total chain duration
                duration_hours = job_item.get('processing_time', 3600) / 3600
                total_chain_duration += duration_hours
            
            if earliest_lcd:
                days_until_lcd = (earliest_lcd - current_time) / 86400

                # ENHANCEMENT: Calculate required start time using realistic preemptive scheduling
                # Instead of simple 17.5h/day, estimate based on actual working calendar
                # Real schedule: ~2.5x longer due to breaks, weekends, working hours
                # Guard against zero duration chains
                if total_chain_duration > 0:
                    realistic_calendar_days = (total_chain_duration / 17.5) * 2.5  # More realistic multiplier
                else:
                    realistic_calendar_days = 0
                required_start_epoch = earliest_lcd - (realistic_calendar_days * 24 * 3600)
                days_until_must_start = (required_start_epoch - current_time) / 86400
                
                # Base urgency score
                if days_until_lcd <= 0:
                    urgency = 1000 + abs(days_until_lcd)  # Overdue
                elif days_until_lcd <= 30:
                    urgency = 900 - days_until_lcd * 10   # Critical
                elif days_until_lcd <= 90:
                    urgency = 500 - days_until_lcd * 2    # Important  
                else:
                    urgency = max(0, 100 - days_until_lcd * 0.5)  # Normal
                
                # ULTRA-MASSIVE BOOST: Apply chain completion urgency multiplier
                if days_until_must_start <= 0:
                    chain_boost = 100.0  # Family must start NOW - override everything!
                    logger.warning(f"FAMILY ULTRA-CRITICAL: {family} past required start - applying 100x boost!")
                elif days_until_must_start <= 7:
                    chain_boost = 50.0   # Must start within week - extremely urgent
                    logger.info(f"FAMILY MEGA-URGENT: {family} must start within 7 days - applying 50x boost")
                elif days_until_must_start <= 14:
                    chain_boost = 20.0   # Must start within 2 weeks - very urgent
                    logger.info(f"FAMILY SUPER-URGENT: {family} must start within 14 days - applying 20x boost")
                elif days_until_must_start <= 30:
                    chain_boost = 5.0    # Must start within month - urgent
                    logger.info(f"FAMILY URGENT: {family} must start within 30 days - applying 5x boost")
                else:
                    chain_boost = 1.0   # Normal priority
                
                urgency *= chain_boost
                
                # Additional boost for complex chains
                process_count = len(family_jobs)
                if process_count > 3:
                    urgency *= 1.1  # 10% boost for complex chains
                
                family_priorities.append((family, urgency))
                
                # Log chain completion analysis
                logger.info(f"Chain analysis for {family}: {total_chain_duration:.1f}h total, "
                          f"must start by {days_until_must_start:.1f} days, boost={chain_boost}x")
            else:
                # No LCD date - lowest priority
                family_priorities.append((family, 0))
        
        # Sort by urgency (highest first)
        family_priorities.sort(key=lambda x: x[1], reverse=True)
        
        # Log family priority order with chain analysis
        logger.info("Enhanced family scheduling priority order:")
        for i, (family, urgency) in enumerate(family_priorities[:10]):
            logger.info(f"  {i+1}. {family}: Chain Urgency Score={urgency:.1f}")
        
        return family_priorities
    
    @staticmethod
    def identify_critical_subcontractor_jobs(subcontractor_jobs: List[Dict[str, Any]], 
                                           current_time: float) -> List[Dict[str, Any]]:
        """
        Identify and prioritize critical subcontractor jobs to fix bottlenecks.
        
        Args:
            subcontractor_jobs: List of subcontractor job dictionaries
            current_time: Current timestamp
            
        Returns:
            List of jobs sorted by criticality (most critical first)
        """
        if not subcontractor_jobs:
            return []
        
        # Analyze each subcontractor job for criticality
        job_analysis = []
        
        for job in subcontractor_jobs:
            job_id = job.get('job_id', '')
            lcd_date = job.get('lcd_date_epoch')
            plan_date = job.get('plan_date_epoch')
            duration = job.get('processing_time', 87.5 * 3600) / 3600  # Default 87.5h
            
            criticality_score = 0
            
            # LCD urgency
            if lcd_date:
                days_until_lcd = (lcd_date - current_time) / 86400
                if days_until_lcd <= 0:
                    criticality_score += 1000  # Overdue
                elif days_until_lcd <= 30:
                    criticality_score += 500 + (30 - days_until_lcd) * 10
                elif days_until_lcd <= 60:
                    criticality_score += 100 + (60 - days_until_lcd) * 2
            
            # Plan date overdue penalty
            if plan_date and plan_date < current_time:
                days_overdue = (current_time - plan_date) / 86400
                criticality_score += days_overdue * 10
            
            # Long duration penalty (blocks other jobs longer)
            if duration > 50:  # > 50 hours
                criticality_score += (duration - 50) * 2
            
            job_analysis.append((job, criticality_score, days_until_lcd if lcd_date else 999))
        
        # Sort by criticality (highest first)
        job_analysis.sort(key=lambda x: x[1], reverse=True)
        
        # Log critical subcontractor jobs
        logger.info("Critical subcontractor job priority:")
        for i, (job, criticality, days_until_lcd) in enumerate(job_analysis[:5]):
            job_id = job.get('job_id', 'unknown')
            logger.info(f"  {i+1}. {job_id}: Criticality={criticality:.1f}, "
                       f"LCD in {days_until_lcd:.1f} days")
        
        return [job for job, _, _ in job_analysis]