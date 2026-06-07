# ⚖️ LexAI — Indian Penal Code Legal Research Assistant

> **A production-grade RAG chatbot that answers questions about the Indian Penal Code using hybrid retrieval, conversational context, and LLM-powered legal reasoning.**

![Python](https://img.shields.io/badge/python-3.11-3776AB?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.104-009688?logo=fastapi&logoColor=white)
![React](https://img.shields.io/badge/React-18-61DAFB?logo=react&logoColor=black)
![TypeScript](https://img.shields.io/badge/TypeScript-5.2-3178C6?logo=typescript&logoColor=white)
![Docker](https://img.shields.io/badge/Docker-ready-2496ED?logo=docker&logoColor=white)
![License](https://img.shields.io/badge/license-MIT-green)

---

## Table of Contents

- [Overview](#overview)
- [Key Features](#key-features)
- [Architecture](#architecture)
- [Tech Stack](#tech-stack)
- [Getting Started](#getting-started)
- [Project Structure](#project-structure)
- [API Reference](#api-reference)
- [Configuration](#configuration)
- [Evaluation Framework](#evaluation-framework)
- [Deployment](#deployment)
- [Troubleshooting](#troubleshooting)
- [Contributing](#contributing)
- [License](#license)
- [Acknowledgments](#acknowledgments)

---

## Overview

LexAI is a full-stack Retrieval-Augmented Generation (RAG) system that provides AI-powered answers to questions about the **Indian Penal Code (IPC)**. Users ask legal questions in natural language, the system retrieves relevant IPC sections from a vector database using hybrid search, and an LLM generates a structured, source-backed legal answer.

### What makes this different from a typical RAG demo?

- **Multi-stage retrieval pipeline** — regex section detection → BM25 keyword search → dense vector search → Reciprocal Rank Fusion → context expansion graph
- **Conversational query condensation** — follow-up questions like _"is it bailable?"_ are automatically rewritten into standalone search queries using a lightweight LLM
- **Context expansion graph** — when Section 302 (Murder Punishment) is retrieved, Sections 300 and 299 (Murder Definition and Culpable Homicide) are automatically injected
- **Production engineering** — JWT authentication via Supabase, rate limiting, structured logging, API key rotation, Docker deployment
- **Quantitative evaluation** — 100+ test queries with measured Groundedness (0.93), Completeness (0.875), and 100% Section Hit Rate

---

## Key Features

### RAG Pipeline

| Capability | Description |
|---|---|
| **Hybrid Retrieval** | Combines BM25 keyword matching with dense vector search (multilingual-e5-base embeddings), fused via Reciprocal Rank Fusion |
| **Section Detection** | Regex patterns detect explicit section references (English + Hindi: "Section 302", "धारा 420") for exact Qdrant scroll lookup — 100% accuracy |
| **Query Condensation** | Contextual follow-ups are rewritten into standalone queries via `llama-3.1-8b-instant`. Standalone queries bypass the LLM entirely (0ms overhead) |
| **Context Expansion** | A curated relational graph auto-injects related IPC sections (e.g., 302 → 300 + 299) before LLM generation |
| **Structured Answers** | Responses follow a legal template: Relevant Provisions → Definition & Elements → Punishment & Penalties → Case Analysis → Limitations |

### Application

| Capability | Description |
|---|---|
| **Multi-user Sessions** | UUID-based sessions persisted in Redis with 24-hour TTL and ownership enforcement |
| **Supabase Authentication** | JWT verification via ES256 with dynamic JWKS key fetching and rotation |
| **Rate Limiting** | IP-based throttling via SlowAPI (configurable, default: 30 req/min) |
| **API Key Rotation** | Supports up to 9 Groq API keys with automatic failover on rate-limit (429) or overload (503) errors |
| **Three-Panel UI** | Collapsible sidebar, center chat feed, and right-side context panel with relevance tiers (Top Match / Related / Expanded) |
| **Developer Mode** | Toggle to reveal RAG analytics: retrieval type, vector DB config, and pipeline execution details |

---

## Architecture

### System Topology

```
┌─────────────────┐      HTTPS       ┌──────────────────────────┐
│   Vercel CDN    │ ────────────────► │   Render (Docker)        │
│   React + Vite  │                   │   FastAPI + Uvicorn      │
│   TailwindCSS   │                   │                          │
└─────────────────┘                   └──────────┬───────────────┘
                                                 │
                              ┌──────────────────┼──────────────────┐
                              │                  │                  │
                              ▼                  ▼                  ▼
                     ┌──────────────┐   ┌──────────────┐   ┌──────────────┐
                     │ Qdrant Cloud │   │   Groq API   │   │   Upstash    │
                     │ (Vector DB)  │   │   (LLM)      │   │   Redis      │
                     │ 548 sections │   │ llama-3.3-70b│   │  (Sessions)  │
                     └──────────────┘   └──────────────┘   └──────────────┘
                              │                                    │
                              ▼                                    ▼
                     ┌──────────────┐                     ┌──────────────┐
                     │ HuggingFace  │                     │   Supabase   │
                     │ Inference API│                     │   (Auth/JWT) │
                     │ (Embeddings) │                     └──────────────┘
                     └──────────────┘
```

### RAG Pipeline (Per Query)

```
User: "is it bailable?"
       │
       ▼
┌──────────────────────────────┐
│  1. JWT Auth Verification    │ ─── Supabase JWKS (ES256)
└──────────────┬───────────────┘
               ▼
┌──────────────────────────────┐
│  2. Session Management       │ ─── Redis: load/create session + history
└──────────────┬───────────────┘
               ▼
┌──────────────────────────────┐
│  3. Query Condensation       │ ─── Keyword filter → llama-3.1-8b-instant
│     (Phase 9A)               │     "is it bailable?" → "Is Section 302
│                              │      of IPC bailable or non-bailable?"
└──────────────┬───────────────┘
               ▼
┌──────────────────────────────┐
│  4. Hybrid Retrieval         │
│     a. Regex section detect  │ ─── Exact Qdrant scroll if "Section NNN"
│     b. Static query expansion│ ─── Synonym expansion (deterministic)
│     c. Dense semantic search │ ─── HF e5-base → Qdrant ANN (top 25)
│     d. BM25 keyword search   │ ─── In-memory BM25Okapi (top 25)
│     e. RRF fusion            │ ─── Reciprocal Rank Fusion → top 8
└──────────────┬───────────────┘
               ▼
┌──────────────────────────────┐
│  5. Context Expansion        │ ─── related_sections.json graph
│     (Phase 9B)               │     302 → auto-inject 300, 299
└──────────────┬───────────────┘
               ▼
┌──────────────────────────────┐
│  6. LLM Generation           │ ─── llama-3.3-70b-versatile via Groq
│     System prompt + context  │     Structured legal answer template
│     + chat history (last 8)  │     + key rotation on 429/503
└──────────────┬───────────────┘
               ▼
┌──────────────────────────────┐
│  7. Persist to Redis         │ ─── Save user + assistant messages
└──────────────────────────────┘
```

---

## Tech Stack

### Backend

| Component | Technology | Details |
|---|---|---|
| Web Framework | FastAPI 0.104 | Async ASGI server with auto-generated docs |
| LLM Inference | Groq API | `llama-3.3-70b-versatile` (main), `llama-3.1-8b-instant` (condenser) |
| Vector Database | Qdrant Cloud | Cosine similarity, 768-dim vectors, payload indexing on `section_number` |
| Embeddings | HuggingFace Inference API | `intfloat/multilingual-e5-base` (768 dimensions) |
| Keyword Search | rank-bm25 | In-memory BM25Okapi over tokenized IPC corpus |
| Session Store | Upstash Redis | Serverless, TLS, 24h TTL sessions with ownership enforcement |
| Auth | Supabase + python-jose | ES256 JWT verification with JWKS key caching |
| Rate Limiting | SlowAPI | IP-based, configurable per-minute limit |
| Logging | structlog | JSON in production, pretty-print in development |
| Validation | Pydantic 2.5 | Request/response models with field validators |

### Frontend

| Component | Technology | Details |
|---|---|---|
| Framework | React 18 + TypeScript 5.2 | Type-safe component architecture |
| Build Tool | Vite 5 | Fast HMR dev server, optimized production builds |
| Styling | TailwindCSS 3 | Dark theme with gold accent palette |
| Icons | Lucide React | Consistent, tree-shakeable icon set |
| Markdown | react-markdown | Renders formatted LLM responses |
| HTTP Client | Axios | API calls with auth token injection |
| Auth | @supabase/supabase-js | Client-side authentication flow |

### Infrastructure

| Component | Technology | Cost |
|---|---|---|
| Frontend Hosting | Vercel (CDN) | Free tier |
| Backend Hosting | Render.com (Docker) | Free tier (sleeps after 15min idle) |
| Vector DB | Qdrant Cloud | Free tier (1 GB) |
| Session Store | Upstash Redis | Free tier (500K commands/month) |
| LLM | Groq Cloud | Free tier (rate-limited) |
| Auth | Supabase | Free tier |

---

## Getting Started

### Prerequisites

- Python 3.11+
- Node.js 18+
- Accounts for: [Groq](https://console.groq.com/keys), [Qdrant Cloud](https://cloud.qdrant.io/), [Upstash Redis](https://upstash.com/), [Supabase](https://supabase.com/)
- IPC data already indexed in Qdrant (see [Indexing Data](#indexing-data))

### 1. Clone & Configure

```bash
git clone https://github.com/SurajD45/Legal_AI_Chatbot.git
cd Legal_AI_Chatbot

# Copy and fill in your API keys
cp .env.example .env
```

Edit `.env` with your actual credentials:

```env
GROQ_API_KEY=gsk_your_key_here
QDRANT_URL=https://your-cluster.aws.cloud.qdrant.io
QDRANT_API_KEY=your_qdrant_key
REDIS_URL=rediss://default:your_password@your-host.upstash.io:6379
SUPABASE_URL=https://your-project.supabase.co
```

### 2. Backend Setup

```bash
# Create virtual environment
python -m venv venv

# Activate (Windows)
venv\Scripts\activate

# Activate (macOS/Linux)
source venv/bin/activate

# Install dependencies
pip install -r requirements.base.txt

# Start the server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

The backend will be available at `http://localhost:8000`. In development mode, Swagger docs are at `/docs` and ReDoc at `/redoc`.

### 3. Frontend Setup

```bash
cd frontend
npm install
npm run dev
```

The frontend will be available at `http://localhost:5173` with a proxy to the backend.

### 4. Verify

```bash
# Health check
curl http://localhost:8000/health

# Test query (requires valid JWT — use the frontend for authenticated requests)
curl http://localhost:8000/
```

### Indexing Data

To index the IPC sections into Qdrant (one-time setup):

```bash
python scripts/index_data.py
```

This loads `data/ipc_clean.json` (548 IPC sections), generates embeddings using SentenceTransformer, and uploads them to your Qdrant Cloud collection.

### Docker Deployment

```bash
# Build and run the backend container
docker build -t legal-ai-backend .
docker run -p 8000:8000 --env-file .env legal-ai-backend
```

---

## Project Structure

```
legal-ai-assistant/
│
├── app/                              # Backend application
│   ├── main.py                       # FastAPI app, lifespan, CORS, error handlers
│   ├── config.py                     # Pydantic Settings — all env vars
│   ├── models.py                     # Request/response Pydantic models
│   ├── dependencies.py               # Rate limiter + JWT auth (JWKS/ES256)
│   │
│   ├── api/                          # Route handlers
│   │   ├── chat.py                   # POST /api/query, GET /api/session/latest
│   │   └── health.py                 # GET /health, GET /
│   │
│   ├── core/                         # Business logic
│   │   ├── retriever.py              # Hybrid search: regex + BM25 + dense + RRF
│   │   ├── llm_chain.py              # Groq LLM: prompt building + key rotation
│   │   ├── chat_history.py           # Redis session management
│   │   ├── query_condenser.py        # Conversational query rewriting (Phase 9A)
│   │   ├── context_expander.py       # Related section injection (Phase 9B)
│   │   └── query_expander.py         # Static synonym expansion
│   │
│   └── utils/                        # Cross-cutting concerns
│       ├── logger.py                 # structlog configuration
│       └── exceptions.py             # Custom exception hierarchy
│
├── frontend/                         # React application
│   ├── src/
│   │   ├── App.tsx                   # Main app — three-panel layout
│   │   ├── components/
│   │   │   ├── ChatInput.tsx         # Message input with loading states
│   │   │   ├── ChatMessage.tsx       # Message bubbles with source citations
│   │   │   ├── Welcome.tsx           # Landing screen with example queries
│   │   │   └── Auth.tsx              # Supabase auth component
│   │   ├── hooks/
│   │   │   └── useChat.ts           # Chat state management
│   │   ├── services/
│   │   │   ├── api.ts               # Axios client with auth headers
│   │   │   ├── auth.ts              # Auth helper functions
│   │   │   └── supabase.ts          # Supabase client initialization
│   │   └── types/
│   │       └── index.ts             # TypeScript definitions
│   ├── vercel.json                   # Vercel deployment config
│   ├── vite.config.ts                # Vite config with dev proxy
│   └── tailwind.config.js            # TailwindCSS theme
│
├── evaluation/                       # Quality measurement framework
│   ├── test_queries.json             # 100 curated test cases (7 categories)
│   ├── conversational_queries_v1.json# 10 multi-turn conversation scenarios
│   ├── evaluate_retrieval.py         # Recall@K, MRR, regex accuracy
│   ├── evaluate_answers.py           # Groundedness, completeness, hallucination
│   ├── evaluate_conversational.py    # Multi-turn evaluation
│   ├── llm_judge.py                  # LLM-as-judge evaluation engine
│   └── reports/                      # Generated evaluation reports
│
├── scripts/
│   ├── index_data.py                 # Index IPC JSON → Qdrant Cloud
│   └── archive/
│       └── generate_ipc_json.py      # IPC DOCX → JSON converter
│
├── data/
│   ├── ipc_clean.json                # 548 IPC sections (~543 KB)
│   └── related_sections.json         # Context expansion graph
│
├── tests/
│   ├── test_api.py                   # API endpoint tests
│   └── test_retriever.py             # Retriever unit tests
│
├── Dockerfile                        # Python 3.11-slim, production image
├── render.yaml                       # Render.com deployment blueprint
├── requirements.base.txt             # Production dependencies
├── requirements.dev.txt              # Dev/test dependencies
├── .env.example                      # Environment variable template
└── PROJECT_EVOLUTION.md              # Detailed architectural case study
```

---

## API Reference

### Endpoints

| Method | Path | Description | Auth |
|---|---|---|---|
| `GET` | `/` | Project info + links | None |
| `GET` | `/health` | Service health: Qdrant, embedding, LLM status | None |
| `POST` | `/api/query` | Main RAG endpoint — send query, get answer | JWT + Rate limited |
| `GET` | `/api/session/latest` | Restore latest conversation session | JWT |

### POST `/api/query`

**Request:**

```json
{
  "query": "What is Section 302 of IPC?",
  "session_id": null
}
```

**Headers:**

```
Authorization: Bearer <supabase_jwt_token>
Content-Type: application/json
```

**Response (200):**

```json
{
  "answer": "### RELEVANT PROVISIONS\n- Section 302\n- Punishment for murder\n\n### DEFINITION & ELEMENTS\n...\n\n### PUNISHMENT & PENALTIES\n- Death, or\n- Imprisonment for life, and fine\n\n### LIMITATIONS\n- ...",
  "sources": [
    {
      "section": "302",
      "title": "Punishment for murder",
      "text": "Whoever commits murder shall be punished with death, or imprisonment for life, and shall also be liable to fine.",
      "score": 1.0
    }
  ],
  "session_id": "550e8400-e29b-41d4-a716-446655440000",
  "query": "What is Section 302 of IPC?"
}
```

**Error Response (500):**

```json
{
  "error": "LLMError",
  "message": "Failed to generate answer: Rate limit exceeded",
  "details": {}
}
```

### GET `/health`

```json
{
  "status": "healthy",
  "environment": "production",
  "version": "1.0.0",
  "services": {
    "qdrant": { "status": "healthy", "collection": "ipc_legal_docs", "vectors_count": 548 },
    "embedding_model": { "status": "healthy", "model": "intfloat/multilingual-e5-base" },
    "llm": { "status": "healthy", "provider": "groq" }
  }
}
```

---

## Configuration

All variables are loaded via `app/config.py` using Pydantic Settings. The app **fails fast** on startup if required variables are missing.

| Variable | Required | Default | Description |
|---|---|---|---|
| `GROQ_API_KEY` | **Yes** | — | Primary Groq API key |
| `GROQ_API_KEY_2` … `_5` | No | — | Additional keys for rotation |
| `QDRANT_URL` | **Yes** | — | Qdrant Cloud cluster URL |
| `QDRANT_API_KEY` | **Yes** | — | Qdrant Cloud API key |
| `QDRANT_COLLECTION_NAME` | No | `ipc_legal_docs` | Qdrant collection name |
| `REDIS_URL` | **Yes** | — | Upstash Redis URL (TLS) |
| `SUPABASE_URL` | **Yes** | — | Supabase project URL |
| `HF_API_TOKEN` | No | — | HuggingFace token (optional, for rate limits) |
| `ENVIRONMENT` | No | `development` | `development` / `staging` / `production` |
| `HOST` | No | `0.0.0.0` | Bind host |
| `PORT` | No | `8000` | Bind port |
| `LOG_LEVEL` | No | `INFO` | Logging level |
| `CORS_ORIGINS` | No | `localhost` | Comma-separated allowed origins |
| `LLM_MODEL` | No | `llama-3.3-70b-versatile` | Groq model for answer generation |
| `EMBEDDING_MODEL` | No | `intfloat/multilingual-e5-base` | HuggingFace embedding model |
| `EMBEDDING_DIMENSION` | No | `768` | Vector dimension |
| `DEFAULT_TOP_K` | No | `5` | Final results after RRF fusion |
| `DENSE_CANDIDATES` | No | `20` | Dense search candidates before fusion |
| `BM25_CANDIDATES` | No | `20` | BM25 candidates before fusion |
| `RRF_K` | No | `60` | RRF smoothing constant |
| `MAX_CONTEXT_LENGTH` | No | `4000` | Max characters sent to LLM |
| `RATE_LIMIT_PER_MINUTE` | No | `30` | API rate limit per IP |

---

## Evaluation Framework

The `evaluation/` directory contains a quantitative testing framework that measures retrieval quality and answer correctness.

### Test Datasets

| Dataset | Queries | Categories |
|---|---|---|
| `test_queries.json` | 100 | exact_match (10), exact_match_hindi (3), multi_section (5), semantic (37), semantic_complex (13), semantic_hindi (4), edge_case (8) |
| `conversational_queries_v1.json` | 10 scenarios | Multi-turn conversations (e.g., "What is 302?" → "is it bailable?") |

### Evaluation Results

| Metric | Target | Final Score | Status |
|---|---|---|---|
| **Groundedness** | ≥ 0.90 | **0.930** | ✅ Met |
| **Completeness** | ≥ 0.85 | **0.875** | ✅ Met |
| **Section Hit Rate** | 100% | **100%** | ✅ Met |
| **Query Condensation Accuracy** | — | **90%** | ✅ |

### Running Evaluations

```bash
# Retrieval quality (Recall@K, MRR, regex accuracy)
python evaluation/evaluate_retrieval.py

# Answer quality (LLM-as-judge: groundedness, completeness, hallucination)
python evaluation/evaluate_answers.py

# Conversational evaluation (multi-turn scenarios)
python evaluation/evaluate_conversational.py
```

---

## Deployment

### Current Production Setup

| Service | Platform | URL Pattern |
|---|---|---|
| Frontend | Vercel CDN | `your-app.vercel.app` |
| Backend | Render.com (Docker) | `your-app.onrender.com` |
| Vector DB | Qdrant Cloud | `xxx.aws.cloud.qdrant.io` |
| Sessions | Upstash Redis | `xxx.upstash.io` |
| Auth | Supabase | `xxx.supabase.co` |

### Deploy Backend to Render

1. Push to GitHub
2. Connect repository on [Render Dashboard](https://dashboard.render.com)
3. Render will auto-detect `render.yaml` and configure the service
4. Add environment variables in Render's dashboard
5. Deploy — the health check at `/health` confirms readiness

### Deploy Frontend to Vercel

1. Import the `frontend/` directory on [Vercel](https://vercel.com)
2. Set build command: `npm run build`
3. Set output directory: `dist`
4. Add `VITE_API_URL` environment variable pointing to your Render backend URL
5. Deploy

### Render Blueprint (`render.yaml`)

The included `render.yaml` defines the backend service configuration:

```yaml
services:
  - type: web
    name: legal-ai-backend
    runtime: docker
    plan: free
    dockerfilePath: ./Dockerfile
    healthCheckPath: /health
    envVars:
      - key: GROQ_API_KEY
        sync: false
      - key: QDRANT_URL
        sync: false
      # ... (see render.yaml for full list)
```

---

## Troubleshooting

### Backend won't start — Pydantic validation error

**Cause:** Missing required environment variables.

```bash
# Check which variables are missing
cat .env | grep -E "GROQ_API_KEY|QDRANT_URL|QDRANT_API_KEY|REDIS_URL|SUPABASE_URL"
```

All five are required. See `.env.example` for the full template.

### 401 Unauthorized on `/api/query`

**Cause:** Missing or expired JWT token.

The `/api/query` and `/api/session/latest` endpoints require a valid Supabase JWT in the `Authorization: Bearer <token>` header. Use the frontend's auth flow, or obtain a token from your Supabase project for testing.

### CORS errors in browser

**Cause:** Frontend origin not in `CORS_ORIGINS`.

```bash
# Add your frontend URL
CORS_ORIGINS=http://localhost:5173,https://your-app.vercel.app
```

### Groq rate limit errors (429)

**Cause:** Exceeded Groq free tier limits.

**Solutions:**
1. Add more API keys: set `GROQ_API_KEY_2`, `GROQ_API_KEY_3`, etc. — the app auto-rotates
2. Switch to a smaller model: `LLM_MODEL=llama-3.1-8b-instant`
3. Upgrade to Groq paid tier

### Slow responses (> 5 seconds)

**Possible causes:**
- Render free tier cold start (~50s after 15min idle). Send a `/health` ping first
- HuggingFace Inference API cold start. First request loads the model (~10s)
- Reduce `DENSE_CANDIDATES` and `BM25_CANDIDATES` from 25 to 15
- Reduce `DEFAULT_TOP_K` from 8 to 5

### Qdrant connection failures

```bash
# Verify Qdrant is reachable
curl https://your-cluster.aws.cloud.qdrant.io/collections -H "api-key: your_key"
```

Check that `QDRANT_URL` includes `https://` and `QDRANT_API_KEY` is correct.

---

## Contributing

### Setup

```bash
# Fork and clone
git clone https://github.com/your-username/Legal_AI_Chatbot.git
cd Legal_AI_Chatbot

# Install all dependencies (including dev tools)
pip install -r requirements.base.txt
pip install -r requirements.dev.txt

# Run tests
pytest tests/ -v

# Format code
black app/ scripts/

# Type check
mypy app/
```

### Code Standards

- **Python:** PEP 8, formatted with Black
- **TypeScript:** ESLint rules from `.eslintrc.cjs`
- **Commits:** Conventional commits (`feat:`, `fix:`, `docs:`, `refactor:`)
- **Tests:** Add tests for new features in `tests/`

---

## Roadmap

- [ ] Streaming responses (Groq `stream=True` → frontend SSE)
- [ ] BNS/BNSS/BSA migration (new Indian criminal codes replacing IPC)
- [ ] Cross-encoder re-ranking between retrieval and LLM generation
- [ ] Conversation export (PDF/JSON)
- [ ] Additional legal datasets (CrPC, CPC)

---

## License

MIT License — see [LICENSE](LICENSE) for details.

---

## Acknowledgments

- **IPC Data** — Government of India
- **Embedding Model** — [intfloat/multilingual-e5-base](https://huggingface.co/intfloat/multilingual-e5-base) (HuggingFace)
- **LLM** — [Groq](https://groq.com/) (Llama 3 by Meta)
- **Vector Database** — [Qdrant](https://qdrant.tech/)
- **Icons** — [Lucide](https://lucide.dev/)
- **Auth** — [Supabase](https://supabase.com/)

---

**Built by [Suraj Doifode](https://github.com/SurajD45)**
