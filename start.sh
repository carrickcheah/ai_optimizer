#!/bin/bash

# Start nginx in background
nginx -g "daemon off;" &

# Start FastAPI backend
cd /app/backend
export PYTHONPATH=/app/backend
su app -c "uvicorn app.main:app --host 127.0.0.1 --port 8000" &

# Wait for any process to exit
wait -n

# Exit with status of process that exited first
exit $? 