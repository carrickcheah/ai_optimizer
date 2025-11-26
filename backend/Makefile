# Kill all related ports (8000 backend, 3000/3001 frontend)
down:
	@echo "Killing processes on ports 8000, 3000, 3001..."
	@lsof -ti:8000 | xargs kill -9 2>/dev/null || true
	@lsof -ti:3000 | xargs kill -9 2>/dev/null || true
	@lsof -ti:3001 | xargs kill -9 2>/dev/null || true
	@echo "All ports cleared."

# Kill all ports and start backend
run: down
	@echo "Starting backend on port 8000..."
	uv run uvicorn main:app --host 0.0.0.0 --port 8000 --reload

ingest:
	uv run python app/data_ingestion/mariadb_parser.py





# uv run python -m app.main