# Main development command
start:
	@echo "🚀 Starting AI Optimizer..."
	@make -j2 backend frontend

# Individual services - Updated to use virtual environment
backend:
	@echo "Starting backend on port 8000..."
	@cd services/backend && \
	source ../../.venv/bin/activate && \
	python -m uvicorn app.main:app --reload --port 8000

frontend:
	@echo "Starting frontend on port 3000..."
	@npm run dev --prefix services/frontend

# Stop all services
stop:
	@pkill -f "uvicorn app.main:app" || true
	@pkill -f "vite" || true

llm:
	@echo "🚀🚀🚀 yahooo on board now! We fly together..."
	uv run services/sql_agent/src/sql_agent/models/llm.py


.PHONY: start backend frontend stop