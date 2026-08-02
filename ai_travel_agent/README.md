# Wanderline — AI Travel Concierge

A local-first travel chat assistant with persistent memory, built on:
- **Backend:** FastAPI + mem0 (fact extraction/recall) + Qdrant (vector store)
- **LLM:** Ollama, running fully on your machine (`llama3.2` for chat, `nomic-embed-text` for embeddings)
- **Frontend:** plain HTML/CSS/JS, no build step

```
travel_agent/
├── backend/          # FastAPI app
├── frontend/          # static HTML/CSS/JS
└── docker-compose.yml
```

---

## Prerequisites (both run modes)

Ollama must be running on your **host machine** — it is not containerized:

```bash
ollama serve                     # if not already running
ollama pull llama3.2
ollama pull nomic-embed-text
```

---

## Option A — Docker Compose (recommended)

Starts Qdrant, the backend, and the frontend together with one command.

```bash
cd travel_agent
docker compose up --build
```

- Frontend: http://localhost:5500
- Backend docs: http://localhost:8000/docs
- Qdrant: http://localhost:6333

Stop everything with `docker compose down`. Add `-v` to also wipe stored memories (`docker compose down -v`).

**Note:** the backend container reaches your host's Ollama via `host.docker.internal` — this is pre-configured in `docker-compose.yml` and works on Docker Desktop (Mac/Windows) and Linux alike.

---

## Option B — Run manually (no Docker)

**1. Start Qdrant** (still easiest via Docker, even in "manual" mode):
```bash
docker run -p 6333:6333 qdrant/qdrant
```

**2. Backend:**
```bash
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python3 -m uvicorn app.main:app --reload --port 8000
```

**3. Frontend** (separate terminal):
```bash
cd frontend
python3 -m http.server 5500
```

Open http://localhost:5500.

---

## Configuration

All backend settings are in `backend/app/config.py`, overridable via `backend/.env` (manual mode) or environment variables in `docker-compose.yml` (Docker mode). See `backend/.env.example` for the full list.

## Troubleshooting

- **"Failed to fetch" in the UI** — check the backend is actually running (`curl http://localhost:8000/api/health`) and that you opened the frontend via `http://localhost:5500`, not by double-clicking `index.html`.
- **404 on `/api/chat/stream`** — backend files are out of sync; make sure `routers/chat.py`, `services/chat_service.py`, and `services/llm_service.py` are all on the same version.
- **Empty/slow replies** — confirm `ollama list` shows both `llama3.2` and `nomic-embed-text` pulled, and that `ollama serve` is running.