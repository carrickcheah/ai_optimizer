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

# Install uv for fast dependency management
RUN pip install uv

# Copy backend dependency files
COPY backend/pyproject.toml backend/uv.lock ./

# Create virtual environment and install dependencies
RUN uv venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
RUN uv sync --frozen --no-dev

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