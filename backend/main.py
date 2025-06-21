import os
import logging
import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from typing import Dict, Any
import sys

# Configure logging for container environments
def setup_logging():
    """Setup logging that works in both local and container environments."""
    log_handlers = [logging.StreamHandler(sys.stdout)]
    
    # Only add file handler if running locally (not in container)
    if not os.getenv('PYTHONUNBUFFERED'):  # Container environments set this
        try:
            log_handlers.append(logging.FileHandler('app.log', mode='a'))
        except PermissionError:
            pass  # Skip file logging if no write permissions
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=log_handlers
    )

setup_logging()
logger = logging.getLogger(__name__)

class AppConfig:
    """Application configuration loaded from environment variables."""
    
    def __init__(self):
        self.required_vars = [
            'MARIADB_HOST',
            'MARIADB_USERNAME', 
            'MARIADB_PASSWORD',
            'MARIADB_DATABASE',
            'MARIADB_PORT'
        ]
        self.optional_vars = {
            'PORT': '8000',
            'HOST': '0.0.0.0',
            'RELOAD': 'false',
            'LOG_LEVEL': 'INFO',
            'CORS_ORIGINS': '*',
            'API_TITLE': 'AI Optimizer API',
            'API_DESCRIPTION': 'API for Production Scheduler Optimizer',
            'API_VERSION': '1.0.0'
        }
        self.config = {}
        self._load_config()
    
    def _load_config(self):
        """Load and validate configuration from environment variables."""
        missing_vars = []
        invalid_vars = []
        
        # Check required variables
        for var in self.required_vars:
            value = os.getenv(var)
            if not value:
                missing_vars.append(var)
            else:
                self.config[var] = value.strip()
        
        # Load optional variables with defaults
        for var, default in self.optional_vars.items():
            value = os.getenv(var, default).strip()
            self.config[var] = value
        
        # Validate specific configurations
        try:
            self.config['MARIADB_PORT'] = int(self.config.get('MARIADB_PORT', '3306'))
        except (ValueError, TypeError):
            invalid_vars.append(f"MARIADB_PORT={os.getenv('MARIADB_PORT')}")
        
        try:
            self.config['PORT'] = int(self.config.get('PORT', '8000'))
        except (ValueError, TypeError):
            # Handle special cases like Zeabur's ${PORT} format
            port_env = os.getenv('PORT', '8000')
            if port_env.startswith('${') or not port_env.replace('-', '').isdigit():
                logger.warning(f"Invalid PORT format: {port_env}. Using default 8000")
                self.config['PORT'] = 8000
            else:
                invalid_vars.append(f"PORT={port_env}")
        
        # Validate boolean values
        self.config['RELOAD'] = self.config.get('RELOAD', 'false').lower() in ('true', '1', 'yes', 'on')
        
        # Validate CORS origins
        cors_origins = self.config.get('CORS_ORIGINS', '*')
        if cors_origins == '*':
            self.config['CORS_ORIGINS'] = ["*"]
        else:
            self.config['CORS_ORIGINS'] = [origin.strip() for origin in cors_origins.split(',')]
        
        # Check for critical configuration errors
        if missing_vars:
            error_msg = f"❌ CRITICAL CONFIG ERROR: Missing required environment variables: {', '.join(missing_vars)}"
            logger.error(error_msg)
            raise ValueError(error_msg)
        
        if invalid_vars:
            error_msg = f"❌ CRITICAL CONFIG ERROR: Invalid environment variable values: {', '.join(invalid_vars)}"
            logger.error(error_msg)
            raise ValueError(error_msg)
        
        logger.info(f"✅ Successfully loaded application configuration")
        logger.info(f"📊 Database: {self.config['MARIADB_HOST']}:{self.config['MARIADB_PORT']}/{self.config['MARIADB_DATABASE']}")
        logger.info(f"🌐 Server: {self.config['HOST']}:{self.config['PORT']}")
        logger.info(f"🔗 CORS Origins: {self.config['CORS_ORIGINS']}")
    
    def get(self, key: str, default=None):
        """Get configuration value."""
        return self.config.get(key, default)
    
    def get_database_config(self) -> Dict[str, Any]:
        """Get database configuration dictionary."""
        return {
            'host': self.config['MARIADB_HOST'],
            'user': self.config['MARIADB_USERNAME'],
            'password': self.config['MARIADB_PASSWORD'],
            'database': self.config['MARIADB_DATABASE'],
            'port': self.config['MARIADB_PORT']
        }

def load_environment():
    """Load environment variables with proper path resolution."""
    # Try multiple .env file locations
    env_paths = [
        os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env'),  # Parent directory
        os.path.join(os.path.dirname(__file__), '.env'),  # Current directory
        '.env'  # Current working directory
    ]
    
    loaded = False
    for env_path in env_paths:
        if os.path.exists(env_path):
            load_dotenv(env_path)
            logger.info(f"✅ Loaded environment variables from: {env_path}")
            loaded = True
            break
    
    if not loaded:
        logger.warning(f"⚠️ No .env file found in locations: {env_paths}")
        logger.info("Using system environment variables only")

def validate_critical_services():
    """Validate that critical services and configurations are available."""
    try:
        # Test database configuration
        from app.api.fastapi_app import get_db_connection_from_pool
        with get_db_connection_from_pool() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT 1")
            cursor.fetchone()
            cursor.close()
        logger.info("✅ Database connection validated")
        
    except Exception as e:
        error_msg = f"❌ CRITICAL SERVICE ERROR: Database connection failed: {e}"
        logger.error(error_msg)
        raise RuntimeError(error_msg)
    
    # Validate that required modules can be imported
    try:
        from app.reporting.production_report_generator import ProductionReportGenerator
        # Test that report generator can initialize (validates all config)
        ProductionReportGenerator()
        logger.info("✅ Report generator configuration validated")
        
    except Exception as e:
        error_msg = f"❌ CRITICAL SERVICE ERROR: Report generator initialization failed: {e}"
        logger.error(error_msg)
        raise RuntimeError(error_msg)

def create_app() -> FastAPI:
    """Create and configure the FastAPI application with strict validation."""
    try:
        # Load environment variables
        load_environment()
        
        # Load and validate configuration
        config = AppConfig()
        
        # Validate critical services
        validate_critical_services()
        
        # Initialize FastAPI app with configuration
        app = FastAPI(
            title=config.get('API_TITLE'),
            description=config.get('API_DESCRIPTION'),
            version=config.get('API_VERSION'),
            docs_url="/docs",
            redoc_url="/redoc"
        )
        
        # Configure CORS with environment-based origins
        app.add_middleware(
            CORSMiddleware,
            allow_origins=config.get('CORS_ORIGINS'),
            allow_credentials=True,
            allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
            allow_headers=["*"],
        )
        
        # Store config in app state for access by routes
        app.state.config = config
        
        logger.info("✅ FastAPI application configured successfully")
        
    except Exception as e:
        logger.error(f"❌ FAILED to create FastAPI application: {e}")
        raise
    
    try:
        # Import and include routers - with error handling
        from app.api import router as api_router
        from app.api.endpoints import production_jobs_endpoints, reporting_endpoints, logs_endpoints, ai_report_endpoints
        
        # Include routers with error handling
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
        app.include_router(
            logs_endpoints.router, 
            prefix="/api/logs", 
            tags=["Logs"]
        )
        app.include_router(
            ai_report_endpoints.router, 
            prefix="/api/reports", 
            tags=["AI Reports"]
        )
        
        logger.info("✅ API routes configured successfully")
        
    except Exception as e:
        logger.error(f"❌ FAILED to configure API routes: {e}")
        raise
    
    # Add root endpoint with configuration info
    @app.get("/")
    async def root():
        return {
            "message": "AI Optimizer API is running",
            "version": config.get('API_VERSION'),
            "status": "operational",
            "endpoints": {
                "docs": "/docs",
                "health": "/health",
                "api": "/api",
                "production_jobs": "/api/production-jobs",
                "reports": "/api/reports"
            }
        }
    
    # Enhanced health endpoint with system checks
    @app.get("/health")
    async def health():
        health_status = {
            "status": "healthy",
            "service": "ai-optimizer",
            "version": config.get('API_VERSION'),
            "timestamp": os.times(),
            "checks": {}
        }
        
        # Database health check
        try:
            from app.api.fastapi_app import get_db_connection_from_pool
            with get_db_connection_from_pool() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT 1")
                cursor.fetchone()
                cursor.close()
            health_status["checks"]["database"] = "healthy"
        except Exception as e:
            health_status["checks"]["database"] = f"unhealthy: {str(e)}"
            health_status["status"] = "unhealthy"
        
        # Configuration health check
        try:
            from app.reporting.production_report_generator import ProductionReportGenerator
            ProductionReportGenerator()
            health_status["checks"]["configuration"] = "healthy"
        except Exception as e:
            health_status["checks"]["configuration"] = f"unhealthy: {str(e)}"
            health_status["status"] = "unhealthy"
        
        if health_status["status"] == "unhealthy":
            raise HTTPException(status_code=503, detail=health_status)
        
        return health_status
    
    # Add configuration endpoint (for debugging)
    @app.get("/config")
    async def get_config():
        """Get sanitized configuration information (excluding sensitive data)."""
        safe_config = {
            "api_title": config.get('API_TITLE'),
            "api_version": config.get('API_VERSION'),
            "database_host": config.get('MARIADB_HOST'),
            "database_port": config.get('MARIADB_PORT'),
            "database_name": config.get('MARIADB_DATABASE'),
            "server_host": config.get('HOST'),
            "server_port": config.get('PORT'),
            "cors_origins": config.get('CORS_ORIGINS'),
            "reload_enabled": config.get('RELOAD')
        }
        return {"configuration": safe_config}
    
    return app

def main():
    """Main application entry point with comprehensive error handling."""
    try:
        # Load environment and configuration
        load_environment()
        config = AppConfig()
        
        # Create the application
        app = create_app()
        
        # Start the server
        server_config = {
            "app": "main:app",
            "host": config.get('HOST'),
            "port": config.get('PORT'),
            "reload": config.get('RELOAD'),
            "log_level": config.get('LOG_LEVEL').lower(),
            "access_log": True
        }
        
        logger.info(f"🚀 Starting Uvicorn server with configuration: {server_config}")
        uvicorn.run(**server_config)
        
    except Exception as e:
        logger.error(f"❌ FAILED to start application: {e}")
        sys.exit(1)

# Create the FastAPI application instance
try:
    load_environment()
    app = create_app()
    logger.info("✅ Application instance created successfully")
except Exception as e:
    logger.error(f"❌ FAILED to create application instance: {e}")
    # Don't raise here as this breaks imports, but log the error
    app = None

if __name__ == "__main__":
    main()