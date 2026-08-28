# Environment variables

Read from `backend/.env` (local dev) or `backend/.env.docker` (Docker
Compose), validated at startup by `app/core/config.py`'s `Settings` model —
a missing required variable or a wrong URL scheme fails fast with an
actionable message rather than surfacing deep inside a request handler.
`backend/.env.example` documents the same list with safe local defaults.

| Variable | Required | Default | Notes |
|---|---|---|---|
| `ENVIRONMENT` | no | `development` | `development` \| `test` \| `production`. `test` switches the rate limiter to in-process storage instead of Redis. |
| `LOG_LEVEL` | no | `INFO` | Passed to Python's `logging` and `structlog`. |
| `API_PREFIX` | no | `/api/v1` | |
| `JWT_SECRET_KEY` | **yes** | — | HMAC signing secret. Generate with `openssl rand -hex 32`. Never reuse the value in `.env.docker` (a clearly-marked local-only placeholder) for anything real. |
| `JWT_ALGORITHM` | no | `HS256` | |
| `ACCESS_TOKEN_TTL_MINUTES` | no | `15` | |
| `REFRESH_TOKEN_TTL_DAYS` | no | `14` | |
| `DATABASE_URL` | **yes** | — | Async SQLAlchemy URL, e.g. `postgresql+asyncpg://user:pass@host:5432/db`. Must use an async driver — a plain `postgresql://` URL is rejected at startup with an explanatory error. |
| `REDIS_URL` | no | `redis://localhost:6379/0` | Cache, rate limiting, Celery broker/result backend (unless overridden below). |
| `CELERY_BROKER_URL` | no | falls back to `REDIS_URL` | |
| `CELERY_RESULT_BACKEND` | no | falls back to `REDIS_URL` | |
| `QDRANT_URL` | no | `http://localhost:6333` | |
| `QDRANT_API_KEY` | no | unset | Set when using Qdrant Cloud or an auth-enabled instance. |
| `QDRANT_COLLECTION` | no | `code_chunks` | |
| `LLM_PROVIDER` | no | `ollama` | `ollama` (real, local) or `fake` (deterministic, tests only — also switches the vector store to an in-process fake, see `services/retrieval/vector_store.py`). |
| `OLLAMA_BASE_URL` | no | `http://localhost:11434` | |
| `OLLAMA_CHAT_MODEL` | no | `qwen2.5-coder:1.5b` | Must be pulled first: `ollama pull qwen2.5-coder:1.5b`. |
| `OLLAMA_EMBEDDING_MODEL` | no | `nomic-embed-text` | Must be pulled first. |
| `EMBEDDING_DIMENSIONS` | no | `768` | Must match the embedding model's actual output size, and match the Qdrant collection's configured vector size (the collection is created with this size on first use). |
| `S3_ENDPOINT_URL` | no | `http://localhost:9000` | MinIO locally. Unset (leave blank) to use real AWS S3. |
| `S3_ACCESS_KEY` / `S3_SECRET_KEY` | no | `minioadmin` / `minioadmin` | MinIO's well-known local-dev default credentials — never use these against a real S3 bucket. |
| `S3_BUCKET_REPOSITORIES` | no | `masea-repositories` | |
| `S3_REGION` | no | `us-east-1` | |
| `MLFLOW_TRACKING_URI` | no | `file:./mlruns` | Points at a real `mlflow server` in Docker Compose (`http://mlflow:5000`); `evals/run_evals.py` overrides this to a temp sqlite store by default (see its docstring — a plain `file:` URI hits MLflow 3.x's filesystem-store deprecation guard when used directly, not through a server). |
| `MLFLOW_EXPERIMENT_NAME` | no | `masea-evals` | |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | no | unset | Leave unset to log spans to console instead of exporting via OTLP. |
| `OTEL_SERVICE_NAME` | no | `masea-backend` | |
| `ENABLE_PROMETHEUS` | no | `true` | |
| `RATE_LIMIT_DEFAULT` | no | `60/minute` | slowapi rate-limit string syntax. |
| `RATE_LIMIT_AUTH` | no | `10/minute` | Applied to `/auth/register` and `/auth/login`. |
| `INGESTION_MAX_REPO_SIZE_MB` | no | `500` | Clone is rejected after exceeding this. |
| `INGESTION_CLONE_TIMEOUT_SECONDS` | no | `120` | Hard subprocess timeout on `git clone`. |
| `PATCH_SANDBOX_TIMEOUT_SECONDS` | no | `60` | Hard subprocess timeout on the approved patch's test command. |
| `WORKSPACE_ROOT` | no | `./.workspace` | Where cloned repos and sandbox copies live on disk. `/app/.workspace` in Docker (a named volume). |
| `CORS_ALLOW_ORIGINS` | no | `["http://localhost:5173"]` | JSON array string (pydantic-settings parses list/tuple-typed env vars as JSON). |

## Frontend

| Variable | Where | Notes |
|---|---|---|
| `VITE_API_PROXY_TARGET` | `frontend/vite.config.ts`, dev server only | Where Vite's dev server proxies `/api/*`. Defaults to `http://localhost:8000`. Not used in the production Docker image — there, nginx proxies `/api/` to the `backend` service by container DNS name (`frontend/nginx.conf`). |
| `E2E_BASE_URL` | `frontend/playwright.config.ts` | Base URL the e2e suite drives a browser against. Defaults to `http://localhost:5173`. |

## Root-level (Docker Compose host-port overrides only)

See `.env.example` at the repo root: `POSTGRES_PORT`, `REDIS_PORT`,
`QDRANT_PORT`, `OLLAMA_PORT`, `MINIO_API_PORT`, `MINIO_CONSOLE_PORT`,
`MLFLOW_PORT`, `BACKEND_PORT`, `FRONTEND_PORT`, `PROMETHEUS_PORT`,
`GRAFANA_PORT` — only needed if a default host port is already taken on
your machine. These do not affect in-cluster/inter-container networking
(services always talk to each other over their container's real port).
