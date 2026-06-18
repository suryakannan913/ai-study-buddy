# AI Study Buddy

A free, portfolio-ready AI tutor. Upload your study materials, ask questions, and
get patient, personalized explanations grounded in your own notes.

**Stack:** Next.js (frontend) · FastAPI (backend) · Groq / Llama 3 (LLM) ·
Qdrant (vector search) · Postgres (data) · `fastembed` (local embeddings).

> Status: **Phase 1 — backend foundation** (FastAPI + Postgres + Groq + `/chat`).
> Phase 2 adds PDF upload + RAG; Phase 3 adds auth, dashboard, and deploy.

## Backend — run locally

### 1. Start Postgres + Qdrant

```bash
docker compose up -d
```

### 2. Set up the Python env

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env        # then add your GROQ_API_KEY
```

Get a free Groq API key at <https://console.groq.com>.

### 3. Run the API

```bash
uvicorn main:app --reload
```

- API: <http://localhost:8000>
- Interactive docs: <http://localhost:8000/docs>
- Health check: <http://localhost:8000/health>

### Try the chat endpoint

```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Explain big-O notation simply."}'
```

The response includes a `conversation_id` — pass it back on the next request to
continue the same conversation.

## Notes

- **Auth is deferred.** Everything runs as a single dev user until Firebase is
  added in Phase 3.
- Model id is set via `GROQ_MODEL` in `.env`. Verify current ids at
  <https://console.groq.com/docs/models> (e.g. `llama-3.3-70b-versatile`,
  `llama-3.1-8b-instant`).
- Tables auto-create on startup for dev; production should use migrations.
