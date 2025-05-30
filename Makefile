# Main development command
start:
	@echo "🚀 Starting AI Optimizer (no auto-reload)..."
	@make -j2 backend frontend

# Individual services
backend:
	@echo "Starting backend on port 8000 (no reload)..."
	@cd services/backend && \
	source ../../.venv/bin/activate && \
	python -m uvicorn app.main:app --port 8000

frontend:
	@echo "Starting frontend on port 3000..."
	@npm run dev --prefix services/frontend

# Stop all services
stop:
	@echo "🛑 Stopping all services..."
	@pkill -f "uvicorn app.main:app" || true
	@pkill -f "vite" || true
	@pkill -f "node.*vite" || true

# Reset services
reset:
	@echo "🔄 Resetting AI Optimizer..."
	@make stop
	@sleep 3
	@make start

# Alternative: start with reload for development
start-dev:
	@echo "🚀 Starting AI Optimizer (with auto-reload)..."
	@make -j2 backend-dev frontend

backend-dev:
	@echo "Starting backend on port 8000 (with reload)..."
	@cd services/backend && \
	source ../../.venv/bin/activate && \
	python -m uvicorn app.main:app --reload --port 8000

.PHONY: start backend frontend stop reset start-dev backend-dev