# Changelog

All notable changes to this project are documented here. Format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

### Added

- FastAPI backend: Argon2id auth with single-use JWT refresh rotation and
  reuse detection, async SQLAlchemy 2.0 models, Alembic migrations.
- Secure repository ingestion: SSRF-guarded clone, file walker, Python AST
  symbol extraction, LangChain-based chunking with real line-span tracking.
- Hybrid retrieval: Postgres full-text search + Qdrant dense vectors, fused
  with Reciprocal Rank Fusion.
- Three agent workflows (repository Q&A, bug investigation, patch proposal)
  on a small hand-rolled deterministic graph executor, with an Ollama/fake
  LLM provider abstraction.
- Human-gated patch approval and sandboxed diff-apply/test execution,
  isolated from the canonical ingested clone.
- REST API wiring all of the above, a Celery ingestion worker, Prometheus
  metrics, OpenTelemetry tracing, structured logging.
- React/TypeScript frontend: auth, repository ingestion, all three chat
  workflows, patch-proposal review/approval.
- Docker Compose for the full free local stack (Postgres, Redis, Qdrant,
  Ollama, MinIO, MLflow, Prometheus, Grafana).
- Reproducible MLflow evaluation suite (`evals/`) covering retrieval
  quality, groundedness, citation accuracy, latency, and task success.
- GitHub Actions CI, a Jenkins pipeline, Dependabot, Kubernetes manifests,
  and a Terraform EKS reference module.

### Fixed

- `ChatOllama.ainvoke()` doesn't accept a bare `temperature` kwarg; now set
  via `model_copy()`.
- Patch-proposal diffs from a small local model are commonly wrapped in
  markdown fences and their test command wrapped in backticks (which is
  POSIX command-substitution syntax under `shell=True`, not a no-op); both
  are stripped, plus a repair step for a hunk's blank context line missing
  its leading-space marker.
- `subprocess.run(..., text=True)` silently converts LF to CRLF when writing
  diff input to `git apply`'s stdin on Windows, desyncing the diff from the
  target file; input is now passed as explicit UTF-8 bytes.
