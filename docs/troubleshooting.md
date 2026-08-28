# Troubleshooting

Local-dev setup problems. For a running deployment misbehaving, see
[docs/runbook.md](runbook.md).

## `docker compose up` fails with a port-already-in-use error

Another process (or another project's stack) already has a default port.
Copy `.env.example` to `.env` at the repo root and override the specific
`*_PORT` variable that conflicts — every service's host-side port is
overridable (see `docker-compose.yml`). Container-to-container networking
is unaffected either way.

## `alembic upgrade head` fails to connect

Confirm Postgres is actually up and healthy first:
`docker compose ps postgres`. If running the backend outside Docker,
confirm `DATABASE_URL` in `backend/.env` points at `localhost` (not the
Docker service name `postgres`, which only resolves inside the Compose
network).

## An LLM/embedding call fails immediately

You likely haven't pulled the models yet:

```bash
docker compose exec ollama ollama pull qwen2.5-coder:1.5b
docker compose exec ollama ollama pull nomic-embed-text
docker compose exec ollama ollama list   # confirm both are present
```

## Repository ingestion fails immediately with a 422

Check the error `detail` — the ingestion endpoint validates the source URL
before ever calling `git clone` (`services/ingestion/security.py`):

- Only `https://` URLs are accepted.
- The hostname must resolve to a public IP — `localhost`, private ranges,
  and cloud metadata addresses are rejected by design (SSRF protection, see
  [docs/security.md](security.md)). This means you cannot ingest a
  repository served from `localhost`/an internal address during local dev
  without changing that check — it's intentionally not configurable via
  environment variable, only via `allow_private_hosts=True` in test code.

## `pytest` fails with a Redis connection error

This should not happen — `ENVIRONMENT=test` switches the rate limiter to
in-process storage specifically so the fast suite never needs a live
Redis (`app/core/rate_limit.py`). If you see this, confirm
`backend/.env.test`'s `ENVIRONMENT=test` is actually being picked up
(`tests/conftest.py` loads it via `load_dotenv(..., override=True)` before
any `app.*` import) and that you're not accidentally running against a
different `.env` file.

## Frontend `npm run test:e2e` fails with "Gateway Time-out" or a connection error

Confirm the full stack is actually up and healthy
(`docker compose ps` — backend, worker, and frontend should all be
`healthy`), and that `E2E_BASE_URL` (if set) points at the frontend's real
host port. If it fails specifically on the QA/patch-proposal steps with a
504-style error, see the nginx timeout note in
[docs/testing.md](testing.md#end-to-end-playwright).

## Frontend `npm test` fails with `localStorage.clear is not a function`

A known Node.js quirk, not an app bug: Node 22+ ships a built-in
`localStorage` global that can shadow jsdom's simulated one and lacks
`.clear()` without a `--localstorage-file` flag. `frontend/src/test/setup.ts`
installs a minimal working replacement for tests specifically because of
this — if you see this error, your setup file changes may have removed
that shim.

## `terraform validate` fails

Run `terraform init -backend=false` first in `terraform/eks/` — `validate`
needs the providers/modules downloaded, which `init` does. Ensure Docker
has network access if running via the containerized workflow
(`docker run ... hashicorp/terraform:1.16 ...`, see `terraform/eks/README.md`).

## Windows-specific: a patch approval fails with "corrupt patch" even though the diff looks fine

This was a real bug, now fixed: `subprocess.run(..., text=True)` on Windows
silently converts LF to CRLF when writing to a child process's stdin,
corrupting a unified diff before `git apply` ever sees it.
`services/patch/sandbox.py` now passes the diff as explicit UTF-8 bytes. If
you see this again, check whether a change reintroduced `text=True` on that
specific subprocess call.
