# Component view

```mermaid
flowchart TB
    subgraph api["app/api"]
        routes["routes/*.py<br/>(auth, repositories, chat, patches, health)"]
        deps["deps.py<br/>get_current_user, get_owned_repository"]
    end

    subgraph services["app/services"]
        auth_svc["auth.py"]
        ingestion["ingestion/*<br/>security, clone, walker,<br/>python_symbols, chunking, service"]
        retrieval["retrieval/*<br/>lexical, vector_store, hybrid, embeddings"]
        llm["llm/*<br/>ports, providers"]
        agents["agents/*<br/>graph, prompts, citations,<br/>diff_extraction, workflows"]
        patch_svc["patch/*<br/>sandbox, service"]
        idempotency["idempotency.py"]
    end

    subgraph core["app/core"]
        config["config.py"]
        security["security.py"]
        telemetry["telemetry.py"]
        rate_limit["rate_limit.py"]
        exceptions["exceptions.py"]
    end

    subgraph models["app/models"]
        m1["user, repository,<br/>conversation, patch, misc"]
    end

    workers["app/workers<br/>celery_app.py, tasks.py"]

    routes --> deps --> services
    services --> models
    services --> core
    workers --> services
    workers --> models
    agents --> retrieval
    agents --> llm
    patch_svc --> patch_svc
    routes -.idempotency-check.-> idempotency
```

## Dependency direction rules (enforced by convention, not tooling)

- `app/api/*` may import `app/services/*`, `app/models/*`, `app/schemas/*`,
  `app/core/*`. Never the reverse.
- `app/services/*` may import `app/models/*`, `app/core/*`, and other
  `app/services/*` submodules. Never `app/api/*`.
- `app/workers/*` imports `app/services/*` directly (it is itself a
  caller, like a route, not a service).
- Every "real vs. local/fake" provider pair (LLM chat, embeddings, vector
  store) is behind a `Protocol` in a `ports.py`, obtained only through a
  `get_*()` factory keyed off `settings.llm_provider` — see
  `services/retrieval/ports.py`, `services/llm/ports.py`.

## Where a new feature usually goes

| Kind of change | Where |
|---|---|
| New API endpoint | `app/api/routes/`, thin — calls into a service |
| New business rule / workflow step | `app/services/` |
| New DB table | `app/models/` + a new Alembic revision (`alembic revision --autogenerate`) |
| New background job | `app/workers/tasks.py`, following the `_run_coroutine_blocking` + own-DB-engine pattern (see its docstring) |
| New external integration (another LLM provider, another vector store) | A new implementation of the relevant `Protocol` in the matching `ports.py`, wired into its `get_*()` factory |
