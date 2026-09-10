# AutoFix Agent - Backend

Backend service for the AutoFix Agent autonomous code repair system, built with Python, FastAPI, LangGraph, and Groq.

## Project Structure

```text
backend/
├── app/
│   ├── __init__.py
│   └── main.py
├── tests/
│   └── test_health.py
├── .env.example
├── requirements.txt
└── README.md
```

## Setup & Running

### 1. Create Python Virtual Environment (Python 3.12+)

```bash
cd backend
python -m venv venv
```

Activate the environment:
- **Windows (PowerShell)**: `.\venv\Scripts\Activate.ps1`
- **Windows (CMD)**: `.\venv\Scripts\activate.bat`
- **Linux/macOS**: `source venv/bin/activate`

### 2. Install Dependencies

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

### 3. Configure Environment Variables

```bash
cp .env.example .env
```

### 4. Run the Development Server

```bash
uvicorn app.main:app --reload --port 8000
```

The server will be available at `http://localhost:8000`.

Interactive API docs:
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

### 5. Run Tests

```bash
pytest
```
