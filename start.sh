#!/bin/bash

# Start nginx in background
nginx -g "daemon off;" &
NGINX_PID=$!

# Start FastAPI backend in background
cd /app/backend
export PYTHONPATH=/app/backend
su app -c "uvicorn app.main:app --host 127.0.0.1 --port 8000" &
UVICORN_PID=$!

# Function to cleanup processes
cleanup() {
    echo "Stopping services..."
    kill $NGINX_PID $UVICORN_PID
    exit 0
}

# Trap signals for graceful shutdown
trap cleanup SIGTERM SIGINT

# Wait for any process to exit
wait -n

# Exit with status of process that exited first
exit $? 