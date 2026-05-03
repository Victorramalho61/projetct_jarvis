"""Roteador determinístico — decide próxima ação SEM chamar LLM."""
import logging

log = logging.getLogger(__name__)

# event_type → agente responsável (mesma tabela do cto_agent, sem LLM)
_EVENT_ROUTING: dict[str, str] = {
    "security_alert":       "security",
    "container_down":       "uptime",
    "error_detected":       "log_improver",
    "log_findings":         "log_improver",
    "quality_degraded":     "quality",
    "integration_failed":   "integration_validator",
    "change_requested":     "change_mgmt",
    "agents_health_critical": "uptime",
}

# Eventos que o CTO deve processar com LLM (não rotear para sub-agente)
_CTO_ONLY_EVENTS = {"proposal_ready", "improvement_proposal", "deploy_start", "deploy_end", "task_dispatched"}

# pipeline → agente principal (primeiro a rodar, determina o "tema")
_PIPELINE_LEAD: dict[str, str] = {
    "monitoring":  "uptime",
    "security":    "security",
    "cicd":        "cicd_monitor",
    "dba":         "db_dba_agent",
    "governance":  "opportunity_scout",
    "evolution":   "evolution_agent",
    "manual":      "END",  # manual → CTO decide via LLM
}


def route(pending_events: list[dict], current_pipeline: str) -> str | None:
    """
    Retorna o nome do agente a acionar, ou None se a decisão requer LLM.

    - Se há evento crítico/high com routing conhecido → retorna agente imediato
    - Se pipeline definido e sem eventos urgentes → retorna agente líder do pipeline
    - Se há eventos apenas para o CTO processar → retorna None (LLM decide)
    - Se nada → retorna "END"
    """
    # Prioridade: eventos critical/high primeiro
    urgent = [e for e in pending_events if e.get("priority") in ("critical", "high")]
    for event in urgent:
        etype = event.get("event_type", "")
        if etype in _EVENT_ROUTING:
            agent = _EVENT_ROUTING[etype]
            log.info("[DeterministicRouter] evento '%s' → agente '%s'", etype, agent)
            return agent

    # Eventos que exigem LLM (proposals, deploy signals)
    cto_events = [e for e in pending_events if e.get("event_type") in _CTO_ONLY_EVENTS]
    if cto_events:
        log.info("[DeterministicRouter] eventos CTO-only detectados → LLM necessário")
        return None  # sinaliza: chamar LLM

    # Fallback: pipeline define agente líder
    if current_pipeline and current_pipeline in _PIPELINE_LEAD:
        agent = _PIPELINE_LEAD[current_pipeline]
        log.info("[DeterministicRouter] pipeline '%s' → agente líder '%s'", current_pipeline, agent)
        return agent

    # Nada urgente, nada a fazer
    return "END"
