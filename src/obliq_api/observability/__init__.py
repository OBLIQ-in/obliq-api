"""OpenTelemetry SDK setup for obliq-api.

Call ``configure_telemetry(app)`` once inside the FastAPI lifespan, after
the app object is created but before it starts serving requests.

Traces and metrics are exported via OTLP (gRPC) when
``OTEL_EXPORTER_OTLP_ENDPOINT`` is set in the environment.  When the
endpoint is absent (local dev), a no-op exporter is used so the
instrumentation is exercised without needing a collector.

Custom instruments:
    - obliq.ocr.page_duration_seconds  (histogram)
    - obliq.ocr.low_confidence_pages   (counter)
    - obliq.ocr.jobs_total             (counter, labelled by status)
    - obliq.ocr.credits_charged_total  (counter)

These are recorded via ``record_ocr_metrics()`` which is called from
``services/jobs.py`` after each job completes.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from opentelemetry import metrics, trace
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.redis import RedisInstrumentor
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import (
    ConsoleMetricExporter,
    PeriodicExportingMetricReader,
)
from opentelemetry.sdk.resources import SERVICE_NAME, Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter

if TYPE_CHECKING:
    from fastapi import FastAPI

# ---------------------------------------------------------------------------
# Module-level instrument handles — populated by configure_telemetry()
# ---------------------------------------------------------------------------
_page_duration: metrics.Histogram | None = None
_low_confidence_counter: metrics.Counter | None = None
_jobs_counter: metrics.Counter | None = None
_credits_counter: metrics.Counter | None = None


def configure_telemetry(app: "FastAPI") -> None:
    """Initialise the OTel SDK and instrument FastAPI, SQLAlchemy, and Redis."""
    from obliq_api.config import get_settings
    from obliq_api.db.session import engine

    settings = get_settings()
    endpoint = settings.otel_exporter_otlp_endpoint
    service_name = settings.otel_service_name

    resource = Resource(attributes={SERVICE_NAME: service_name})

    # ── Traces ────────────────────────────────────────────────────────────
    if endpoint:
        from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import (
            OTLPSpanExporter,
        )
        span_exporter = OTLPSpanExporter(endpoint=endpoint, insecure=True)
    else:
        span_exporter = ConsoleSpanExporter()  # type: ignore[assignment]

    tracer_provider = TracerProvider(resource=resource)
    tracer_provider.add_span_processor(BatchSpanProcessor(span_exporter))
    trace.set_tracer_provider(tracer_provider)

    # ── Metrics ───────────────────────────────────────────────────────────
    if endpoint:
        from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import (
            OTLPMetricExporter,
        )
        metric_exporter = OTLPMetricExporter(endpoint=endpoint, insecure=True)
    else:
        metric_exporter = ConsoleMetricExporter()  # type: ignore[assignment]

    reader = PeriodicExportingMetricReader(metric_exporter, export_interval_millis=15_000)
    meter_provider = MeterProvider(resource=resource, metric_readers=[reader])
    metrics.set_meter_provider(meter_provider)

    # ── Custom instruments ────────────────────────────────────────────────
    meter = metrics.get_meter("obliq.api", schema_url="https://obliq.ai/otel/schema/1.0")

    global _page_duration, _low_confidence_counter, _jobs_counter, _credits_counter

    _page_duration = meter.create_histogram(
        name="obliq.ocr.page_duration_seconds",
        description="Per-page OCR processing time in seconds",
        unit="s",
    )
    _low_confidence_counter = meter.create_counter(
        name="obliq.ocr.low_confidence_pages",
        description="Number of pages returned with low OCR confidence",
        unit="pages",
    )
    _jobs_counter = meter.create_counter(
        name="obliq.ocr.jobs_total",
        description="Total OCR jobs by final status",
        unit="jobs",
    )
    _credits_counter = meter.create_counter(
        name="obliq.ocr.credits_charged_total",
        description="Total credits charged across all jobs",
        unit="credits",
    )

    # ── Library instrumentation ───────────────────────────────────────────
    FastAPIInstrumentor.instrument_app(app, tracer_provider=tracer_provider)
    SQLAlchemyInstrumentor().instrument(
        engine=engine.sync_engine,
        tracer_provider=tracer_provider,
    )
    RedisInstrumentor().instrument(tracer_provider=tracer_provider)


def record_ocr_metrics(
    *,
    status: str,
    actual_pages: int,
    charged_credits: int,
    low_confidence_pages: int,
    page_durations_seconds: list[float],
) -> None:
    """Record per-job metrics.  Safe to call even before configure_telemetry()."""
    if _jobs_counter is not None:
        _jobs_counter.add(1, {"status": status})

    if _credits_counter is not None:
        _credits_counter.add(charged_credits)

    if _low_confidence_counter is not None and low_confidence_pages > 0:
        _low_confidence_counter.add(low_confidence_pages)

    if _page_duration is not None:
        for dur in page_durations_seconds:
            _page_duration.record(dur, {"status": status})
