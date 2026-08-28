# Runbook

Operational playbooks for common failure scenarios. See
[docs/troubleshooting.md](troubleshooting.md) for local-dev setup problems;
this doc is about a running deployment misbehaving.

## Backend is unhealthy / `/api/v1/ready` returns `ready: false`

1. `docker compose ps` — confirm `postgres` is `healthy`. `/ready` only
   checks the database today (`app/api/routes/health.py`); extend its
   `checks` dict if you add another hard dependency (Redis, Qdrant).
2. `docker compose logs backend --tail 100` — look for a connection error
   at startup vs. mid-request.
3. If Postgres itself is unhealthy: `docker compose logs postgres`; a
   corrupt/incompatible data volume is the most common local-dev cause
   (`docker compose down -v` to reset it — **destroys local data**, only
   for a dev environment you don't care about).

## Ingestion jobs stuck in `PENDING` or `CLONING`

1. Confirm the Celery worker is actually running and healthy:
   `docker compose ps worker` should show `healthy` (its healthcheck is
   `celery inspect ping`, not an HTTP check — it has no web server).
2. `docker compose logs worker` — a task that never started logging means
   it's not reaching the broker; confirm `REDIS_URL`/`CELERY_BROKER_URL`
   matches between `backend` and `worker` (`backend/.env.docker` is shared
   by both services in Compose).
3. A task that started but never finished: check for a hung `git clone`
   against a slow/unresponsive remote — `INGESTION_CLONE_TIMEOUT_SECONDS`
   bounds this (default 120s), so it should self-resolve to `FAILED`
   eventually; if it doesn't, the worker process itself may be stuck and
   needs a restart (`docker compose restart worker`).

## A workflow request (`/qa`, `/bug-investigations`, `/patch-proposals`) times out or 504s

1. This is expected to be *slow*, not necessarily broken — CPU-bound local
   LLM inference against `qwen2.5-coder:1.5b` was observed at 0.6s-95s per
   call depending on prompt/context size during development. Confirm
   Ollama itself is responsive: `docker compose exec ollama ollama list`.
2. If using the frontend's nginx proxy specifically: confirm
   `proxy_read_timeout`/`proxy_send_timeout` in `frontend/nginx.conf` are
   still ≥300s — a real regression here (nginx's 60s default) caused a
   bare "Gateway Time-out" during development; see
   [docs/testing.md](testing.md) for the story.
3. If a real 500 (not a timeout): check `docker compose logs backend` for
   the traceback. LLM-provider integration errors (a bad response shape, an
   unsupported call kwarg) surface here — see `CHANGELOG.md`'s "Fixed"
   section for the kind of thing this has caught before.

## A patch approval always fails with "corrupt patch" / `git apply failed`

This can be a genuine, expected outcome (a small local model produced a
malformed diff — the sandbox correctly rejected it, nothing was applied) or
a regression in `services/agents/diff_extraction.py`'s repair logic. To
tell them apart:

1. Check `PatchProposal.diff_text` (via `GET /patch-proposals/{id}` or the
   frontend's diff view) for the actual content that was attempted.
2. If it looks like a well-formed unified diff and still fails: reproduce
   locally with `tests/unit/test_diff_extraction.py` as a starting point —
   add the failing case as a new test before fixing it.
3. If it's genuinely malformed (wrong context, wrong line counts): this is
   the safety mechanism working as intended, not a bug. See
   [ADR 0003](adr/0003-process-level-sandbox-isolation.md).

## Rate limit false-positives (legitimate users getting 429s)

`RATE_LIMIT_DEFAULT`/`RATE_LIMIT_AUTH` (env vars, see
[docs/environment-variables.md](environment-variables.md)) are shared across
all backend replicas via Redis in every environment except `ENVIRONMENT=test`.
If replicas disagree about the limit, confirm they're all pointed at the
same `REDIS_URL`.

## Rolling back a bad deployment (Kubernetes)

```bash
kubectl -n masea rollout undo deployment/masea-backend
kubectl -n masea rollout undo deployment/masea-worker
kubectl -n masea rollout status deployment/masea-backend
```

## Database migration went wrong

```bash
# See current revision:
docker compose exec backend alembic current
# Roll back one revision:
docker compose exec backend alembic downgrade -1
```

Never run `alembic downgrade` against a production database without a
recent backup — the `chunk_fulltext_index` migration's downgrade, for
example, drops a column.
