"""Ferramentas exclusivas do CTO Agent — despacho, governança e controle de deploy."""
import logging
from datetime import datetime, timedelta, timezone

from langchain_core.tools import tool

from graph_engine.tools.supabase_tools import (
    close_deployment_window,
    get_active_deployment_window,
    get_agent_tasks,
    get_error_frequency_map,
    get_latest_governance_report,
    get_pending_agent_events,
    insert_agent_event,
    insert_agent_task,
    insert_deployment_window,
    insert_governance_report,
    log_event,
    mark_agent_event_processed,
    query_agent_runs,
    query_improvement_proposals,
    query_quality_metrics,
    update_agent_task,
    update_improvement_proposal,
)
from graph_engine.tools.http_tools import check_all_services
from graph_engine.tools.docker_tools import list_containers, get_container_stats

log = logging.getLogger(__name__)


@tool
def dispatch_agent(agent_name: str, task_description: str, priority: str = "medium", context: dict | None = None) -> dict:
    """Despacha uma tarefa para um agente específico via fila agent_tasks.

    Args:
        agent_name: Nome do agente destino (ex: 'log_scanner', 'security', 'uptime').
        task_description: Descrição clara da tarefa a executar.
        priority: critical | high | medium | low
        context: Dados adicionais para o agente.
    """
    task = insert_agent_task(
        assigned_to=agent_name,
        task_description=task_description,
        priority=priority,
        context=context or {},
        dispatched_by="cto",
    )
    insert_agent_event(
        event_type="task_dispatched",
        source="cto",
        payload={"task_id": task.get("id"), "agent": agent_name, "priority": priority},
        priority=priority,
    )
    log_event("info", "cto_agent", f"Tarefa despachada para {agent_name} [{priority}]", task_description[:200])
    return {"task_id": task.get("id"), "agent": agent_name, "status": "dispatched"}


@tool
def set_deployment_window(active: bool, reason: str, started_by: str = "cto_agent", duration_minutes: int = 30) -> dict:
    """Abre ou fecha uma janela de deploy, suspendendo/retomando automações de uptime.

    Args:
        active: True para abrir janela, False para fechar.
        reason: Motivo do deploy ou encerramento.
        started_by: Quem acionou (usuário ou serviço).
        duration_minutes: Duração prevista (apenas ao abrir).
    """
    if active:
        expected_end = (datetime.now(timezone.utc) + timedelta(minutes=duration_minutes)).isoformat()
        window = insert_deployment_window(reason=reason, started_by=started_by, expected_end=expected_end)
        insert_agent_event(
            event_type="deploy_start",
            source="cto",
            payload={"reason": reason, "window_id": window.get("id"), "duration_minutes": duration_minutes},
            priority="high",
        )
        log_event("warning", "cto_agent", f"Janela de deploy aberta por {started_by}", reason)
        return {"action": "opened", "window_id": window.get("id"), "expected_end": expected_end}
    else:
        window = get_active_deployment_window()
        if window:
            close_deployment_window(window["id"])
            insert_agent_event(
                event_type="deploy_end",
                source="cto",
                payload={"window_id": window["id"], "reason": reason},
                priority="medium",
            )
            log_event("info", "cto_agent", "Janela de deploy encerrada", reason)
            return {"action": "closed", "window_id": window["id"]}
        return {"action": "noop", "message": "Nenhuma janela de deploy ativa"}


@tool
def get_system_health_summary() -> dict:
    """Retorna um resumo consolidado da saúde de todos os serviços e containers."""
    services = check_all_services()
    services_down = [s for s in services if s.get("status") == "down"]

    containers = list_containers()
    exited = list_containers(status="exited")

    high_mem = []
    for c in containers:
        if isinstance(c, dict) and "error" not in c:
            stats = get_container_stats(c["name"])
            if stats.get("memory_percent", 0) > 80:
                high_mem.append({"container": c["name"], "memory_percent": stats["memory_percent"]})

    recent_runs = query_agent_runs(limit=50)
    failed_runs = [r for r in recent_runs if r.get("status") == "error"]

    proposals = query_improvement_proposals(status="pending_cto", limit=20)

    return {
        "services_total": len(services),
        "services_down": services_down,
        "containers_exited": [c.get("name") for c in exited if isinstance(c, dict)],
        "containers_high_memory": high_mem,
        "agent_runs_failed_recent": len(failed_runs),
        "pending_proposals": len(proposals),
        "deployment_active": get_active_deployment_window() is not None,
        "summary_at": datetime.now(timezone.utc).isoformat(),
    }


@tool
def list_pending_tasks(priority_filter: str | None = None, assigned_to: str | None = None) -> list[dict]:
    """Lista tarefas pendentes na fila agent_tasks.

    Args:
        priority_filter: Filtrar por prioridade (critical/high/medium/low). Opcional.
        assigned_to: Filtrar por agente destino. Opcional.
    """
    return get_agent_tasks(status="pending", assigned_to=assigned_to, priority=priority_filter, limit=30)


@tool
def get_agent_run_status(agent_name: str) -> dict:
    """Retorna status do último run de um agente específico.

    Args:
        agent_name: Nome do agente (ex: 'log_scanner', 'security').
    """
    runs = query_agent_runs(limit=5)
    agent_runs = [r for r in runs if agent_name in (r.get("agent_id") or "")]
    if not agent_runs:
        return {"agent": agent_name, "status": "no_recent_runs"}
    last = agent_runs[0]
    return {
        "agent": agent_name,
        "status": last.get("status"),
        "started_at": last.get("started_at"),
        "finished_at": last.get("finished_at"),
        "error": last.get("error"),
    }


@tool
def escalate_to_human(title: str, description: str, severity: str = "medium") -> dict:
    """Escala um problema para intervenção humana via Freshservice.

    Args:
        title: Título do incidente.
        description: Descrição detalhada do problema.
        severity: low | medium | high | critical
    """
    import httpx, os, jwt as pyjwt
    freshservice_url = os.getenv("FRESHSERVICE_SERVICE_URL", "http://freshservice-service:8003")
    jwt_secret = os.getenv("JWT_SECRET", "")
    token = pyjwt.encode(
        {"id": "cto-agent", "role": "admin", "active": True},
        jwt_secret,
        algorithm="HS256",
    )
    priority_map = {"low": 1, "medium": 2, "high": 3, "critical": 4}
    try:
        r = httpx.post(
            f"{freshservice_url}/api/freshservice/tickets",
            json={
                "subject": f"[CTO Agent] {title}",
                "description": description,
                "priority": priority_map.get(severity, 2),
                "source": 2,
                "status": 2,
                "tags": ["cto_agent", "automated"],
            },
            headers={"Authorization": f"Bearer {token}"},
            timeout=15.0,
        )
        r.raise_for_status()
        ticket_id = r.json().get("ticket", {}).get("id")
        log_event("warning", "cto_agent", f"Escalado ao Freshservice: {title}", f"Ticket #{ticket_id}")
        insert_agent_event("human_escalation", "cto", {"title": title, "ticket_id": ticket_id, "severity": severity}, severity)
        return {"escalated": True, "ticket_id": ticket_id}
    except Exception as e:
        log.warning("Falha ao criar ticket Freshservice: %s", e)
        log_event("error", "cto_agent", f"Falha ao escalar: {title}", str(e))
        return {"escalated": False, "error": str(e)}


@tool
def review_pending_proposals(limit: int = 10) -> list[dict]:
    """Busca propostas de melhoria aguardando decisão do CTO.

    Args:
        limit: Máximo de propostas a retornar.
    """
    return query_improvement_proposals(status="pending_cto", limit=limit)


@tool
def approve_proposal(proposal_id: str, reasoning: str, auto_implement: bool = False) -> dict:
    """Aprova uma proposta de melhoria e opcionalmente a marca para implementação automática.

    Args:
        proposal_id: ID da proposta em improvement_proposals.
        reasoning: Justificativa da decisão do CTO.
        auto_implement: Se True, marca para pipeline auto_fix executar.
    """
    new_status = "auto_implementing" if auto_implement else "approved"
    result = update_improvement_proposal(proposal_id, new_status, reason=reasoning)
    insert_agent_event(
        "proposal_approved",
        "cto",
        {"proposal_id": proposal_id, "auto_implement": auto_implement, "reasoning": reasoning[:200]},
        "high" if auto_implement else "medium",
    )
    return result


@tool
def reject_proposal(proposal_id: str, reasoning: str) -> dict:
    """Rejeita uma proposta de melhoria.

    Args:
        proposal_id: ID da proposta.
        reasoning: Justificativa da rejeição.
    """
    result = update_improvement_proposal(proposal_id, "rejected", cto_reasoning=reasoning)
    return result


@tool
def generate_governance_report(period: str = "daily") -> dict:
    """Gera e persiste um relatório de governança ITIL.

    Args:
        period: daily | weekly
    """
    health = get_system_health_summary.invoke({})
    freq_map = get_error_frequency_map(days=1 if period == "daily" else 7)
    proposals = query_improvement_proposals(status="pending_cto", limit=50)
    metrics = {
        "services_down": len(health.get("services_down", [])),
        "containers_exited": len(health.get("containers_exited", [])),
        "pending_proposals": len(proposals),
        "top_error_patterns": sorted(freq_map.items(), key=lambda x: -x[1])[:5],
        "agent_runs_failed": health.get("agent_runs_failed_recent", 0),
    }
    findings = []
    if metrics["services_down"]:
        findings.append(f"{metrics['services_down']} serviço(s) offline.")
    if metrics["containers_exited"]:
        findings.append(f"{metrics['containers_exited']} container(s) parado(s).")
    if metrics["pending_proposals"]:
        findings.append(f"{metrics['pending_proposals']} proposta(s) aguardando revisão do CTO.")
    if metrics["top_error_patterns"]:
        top = metrics["top_error_patterns"][0]
        findings.append(f"Padrão de erro mais frequente: '{top[0]}' ({top[1]}x).")

    recommendations = []
    if metrics["pending_proposals"] > 5:
        recommendations.append("Revisar backlog de propostas de melhoria — acúmulo detectado.")
    if metrics["services_down"]:
        recommendations.append("Investigar serviços offline imediatamente.")
    if not recommendations:
        recommendations.append("Sistema operando dentro dos parâmetros normais.")

    report = insert_governance_report(
        period=period,
        report_date=datetime.now(timezone.utc).date().isoformat(),
        metrics=metrics,
        findings_summary="\n".join(findings) or "Nenhuma anomalia detectada.",
        recommendations="\n".join(recommendations),
        agents_health=health,
    )
    log_event("info", "cto_agent", f"Relatório {period} de governança gerado", f"Métricas: {metrics}")
    return report
