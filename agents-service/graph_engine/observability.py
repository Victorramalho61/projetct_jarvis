"""Observability: trace IDs, métricas Prometheus, logging estruturado."""
import logging
import time
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Generator

log = logging.getLogger(__name__)

# ── Prometheus metrics (lazy-init para não quebrar se prometheus-client não estiver disponível) ──
try:
    from prometheus_client import Counter, Histogram, Gauge, CollectorRegistry, REGISTRY

    _pipeline_duration = Histogram(
        "agents_pipeline_duration_seconds",
        "Duração total de pipeline runs",
        ["pipeline"],
        buckets=[5, 15, 30, 60, 120, 300, 600],
    )
    _agent_duration = Histogram(
        "agents_agent_duration_seconds",
        "Duração por agente dentro de um pipeline",
        ["agent", "pipeline"],
        buckets=[1, 5, 10, 30, 60, 120],
    )
    _findings_counter = Counter(
        "agents_findings_total",
        "Total de findings acumulados",
        ["pipeline"],
    )
    _errors_counter = Counter(
        "agents_errors_total",
        "Total de agentes que falharam",
        ["agent", "pipeline"],
    )
    _success_counter = Counter(
        "agents_pipeline_success_total",
        "Total de pipeline runs com sucesso",
        ["pipeline"],
    )
    _active_pipelines = Gauge(
        "agents_active_pipelines",
        "Pipelines em execução agora",
    )
    _PROMETHEUS_OK = True
except ImportError:
    _PROMETHEUS_OK = False
    log.warning("prometheus-client não instalado — /metrics não disponível")


def new_trace_id() -> str:
    return uuid.uuid4().hex[:16]


def record_agent_run(agent: str, pipeline: str, duration_s: float, success: bool, findings: int = 0) -> None:
    """Registra métricas de uma execução de agente."""
    if not _PROMETHEUS_OK:
        return
    _agent_duration.labels(agent=agent, pipeline=pipeline).observe(duration_s)
    if not success:
        _errors_counter.labels(agent=agent, pipeline=pipeline).inc()
    if findings:
        _findings_counter.labels(pipeline=pipeline).inc(findings)


@contextmanager
def pipeline_span(pipeline: str) -> Generator[dict, None, None]:
    """Context manager que mede duração total do pipeline e emite métricas."""
    trace_id = new_trace_id()
    started  = time.monotonic()
    ctx = {"trace_id": trace_id, "pipeline": pipeline, "started_at": datetime.now(timezone.utc).isoformat()}

    if _PROMETHEUS_OK:
        _active_pipelines.inc()

    log.info("[TRACE:%s] pipeline '%s' iniciado", trace_id, pipeline)
    try:
        yield ctx
        duration = time.monotonic() - started
        if _PROMETHEUS_OK:
            _pipeline_duration.labels(pipeline=pipeline).observe(duration)
            _success_counter.labels(pipeline=pipeline).inc()
        log.info("[TRACE:%s] pipeline '%s' concluído em %.1fs", trace_id, pipeline, duration)
    except Exception:
        duration = time.monotonic() - started
        if _PROMETHEUS_OK:
            _pipeline_duration.labels(pipeline=pipeline).observe(duration)
        log.error("[TRACE:%s] pipeline '%s' falhou após %.1fs", trace_id, pipeline, duration)
        raise
    finally:
        if _PROMETHEUS_OK:
            _active_pipelines.dec()


def generate_metrics_text() -> str:
    """Retorna métricas no formato texto Prometheus (para endpoint /metrics)."""
    if not _PROMETHEUS_OK:
        return "# prometheus-client não disponível\n"
    from prometheus_client import generate_latest
    return generate_latest().decode("utf-8")
