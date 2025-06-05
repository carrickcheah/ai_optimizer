# backend/app/api/__init__.py
"""Production-grade API module with organized endpoints and utilities.

This module provides a comprehensive FastAPI-based REST API for the AI Optimizer service,
including endpoints for production job management, scheduling optimization, and reporting.
"""

__version__ = "1.0.0"
__author__ = "AI Optimizer Team"

# Import main router and utilities
from .fastapi_app import (
    router,
    ProductionJobData,
    ProductionJobResponse,
    DataTransformer,
    get_db_connection_from_pool,
    monitor_performance
)

# Import endpoint routers
from .endpoints import (
    production_jobs_endpoints
    # reporting_endpoints  # Temporarily disabled due to import complexity
)

__all__ = [
    "router",
    "ProductionJobData", 
    "ProductionJobResponse",
    "DataTransformer",
    "get_db_connection_from_pool",
    "monitor_performance",
    "production_jobs_endpoints",
    # "reporting_endpoints",  # Temporarily disabled
    "__version__"
]
