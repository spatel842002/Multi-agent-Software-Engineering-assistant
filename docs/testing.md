# Testing

## Backend

```bash
cd backend
pytest                                          # fast suite: unit + contract + most integration, SQLite-backed
pytest --cov                                    # with coverage (fails under 70%, see pyproject.toml)
pytest -m integration                           # needs Postgres/Redis/Qdrant reachable
pytest -m "integration and not model_download"  # same, minus anything that pulls a real Ollama model response
```

As of the last run in this environment: **65 tests passing, 88.6%
coverage** (`app/main.py` is excluded from the coverage target — it's
wiring, exercised by every contract test but not meaningfully unit-testable
on its own).

Test layout:

| Directory | What it covers |
|---|---|
| `tests/unit/` | Pure functions: security, ingestion parsing/chunking/SSRF-guard, citation resolution, diff extraction, patch sandbox (real `git apply` against a temp dir, no DB) |
| `tests/contract/` | API request/response contracts via `httpx.AsyncClient` against the real FastAPI app (SQLite-backed) — auth flows, repository/chat/patch endpoint auth+ownership |
| `tests/integration/` | Multi-component paths: full ingestion pipeline against the checked-in fixture repo, the three agent workflows end-to-end with a fake LLM, patch approval → sandbox execution, the Celery task wrapper, and (marked `integration`, auto-skipped if unreachable) real calls against a live Ollama server |
| `tests/fixtures/` | `sample_repo/` — a tiny real Python module checked into the repo so ingestion/retrieval tests never depend on network access |

Why SQLite for the default suite despite Postgres being the real database:
see [ADR 0002](adr/0002-sqlite-for-fast-tests.md).

## Frontend

```bash
cd frontend
npm test              # Vitest + Testing Library, jsdom
npm run test:e2e      # Playwright, real browser, needs the full stack running (see below)
```

Unit/component tests: 10 passing, covering the API client (token
storage/attachment, error normalization), `StatusBadge`, `CitationList`, and
`LoginPage`'s success/failure flows against a mocked `fetch`.

### End-to-end (Playwright)

`frontend/e2e/smoke.spec.ts` drives a real browser against the real running
stack: register → ingest a real GitHub repo → ask a question (real Ollama
call) → propose a patch (real Ollama call) → review and reject it. It is
**not** part of the fast CI job (`frontend` job in
`.github/workflows/ci.yml`) because it needs Ollama and takes real wall-clock
LLM latency (observed: sub-second to ~95s per call depending on prompt size
and repository content — see the note on latency below).

Run it:

```bash
docker compose up -d --build
docker compose exec ollama ollama pull qwen2.5-coder:1.5b
docker compose exec ollama ollama pull nomic-embed-text
cd frontend
E2E_BASE_URL=http://localhost:5173 npm run test:e2e   # omit E2E_BASE_URL if using the default port
```

Screenshots land in `frontend/e2e/screenshots/` (gitignored, regenerated
each run); a curated set from a real run is committed under
[docs/assets/screenshots/](assets/screenshots/).

**A real infrastructure bug this test caught**: the frontend's nginx
reverse proxy has a default 60-second `proxy_read_timeout`, which returned a
bare "Gateway Time-out" mid-request the first time this test ran against a
slower/larger prompt, before the backend's own (much longer) response had
finished. Fixed in `frontend/nginx.conf` by raising the proxy timeouts to
300s. This is exactly the kind of bug a purely-mocked test suite cannot
find — see the retrieval/evaluation methodology doc below for more on why
this project prioritizes running the real stack.

## Evaluation suite (`evals/`)

```bash
python evals/run_evals.py --provider fake      # deterministic, offline, CI-safe
python evals/run_evals.py --provider ollama    # real model, real answer/patch quality
```

See [docs/architecture/retrieval-evaluation-methodology.md](architecture/retrieval-evaluation-methodology.md)
for what each metric means and its honest limitations, and
[docs/benchmarks/](benchmarks/) for committed report JSON.

## Infra validation

```bash
cd terraform/eks && terraform fmt -check -recursive && terraform init -backend=false && terraform validate
python -c "import yaml,pathlib; [yaml.safe_load_all(p.read_text()) for p in pathlib.Path('k8s').glob('*.yaml')]"
docker compose config -q
```

Terraform `fmt`/`init`/`validate` all pass; it has never been `apply`'d (no
AWS account was provisioned for this project). Kubernetes manifests are
schema-valid — verified with `kubeconform -strict`, both in CI and locally
(`10 resources found in 6 files - Valid: 10, Invalid: 0, Errors: 0`) — but
not exercised against a live cluster in this environment — see
[docs/deployment.md](deployment.md) for the honest scope of what's verified.
