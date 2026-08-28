# Observability

## Logging

Structured JSON logging via `structlog` (`app/core/logging.py`) — every log
line is a JSON object, safe to ship to any log aggregator without a custom
parser. Configured level via `LOG_LEVEL`.

## Metrics (Prometheus)

Exposed at `GET /metrics` (`app/main.py`), scraped by the `prometheus`
Compose service per `infra/prometheus/prometheus.yml`. Application-level
metrics (`app/core/telemetry.py`), all real and wired to actual code paths
(verified — see `CHANGELOG.md` for the two that were initially defined but
not yet observed anywhere, since fixed):

| Metric | Type | Labels | Where it's recorded |
|---|---|---|---|
| `masea_llm_request_latency_seconds` | Histogram | `workflow`, `provider` | `services/agents/workflows.py::_complete_with_metrics`, wrapping every chat-provider call across all three workflows |
| `masea_llm_request_errors_total` | Counter | `workflow`, `provider` | Same wrapper, on exception |
| `masea_retrieval_latency_seconds` | Histogram | `retrieval_mode` | `services/retrieval/hybrid.py::hybrid_retrieve` |
| `masea_ingestion_jobs_total` | Counter | `status` | `app/workers/tasks.py`, one increment per terminal ingestion status |
| `masea_patch_approval_decisions_total` | Counter | `decision` | `services/patch/service.py::decide_patch_proposal` |

Plus the standard `prometheus-client` process/GC metrics (`process_*`,
`python_gc_*`).

A starter Grafana dashboard (`infra/grafana/dashboards/masea-overview.json`,
auto-provisioned) graphs all five: LLM latency p50/p95 by workflow, LLM
error rate by workflow, retrieval latency p50/p95, ingestion jobs by
terminal status, and patch approval decisions.

## Tracing (OpenTelemetry)

`app/core/telemetry.py::setup_tracing` instruments the FastAPI app
(`FastAPIInstrumentor`) and exports spans via OTLP if
`OTEL_EXPORTER_OTLP_ENDPOINT` is set, otherwise to console (so
instrumentation code paths are always exercised, even in the fully-local
default setup with nothing else to receive traces). Disabled entirely when
`ENVIRONMENT=test`, so the test suite's log output isn't full of trace spam.

## MLflow (evaluation tracking, not production request tracing)

`evals/run_evals.py` logs every eval run's metrics/params to MLflow — see
[docs/testing.md](testing.md) and
[docs/architecture/retrieval-evaluation-methodology.md](architecture/retrieval-evaluation-methodology.md).
MLflow here is a benchmark/eval tool, never on the live request-serving
path.

## What to actually look at when something's wrong

1. `docker compose logs backend` / `docker compose logs worker` — structured
   JSON, `grep` for `"level":"error"` or a specific `trace_id`.
2. `/api/v1/ready` — reports whether the database is reachable (extend this
   if you add a dependency that should also gate readiness).
3. Grafana (`http://localhost:3001`) — the pre-provisioned dashboard for
   latency/error trends.
4. Prometheus (`http://localhost:9090`) — raw query access for anything not
   on the dashboard, e.g. `rate(masea_llm_request_errors_total[5m])`.

See [docs/runbook.md](runbook.md) for specific incident playbooks.
