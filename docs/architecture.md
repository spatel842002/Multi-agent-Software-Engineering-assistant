# Architecture

## System overview

```mermaid
flowchart TB
    subgraph Client
        FE[React/TS frontend<br/>Vite + nginx]
    end

    subgraph Backend[FastAPI backend]
        API[API routes<br/>auth / repositories / chat / patches]
        Deps[api/deps.py<br/>auth + owner-scoping]
        Services[services/*]
    end

    subgraph Async
        Celery[Celery worker]
    end

    subgraph Data
        PG[(PostgreSQL<br/>+ Alembic migrations)]
        Redis[(Redis<br/>cache, rate limit, Celery broker)]
        Qdrant[(Qdrant<br/>dense vectors)]
    end

    subgraph LLM
        Ollama[Ollama<br/>chat + embedding models]
    end

    subgraph Observability
        Prom[Prometheus]
        Grafana
        OTel[OTel Collector]
        MLflow
    end

    FE -->|REST /api/v1, bearer JWT| API
    API --> Deps --> Services
    Services --> PG
    Services --> Redis
    Services --> Qdrant
    Services --> Ollama
    API -->|.delay| Celery
    Celery --> PG
    Celery --> Qdrant
    API -->|/metrics| Prom --> Grafana
    API -->|spans| OTel
    Evals[evals/run_evals.py] --> MLflow
    Evals -.exercises.-> Services
```

## Request flow: repository ingestion

```mermaid
sequenceDiagram
    participant U as User (frontend)
    participant API as POST /repositories
    participant DB as Postgres
    participant Q as Celery task
    participant Git as git clone
    participant Idx as Indexer
    participant Vec as Qdrant

    U->>API: name, source_url
    API->>API: validate_source_url() -- scheme + SSRF check
    API->>DB: insert Repository(status=PENDING)
    API-->>U: 202, repository (PENDING)
    API->>Q: run_ingestion_task.delay(repo_id)
    Q->>DB: status=CLONING
    Q->>Git: git clone --depth 1 (bounded timeout)
    Git-->>Q: local path, commit sha
    Q->>DB: status=INDEXING
    Q->>Idx: walk files, extract Python symbols, chunk
    Idx->>DB: IngestedFile, Symbol, Chunk rows
    Idx->>Vec: upsert_chunks(embeddings)
    Q->>DB: status=READY, file/symbol/chunk counts
```

## Request flow: a retrieval-grounded workflow (Q&A / bug investigation)

```mermaid
sequenceDiagram
    participant U as User
    participant API as POST /repositories/{id}/qa
    participant Hyb as hybrid_retrieve()
    participant Lex as Postgres tsvector
    participant Vec as Qdrant
    participant LLM as Ollama
    participant Cit as resolve_citations()
    participant DB as Postgres

    U->>API: question
    API->>Hyb: repository_id, query
    Hyb->>Lex: lexical_search()
    Hyb->>Vec: search(query_vector)
    Hyb->>Hyb: Reciprocal Rank Fusion
    Hyb-->>API: ranked chunks
    API->>LLM: system prompt + numbered excerpts
    LLM-->>API: answer + "Citations: [..]"
    API->>Cit: resolve against retrieved excerpts
    Cit-->>API: only real, resolvable citations
    API->>DB: persist Conversation/Message/Citation
    API-->>U: answer + citations + prompt_version + latency
```

## Request flow: patch proposal and human-gated approval

```mermaid
sequenceDiagram
    participant U as User
    participant API as POST .../patch-proposals
    participant LLM as Ollama
    participant DE as diff_extraction
    participant DB as Postgres
    participant Dec as POST .../decision
    participant SB as patch sandbox

    U->>API: task_description
    API->>LLM: generate diff + test command
    LLM-->>API: raw response
    API->>DE: extract_diff_text() -- strip fences, repair markers
    API->>DB: PatchProposal(status=PENDING_APPROVAL)
    Note over API,DB: Graph halts here. Nothing applies or executes.
    U->>Dec: decision=approve|reject
    alt reject
        Dec->>DB: status=REJECTED
    else approve
        Dec->>DB: status=APPROVED, ApprovalEvent recorded
        Dec->>SB: copy repo -> disposable dir (excludes .git)
        SB->>SB: git apply (bytes stdin, not text=True)
        alt apply fails
            SB-->>Dec: TEST_RUN_FAILED, apply_output
        else apply succeeds
            SB->>SB: run test_command (bounded timeout)
            SB-->>Dec: TEST_RUN_PASSED / TEST_RUN_FAILED
        end
        Dec->>DB: final status + test_output
    end
```

## Component map

| Layer | Path | Notes |
|---|---|---|
| API routes | `backend/app/api/routes/` | Thin: auth, request validation, calling services |
| Auth | `backend/app/core/security.py`, `services/auth.py` | Argon2id, JWT access + single-use refresh with reuse detection |
| Ingestion | `backend/app/services/ingestion/` | SSRF guard, clone, walk, Python AST symbols, LangChain chunking |
| Retrieval | `backend/app/services/retrieval/` | Lexical (Postgres tsvector), dense (Qdrant), RRF fusion |
| LLM | `backend/app/services/llm/` | `ChatProvider` port; Ollama and deterministic-fake implementations |
| Agent orchestration | `backend/app/services/agents/` | Graph executor, prompts, citation resolution, diff extraction, the 3 workflows |
| Patch approval | `backend/app/services/patch/` | The one path that can apply/execute a proposal; sandbox isolation |
| Async work | `backend/app/workers/` | Celery task wrapping ingestion with its own DB engine |
| Observability | `backend/app/core/telemetry.py` | Prometheus metrics, OTel tracing setup |
| Frontend | `frontend/src/` | React Router pages, a dependency-free typed `fetch` client, Tailwind |
| Evaluation | `evals/` | Reproducible MLflow eval suite, fake or real Ollama provider |
| Infra | `k8s/`, `terraform/eks/`, `infra/` | Kubernetes manifests, Terraform EKS reference, Prometheus/Grafana config |

## Why a hybrid retriever (not just embeddings)

Dense (embedding) search alone misses exact-identifier lookups common in
code search (a variable or function name is often a poor embedding-space
neighbor of its own usages). Lexical (full-text) search alone misses
semantic/paraphrased questions. Reciprocal Rank Fusion combines both
rankers' *positions* rather than trying to normalize incomparable score
scales (cosine similarity vs. `ts_rank`) — see
`backend/app/services/retrieval/hybrid.py`.

## Why the agent orchestration is a hand-rolled graph, not LangGraph

See [docs/adr/0004-hand-rolled-agent-graph.md](adr/0004-hand-rolled-agent-graph.md).

## Deployment view

Local: `docker compose up` brings up every service in this diagram on one
machine. Production reference: `k8s/` manifests (backend/worker/frontend
Deployments, a ConfigMap/Secret pair, an Ingress) targeting a cluster
provisioned by `terraform/eks/` (VPC, EKS, RDS Postgres, ElastiCache Redis,
S3) — see [docs/deployment.md](deployment.md).
