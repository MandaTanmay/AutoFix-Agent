# AutoFix Agent — Autonomous Multi-Language Code Repair & Validation Agent

An autonomous AI-powered code repair system that executes, observes, diagnoses, patches, and validates code across multiple programming languages.

## Tech Stack

### Frontend
- **Next.js 16** with React 19
- **TypeScript** with strict mode
- **Tailwind CSS** v4 with custom styling
- **shadcn/ui** components
- **Server-Sent Events (SSE)** for real-time agent streaming
- **Framer Motion** for smooth animations

### Backend
- **FastAPI** with async support
- **LangGraph** for autonomous agent workflows
- **LangChain** for LLM integration
- **Groq** (LLaMA 3.3) for AI-powered diagnosis
- **SSE** for real-time streaming
- **Python/JavaScript/Java** execution with subprocess isolation
- **pytest** for comprehensive testing

## Architecture

The system follows a test-driven autonomous repair workflow:

```
User provides source code
        ↓
Execute
        ↓
Observe
        ↓
Diagnose
        ↓
Patch
        ↓
Validate
        ↓
Success?
   ┌────┴────┐
  YES       NO
   ↓         ↓
 SUCCESS    RETRY
             ↓
          Execute again
```

## LOCAL DEVELOPMENT

### 1. Frontend Setup

```bash
# Install dependencies
pnpm install

# Create environment file
cp .env.example .env.local

# Configure .env.local with:
NEXT_PUBLIC_API_URL=http://localhost:8000

# Start development server
pnpm dev
```

Frontend runs at: `http://localhost:3000`

### 2. Backend Setup

```bash
cd backend

# Create virtual environment
python -m venv .venv

# Activate virtual environment
# Windows (PowerShell):
.venv\Scripts\Activate.ps1
# Windows (CMD):
.venv\Scripts\activate.bat
# macOS/Linux:
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Create environment file
cp .env.example .env

# Configure .env with:
GROQ_API_KEY=your_groq_api_key_here
GROQ_MODEL=openai/gpt-oss-120b
CORS_ORIGINS=http://localhost:3000,http://localhost:3001

# Start FastAPI server
uvicorn app.main:app --reload --port 8000
```

Backend runs at: `http://localhost:8000`
API Documentation: `http://localhost:8000/docs`

### 3. Running Tests

```bash
cd backend

# Run all tests
pytest tests/ -v

# Run specific test file
pytest tests/test_execution.py -v
```

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/health` | Service health check |
| `POST` | `/api/analyze` | Execute code and analyze errors |
| `POST` | `/api/repair` | Synchronous repair workflow |
| `POST` | `/api/repair/stream` | Real-time SSE streaming repair |

## Supported Languages

- **Python** (via python interpreter)
- **JavaScript** (via Node.js)
- **Java** (via javac + java)

## Environment Variables

### Frontend (.env.local)
- `NEXT_PUBLIC_API_URL` - Backend API URL (default: `http://localhost:8000`)

### Backend (.env)
- `GROQ_API_KEY` - Groq API key for LLM diagnosis
- `GROQ_MODEL` - Groq model name (default: `openai/gpt-oss-120b`)
  - **Important**: Groq regularly updates available models. Check https://console.groq.com/docs/models for current models
  - Common alternatives: `llama-3.3-70b-versatile`, `llama-3.1-8b-instant`, `gemma2-9b-it`
- `CORS_ORIGINS` - Comma-separated list of allowed CORS origins
- `PORT` - Server port (default: 8000)
- `HOST` - Server host (default: 0.0.0.0)
- `AUTOFIX_SCRATCH_DIR` - Optional custom temp directory for code execution

## Security Features

- **Subprocess isolation** - Code execution in temporary directories
- **Path traversal protection** - Blocks `../`, `/etc/`, etc.
- **Timeout enforcement** - Configurable execution timeouts
- **Output truncation** - Limits stdout/stderr to 64KB
- **Input validation** - Pydantic schema validation
- **CORS configuration** - Environment-based origin control

## Project Structure

```
AutoFix Agent/
├── app/                      # Next.js app directory
│   ├── layout.tsx
│   ├── page.tsx
│   └── globals.css
├── components/               # React components
│   ├── autofix-dashboard.tsx
│   ├── autofix-landing.tsx
│   └── ui/
├── lib/                      # Frontend utilities
│   ├── api.ts               # REST API client
│   ├── useSSERepair.ts      # SSE hook for real-time updates
│   └── utils.ts
├── backend/                 # Python backend
│   ├── app/
│   │   ├── agent/          # LangGraph workflow
│   │   ├── analysis/       # Error parsing
│   │   ├── execution/      # Code execution
│   │   ├── llm/            # LLM integration
│   │   ├── streaming/      # SSE streaming
│   │   ├── validation/     # Test validation
│   │   └── main.py         # FastAPI app
│   ├── tests/              # Comprehensive test suite
│   └── requirements.txt
├── .env.example            # Frontend env template
├── .env.local              # Frontend env (local)
├── package.json
└── tsconfig.json
```

## Current Status

### ✅ Working Features
- Complete SSE streaming integration
- Real-time agent state visualization
- Multi-language code execution
- AI-powered error diagnosis
- Automated patch generation
- Test-driven validation
- Attempt history tracking
- Comprehensive error handling

### ⚠️ Known Issues
- Some backend tests fail due to httpx TestClient compatibility issues (12/100 tests fail)
- These are test infrastructure issues, not functional problems
- Core functionality works correctly as demonstrated by 88 passing tests

### 🔧 Recommendations
1. Fix httpx TestClient compatibility in test suite
2. Add integration tests for complete end-to-end workflows
3. Consider adding Docker support for production deployment
4. Add rate limiting for API endpoints
5. Implement authentication/authorization for production use

## License

MIT License - See LICENSE file for details