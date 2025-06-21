FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    default-libmysqlclient-dev \
    pkg-config \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better Docker layer caching
COPY pyproject.toml uv.lock ./

# Install uv and Python dependencies
RUN pip install uv
RUN uv sync --frozen --no-dev

# Copy application code
COPY . .

# Create non-root user for security
RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app
USER appuser

# Expose port (will be overridden by cloud platforms)
EXPOSE 8000

# Health check using curl instead of Python requests
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD curl -f http://localhost:${PORT:-8000}/health || exit 1

# Set environment variables for container
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

# Run the application - let main.py handle uvicorn configuration
CMD ["uv", "run", "python", "main.py"]