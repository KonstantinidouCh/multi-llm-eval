# Multi-LLM Eval

A comprehensive tool for comparing responses from multiple free LLM providers. Evaluate query responses across different models and analyze metrics like latency, quality, coherence, and cost efficiency.

## Features

- **Multiple LLM Providers**: Groq, HuggingFace, Ollama (local), and Google Gemini
- **Comprehensive Metrics**: Latency, tokens/second, quality scores, cost estimation
- **Visual Comparison**: Charts and graphs for easy comparison
- **LangGraph Workflow**: Orchestrated evaluation pipeline with stateful processing
- **MCP Server**: Integration with Claude Desktop and other MCP clients
- **Observability**: Full tracing and analytics with Langfuse integration
- **User Authentication**: JWT-based authentication with session management
- **Chat Interface**: Follow-up conversations on evaluation results
- **Clean Architecture**: Well-structured, maintainable codebase

## Tech Stack

- **Frontend**: React 18, TypeScript, Tailwind CSS, shadcn/ui, Recharts, React Query
- **Backend**: FastAPI, Python 3.12+, SQLAlchemy, Alembic
- **Database**: PostgreSQL (production), SQLite (development)
- **Orchestration**: LangGraph, LangChain
- **Observability**: Langfuse (with ClickHouse, Redis, MinIO)
- **Integration**: MCP (Model Context Protocol)
- **Containerization**: Docker & Docker Compose

## Quick Start

### Prerequisites

- Node.js 20+
- Python 3.12+
- Docker (optional)

### Setup

1. Clone the repository:
```bash
git clone https://github.com/YOUR_USERNAME/multi-llm-eval.git
cd multi-llm-eval
```

2. Configure API keys:
```bash
cp .env.example .env
# Edit .env with your API keys
```

3. Start with Docker:
```bash
docker-compose up --build
```

Or run manually:

**Backend:**
```bash
cd backend
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
# Edit .env with your API keys
uvicorn app.main:app --reload
```

**Frontend:**
```bash
cd frontend
npm install
npm run dev
```

4. Open http://localhost:3000

## Getting Free API Keys

### Groq (Recommended - Very Fast)
1. Go to https://console.groq.com
2. Sign up for a free account
3. Generate an API key

### HuggingFace
1. Go to https://huggingface.co/settings/tokens
2. Create a new token with "Read" permissions

### Google Gemini
1. Go to https://aistudio.google.com/apikey
2. Create a new API key

### Ollama (Local - Completely Free)
1. Install Ollama: https://ollama.ai
2. Pull a model: `ollama pull llama3`
3. Ollama runs at http://localhost:11434

## MCP Server Integration

To use with Claude Desktop, add to your claude_desktop_config.json:

```json
{
  "mcpServers": {
    "multi-llm-eval": {
      "command": "python",
      "args": ["path/to/multi-llm-eval/mcp-server/server.py"]
    }
  }
}
```

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | /api/providers | List available LLM providers |
| POST | /api/evaluate | Run evaluation across providers |
| GET | /api/history | Get evaluation history |
| GET | /api/evaluations/{id} | Get specific evaluation |
| GET | /api/health | Health check |
| POST | /api/auth/login | User login |
| POST | /api/auth/register | User registration |
| POST | /api/chat | Chat with evaluation context |

## Project Structure

```
multi-llm-eval/
├── frontend/                 # React TypeScript frontend
│   ├── src/
│   │   ├── components/      # UI components (QueryInput, ResultsDisplay, ChatPanel, etc.)
│   │   ├── services/        # API services
│   │   ├── contexts/        # React contexts (AuthContext)
│   │   ├── types/           # TypeScript interfaces
│   │   └── lib/             # Utilities
│   └── ...
├── backend/                  # FastAPI backend (Clean Architecture)
│   └── app/
│       ├── domain/          # Business entities & repository interfaces
│       │   ├── entities/    # EvaluationRequest, EvaluationResult, LLMResponse
│       │   └── repositories/
│       ├── application/     # Use cases & services
│       │   ├── services/    # AuthService, ChatService
│       │   └── use_cases/   # EvaluateLLMs, MetricsCalculator
│       ├── infrastructure/  # External services
│       │   ├── llm_providers/  # Groq, HuggingFace, Ollama, Gemini
│       │   ├── langgraph/      # Evaluation workflow orchestration
│       │   ├── observability/  # Langfuse integration
│       │   └── persistence/    # Database (PostgreSQL/SQLite)
│       └── interfaces/      # API routes
│           └── api/         # REST endpoints & auth
├── mcp-server/              # MCP server for Claude Desktop
└── docker-compose.yml       # Full stack with Langfuse observability
```

## Environment Variables

Create a `.env` file in the backend directory with the following variables:

```bash
# LLM Provider API Keys
GROQ_API_KEY=your_groq_api_key
HUGGINGFACE_API_KEY=your_huggingface_api_key
GEMINI_API_KEY=your_gemini_api_key

# Ollama (local)
OLLAMA_BASE_URL=http://localhost:11434

# Database
DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/multi_llm_eval

# Authentication
JWT_SECRET_KEY=your_secret_key

# Langfuse (optional - for observability)
LANGFUSE_PUBLIC_KEY=your_public_key
LANGFUSE_SECRET_KEY=your_secret_key
LANGFUSE_HOST=http://localhost:3001
```

## License

MIT
