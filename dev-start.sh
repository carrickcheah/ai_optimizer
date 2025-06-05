#!/bin/bash

# Development startup script for AI Optimizer
echo "🚀 Starting AI Optimizer Development Environment"

# Function to cleanup processes
cleanup() {
    echo "🛑 Stopping services..."
    if [ ! -z "$BACKEND_PID" ]; then
        kill $BACKEND_PID 2>/dev/null || true
    fi
    if [ ! -z "$FRONTEND_PID" ]; then
        kill $FRONTEND_PID 2>/dev/null || true
    fi
    exit 0
}

# Trap signals for graceful shutdown
trap cleanup SIGTERM SIGINT EXIT

echo "📁 Project structure:"
echo "├── backend/    - FastAPI backend (Python)"
echo "├── frontend/   - React + Vite frontend"
echo "└── docker/     - Docker configurations"
echo

# Check if backend virtual environment exists
if [ ! -d "backend/.venv" ]; then
    echo "❌ Backend virtual environment not found. Run: cd backend && uv sync"
    exit 1
fi

# Check if frontend dependencies are installed
if [ ! -d "frontend/node_modules" ]; then
    echo "❌ Frontend dependencies not found. Run: cd frontend && npm install"
    exit 1
fi

echo "🔧 Starting Backend (FastAPI)..."
cd backend
source .venv/bin/activate
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload &
BACKEND_PID=$!
echo "   Backend running at: http://localhost:8000"
echo "   Backend API docs: http://localhost:8000/docs"
cd ..

echo "🎨 Starting Frontend (React + Vite)..."
cd frontend
npm run dev &
FRONTEND_PID=$!
echo "   Frontend will be available at: http://localhost:3000"
cd ..

echo
echo "✅ Both services starting..."
echo "📊 Frontend: http://localhost:3000"
echo "🔧 Backend API: http://localhost:8000"
echo "📖 API Docs: http://localhost:8000/docs"
echo
echo "Press Ctrl+C to stop both services"

# Wait for both processes
wait