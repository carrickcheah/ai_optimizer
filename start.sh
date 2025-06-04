#!/bin/bash

# Exit on any error
set -e

# Function to cleanup processes
cleanup() {
    echo "Stopping services..."
    if [ ! -z "$NGINX_PID" ]; then
        kill $NGINX_PID 2>/dev/null || true
    fi
    if [ ! -z "$UVICORN_PID" ]; then
        kill $UVICORN_PID 2>/dev/null || true
    fi
    exit 0
}

# Trap signals for graceful shutdown
trap cleanup SIGTERM SIGINT EXIT

echo "Starting services..."

# Start nginx in background
nginx -g "daemon off;" &
NGINX_PID=$!
echo "Nginx started with PID: $NGINX_PID"

# Start FastAPI backend in background
cd /app/backend
export PYTHONPATH=/app/backend
echo "Starting uvicorn..."
su app -c "uvicorn app.main:app --host 127.0.0.1 --port 8000" &
UVICORN_PID=$!
echo "Uvicorn started with PID: $UVICORN_PID"

# Wait for both processes
echo "Waiting for processes..."
wait 