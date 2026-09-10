# AutoFix Agent - Backend

Production-ready backend service for AutoFix Agent — an autonomous, multi-language self-healing code repair system powered by LangGraph, FastAPI, and Groq/Ollama LLMs.

---

## Architecture Overview

```text
backend/
├── app/
│   ├── agent/                 # Core LangGraph autonomous repair graph
│   │   ├── graph.py           # StateGraph builder and compiled workflow
│   │   ├── nodes.py           # Node handlers (execute, observe, diagnose, patch, validate)
│   │   ├── routing.py         # Conditional routing & loop-termination logic
│   │   └── state.py           # TypedDict AgentState & Pydantic models
│   ├── analysis/              # Multi-language error parsing
│   │   ├── error_parser.py    # Regex & AST error extractors (Python, JS, Java)
│   │   └── models.py          # ErrorObservation Pydantic model
│   ├── execution/             # Isolated subprocess execution engine
│   │   ├── base.py            # BaseExecutor & ExecutionResult
│   │   ├── python_executor.py # Python isolated execution
│   │   ├── javascript_executor.py # Node.js isolated execution
│   │   ├── java_executor.py   # Java javac & java execution
│   │   └── manager.py         # Language executor registry & dispatcher
│   ├── llm/                   # Structured LLM diagnosis & repair
│   │   ├── client.py          # LangChain structured outputs via Groq/Ollama
│   │   ├── models.py          # RepairDiagnosis & RepairAttempt schemas
│   │   └── prompts.py         # Prompt templates for diagnosis & patching
│   ├── streaming/             # Real-time SSE streaming engine
│   │   ├── emitter.py         # SSE event generation & dispatch
│   │   └── events.py          # Typed SSEEvent models
│   ├── validation/            # Test-driven validation engine
│   │   ├── base.py            # BaseValidator & ValidationResult models
│   │   ├── python_validator.py # pytest runner & test failure parser
│   │   ├── javascript_validator.py # Node.js test harness
│   │   ├── java_validator.py   # Java assertion test runner
│   │   └── manager.py         # Validator manager & dispatcher
│   └── main.py                # FastAPI application & REST/SSE endpoints
├── tests/                     # 100+ comprehensive automated tests
│   ├── test_agent_graph.py
│   ├── test_analysis.py
│   ├── test_api.py
│   ├── test_execution.py
│   ├── test_health.py
│   ├── test_llm_client.py
│   ├── test_streaming.py
│   └── test_validation_workflow.py
├── .env.example
├── requirements.txt
└── README.md
```

---

## API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/health` | Service health status, version, and supported languages |
| `POST` | `/api/analyze` | Standalone execution and structured error diagnosis |
| `POST` | `/api/repair` | Synchronous end-to-end autonomous repair workflow |
| `POST` | `/api/repair/stream` | Real-time Server-Sent Events (SSE) streaming repair |

---

## Setup & Running

### 1. Python Environment (Python 3.10+)

```bash
cd backend
python -m venv venv
```

Activate:
- **Windows (PowerShell)**: `.\venv\Scripts\Activate.ps1`
- **Windows (CMD)**: `.\venv\Scripts\activate.bat`
- **Linux / macOS**: `source venv/bin/activate`

### 2. Install Dependencies

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

### 3. Configure Environment

```bash
cp .env.example .env
```

Set your `GROQ_API_KEY` in `.env`:
```ini
GROQ_API_KEY=gsk_your_groq_api_key_here
GROQ_MODEL=llama-3.3-70b-versatile
```

### 4. Run the Backend Server

```bash
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

- API Documentation (Swagger UI): `http://127.0.0.1:8000/docs`
- ReDoc: `http://127.0.0.1:8000/redoc`

### 5. Run the Test Suite

```bash
pytest tests/ -v
```
