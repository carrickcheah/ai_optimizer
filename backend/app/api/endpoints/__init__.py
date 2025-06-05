# backend/app/api/endpoints/__init__.py
"""Production-grade API endpoints module.

This module contains all API endpoint implementations organized by functionality:
- production_jobs_endpoints: CRUD operations for production jobs
- reporting_endpoints: Reporting and analytics endpoints
"""

from . import production_jobs_endpoints
# from . import reporting_endpoints  # Temporarily disabled due to import complexity

# Import specific routers for convenience
from .production_jobs_endpoints import router as production_jobs_router
# from .reporting_endpoints import router as reporting_router  # Temporarily disabled

__all__ = [
    "production_jobs_endpoints",
    # "reporting_endpoints",  # Temporarily disabled
    "production_jobs_router",
    # "reporting_router"  # Temporarily disabled
] 