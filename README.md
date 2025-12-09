# Multi-LLM Eval

A comprehensive tool for comparing responses from multiple free LLM providers. Evaluate query responses across different models and analyze metrics like latency, quality, coherence, and cost efficiency.

## Features

- **Multiple LLM Providers**: Groq, Together AI, HuggingFace, and Ollama (local)
- **Comprehensive Metrics**: Latency, tokens/second, quality scores, cost estimation
- **Visual Comparison**: Charts and graphs for easy comparison
- **LangGraph Workflow**: Orchestrated evaluation pipeline
- **MCP Server**: Integration with Claude Desktop and other MCP clients
- **Clean Architecture**: Well-structured, maintainable codebase

## Tech Stack

- **Frontend**: React, Tailwind CSS, shadcn/ui, Recharts
- **Backend**: FastAPI, Python 3.12
- **Orchestration**: LangGraph
- **Integration**: MCP (Model Context Protocol)
- **Containerization**: Docker

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

### Together AI
1. Go to https://api.together.xyz
2. Sign up for a free account
3. Get your API key from settings

### HuggingFace
1. Go to https://huggingface.co/settings/tokens
2. Create a new token with "Read" permissions

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

## Project Structure

```
multi-llm-eval/
├── frontend/                 # React frontend
│   ├── src/
│   │   ├── components/      # UI components
│   │   ├── services/        # API services
│   │   └── lib/            # Utilities
│   └── ...
├── backend/                  # FastAPI backend
│   └── app/
│       ├── domain/          # Business entities
│       ├── application/     # Use cases
│       ├── infrastructure/  # External services
│       │   ├── llm_providers/
│       │   ├── langgraph/
│       │   └── persistence/
│       └── interfaces/      # API routes
├── mcp-server/              # MCP server
└── docker-compose.yml
```

## License

MIT
