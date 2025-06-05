"""
Scheduler Configuration Module
Centralizes all hardcoded values from cpsat_solver.py for better maintainability.
Uses Pydantic Settings for type validation and environment variable support.
"""

from typing import Dict, Any
from pydantic import Field
from pydantic_settings import BaseSettings


class SchedulerConfig(BaseSettings):
    """Configuration class for CP-SAT scheduler parameters using Pydantic."""
    
    # Solver Performance Settings
    solver_time_limit_seconds: int = Field(
        default=120,
        gt=0,
        description="Solver time limit in seconds"
    )
    max_jobs_limit: int = Field(
        default=1000,
        gt=0,
        description="Maximum number of jobs to process for performance"
    )
    planning_horizon_days: int = Field(
        default=60,
        gt=0,
        description="Planning horizon in days"
    )
    
    # Solver Worker Settings
    max_workers_limit: int = Field(
        default=8,
        gt=0,
        description="Maximum number of solver workers"
    )
    
    # Time Constraints
    grace_period_hours: int = Field(
        default=24,
        ge=0,
        description="Grace period in hours for already late jobs"
    )
    minimum_horizon_hours: int = Field(
        default=24 * 7,  # 1 week
        gt=0,
        description="Minimum horizon in hours"
    )
    
    # Setup Times (in hours)
    same_machine_setup_time: float = Field(
        default=0.25,
        ge=0,
        le=24,
        description="Setup time for same machine transitions"
    )
    different_machine_setup_time: float = Field(
        default=0.5,
        ge=0,
        le=24,
        description="Setup time for different machine transitions"
    )
    
    # Solver Optimization Parameters
    relative_gap_limit: float = Field(
        default=0.02,
        gt=0,
        lt=1,
        description="Relative gap limit for solver (2%)"
    )
    absolute_gap_limit: int = Field(
        default=1000,
        gt=0,
        description="Absolute gap limit for solver"
    )
    
    # Priority Weights
    priority_weight: int = Field(
        default=100,
        gt=0,
        description="Weight for priority optimization"
    )
    
    # Emergency Fallback Times
    emergency_minimum_start_hour: int = Field(
        default=6,
        ge=0,
        le=23,
        description="Emergency minimum start hour (6 AM)"
    )
    
    class Config:
        env_file = ".env"
        case_sensitive = False
        validate_assignment = True
        extra = "ignore"
    
    def get_setup_times_dict(self, from_machine: str, to_machine: str) -> float:
        """Get setup time between machines."""
        if from_machine == to_machine:
            return self.same_machine_setup_time
        else:
            return self.different_machine_setup_time
    
    def get_dynamic_limits(self, job_count: int) -> Dict[str, Any]:
        """Calculate dynamic limits based on problem size."""
        if job_count < 100:
            return {
                'time_limit_seconds': min(self.solver_time_limit_seconds, 60),
                'planning_horizon_days': min(self.planning_horizon_days, 30),
                'max_jobs_limit': self.max_jobs_limit
            }
        elif job_count < 500:
            return {
                'time_limit_seconds': self.solver_time_limit_seconds,
                'planning_horizon_days': min(self.planning_horizon_days, 45),
                'max_jobs_limit': self.max_jobs_limit
            }
        else:
            return {
                'time_limit_seconds': max(self.solver_time_limit_seconds, 180),
                'planning_horizon_days': self.planning_horizon_days,
                'max_jobs_limit': self.max_jobs_limit
            }
    
    def print_config(self) -> None:
        """Print current configuration for debugging."""
        print("=== Scheduler Configuration (Pydantic) ===")
        print(f"Solver Time Limit: {self.solver_time_limit_seconds}s")
        print(f"Max Jobs Limit: {self.max_jobs_limit}")
        print(f"Planning Horizon: {self.planning_horizon_days} days")
        print(f"Max Workers: {self.max_workers_limit}")
        print(f"Grace Period: {self.grace_period_hours}h")
        print(f"Min Horizon: {self.minimum_horizon_hours}h")
        print(f"Setup Times: Same={self.same_machine_setup_time}h, Different={self.different_machine_setup_time}h")
        print(f"Gap Limits: Relative={self.relative_gap_limit}, Absolute={self.absolute_gap_limit}")
        print("==========================================")


# Create singleton instance
scheduler_config = SchedulerConfig()