# PROJECT CONTEXT — Legal AI Assistant

> This file provides full context for any AI tool or developer to understand this project instantly.
> Last updated: 2026-05-30

---

## 1. What This Project Is

**Legal AI Assistant** is a full-stack Retrieval-Augmented Generation (RAG) chatbot that answers questions about the **Indian Penal Code (IPC)**. Users ask legal questions in natural language, the system retrieves relevant IPC sections from a vector database, and an LLM generates a structured legal answer grounded in those sections.

### Key Capabilities
- Natural language legal Q&A over 500+ IPC sections
- Hybrid retrieval: regex-based section detection + semantic vector search
- Multi-user chat sessions with persistent conversation history
- Rate limiting, structured logging, production error handling
- Evaluation framework with 100 test queries measuring retrieval quality

---

## 2. Tech Stack

| Layer | Technology | Purpose |
|-------|-----------|---------|
| **Backend** | Python 3.11 + FastAPI | REST API server |
| **Frontend** | React 18 + TypeScript + Vite | Chat UI |
| **LLM Inference** | Groq API (`llama-3.3-70b-versatile`) | Answer generation via LPU |
| **Vector Database** | Qdrant Cloud | IPC section storage + semantic search |
| **Embeddings** | HuggingFace Inference API (`intfloat/multilingual-e5-base`) | Query → vector embedding |
| **Chat History** | Upstash Redis (serverless) | Session persistence, multi-user support |
| **Styling** | TailwindCSS 3 | Frontend styling |
| **Backend Hosting** | Render.com (free tier) | Docker-based deployment |
| **Frontend Hosting** | Vercel (free tier) | Static site CDN |

---

## 3. Architecture & Data Flow

```
User Query
    │
    ▼
┌─────────────────────────────────────────────┐
│  Frontend (React + Vite on Vercel)          │
│  - Chat UI with message history             │
│  - Sends POST /api/query with user_id +     │
│    query + optional session_id              │
└────────────────────┬────────────────────────┘
                     │ HTTPS
                     ▼
┌─────────────────────────────────────────────┐
│  Backend (FastAPI on Render)                │
│                                             │
│  1. Chat History Manager (Upstash Redis)    │
│     - Creates/restores session              │
│     - Loads conversation history            │
│                                             │
│  2. Document Retriever (Qdrant + HF API)    │
│     a. Regex: detect "Section 302" patterns │
│        → exact match via Qdrant scroll      │
│     b. Fallback: semantic search            │
│        → HF API embeds query → Qdrant ANN   │
│     Returns: List[RetrievedDocument]        │
│                                             │
│  3. LLM Chain (Groq API)                    │
│     - Builds system prompt (IPC specialist) │
│     - Injects retrieved context + query     │
│     - Calls Groq chat.completions.create()  │
│     - Returns structured legal answer       │
│                                             │
│  4. Saves user msg + assistant msg to Redis │
│  5. Returns ChatResponse to frontend        │
└─────────────────────────────────────────────┘
```

---

## 4. Project File Structure & Purpose

```
legal-ai-assistant/
│
├── app/                          # Backend application
│   ├── __init__.py               # Package init, version = "1.0.0"
│   ├── config.py                 # Pydantic Settings — all env vars loaded here
│   ├── main.py                   # FastAPI app, lifespan, explicit CORS, error handlers
│   ├── models.py                 # Pydantic models: ChatRequest, ChatResponse, etc.
│   ├── dependencies.py           # SlowAPI rate limiter setup
│   │
│   ├── api/                      # API route handlers
│   │   ├── __init__.py           # Route module exports
│   │   ├── health.py             # GET /health (Qdrant + LLM + embedding status), GET /
│   │   └── chat.py               # POST /api/query (main RAG endpoint),
│   │                             #   GET /api/session/latest (restore session)
│   │
│   ├── core/                     # Business logic layer
│   │   ├── __init__.py           # Exports: get_retriever, get_llm_chain, get_history_manager
│   │   ├── retriever.py          # DocumentRetriever: Qdrant + HF embedding API
│   │   │                         #   - hybrid_search(): section regex → exact match → semantic
│   │   │                         #   - _get_embedding(): calls HF Inference API
│   │   ├── llm_chain.py          # LLMChain: Groq SDK for chat completions
│   │   │                         #   - generate_answer(): builds prompt + calls Groq API
│   │   └── chat_history.py       # ChatHistoryManager: Redis/Upstash session store
│   │                             #   - create_session(), get_history(), add_message()
│   │                             #   - Multi-user with ownership enforcement
│   │                             #   - TTL-based session expiry (24h)
│   │
│   └── utils/                    # Cross-cutting utilities
│       ├── __init__.py           # Re-exports all utilities
│       ├── logger.py             # structlog config (JSON in prod, console in dev)
│       └── exceptions.py         # Custom exceptions: LLMError, RetrievalError, etc.
│
├── frontend/                     # React frontend (deploys to Vercel)
│   ├── src/
│   │   ├── App.tsx               # Main app component — chat interface
│   │   ├── main.tsx              # React entry point
│   │   ├── index.css             # TailwindCSS imports
│   │   ├── components/
│   │   │   ├── ChatInput.tsx     # Message input box
│   │   │   ├── ChatMessage.tsx   # Individual message bubble
│   │   │   ├── Welcome.tsx       # Landing/welcome screen
│   │   │   └── Auth.tsx          # Supabase auth component
│   │   ├── hooks/
│   │   │   └── useChat.ts        # Chat state management hook
│   │   ├── services/
│   │   │   ├── api.ts            # Axios API client (POST /api/query)
│   │   │   ├── auth.ts           # Auth helper functions
│   │   │   └── supabase.ts       # Supabase client init
│   │   └── types/
│   │       └── index.ts          # TypeScript type definitions
│   ├── package.json
│   ├── vite.config.ts            # Dev proxy to localhost:8000
│   ├── vercel.json               # Vercel build config
│   └── tailwind.config.js
│
├── evaluation/                   # Quality measurement framework
│   ├── test_queries.json         # 100 curated test cases (7 categories)
│   ├── evaluate_retrieval.py     # Recall@K, MRR, regex accuracy metrics
│   └── evaluate_answers.py       # Section coverage, format compliance, hallucination detection
│
├── scripts/
│   ├── index_data.py             # Indexes IPC JSON → Qdrant Cloud (uses SentenceTransformer)
│   └── archive/
│       └── generate_ipc_json.py  # Archived: IPC DOCX → JSON converter (for future BNS migration)
│
├── data/
│   └── ipc_clean.json            # 500+ IPC sections (JSON, ~543KB)
│
├── tests/
│   ├── test_api.py               # API endpoint tests
│   └── test_retriever.py         # Retriever unit tests
│
├── .env.example                  # Environment variable template
├── .gitignore
├── .dockerignore
├── Dockerfile                    # Python 3.11-slim, production-only deps
├── render.yaml                   # Render.com deployment blueprint
├── requirements.base.txt         # Production dependencies (incl. groq SDK)
├── requirements.dev.txt          # Dev/test dependencies (pytest, black, mypy)
├── PROJECT_CONTEXT.md            # This file
└── README.md
```

---

## 5. Environment Variables

All loaded via `app/config.py` using Pydantic Settings with `.env` file support.

| Variable | Required | Description | Example |
|----------|----------|-------------|---------|
| `GROQ_API_KEY` | **Yes** | Groq API key for LLM inference | `gsk_Mw...` |
| `QDRANT_URL` | **Yes** | Qdrant Cloud cluster URL | `https://xxx.aws.cloud.qdrant.io` |
| `QDRANT_API_KEY` | **Yes** | Qdrant Cloud API key | `eyJhbG...` |
| `QDRANT_COLLECTION_NAME` | No | Collection name (default: `ipc_legal_docs`) | `ipc_legal_docs` |
| `REDIS_URL` | **Yes** | Upstash Redis URL (TLS) | `rediss://default:xxx@host:6379` |
| `HF_API_TOKEN` | No | HuggingFace token (optional, for rate limits) | `hf_xxx` |
| `ENVIRONMENT` | No | `development` / `production` (default: `development`) | `production` |
| `HOST` | No | Bind host (default: `0.0.0.0`) | `0.0.0.0` |
| `PORT` | No | Bind port (default: `8000`) | `8000` |
| `LOG_LEVEL` | No | Logging level (default: `INFO`) | `INFO` |
| `CORS_ORIGINS` | No | Comma-separated allowed origins | `https://app.vercel.app` |
| `LLM_MODEL` | No | Groq model ID (default: `llama-3.3-70b-versatile`) | `llama-3.3-70b-versatile` |
| `EMBEDDING_MODEL` | No | HF model (default: `intfloat/multilingual-e5-base`) | |
| `EMBEDDING_DIMENSION` | No | Vector dimension (default: `768`) | `768` |
| `DEFAULT_TOP_K` | No | Results per search (default: `5`) | `5` |
| `MAX_CONTEXT_LENGTH` | No | Max chars to LLM (default: `4000`) | `4000` |
| `RATE_LIMIT_PER_MINUTE` | No | API rate limit (default: `30`) | `30` |

---

## 6. API Endpoints

| Method | Path | Description | Auth |
|--------|------|-------------|------|
| `GET` | `/` | Root — project info + links | None |
| `GET` | `/health` | Health — Qdrant, embedding, LLM status | None |
| `POST` | `/api/query` | **Main** — send query, get RAG answer | Rate limited |
| `GET` | `/api/session/latest?user_id=xxx` | Restore latest session | None |

### POST `/api/query` — Request
```json
{
  "user_id": "user-001",
  "query": "What is Section 302 of IPC?",
  "session_id": null
}
```

### POST `/api/query` — Response
```json
{
  "answer": "RELEVANT PROVISIONS:\n- Section 302: Punishment for murder...",
  "sources": [
    { "section": "302", "title": "Punishment for murder", "text": "...", "score": 1.0 }
  ],
  "session_id": "uuid-here",
  "query": "What is Section 302 of IPC?"
}
```

---

## 7. Key Design Decisions

1. **Hybrid Retrieval**: Regex detects explicit section references (e.g., "Section 302", "धारा 420") for exact match via Qdrant scroll filter. Falls back to semantic ANN search. 100% accuracy on section lookups while handling natural language.

2. **HF Inference API for Embeddings**: Avoids shipping 1.1GB SentenceTransformer model in Docker image. Image goes from ~3GB to ~200MB. Trade-off: ~200ms latency per embedding call.

3. **Groq API for LLM**: LPU-accelerated inference. `llama-3.3-70b-versatile` provides strong legal reasoning. Official Python SDK with OpenAI-compatible interface. Free tier sufficient for demo.

4. **Upstash Serverless Redis**: Wire-compatible with standard Redis — zero code changes needed. Free tier: 500K commands/mo, 256MB. No self-hosted Redis server management.

5. **Explicit CORS**: Uses parsed origins from `CORS_ORIGINS` env var instead of wildcard `*`. Looks professional, prevents CSRF in production.

6. **Optional HF Token**: `HF_API_TOKEN` defaults to `None`. Public HF models work without auth, but token available for rate-limited endpoints in future.

7. **Singleton Pattern**: `get_retriever()`, `get_llm_chain()`, `get_history_manager()` use `lru_cache` or global instance. Single connection per service throughout app lifecycle.

---

## 8. IPC Data Schema

`data/ipc_clean.json` — array of IPC sections:

```json
{
  "section_number": "302",
  "title": "Punishment for murder",
  "chapter": "XVI",
  "chapter_title": "Of Offences Affecting The Human Body",
  "text": "Whoever commits murder shall be punished with death, or imprisonment for life...",
  "source": "The Indian Penal Code"
}
```

**Qdrant Collection**: `ipc_legal_docs`
- Vector size: 768 (multilingual-e5-base)
- Distance: Cosine
- Payload index: `section_number` (KEYWORD) — required for exact match filtering

---

## 9. Evaluation Framework

Located in `evaluation/` — measures retrieval quality and answer correctness.

### Test Dataset
- `test_queries.json`: 100 queries across 7 categories
  - `exact_match` (10): "What is Section 302?"
  - `exact_match_hindi` (3): "धारा 302 क्या है?"
  - `multi_section` (5): "Difference between 302 and 304"
  - `semantic` (37): "punishment for theft in India"
  - `semantic_complex` (13): "my neighbour broke into my house at night"
  - `semantic_hindi` (4): "chori ki saja kya hai?"
  - `edge_case` (8): irrelevant/out-of-scope queries

### Retrieval Metrics (`evaluate_retrieval.py`)
- **Recall@5**: fraction of expected sections in top 5 results
- **Recall@10**: fraction of expected sections in top 10 results
- **MRR (Mean Reciprocal Rank)**: how high is the correct result ranked
- **Regex Detection Accuracy**: section pattern matching success rate

### Answer Quality Metrics (`evaluate_answers.py`)
- **Section Coverage**: expected sections mentioned in generated answer
- **Format Compliance**: structured format (PROVISIONS / ANALYSIS / PUNISHMENT)
- **Hallucination Detection**: sections in answer not in retrieved context
- **Latency**: retrieval + generation time breakdown

---

## 10. Deployment Architecture

```
┌─────────────┐     HTTPS      ┌──────────────┐
│   Vercel    │ ──────────────► │   Render     │
│  (Frontend) │                 │  (Backend)   │
│  React+Vite │                 │  FastAPI     │
└─────────────┘                 └──────┬───────┘
                                       │
                        ┌──────────────┼──────────────┐
                        │              │              │
                        ▼              ▼              ▼
                 ┌────────────┐ ┌───────────┐ ┌────────────┐
                 │ Groq API   │ │  Qdrant   │ │  Upstash   │
                 │ (LLM)      │ │  Cloud    │ │  Redis     │
                 │ Free tier  │ │  (VecDB)  │ │  (Sessions)│
                 └────────────┘ └───────────┘ └────────────┘
```

| Service | URL Pattern | Cost |
|---------|------------|------|
| Frontend | `your-app.vercel.app` | Free |
| Backend | `your-app.onrender.com` | Free (sleeps after 15min idle) |
| Groq | `api.groq.com` | Free tier |
| Qdrant | `xxx.aws.cloud.qdrant.io` | Free tier (1GB) |
| Upstash | `xxx.upstash.io` | Free (500K cmds/mo) |

### Deployment Files
- `Dockerfile` — Python 3.11-slim, copies only `app/` and `data/`
- `render.yaml` — Render Blueprint for one-click backend deploy
- `frontend/vercel.json` — Vercel build config for frontend

---

## 11. Future Roadmap

- **Cross-Encoder Re-ranking**: Add `app/core/reranker.py` using `cross-encoder/ms-marco-MiniLM-L-6-v2` via HF API between retriever and LLM for better answer quality on ambiguous queries.
- **BNS/BNSS/BSA Migration**: Use archived `scripts/archive/generate_ipc_json.py` as template to preprocess new Bharatiya Nyaya Sanhita data.
- **Streaming Responses**: Enable `stream=True` on Groq SDK for real-time token streaming to frontend.
