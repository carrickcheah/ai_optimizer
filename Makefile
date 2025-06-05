# Quick development start (equivalent to dev-start.sh)
dev:
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
stop:
	@echo "🛑 Stopping all services..."
	@pkill -f "uvicorn main:app" || true
	@pkill -f "vite" || true
	@pkill -f "node.*vite" || true

.PHONY: dev backend-dev frontend-dev stop