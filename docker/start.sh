#!/bin/bash
# Start script for AI Optimizer container
# Runs nginx (frontend) and uvicorn (backend) together

set -e

# Start nginx in background
nginx &

# Start backend with python (venv already in PATH)
cd /app/backend
exec python main.py
