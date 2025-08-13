# Quick development start (equivalent to dev-start.sh)
run:
	@echo "🚀 Starting AI Optimizer Development Environment"
	@echo "📁 Project structure:"
	@echo "├── backend/    - FastAPI backend (Python)"
	@echo "├── frontend/   - React + Vite frontend"
	@echo "└── docker/     - Docker configurations"
	@echo ""
	@if [ ! -d "backend/.venv" ]; then echo "❌ Backend virtual environment not found. Run: cd backend && uv sync"; exit 1; fi
	@if [ ! -d "frontend/node_modules" ]; then echo "❌ Frontend dependencies not found. Run: cd frontend && npm install"; exit 1; fi
	@echo "🔧 Starting Backend (FastAPI)..."
	@echo "🎨 Starting Frontend (React + Vite)..."
	@echo ""
	@make -j2 backend-dev frontend-dev
	@echo "✅ Both services running..."
	@echo "📊 Frontend: http://localhost:5173"
	@echo "🔧 Backend API: http://localhost:8000"
	@echo "📖 API Docs: http://localhost:8000/docs"
	@echo ""
	@echo "Press Ctrl+C to stop both services"

# Legacy alias for run
dev:
	@make run

# Backend development server
backend-dev:
	@cd backend && \
	source .venv/bin/activate && \
	uvicorn main:app --host $${BACKEND_HOST:-127.0.0.1} --port $${BACKEND_PORT:-8000}

# Frontend development server  
frontend-dev:
	@cd frontend && \
	npm run dev

# Stop all services
down:
	@echo "🛑 Stopping all services..."
	@echo "🔍 Finding and killing backend processes..."
	@pkill -f "uvicorn main:app" || true
	@pkill -f "uvicorn.*main:app" || true
	@pkill -f "python.*main.py" || true
	@lsof -ti:8000 | xargs kill -9 2>/dev/null || true
	@echo "🔍 Finding and killing frontend processes..."
	@pkill -f "vite" || true
	@pkill -f "node.*vite" || true
	@pkill -f "npm run dev" || true
	@lsof -ti:5173 | xargs kill -9 2>/dev/null || true
	@echo "🔍 Cleaning up any remaining processes on common ports..."
	@lsof -ti:3000 | xargs kill -9 2>/dev/null || true
	@lsof -ti:8080 | xargs kill -9 2>/dev/null || true
	@echo "✅ All processes stopped"

# Legacy alias for down
stop:
	@make down

# Nuclear option - kill everything aggressively
kill-all:
	@echo "💀 NUCLEAR OPTION: Killing all related processes..."
	@echo "🔍 Killing all Python processes..."
	@pkill -f "python" || true
	@pkill -f "uvicorn" || true
	@echo "🔍 Killing all Node processes..."
	@pkill -f "node" || true
	@pkill -f "npm" || true
	@echo "🔍 Force killing all processes on development ports..."
	@lsof -ti:3000,5173,8000,8080 | xargs kill -9 2>/dev/null || true
	@echo "⚠️  All processes killed - you may need to restart your terminal"

# Check what's running on ports
ports:
	@echo "🔍 Checking what's running on development ports..."
	@echo "Port 3000 (React default):"
	@lsof -i :3000 || echo "  - Nothing running"
	@echo "Port 5173 (Vite default):"
	@lsof -i :5173 || echo "  - Nothing running"  
	@echo "Port 8000 (FastAPI):"
	@lsof -i :8000 || echo "  - Nothing running"
	@echo "Port 8080 (Alternative):"
	@lsof -i :8080 || echo "  - Nothing running"

.PHONY: run dev backend-dev frontend-dev down stop kill-all ports