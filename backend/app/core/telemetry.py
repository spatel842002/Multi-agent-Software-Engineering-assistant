from __future__ import annotations

from typing import TYPE_CHECKING

from prometheus_client import Counter, Histogram

from app.core.config import get_settings

if TYPE_CHECKING:
    from fastapi import FastAPI

# --- Application-level metrics (in addition to the default HTTP metrics that
# opentelemetry-instrumentation-fastapi / a Prometheus ASGI middleware expose) ---

LLM_REQUEST_LATENCY_SECONDS = Histogram(
    "masea_llm_request_latency_seconds",
    "Latency of a single LLM call, labeled by workflow and provider.",
    labelnames=("workflow", "provider"),
)

LLM_REQUEST_ERRORS = Counter(
    "masea_llm_request_errors_total",
    "Number of failed LLM calls, labeled by workflow and provider.",
    labelnames=("workflow", "provider"),
)

RETRIEVAL_LATENCY_SECONDS = Histogram(
    "masea_retrieval_latency_seconds",
    "Latency of a hybrid retrieval call.",
    labelnames=("retrieval_mode",),
)

INGESTION_JOBS = Counter(
    "masea_ingestion_jobs_total",
    "Repository ingestion jobs, labeled by terminal status.",
    labelnames=("status",),
)

PATCH_APPROVAL_DECISIONS = Counter(
    "masea_patch_approval_decisions_total",
    "Human approval decisions on proposed patches.",
    labelnames=("decision",),
)


def setup_tracing(app: FastAPI) -> None:
    """Wire OpenTelemetry tracing. Exports to OTLP if configured, otherwise the
    tracer still runs (in-process spans only) so instrumentation code paths
    are always exercised even in the free local-only setup.
    """
    settings = get_settings()
    from opentelemetry import trace
    from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
    from opentelemetry.sdk.resources import SERVICE_NAME, Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter

    resource = Resource.create({SERVICE_NAME: settings.otel_service_name})
    provider = TracerProvider(resource=resource)

    if settings.otel_exporter_otlp_endpoint:
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter

        provider.add_span_processor(
            BatchSpanProcessor(OTLPSpanExporter(endpoint=settings.otel_exporter_otlp_endpoint))
        )
    else:
        provider.add_span_processor(BatchSpanProcessor(ConsoleSpanExporter()))

    trace.set_tracer_provider(provider)
    FastAPIInstrumentor.instrument_app(app)
