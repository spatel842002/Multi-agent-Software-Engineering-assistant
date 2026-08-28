# API reference

Interactive docs (Swagger UI) at `/docs`, ReDoc at `/redoc`, and the raw
OpenAPI 3.1 spec at `/openapi.json` on any running backend instance. A
snapshot generated from a real running instance is committed at
[docs/api/openapi.json](api/openapi.json) — regenerate it after any route
change:

```bash
curl -s http://localhost:8000/openapi.json | python -m json.tool > docs/api/openapi.json
```

All endpoints below are prefixed with `API_PREFIX` (`/api/v1` by default).

## Auth (`/auth`)

| Method | Path | Auth | Rate limit | Notes |
|---|---|---|---|---|
| POST | `/auth/register` | none | 10/min | `{email, password}` (password ≥12 chars). 409 if the email is taken. |
| POST | `/auth/login` | none | 10/min | `{email, password}` → `{access_token, refresh_token, token_type}`. 401 on bad credentials. |
| POST | `/auth/refresh` | none | 30/min | `{refresh_token}` → a new token pair. 401 if expired, invalid, or already-used (reuse revokes the whole chain — see [docs/security.md](security.md)). |
| GET | `/auth/me` | Bearer | default | Current user. |

## Repositories (`/repositories`)

| Method | Path | Auth | Notes |
|---|---|---|---|
| POST | `/repositories` | Bearer | `{name, source_url}` → 202 + `Repository` (status `pending`), enqueues async ingestion. |
| GET | `/repositories` | Bearer | Lists the caller's own repositories only. |
| GET | `/repositories/{id}` | Bearer | 404 (not 403) if it exists but isn't the caller's. |

`Repository.status` transitions: `pending → cloning → indexing → ready` (or
`failed`, with `status_detail` explaining why).

## Chat workflows (`/repositories/{repository_id}/...`)

All three require the repository to belong to the caller (404 otherwise)
and return the same `WorkflowResponse` shape:

```json
{
  "conversation_id": "uuid",
  "message_id": "uuid",
  "answer": "string",
  "citations": [{"file_path": "string", "start_line": 0, "end_line": 0}],
  "prompt_version": "repo_qa.v1",
  "latency_ms": 0,
  "patch_proposal_id": "uuid | null"
}
```

| Method | Path | Body |
|---|---|---|
| POST | `/repositories/{id}/qa` | `{question}` |
| POST | `/repositories/{id}/bug-investigations` | `{bug_description}` |
| POST | `/repositories/{id}/patch-proposals` | `{task_description}` — response's `patch_proposal_id` is non-null; nothing is applied yet. |

## Patch proposals (`/patch-proposals`)

| Method | Path | Notes |
|---|---|---|
| GET | `/patch-proposals/{id}` | 404 if it exists but isn't owned (via its repository) by the caller. |
| POST | `/patch-proposals/{id}/decision` | `{decision: "approve"\|"reject", reason?}`. `approve` triggers sandboxed apply+test; response's `status` becomes `applied`/`test_run_passed`/`test_run_failed` (approve) or `rejected`. 409 if already decided. |

## Operational endpoints

| Method | Path | Auth | Notes |
|---|---|---|---|
| GET | `/api/v1/health` | none | Liveness — process is up, no dependency checks. |
| GET | `/api/v1/ready` | none | Readiness — checks the database is reachable. |
| GET | `/metrics` | none | Prometheus exposition format (no `/api/v1` prefix). |

## Error shape

Every error response is `{"detail": "human-readable message"}` — FastAPI's
default for validation errors (422) and this project's `AppError` hierarchy
(`app/core/exceptions.py`) for domain errors (401/403/404/409/422).
