## llms_project

    services/ai_optimizer/
    ├── .venv/
    ├── backend/
    │   ├── .DS_Store
    │   ├── .venv/
    │   ├── .vscode/
    │   ├── Makefile
    │   ├── __pycache__/
    │   ├── app/
    │   │   ├── __init__.py
    │   │   ├── agent/
    │   │   │   └── __init__.py
    │   │   ├── api/
    │   │   │   ├── __init__.py
    │   │   │   ├── fastapi_app.py  <-- FastAPI app logic moved here
    │   │   │   ├── jobs_api.py
    │   │   │   ├── reports_api.py
    │   │   │   └── schedule_api.py
    │   │   ├── config.py
    │   │   ├── core/
    │   │   │   ├── __init__.py
    │   │   │   └── orchestrator.py
    │   │   ├── data_ingestion/
    │   │   │   ├── __init__.py
    │   │   │   └── excel_parser.py
    │   │   ├── llm_integration/
    │   │   │   └── __init__.py
    │   │   ├── logging_config.py
    │   │   ├── main.py             <-- Lean Uvicorn runner
    │   │   ├── reporting/
    │   │   │   ├── __init__.py
    │   │   │   ├── chart_data_generator.py
    │   │   │   ├── metrics_calculator.py
    │   │   │   └── production_report_generator.py
    │   │   ├── scheduling/
    │   │   │   ├── __init__.py
    │   │   │   ├── cpsat_solver.py
    │   │   │   ├── greedy_solver.py
    │   │   │   ├── scheduler_utils.py
    │   │   │   ├── setup_buffer.py
    │   │   │   └── urgent_handling.py
    │   │   └── utils/
    │   │       ├── __init__.py
    │   │       └── time_utils.py
    │   └── main.py
    │ 
    ├── frontend/
    │   ├── .stylelintrc
    │   ├── .vscode/
    │   ├── index.html
    │   ├── node_modules/
    │   ├── package-lock.json
    │   ├── package.json
    │   ├── postcss.config.js
    │   ├── public/
    │   ├── src/
    │   ├── tailwind.config.js
    │   └── vite.config.js
    ├── package-lock.json
    ├── package.json
    ├── pyproject.toml
    └── uv.lock