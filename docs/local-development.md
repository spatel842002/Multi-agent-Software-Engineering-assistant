# Local development

## Option A: everything in Docker (fastest to a working demo)

```bash
git clone https://github.com/spatel842002/Multi-agent-Software-Engineering-assistant.git
cd Multi-agent-Software-Engineering-assistant
cp .env.example .env   # only if a default port below conflicts on your machine
docker compose up -d --build
docker compose exec ollama ollama pull qwen2.5-coder:1.5b
docker compose exec ollama ollama pull nomic-embed-text
docker compose exec backend alembic upgrade head
```

Frontend at http://localhost:5173, API at http://localhost:8000/docs.

## Option B: backend outside Docker, infra in Docker (for active backend work)

```bash
docker compose up -d postgres redis qdrant ollama minio mlflow
docker compose exec ollama ollama pull qwen2.5-coder:1.5b
docker compose exec ollama ollama pull nomic-embed-text

cd backend
python -m venv .venv && . .venv/Scripts/activate   # or source .venv/bin/activate on macOS/Linux
pip install -r requirements-dev.txt
cp .env.example .env
# Edit .env: DATABASE_URL/REDIS_URL/QDRANT_URL/OLLAMA_BASE_URL should point at
# localhost (Docker Compose publishes each service's port to the host), and
# generate a real JWT_SECRET_KEY: openssl rand -hex 32
alembic upgrade head
uvicorn app.main:app --reload
```

In a second terminal, run the Celery worker (ingestion needs it):

```bash
cd backend && . .venv/Scripts/activate
celery -A app.workers.celery_app worker --loglevel=INFO --pool=solo   # --pool=solo is Windows-friendly; omit on Linux/macOS
```

## Option C: frontend outside Docker (for active frontend work)

```bash
cd frontend
npm ci
npm run dev
```

Vite's dev server proxies `/api/*` to `http://localhost:8000` by default
(see `vite.config.ts`); override with `VITE_API_PROXY_TARGET` if your
backend runs elsewhere.

## Running the fast test suites (no Docker required)

```bash
cd backend && pytest                      # SQLite-backed, no external services
cd frontend && npm test
```

## Running the full integration/e2e suites (Docker required)

```bash
docker compose up -d --build
docker compose exec ollama ollama pull qwen2.5-coder:1.5b
docker compose exec ollama ollama pull nomic-embed-text

cd backend && pytest -m integration       # needs Postgres/Redis/Qdrant/Ollama reachable on localhost
cd frontend && npm run test:e2e           # needs the full stack up at http://localhost:5173
```

See [docs/testing.md](testing.md) for what each suite actually covers.

## Common gotchas

- **Ports already in use**: copy `.env.example` to `.env` at the repo root
  and override the conflicting `*_PORT` variable(s) — every service's host
  port is overridable this way (see `docker-compose.yml`).
- **First LLM/embedding call fails or times out**: you likely haven't run
  the two `ollama pull` commands above. `docker compose exec ollama ollama list`
  shows what's currently pulled.
- **Alembic can't connect**: migrations read `DATABASE_URL` from your
  environment (`backend/.env` locally, `backend/.env.docker` in Compose) —
  confirm Postgres is up (`docker compose ps postgres`) first.
- More: [docs/troubleshooting.md](troubleshooting.md).
