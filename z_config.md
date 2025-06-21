# Cloud-Native Configuration Strategy

## Overview
Best practices for environment configuration that works across development, staging, and production environments with proper security and maintainability.

## Core Principles

### 1. Environment-Based Configuration Strategy

```python
# config.py
import os
from enum import Enum
from typing import Optional
import logging

logger = logging.getLogger(__name__)

class Environment(Enum):
    LOCAL = "local"
    DEVELOPMENT = "development" 
    STAGING = "staging"
    PRODUCTION = "production"

class Config:
    def __init__(self):
        self.env = Environment(os.getenv("APP_ENV", "local"))
        
        # Only try to load .env in local development
        if self.env == Environment.LOCAL:
            self._load_dotenv()
        else:
            logger.info(f"Running in {self.env.value} environment - using system environment variables")
        
        # Load and validate configuration
        self._load_config()
        
    def _load_dotenv(self):
        try:
            from dotenv import load_dotenv
            load_dotenv()
            logger.info("✅ Loaded .env file for local development")
        except ImportError:
            logger.info("ℹ️ Running without .env file (using system environment variables)")
    
    def _load_config(self):
        # Required configuration
        self.database_url = self._get_required("DATABASE_URL")
        
        # Optional configuration with defaults
        self.port = int(os.getenv("PORT", 8000))
        self.log_level = os.getenv("LOG_LEVEL", "INFO")
        
    def _get_required(self, key: str) -> str:
        value = os.getenv(key)
        if not value:
            raise ValueError(f"❌ Required environment variable '{key}' is not set")
        return value
```

### 2. Build-Time vs Runtime Configuration

#### Frontend (Build-Time Variables)
```dockerfile
# Frontend Dockerfile
FROM node:20-alpine

WORKDIR /app

# Copy package files
COPY package*.json ./
RUN npm ci

# Copy source code
COPY . .

# Build arguments for environment variables
ARG VITE_API_URL
ARG VITE_APP_ENV=production
ARG VITE_SUPABASE_URL
ARG VITE_SUPABASE_ANON_KEY

# Set environment variables for build
ENV VITE_API_URL=$VITE_API_URL
ENV VITE_APP_ENV=$VITE_APP_ENV
ENV VITE_SUPABASE_URL=$VITE_SUPABASE_URL
ENV VITE_SUPABASE_ANON_KEY=$VITE_SUPABASE_ANON_KEY

# Build the application
RUN npm run build

# Serve static files
RUN npm install -g serve
EXPOSE 3000
CMD ["serve", "-s", "dist", "-l", "tcp://0.0.0.0:3000"]
```

```javascript
// frontend/src/config.js
const config = {
  // Build-time variables (baked into bundle)
  apiUrl: import.meta.env.VITE_API_URL || '/api',
  appEnv: import.meta.env.VITE_APP_ENV || 'development',
  
  // Validation
  get isProduction() {
    return this.appEnv === 'production';
  },
  
  get isDevelopment() {
    return this.appEnv === 'development';
  }
};

// Validate configuration in production
if (config.isProduction && !config.apiUrl.startsWith('http')) {
  console.error('❌ Invalid API URL in production:', config.apiUrl);
}

export default config;
```

#### Backend (Runtime Variables)
```dockerfile
# Backend Dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install -r requirements.txt

# Copy application code
COPY . .

# Runtime environment variables will be injected by the platform
EXPOSE 8000
CMD ["python", "main.py"]
```

### 3. Configuration Validation with Pydantic

```python
# config_validator.py
from pydantic import BaseSettings, validator, Field
from typing import Optional
import os

class AppConfig(BaseSettings):
    # Environment detection
    app_env: str = Field(default="local", env="APP_ENV")
    
    # Required fields
    database_url: str = Field(..., env="DATABASE_URL")
    
    # Optional with defaults
    port: int = Field(default=8000, env="PORT")
    log_level: str = Field(default="INFO", env="LOG_LEVEL")
    cors_origins: str = Field(default="*", env="CORS_ORIGINS")
    
    # Optional secrets
    api_key: Optional[str] = Field(default=None, env="API_KEY")
    
    @validator("database_url")
    def validate_database_url(cls, v):
        if not v or not any(v.startswith(proto) for proto in ["postgresql://", "mysql://", "sqlite://"]):
            raise ValueError("Invalid database URL format")
        return v
    
    @validator("port")
    def validate_port(cls, v):
        if not 1 <= v <= 65535:
            raise ValueError("Port must be between 1 and 65535")
        return v
    
    @property
    def is_production(self) -> bool:
        return self.app_env == "production"
    
    @property
    def is_local(self) -> bool:
        return self.app_env == "local"
    
    class Config:
        # Only load .env file in local development
        env_file = ".env" if os.getenv("APP_ENV", "local") == "local" else None
        env_file_encoding = "utf-8"

# Usage
try:
    config = AppConfig()
    logger.info(f"✅ Configuration loaded successfully for {config.app_env} environment")
except ValueError as e:
    logger.error(f"❌ Configuration error: {e}")
    exit(1)
```

### 4. Platform-Agnostic Design

```python
# platform_utils.py
import os
from typing import Optional

class PlatformUtils:
    @staticmethod
    def get_port() -> int:
        """Get port from various cloud platform conventions"""
        port_sources = [
            "PORT",           # Heroku, Render, Railway
            "WEB_PORT",       # Zeabur
            "WEBSITES_PORT",  # Azure App Service
            "SERVER_PORT"     # Custom
        ]
        
        for source in port_sources:
            port = os.getenv(source)
            if port and port.isdigit():
                return int(port)
        
        return 8000  # Default port
    
    @staticmethod
    def get_database_url() -> Optional[str]:
        """Get database URL from various sources"""
        db_sources = [
            "DATABASE_URL",     # Standard
            "DB_URL",           # Alternative
            "MYSQL_URL",        # MySQL specific
            "POSTGRES_URL"      # PostgreSQL specific
        ]
        
        for source in db_sources:
            url = os.getenv(source)
            if url:
                return url
        
        return None
    
    @staticmethod
    def detect_platform() -> str:
        """Detect which cloud platform we're running on"""
        if os.getenv("HEROKU_APP_NAME"):
            return "heroku"
        elif os.getenv("ZEABUR_PROJECT_ID"):
            return "zeabur"
        elif os.getenv("RAILWAY_PROJECT_ID"):
            return "railway"
        elif os.getenv("VERCEL_ENV"):
            return "vercel"
        else:
            return "unknown"
```

### 5. Cloud Platform Configuration Files

#### Zeabur Configuration
```yaml
# zeabur.yaml
services:
  backend:
    type: dockerfile
    dockerfile: ./backend/Dockerfile
    env:
      - name: APP_ENV
        value: production
      - name: DATABASE_URL
        valueFrom:
          secretRef: 
            name: database-connection
            key: url
    
  frontend:
    type: dockerfile
    dockerfile: ./frontend/Dockerfile
    build:
      args:
        VITE_API_URL: ${BACKEND_URL}/api
        VITE_APP_ENV: production
```

#### Docker Compose (Development)
```yaml
# docker-compose.yml
version: '3.8'

services:
  backend:
    build: ./backend
    environment:
      - APP_ENV=development
      - DATABASE_URL=postgresql://user:pass@db:5432/appdb
      - PORT=8000
    ports:
      - "8000:8000"
    depends_on:
      - db
  
  frontend:
    build: 
      context: ./frontend
      args:
        VITE_API_URL: http://localhost:8000/api
        VITE_APP_ENV: development
    ports:
      - "3000:3000"
    depends_on:
      - backend
  
  db:
    image: postgres:15
    environment:
      POSTGRES_DB: appdb
      POSTGRES_USER: user
      POSTGRES_PASSWORD: pass
    volumes:
      - postgres_data:/var/lib/postgresql/data

volumes:
  postgres_data:
```

### 6. Secret Management

```python
# secrets_manager.py
import os
from typing import Optional, Dict
import logging

logger = logging.getLogger(__name__)

class SecretManager:
    def __init__(self):
        self.platform = self._detect_platform()
    
    def get_secret(self, key: str) -> Optional[str]:
        """Get secret with fallback strategy"""
        # 1. Try cloud provider secret manager
        if self.platform != "local":
            secret = self._get_cloud_secret(key)
            if secret:
                return secret
        
        # 2. Fall back to environment variable
        return os.getenv(key)
    
    def _get_cloud_secret(self, key: str) -> Optional[str]:
        """Get secret from cloud provider (implement as needed)"""
        if self.platform == "aws":
            return self._get_aws_secret(key)
        elif self.platform == "gcp":
            return self._get_gcp_secret(key)
        # Add other providers as needed
        return None
    
    def _detect_platform(self) -> str:
        if os.getenv("AWS_REGION"):
            return "aws"
        elif os.getenv("GOOGLE_CLOUD_PROJECT"):
            return "gcp"
        else:
            return "local"
    
    def validate_secrets(self, required_secrets: list) -> Dict[str, bool]:
        """Validate that all required secrets are available"""
        results = {}
        for secret in required_secrets:
            value = self.get_secret(secret)
            results[secret] = value is not None
            if not value:
                logger.error(f"❌ Required secret '{secret}' is missing")
        
        return results
```

### 7. Environment Documentation

```markdown
# Environment Variables Reference

## Required Variables

### Backend
| Variable | Description | Example |
|----------|-------------|---------|
| `DATABASE_URL` | Database connection string | `postgresql://user:pass@host:5432/db` |
| `APP_ENV` | Application environment | `production`, `staging`, `local` |

### Frontend (Build-time)
| Variable | Description | Example |
|----------|-------------|---------|
| `VITE_API_URL` | Backend API endpoint | `https://api.example.com/api` |
| `VITE_APP_ENV` | Application environment | `production` |

## Optional Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `PORT` | `8000` | Server port |
| `LOG_LEVEL` | `INFO` | Logging verbosity |
| `CORS_ORIGINS` | `*` | Allowed CORS origins |

## Local Development Setup

1. Copy environment template:
   ```bash
   cp .env.example .env
   ```

2. Update `.env` with your values:
   ```env
   APP_ENV=local
   DATABASE_URL=postgresql://user:pass@localhost:5432/appdb
   VITE_API_URL=http://localhost:8000/api
   ```

3. Run the application:
   ```bash
   make run-local
   ```

## Cloud Deployment

Set these variables in your cloud platform:
- Zeabur: Project Settings → Variables
- Heroku: Settings → Config Vars
- Vercel: Project Settings → Environment Variables
```

### 8. Development Experience

```makefile
# Makefile
.PHONY: setup run-local run-docker test deploy

setup:
	@echo "Setting up development environment..."
	cp .env.example .env
	@echo "✅ Created .env file - please update with your values"
	pip install -r requirements.txt
	@echo "✅ Dependencies installed"

run-local:
	@echo "Starting local development server..."
	APP_ENV=local python main.py

run-docker:
	@echo "Starting with Docker Compose..."
	docker-compose up --build

test:
	@echo "Running tests..."
	APP_ENV=test pytest

deploy-staging:
	@echo "Deploying to staging..."
	# Add deployment commands

deploy-production:
	@echo "Deploying to production..."
	# Add deployment commands

clean:
	docker-compose down -v
	docker system prune -f
```

```bash
# .env.example
# Copy this file to .env and update values

# Application Environment
APP_ENV=local

# Database Configuration
DATABASE_URL=postgresql://user:password@localhost:5432/ai_optimizer

# Server Configuration
PORT=8000
LOG_LEVEL=INFO
CORS_ORIGINS=http://localhost:3000

# Frontend Configuration (for local development)
VITE_API_URL=http://localhost:8000/api
VITE_APP_ENV=development

# Optional: External Services
DEEPSEEK_API_KEY=your-api-key-here
DEEPSEEK_MODEL=deepseek-chat
```

### 9. Testing Configuration

```python
# test_config.py
import pytest
import os
from unittest.mock import patch
from config_validator import AppConfig

class TestConfig:
    def test_valid_config(self):
        """Test configuration with all required variables"""
        with patch.dict(os.environ, {
            "APP_ENV": "test",
            "DATABASE_URL": "postgresql://test:test@localhost:5432/test"
        }):
            config = AppConfig()
            assert config.app_env == "test"
            assert config.database_url.startswith("postgresql://")
    
    def test_missing_required_config(self):
        """Test that missing required config raises error"""
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(ValueError, match="DATABASE_URL"):
                AppConfig()
    
    def test_invalid_database_url(self):
        """Test validation of database URL format"""
        with patch.dict(os.environ, {
            "DATABASE_URL": "invalid-url"
        }):
            with pytest.raises(ValueError, match="Invalid database URL"):
                AppConfig()
    
    def test_platform_detection(self):
        """Test platform detection logic"""
        from platform_utils import PlatformUtils
        
        with patch.dict(os.environ, {"HEROKU_APP_NAME": "test-app"}):
            assert PlatformUtils.detect_platform() == "heroku"
        
        with patch.dict(os.environ, {"ZEABUR_PROJECT_ID": "test-project"}):
            assert PlatformUtils.detect_platform() == "zeabur"

# Run tests
# pytest test_config.py -v
```

### 10. Migration Strategy

#### Phase 1: Add New Configuration System
```python
# Add alongside existing config
from config_validator import AppConfig

# Legacy config (keep for now)
old_config = load_legacy_config()

# New config
try:
    new_config = AppConfig()
    logger.info("✅ Using new configuration system")
except Exception as e:
    logger.warning(f"⚠️ Falling back to legacy config: {e}")
    new_config = None
```

#### Phase 2: Gradual Migration
```python
# Use new config where available, fall back to legacy
def get_database_url():
    if new_config:
        return new_config.database_url
    return old_config.get("DATABASE_URL")
```

#### Phase 3: Remove Legacy System
```python
# Remove old configuration loading
# Update all references to use new_config
config = AppConfig()  # Only new system
```

## Implementation Checklist

- [ ] Create configuration validator with Pydantic
- [ ] Update Dockerfiles with proper build arguments
- [ ] Add platform detection utilities
- [ ] Create environment documentation
- [ ] Set up development tooling (Makefile, .env.example)
- [ ] Add configuration tests
- [ ] Update deployment scripts
- [ ] Migrate existing configuration gradually
- [ ] Document cloud platform specific setup
- [ ] Add monitoring for configuration issues

## Benefits

✅ **Predictable**: Same configuration pattern across all environments  
✅ **Secure**: Proper separation of secrets and regular config  
✅ **Debuggable**: Clear validation and error messages  
✅ **Maintainable**: Type-safe configuration with validation  
✅ **Portable**: Works across different cloud platforms  
✅ **Developer Friendly**: Easy local development setup  
✅ **Production Ready**: Robust error handling and logging  

## Common Patterns

### Environment-Specific Defaults
```python
def get_log_level():
    if config.is_production:
        return "WARNING"
    elif config.is_staging:
        return "INFO" 
    else:
        return "DEBUG"
```

### Feature Flags
```python
class FeatureFlags:
    def __init__(self, config: AppConfig):
        self.config = config
    
    @property
    def enable_ai_reports(self) -> bool:
        return self.config.app_env in ["staging", "production"]
    
    @property
    def enable_debug_logs(self) -> bool:
        return not self.config.is_production
```

### Configuration Hot Reloading (Advanced)
```python
class ConfigWatcher:
    def __init__(self, config: AppConfig):
        self.config = config
        self.last_modified = time.time()
    
    def check_for_updates(self):
        # Check if configuration source has changed
        # Reload configuration if needed
        pass
```

This configuration strategy ensures your application is maintainable, secure, and deployable across any cloud platform while providing excellent developer experience.