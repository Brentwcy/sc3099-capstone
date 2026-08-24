"""
OpenTelemetry instrumentation and metrics setup for SAIV Face Recognition Service.
"""
from typing import Optional
from fastapi import FastAPI
from .logging_config import logger

def setup_telemetry(app: FastAPI, otel_endpoint: Optional[str] = None):
    """Set up OpenTelemetry tracing and FastAPI instrumentation if configured."""
    if not otel_endpoint:
        return

    try:
        from opentelemetry import trace
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
        from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

        resource = Resource.create({"service.name": "saiv-face-recognition"})
        provider = TracerProvider(resource=resource)
        exporter = OTLPSpanExporter(endpoint=otel_endpoint, insecure=True)
        provider.add_span_processor(BatchSpanProcessor(exporter))
        trace.set_tracer_provider(provider)

        FastAPIInstrumentor.instrument_app(app)
        logger.info("OpenTelemetry instrumentation enabled", endpoint=otel_endpoint)
    except Exception as e:
        logger.warning("Failed to initialize OpenTelemetry", error=str(e))
