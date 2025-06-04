# Multi-stage build for AI Optimizer Full Stack
# Stage 1: Build Frontend (React + Vite)
FROM node:20-alpine as frontend-builder

WORKDIR /app/frontend

# Copy frontend package files
COPY services/frontend/package*.json ./

# Install ALL dependencies (including dev dependencies for build)
RUN npm ci

# Copy frontend source and build
COPY services/frontend/ ./
RUN npm run build

# Stage 2: Build Backend Dependencies
FROM python:3.11-slim as backend-builder

# Install uv for fast dependency management
RUN pip install uv

WORKDIR /app/backend

# Copy backend dependency files
COPY services/backend/pyproject.toml ./

# Install dependencies to virtual environment
RUN uv venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
RUN uv pip install --no-cache -r pyproject.toml

# Stage 3: Production Runtime
FROM python:3.11-slim as production

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
COPY services/backend/app ./app

# Copy nginx configuration
COPY nginx.conf /etc/nginx/nginx.conf

# Create non-root user for backend
RUN useradd --create-home --shell /bin/bash app

# Setup directories and permissions
RUN mkdir -p /app/logs && chown app:app /app/logs
RUN mkdir -p /var/log/nginx

# Expose ports
EXPOSE 80 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD curl -f http://localhost/health || exit 1

# Start script
COPY start.sh /start.sh
RUN chmod +x /start.sh

CMD ["/start.sh"] 