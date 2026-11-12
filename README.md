# GrandPilot

AI-powered policy advisory platform that helps Vietnamese businesses discover government support programs, check eligibility, and get grounded answers backed by real legal citations.

## Overview

GrandPilot combines a **deterministic eligibility engine** with **hybrid RAG** to answer two questions:

- *"What policies exist for businesses like mine?"* — semantic search over legal documents, citations included
- *"Am I actually eligible?"* — rule-based evaluation against 40+ company profile fields, explained in plain language by an LLM

The system is built as three independent microservices:

```
┌─────────────────────────────────────────────────────────────┐
│                        Frontend (React)                      │
│              Lookup Mode          Advisory Mode              │
└────────────────────────┬────────────────────────────────────┘
                         │ NDJSON stream
          ┌──────────────▼──────────────┐
          │     Server B — Retrieval    │  :8001
          │  Hybrid RAG · Query Rewrite │
          │  Session Memory · Streaming │
          └──────┬───────────┬──────────┘
                 │           │ eligibility check
   ┌─────────────▼──┐  ┌─────▼────────────────┐
   │  Server A — API│  │  Server C — Eligibility│  :8002
   │  Company Mgmt  │  │  Rule Engine · Ranking │
   └────────────────┘  └────────────────────────┘
          │
   ┌──────▼──────────────┐   ┌──────────────┐   ┌───────┐
   │  MongoDB Atlas      │   │   Pinecone   │   │ Redis │
   │  legal_documents    │   │  legal_units │   │ chat  │
   │  legal_units        │   │  (vectors)   │   │ memory│
   │  policies           │   └──────────────┘   └───────┘
   └─────────────────────┘
```

## Features

**Hybrid Legal Retrieval**
- Reciprocal Rank Fusion (RRF) merges Pinecone dense vector search + in-memory BM25 sparse retrieval
- Cross-encoder reranking via `bge-reranker-v2-m3` on top-N candidates
- Intelligent routing: exact legal citation (`Điều 5, Khoản 2`) → direct MongoDB lookup; semantic query → hybrid search

**Deterministic Eligibility Engine**
- Operator-based condition graphs (`==`, `in`, `>=`, `contains`, `exists`, ...) evaluate company profiles against policy rules
- LLM (GLM-5.2) is used only to explain decisions in plain language — it never alters eligibility outcomes
- Fact derivation pipeline: normalizes raw company data into 40+ canonical facts with version tracking

**Streaming Multi-Turn Chat**
- NDJSON/SSE protocol streams `legal_units → sources → advisory_result → message` events incrementally
- Redis-backed session memory (last 20 messages) with LLM-powered query rewriting (DeepSeek-V4-Flash) to resolve follow-up pronouns
- Graceful fallback: advisory mode degrades to lookup-only if Server C is unavailable

**Document Ingestion Pipeline**
- Tesseract OCR + Vietnamese language pack for PDF-to-text extraction
- Deduplication by document version, batch Pinecone upsert, JSONL intermediate format for offline testing

## Tech Stack

| Layer | Technology |
|---|---|
| Backend | Python 3.11, FastAPI, Uvicorn, Pydantic v2 |
| Frontend | React 18, TypeScript, Vite, Tailwind CSS |
| Vector DB | Pinecone (dense) + BM25 in-memory (sparse) |
| Document DB | MongoDB Atlas |
| Session Store | Redis 7 (in-memory fallback for local dev) |
| Embeddings | Jina AI — `jina-embeddings-v3` (dense), `jina-reranker-v2-base-multilingual` (rerank) |
| LLM | Groq — `llama-3.3-70b-versatile` (answer, rewrite, advisory, eligibility) |
| OCR | Tesseract + PyTesseract + Pillow |
| Infrastructure | Docker Compose, Nginx, Cloudflare Workers |

## Project Structure

```
GrandPilot/
├── server-a-ingestion/   # Document ingestion API + OCR pipeline
├── server-b-retrieval/   # Chat API — hybrid RAG, streaming, session memory
├── server-c-eligibility/ # Eligibility engine — rule evaluation + ranking
├── frontend/             # React SPA (Vite + TypeScript + Tailwind)
├── shared/               # SQLite policy DB + golden policy list
├── cloudflare-proxy/     # Edge proxy for FPT.AI API (CORS)
└── docker-compose.yml
```

Each service is independently deployable with its own `Dockerfile` and `requirements.txt`.

## Getting Started

### Prerequisites

- Python 3.11+
- Node.js 20+
- Docker + Docker Compose (for containerized setup)

### Environment Variables

Copy `.env.example` to `.env` in the project root and fill in:

```env
# MongoDB
MONGODB_URI=mongodb+srv://...
MONGODB_DB=grantpilot

# Pinecone
PINECONE_API_KEY=...
PINECONE_INDEX_HOST=...
PINECONE_INDEX_NAME=...
PINECONE_NAMESPACE=legal_units

# Embeddings + Reranker (Jina AI — https://jina.ai)
EMBEDDING_API_KEY=jina_...
EMBEDDING_MODEL=jina-embeddings-v3
RERANK_MODEL=jina-reranker-v2-base-multilingual

# LLMs (Groq — https://console.groq.com)
REWRITE_API_KEY=gsk_...
ANSWER_API_KEY=gsk_...
ANSWER_MODEL=llama-3.3-70b-versatile

# Optional tuning
LEGAL_DATA_BACKEND=mongodb        # or: jsonl (offline fallback)
SERVER_C_TIMEOUT_SECONDS=30
ELIGIBILITY_LLM_ENABLED=true
```

### Docker Compose (recommended)

```bash
docker compose up --build
```

Services start in order: Redis → Server A → Server B + Server C → Frontend.

| Service | URL |
|---|---|
| Frontend | http://localhost:8501 |
| Server B (Retrieval API) | http://localhost:8001 |
| Server A (Ingestion API) | http://localhost:8000 |

### Local Dev (without Docker)

Run each service in a separate terminal:

```bash
# Server A — Ingestion API
cd server-a-ingestion
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn api:app --reload --port 8000

# Server B — Retrieval
cd server-b-retrieval
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload --port 8001

# Server C — Eligibility
cd server-c-eligibility
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload --port 8002

# Frontend
cd frontend
npm install
npm run dev       # http://localhost:5173
```

Vite's dev proxy forwards `/api/*` → `http://localhost:8001` automatically.

### Data Ingestion (one-time)

To ingest PDFs into MongoDB + Pinecone, uncomment `server-a-ingestion` in `docker-compose.yml` and run:

```bash
docker compose run --rm server-a-ingestion python ingest_mongodb.py
```

Or locally:

```bash
cd server-a-ingestion
python ingest_mongodb.py
```

## API Reference

### Server B — Chat (POST `/chat`)

Streams NDJSON. Each line is a JSON event:

| Event type | Description |
|---|---|
| `started` | Request ID, conversation ID, mode |
| `legal_units` | Retrieved source document fragments |
| `sources` | Citation metadata for UI rendering |
| `advisory_result` | Policy eligibility + explanations (advisory mode) |
| `message` | LLM-generated answer (streamed token by token) |
| `warning` | Non-fatal issues (e.g. eligibility service timeout) |

**Request body:**
```json
{
  "message": "Doanh nghiệp tôi có được hỗ trợ lãi suất không?",
  "conversation_id": "uuid",
  "mode": "advisory",
  "company_email": "user@example.com"
}
```

### Server C — Eligibility (POST `/evaluate`)

```json
{
  "company": { ... },
  "policy_ids": ["POL-001", "POL-002"]
}
```

Returns eligibility verdicts, missing fields, and legal unit evidence for each policy.

## Testing

Each service has its own test suite:

```bash
# Server A
cd server-a-ingestion && python -m pytest

# Server B
cd server-b-retrieval && python -m pytest tests/

# Server C
cd server-c-eligibility && python -m pytest
```

## Architecture Notes

- **No LLM on the critical path for eligibility**: rule engine runs pure Python logic; LLM only post-processes the verdict into a human-readable explanation.
- **Fallback chain**: Pinecone → BM25 → JSONL; Redis session memory → in-memory dict. The system stays operational without any external dependency.
- **Vietnamese-first NLP**: Multilingual models (Jina embeddings, Llama 3.3) with strong Vietnamese support. Unicode NFC normalization and diacritic-aware regex are applied throughout the legal document pipeline.
- **Multi-provider LLM**: Each role (embedding, reranking, query rewrite, answer generation) can use a different provider. Swap providers by changing env vars — no code changes needed.
- **Stateless services**: All three backends are horizontally scalable. Redis is the only shared state; it can be replaced with a Redis cluster for production scale.
