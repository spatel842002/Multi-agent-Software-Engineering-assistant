# Third-Party Notices

This project's own code is MIT-licensed (see [LICENSE](LICENSE)). It depends
on the open-source packages below. This lists direct dependencies and their
license identifiers; run the commands at the bottom to generate a full
transitive report at any time (transitive dependency sets change as
dependencies are updated, so a static full list here would go stale).

## Backend (Python)

| Package | License |
|---|---|
| fastapi | MIT |
| uvicorn | BSD-3-Clause |
| pydantic / pydantic-settings | MIT |
| sqlalchemy | MIT |
| alembic | MIT |
| asyncpg | Apache-2.0 |
| psycopg2-binary | LGPL-3.0-or-later (with an OpenSSL-style linking exception; see the package's own LICENSE) |
| celery | BSD-3-Clause |
| redis (redis-py) | MIT |
| qdrant-client | Apache-2.0 |
| langchain-core / langchain-text-splitters / langchain-ollama | MIT |
| httpx | BSD-3-Clause |
| argon2-cffi | MIT |
| pyjwt | MIT |
| python-multipart | Apache-2.0 |
| structlog | MIT or Apache-2.0 (dual) |
| prometheus-client | Apache-2.0 |
| opentelemetry-api / -sdk / -exporter-otlp / -instrumentation-fastapi | Apache-2.0 |
| mlflow | Apache-2.0 |
| gitpython | BSD-3-Clause |
| tenacity | Apache-2.0 |
| slowapi | MIT |
| python-dotenv | BSD-3-Clause |
| pytest / pytest-cov / pytest-asyncio | MIT |
| ruff | MIT |
| mypy | MIT |

## Frontend (npm)

| Package | License |
|---|---|
| react / react-dom | MIT |
| react-router-dom | MIT |
| tailwindcss / @tailwindcss/vite | MIT |
| vite / @vitejs/plugin-react | MIT |
| vitest / @testing-library/* | MIT |
| @playwright/test | Apache-2.0 |
| eslint / typescript-eslint / eslint-plugin-react-hooks / eslint-plugin-react-refresh | MIT |
| typescript | Apache-2.0 |
| prettier | MIT |

## Runtime services (not linked into this code, run as separate processes/containers)

| Service | License |
|---|---|
| PostgreSQL | PostgreSQL License (permissive, similar to MIT/BSD) |
| Redis | RSALv2 / SSPLv1 (Redis 7+; check the specific image tag pinned in `docker-compose.yml`) |
| Qdrant | Apache-2.0 |
| Ollama | MIT |
| MinIO | AGPL-3.0 (self-hosted, not distributed as part of this project's code) |
| Prometheus | Apache-2.0 |
| Grafana | AGPL-3.0 |

## Models

| Model | Source | License |
|---|---|---|
| `qwen2.5-coder:1.5b` (default chat model, via Ollama) | Alibaba Qwen team | Apache-2.0 |
| `nomic-embed-text` (default embedding model, via Ollama) | Nomic AI | Apache-2.0 |

Model weights are pulled at runtime via `ollama pull` and are not committed
to this repository. Swap `OLLAMA_CHAT_MODEL`/`OLLAMA_EMBEDDING_MODEL` for any
other Ollama-compatible model; verify its license before production use.

## Generating a full transitive report

```bash
# Backend
cd backend && pip install pip-licenses && pip-licenses --with-urls

# Frontend
cd frontend && npx license-checker --summary
```
