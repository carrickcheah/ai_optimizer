"""
dependency_manager.py - Complex Dependency Management
Handles non-sequential and repeated process dependencies with database-driven configuration
"""

import logging
from typing import Dict, List, Tuple, Optional, Any
from collections import defaultdict
import re
import os
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()


class DependencyManager:
    """Manages complex job dependencies including non-sequential and repeated processes."""
    
    def __init__(self):
        """Initialize dependency manager with caching."""
        self._dependency_cache = {}
        self._sequence_cache = {}
        self._family_sequences = {}  # family -> [(position, process_code)]
        self._position_map = {}      # family -> {process_code -> [positions]}
        self._cache_ttl = int(os.getenv('DEPENDENCY_CACHE_TTL_HOURS', '1')) * 3600
        self._last_cache_refresh = 0
        
    def load_sequences_from_db(self) -> None:
        """
        Load family sequences from database.
        Expected table structure:
        - family_code: varchar
        - sequence_position: int
        - process_code: varchar
        """
        try:
            from app.api.fastapi_app import get_db_connection_from_pool
            
            with get_db_connection_from_pool() as conn:
                cursor = conn.cursor(dictionary=True)
                
                # Check if sequence table exists
                cursor.execute("""
                    SELECT COUNT(*) as count 
                    FROM information_schema.tables 
                    WHERE table_schema = DATABASE() 
                    AND table_name = 'ai_job_sequences'
                """)
                
                if cursor.fetchone()['count'] == 0:
                    logger.info("ai_job_sequences table not found - using default sequential pattern")
                    return
                
                # Load sequences
                cursor.execute("""
                    SELECT family_code, sequence_position, process_code
                    FROM ai_job_sequences
                    ORDER BY family_code, sequence_position
                """)
                
                sequences = cursor.fetchall()
                cursor.close()
                
                # Process sequences into internal structure
                for row in sequences:
                    family = row['family_code']
                    position = row['sequence_position']
                    process = row['process_code']
                    
                    if family not in self._family_sequences:
                        self._family_sequences[family] = []
                        self._position_map[family] = defaultdict(list)
                    
                    self._family_sequences[family].append((position, process))
                    self._position_map[family][process].append(position)
                
                logger.info(f"Loaded {len(self._family_sequences)} family sequences from database")
                
        except ImportError:
            logger.warning("Could not import database connection - sequences will be derived from job data")
        except Exception as e:
            logger.error(f"Error loading sequences from database: {e}")
            
    def derive_sequence_from_jobs(self, jobs: List[Dict[str, Any]]) -> None:
        """
        Derive sequences from actual job data when no database configuration exists.
        This allows the system to learn patterns from the data.
        """
        family_processes = defaultdict(set)
        
        for job in jobs:
            job_id = job.get('job_id', '')
            family, process_code, _ = self.extract_process_info(job_id)
            
            if family and process_code:
                family_processes[family].add(process_code)
        
        # Build sequences from discovered processes
        for family, processes in family_processes.items():
            if family not in self._family_sequences:
                # Sort processes numerically
                sorted_processes = sorted(processes, key=lambda p: int(p[1:]) if p[1:].isdigit() else 999)
                
                # Create sequence with positions
                sequence = []
                position_map = defaultdict(list)
                
                for idx, process in enumerate(sorted_processes, 1):
                    sequence.append((idx, process))
                    position_map[process].append(idx)
                
                self._family_sequences[family] = sequence
                self._position_map[family] = dict(position_map)
                
                logger.debug(f"Derived sequence for family {family}: {' → '.join([p for _, p in sequence])}")
                
    def extract_process_info(self, job_id: str) -> Tuple[str, str, int]:
        """
        Extract family and process code from job ID.
        
        Args:
            job_id: Job identifier (e.g., 'J001_CD02-01/3')
            
        Returns:
            Tuple of (family, process_code, total_processes)
        """
        try:
            # Split job code and process part
            if '_' not in job_id:
                return ('', '', 0)
                
            _, process_part = job_id.split('_', 1)
            
            # Match pattern like CD02-01/3
            match = re.match(r'([A-Z0-9]+)-(\d+)/(\d+)', process_part)
            if match:
                family = match.group(1)
                process_num = match.group(2)
                total_processes = int(match.group(3))
                process_code = f'P{process_num.zfill(2)}'
                return (family, process_code, total_processes)
            
            return ('', '', 0)
            
        except Exception as e:
            logger.error(f"Error extracting process info from {job_id}: {e}")
            return ('', '', 0)
            
    def get_sequence_position(self, family: str, process_code: str, occurrence: int = 1) -> Optional[int]:
        """
        Get the sequence position for a process in a family.
        
        Args:
            family: Job family
            process_code: Process code (e.g., 'P05')
            occurrence: Which occurrence for repeated processes (1-based)
            
        Returns:
            Sequence position or None
        """
        if family not in self._position_map:
            return None
            
        positions = self._position_map[family].get(process_code, [])
        
        if not positions:
            return None
            
        # Handle repeated processes
        if occurrence <= len(positions):
            return positions[occurrence - 1]
        
        # Default to last occurrence if requested occurrence exceeds available
        return positions[-1]
        
    def get_dependency_position(self, family: str, current_position: int) -> Optional[int]:
        """
        Get the position of the dependency (previous process in sequence).
        
        Args:
            family: Job family
            current_position: Current sequence position
            
        Returns:
            Previous position or None if no dependency
        """
        if current_position <= 1:
            return None
            
        return current_position - 1
        
    def get_process_at_position(self, family: str, position: int) -> Optional[str]:
        """
        Get the process code at a specific sequence position.
        
        Args:
            family: Job family
            position: Sequence position
            
        Returns:
            Process code or None
        """
        if family not in self._family_sequences:
            return None
            
        for pos, process in self._family_sequences[family]:
            if pos == position:
                return process
                
        return None
        
    def find_job_dependency(self, job_id: str, family_jobs: List[Dict[str, Any]]) -> Optional[str]:
        """
        Find the specific job that this job depends on.
        
        Args:
            job_id: Current job ID
            family_jobs: All jobs in the same family
            
        Returns:
            Job ID of the dependency or None
        """
        # Extract info from current job
        family, process_code, _ = self.extract_process_info(job_id)
        
        if not family or not process_code:
            return None
            
        # Count occurrences of this process before this job
        process_count = 0
        job_index = -1
        
        for idx, job in enumerate(family_jobs):
            other_job_id = job.get('job_id', '')
            _, other_process, _ = self.extract_process_info(other_job_id)
            
            if other_job_id == job_id:
                job_index = idx
                break
            elif other_process == process_code:
                process_count += 1
        
        if job_index == -1:
            return None
            
        # This is the (process_count + 1)th occurrence of this process
        occurrence = process_count + 1
        
        # Get sequence position
        current_position = self.get_sequence_position(family, process_code, occurrence)
        if not current_position:
            return None
            
        # Get dependency position
        dep_position = self.get_dependency_position(family, current_position)
        if not dep_position:
            return None
            
        # Get process at dependency position
        dep_process = self.get_process_at_position(family, dep_position)
        if not dep_process:
            return None
            
        # Find the job that matches the dependency
        # Count how many times we need to see dep_process
        dep_occurrence_needed = len([p for p, proc in self._family_sequences[family] 
                                   if p <= dep_position and proc == dep_process])
        
        dep_occurrence_count = 0
        for job in family_jobs[:job_index]:  # Only look at jobs before current
            other_job_id = job.get('job_id', '')
            _, other_process, _ = self.extract_process_info(other_job_id)
            
            if other_process == dep_process:
                dep_occurrence_count += 1
                if dep_occurrence_count == dep_occurrence_needed:
                    return other_job_id
                    
        return None
        
    def get_family_sequence_info(self, family: str) -> Dict[str, Any]:
        """
        Get complete sequence information for a family.
        
        Args:
            family: Job family
            
        Returns:
            Dictionary with sequence details
        """
        if family not in self._family_sequences:
            return {
                'exists': False,
                'sequence': [],
                'pattern': 'SEQUENTIAL'
            }
            
        sequence = self._family_sequences[family]
        process_list = [process for _, process in sequence]
        
        # Detect pattern type
        pattern = 'SEQUENTIAL'
        process_numbers = []
        
        for process in process_list:
            match = re.match(r'P(\d+)', process)
            if match:
                process_numbers.append(int(match.group(1)))
        
        # Check if sequential
        if process_numbers:
            is_sequential = all(process_numbers[i] == process_numbers[i-1] + 1 
                              for i in range(1, len(process_numbers)))
            
            # Check for repeated processes
            has_repeats = len(process_list) != len(set(process_list))
            
            if not is_sequential:
                pattern = 'NON_SEQUENTIAL'
            elif has_repeats:
                pattern = 'REPEATED'
                
        return {
            'exists': True,
            'sequence': process_list,
            'pattern': pattern,
            'total_steps': len(sequence)
        }
        
    def validate_job_sequence(self, jobs: List[Dict[str, Any]]) -> Dict[str, List[str]]:
        """
        Validate that jobs follow the required sequence.
        
        Args:
            jobs: List of jobs to validate
            
        Returns:
            Dictionary mapping family to list of validation errors
        """
        errors = defaultdict(list)
        family_jobs = defaultdict(list)
        
        # Group by family
        for job in jobs:
            job_id = job.get('job_id', '')
            family, _, _ = self.extract_process_info(job_id)
            if family:
                family_jobs[family].append(job)
        
        # Validate each family
        for family, jobs_in_family in family_jobs.items():
            sequence_info = self.get_family_sequence_info(family)
            
            if not sequence_info['exists']:
                continue  # No sequence defined, skip validation
                
            expected_sequence = sequence_info['sequence']
            
            # Extract actual sequence from jobs
            actual_processes = []
            for job in sorted(jobs_in_family, key=lambda j: j.get('job_id', '')):
                _, process, _ = self.extract_process_info(job.get('job_id', ''))
                if process:
                    actual_processes.append(process)
            
            # Check if actual matches expected (considering possible gaps)
            expected_idx = 0
            for actual_process in actual_processes:
                if expected_idx < len(expected_sequence):
                    if actual_process == expected_sequence[expected_idx]:
                        expected_idx += 1
                    else:
                        errors[family].append(
                            f"Unexpected process {actual_process}, expected {expected_sequence[expected_idx]}"
                        )
                else:
                    errors[family].append(f"Extra process {actual_process} beyond expected sequence")
                    
        return dict(errors)
        
    def clear_cache(self) -> None:
        """Clear all internal caches."""
        self._dependency_cache.clear()
        self._sequence_cache.clear()
        logger.info("Cleared dependency manager caches")


# Singleton instance
_dependency_manager = None


def get_dependency_manager() -> DependencyManager:
    """Get or create the singleton dependency manager instance."""
    global _dependency_manager
    if _dependency_manager is None:
        _dependency_manager = DependencyManager()
        _dependency_manager.load_sequences_from_db()
    return _dependency_manager