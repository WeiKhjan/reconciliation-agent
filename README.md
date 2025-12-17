# Reconciliation Agent

AI-powered reconciliation logic discovery service using LangGraph and Claude.

## Features

- Upload CSV, Excel, or PDF files for reconciliation
- AI-powered logic discovery using LangGraph + Claude (via OpenRouter)
- Self-correcting code generation with iterative refinement
- User feedback loop for improving results
- Export to n8n workflow JSON
- Deploy on Zeabur

## Architecture

```
+-------------------+     +-------------------+     +-------------------+
|  Streamlit UI     |<--->|   FastAPI Backend |<--->|  LangGraph Agent  |
|  (frontend/)      |     |   (backend/)      |     |  (Claude via      |
|                   |     |                   |     |   OpenRouter)     |
+-------------------+     +-------------------+     +-------------------+
```

## Project Structure

```
recon-agent/
├── backend/
│   ├── app/
│   │   ├── main.py              # FastAPI entry point
│   │   ├── config.py            # Configuration
│   │   ├── models/schemas.py    # Pydantic models
│   │   ├── api/routes.py        # API endpoints
│   │   ├── core/
│   │   │   ├── agent.py         # LangGraph agent
│   │   │   ├── nodes.py         # Graph nodes
│   │   │   ├── state.py         # State definition
│   │   │   └── prompts.py       # LLM prompts
│   │   └── services/
│   │       ├── file_parser.py   # CSV/Excel/PDF parsing
│   │       ├── code_executor.py # Safe code sandbox
│   │       ├── llm_client.py    # OpenRouter client
│   │       └── n8n_exporter.py  # n8n JSON export
│   ├── requirements.txt
│   └── zeabur.json
├── frontend/
│   ├── app.py                   # Streamlit app
│   ├── utils/api_client.py      # Backend API client
│   ├── requirements.txt
│   └── zeabur.json
├── sample data/                 # Sample datasets
├── .env.example
└── README.md
```

## Quick Start

### Prerequisites

- Python 3.11+
- OpenRouter API key (get one at https://openrouter.ai)

### Local Development

1. **Clone and setup backend:**
   ```bash
   cd backend
   pip install -r requirements.txt
   ```

2. **Create .env file in backend/:**
   ```bash
   cp ../.env.example .env
   # Edit .env and add your OPENROUTER_API_KEY
   ```

3. **Run backend:**
   ```bash
   cd backend
   uvicorn app.main:app --reload --port 8080
   ```

4. **Run frontend (in another terminal):**
   ```bash
   cd frontend
   pip install -r requirements.txt
   streamlit run app.py
   ```

5. **Open browser:**
   - Frontend: http://localhost:8501
   - Backend API docs: http://localhost:8080/docs

## Deployment on Zeabur

### 1. Push to GitHub

```bash
git init
git add .
git commit -m "Initial commit"
git remote add origin https://github.com/yourusername/recon-agent.git
git push -u origin main
```

### 2. Deploy on Zeabur

1. Go to [Zeabur Dashboard](https://zeabur.com)
2. Create a new project
3. Add two services from your GitHub repo:

   **Backend Service:**
   - Root directory: `backend/`
   - Add environment variables:
     - `OPENROUTER_API_KEY`: Your OpenRouter API key
     - `OPENROUTER_MODEL`: `anthropic/claude-sonnet-4-20250514`
   - Generate a domain (e.g., `recon-backend.zeabur.app`)

   **Frontend Service:**
   - Root directory: `frontend/`
   - Add environment variables:
     - `BACKEND_URL`: Backend domain URL (e.g., `https://recon-backend.zeabur.app`)
   - Generate a domain (e.g., `recon-agent.zeabur.app`)

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/sessions` | POST | Create new session |
| `/api/sessions/{id}/upload` | POST | Upload files |
| `/api/sessions/{id}/reconcile` | POST | Start reconciliation |
| `/api/sessions/{id}/status` | GET | Get progress status |
| `/api/sessions/{id}/results` | GET | Get results |
| `/api/sessions/{id}/feedback` | POST | Submit feedback |
| `/api/sessions/{id}/export/data` | GET | Download data |
| `/api/sessions/{id}/export/code` | GET | Download Python code |
| `/api/sessions/{id}/export/n8n` | GET | Get n8n workflow JSON |

## Sample Data

The `sample data/` folder contains example files:
- `SOA - Instantcash April 2025_Clean (1).csv` - Statement of Account
- `LBL - InstantCash April 2025 (1).csv` - Line by Line transactions

### Reconciliation Strategy for Sample Data

- **Match Key**: RFX or MY reference numbers
- **SOA**: Reference embedded in Narration field (e.g., `RFX35QEXRL8R9UK`)
- **LBL**: Reference in Description field
- **Date Formats**: SOA uses `D-Mon-YY`, LBL uses `D/M/YYYY`

## How It Works

1. **Upload**: User uploads two datasets (CSV, Excel, or PDF)
2. **Analyze**: Agent analyzes schemas and identifies matching strategy
3. **Generate**: Agent generates Python/Pandas reconciliation code
4. **Execute**: Code runs in a secure sandbox
5. **Evaluate**: Results are checked; agent self-corrects if needed
6. **Feedback**: User can provide feedback for refinement
7. **Export**: Download reconciled data, Python code, or n8n workflow

## n8n Integration

The generated n8n workflow includes:
- **Execute Command Node**: Runs Python code directly (requires Python on n8n server)
- **JavaScript Code Node**: JavaScript implementation for native n8n execution

To import into n8n:
1. Download the n8n workflow JSON
2. In n8n, go to Workflows > Import from file
3. Configure data source nodes to load your datasets
4. Run the workflow

## License

MIT
