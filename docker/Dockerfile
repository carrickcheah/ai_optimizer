# ===========================================
# AI Optimizer Full Stack Dockerfile
# Multi-stage build: Frontend + Backend combined
# ===========================================

# Stage 1: Build Frontend (React + Vite)
FROM node:20-alpine AS frontend-builder

WORKDIR /app/frontend

# Copy frontend package files
COPY frontend/package*.json ./

# Install dependencies
RUN npm ci

# Copy frontend source and build
COPY frontend/ ./
RUN npm run build

# Stage 2: Build Backend Dependencies
FROM python:3.11-slim AS backend-builder

WORKDIR /app/backend

# Install build dependencies
RUN apt-get update && apt-get install -y gcc g++ && rm -rf /var/lib/apt/lists/*

# Create virtual environment
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy backend dependency files and install
COPY backend/pyproject.toml ./
RUN pip install --no-cache-dir -e . || pip install --no-cache-dir \
    fastapi uvicorn mysql-connector-python python-dotenv pytz requests \
    pandas psutil numpy ortools seaborn plotly fastmcp pydantic pydantic-settings tenacity httpx

# Stage 3: Production Runtime
FROM python:3.11-slim AS production

# Install runtime dependencies
RUN apt-get update && apt-get install -y \
    nginx \
    libmariadb3 \
    curl \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Copy Python virtual environment
COPY --from=backend-builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy built frontend to nginx directory
COPY --from=frontend-builder /app/frontend/dist /var/www/html

# Set working directory for backend
WORKDIR /app/backend

# Copy backend application
COPY backend/app ./app
COPY backend/main.py ./main.py

# Copy nginx configuration
COPY docker/nginx.conf /etc/nginx/nginx.conf

# Setup directories and permissions
RUN mkdir -p /app/logs /var/log/nginx

# Expose port 80 (nginx serves both frontend and proxies to backend)
EXPOSE 80

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD curl -f http://localhost/health || exit 1

# Start script
COPY docker/start.sh /start.sh
RUN chmod +x /start.sh

CMD ["/start.sh"] 