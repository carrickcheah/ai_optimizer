import os
import logging
import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    # Load environment variables
    dotenv_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env')
    load_dotenv(dotenv_path)
    
    # Initialize FastAPI app
    app = FastAPI(
        title="AI Optimizer API",
        description="API for Optimizer",
        version="0.1.0"
    )
    
    # Configure CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # Import and include routers
    from app.api import router as api_router
    from app.api.endpoints import production_jobs_endpoints, reporting_endpoints
    
    # Include routers
    app.include_router(api_router, prefix="/api", tags=["API"])
    app.include_router(
        production_jobs_endpoints.router, 
        prefix="/api/production-jobs", 
        tags=["Production Jobs"]
    )
    app.include_router(
        reporting_endpoints.router, 
        prefix="/api/reports", 
        tags=["Reporting"]
    )
    
    # Add root endpoint
    @app.get("/")
    async def root():
        return {"message": "AI Optimizer API is running"}
    
    return app

# Create the FastAPI application
app = create_app()

if __name__ == "__main__":
    server_port = int(os.getenv("PORT", 8000))
    logger.info(f"Starting Uvicorn server on port {server_port}")
    uvicorn.run("app.main:app", host="0.0.0.0", port=server_port, reload=True)