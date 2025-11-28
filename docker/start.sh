#!/bin/bash
# Start script for AI Optimizer container
# Runs nginx (frontend) and uvicorn (backend) together

set -e

# Start nginx in background
nginx &

# Start backend with uvicorn
cd /app/backend
exec uv run python main.py
