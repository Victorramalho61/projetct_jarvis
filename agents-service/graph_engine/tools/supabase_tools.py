"""Ferramentas de acesso ao Supabase para agentes LangGraph."""
from datetime import datetime, timedelta, timezone

from db import get_supabase


def _db():
    return get_supabase()


def query_app_logs(level: str | None = None, limit: int = 100, since_minutes: int = 120) -> list[dict]:
    since = (datetime.now(timezone.utc) - timedelta(minutes=since_minutes)).isoformat()
    q = (
        _db().table("app_logs")
        .select("id,level,module,message,detail,created_at,trace_id")
        .gte("created_at", since)
        .order("created_at", desc=True)
        .limit(limit)
    )
    if level:
        q = q.eq("level", level)
    return q.execute().data or []


def query_agent_runs(status: str | None = None, agent_id: str | None = None, limit: int = 50) -> list[dict]:
    q = (
        _db().table("agent_runs")
        .select("id,agent_id,pipeline_name,run_type,status,started_at,finished_at,output,error")
        .order("started_at", desc=True)
        .limit(limit)
    )
    if status:
        q = q.eq("status", status)
    if agent_id:
        q = q.eq("agent_id", agent_id)
    return q.execute().data or []


def query_system_checks(system_id: str | None = None, limit: int = 50) -> list[dict]:
    q = (
        _db().table("system_checks")
        .select("id,system_id,status,latency_ms,http_status,detail,checked_at")
        .order("checked_at", desc=True)
        .limit(limit)
    )
    if system_id:
        q = q.eq("system_id", system_id)
    return q.execute().data or []


def query_monitored_systems(enabled: bool = True) -> list[dict]:
    q = (
        _db().table("monitored_systems")
        .select("id,name,description,url,system_type,check_interval_minutes,enabled,consecutive_down_count")
        .eq("enabled", enabled)
    )
    return q.execute().data or []


def insert_security_alert(severity: str, category: str, description: str, affected_resource: str | None = None) -> dict:
    res = _db().table("security_alerts").insert({
        "severity": severity,
        "category": category,
        "description": description,
        "affected_resource": affected_resource,
        "status": "open",
    }).execute()
    return res.data[0] if res.data else {}


def insert_quality_metric(metric_name: str, metric_value: float, unit: str | None = None, service: str | None = None, metadata: dict | None = None) -> dict:
    res = _db().table("quality_metrics").insert({
        "metric_name": metric_name,
        "metric_value": metric_value,
        "unit": unit,
        "service": service,
        "metadata": metadata or {},
    }).execute()
    return res.data[0] if res.data else {}


def query_quality_metrics(metric_name: str | None = None, service: str | None = None, since_hours: int = 24, limit: int = 100) -> list[dict]:
    since = (datetime.now(timezone.utc) - timedelta(hours=since_hours)).isoformat()
    q = _db().table("quality_metrics").select("*").gte("measured_at", since).order("measured_at", desc=True).limit(limit)
    if metric_name:
        q = q.eq("metric_name", metric_name)
    if service:
        q = q.eq("service", service)
    return q.execute().data or []


def insert_change_request(
    title: str,
    description: str,
    change_type: str,
    priority: str,
    requested_by: str,
    rollback_plan: str | None = None,
    sla_deadline: str | None = None,
    context: dict | None = None,
) -> dict:
    payload: dict = {
        "title": title,
        "description": description,
        "change_type": change_type,
        "priority": priority,
        "requested_by": requested_by,
        "rollback_plan": rollback_plan,
        "status": "pending",
    }
    if sla_deadline:
        payload["sla_deadline"] = sla_deadline
    if context:
        payload["context"] = context
    res = _db().table("change_requests").insert(payload).execute()
    return res.data[0] if res.data else {}


def update_change_request(request_id: str, status: str, approved_by: str | None = None) -> dict:
    payload: dict = {"status": status, "updated_at": datetime.now(timezone.utc).isoformat()}
    if approved_by:
        payload["approved_by"] = approved_by
    if status == "implementing":
        payload["implemented_at"] = datetime.now(timezone.utc).isoformat()
    if status == "validated":
        payload["validated_at"] = datetime.now(timezone.utc).isoformat()
    res = _db().table("change_requests").update(payload).eq("id", request_id).execute()
    return res.data[0] if res.data else {}


def query_change_requests(status: str | None = None, limit: int = 50) -> list[dict]:
    q = _db().table("change_requests").select("*").order("created_at", desc=True).limit(limit)
    if status:
        q = q.eq("status", status)
    return q.execute().data or []


def insert_improvement_proposal(
    source_agent: str,
    proposal_type: str,
    title: str,
    description: str = "",
    proposed_action: str = "",
    priority: str = "medium",
    estimated_effort: str = "",
    risk: str = "low",
    auto_implementable: bool = False,
    affected_files: list | None = None,
    # Campos novos (v2)
    evidence: str = "",
    proposed_fix: str | None = None,
    sql_proposal: str | None = None,
    expected_gain: str = "",
    business_value: str = "",
    motivational_note: str = "",
) -> dict:
    payload: dict = {
        "source_agent": source_agent,
        "proposal_type": proposal_type,
        "title": title,
        "description": description,
        "proposed_action": proposed_action,
        "priority": priority,
        "estimated_effort": estimated_effort,
        "risk": risk,
        "auto_implementable": auto_implementable,
        "affected_files": affected_files or [],
        "validation_status": "pending",
    }
    if evidence:
        payload["evidence"] = evidence
    if proposed_fix is not None:
        payload["proposed_fix"] = proposed_fix
    if sql_proposal is not None:
        payload["sql_proposal"] = sql_proposal
    if expected_gain:
        payload["expected_gain"] = expected_gain
    if business_value:
        payload["business_value"] = business_value
    if motivational_note:
        payload["motivational_note"] = motivational_note

    # Deduplicação: evita inserir proposta com mesmo título em status não-terminal
    _NON_TERMINAL = ["pending", "pending_cto", "approved", "auto_implementing"]
    try:
        existing = (
            _db().table("improvement_proposals")
            .select("id,validation_status")
            .ilike("title", title)
            .in_("validation_status", _NON_TERMINAL)
            .limit(1)
            .execute()
            .data
        )
        if existing:
            return existing[0]
    except Exception:
        pass

    res = _db().table("improvement_proposals").insert(payload).execute()
    return res.data[0] if res.data else {}


def query_improvement_proposals(status: str | None = None, limit: int = 50) -> list[dict]:
    q = _db().table("improvement_proposals").select("*").order("created_at", desc=True).limit(limit)
    if status and status != "all":
        q = q.eq("validation_status", status)
    return q.execute().data or []


def update_improvement_proposal(proposal_id: str, validation_status: str, reason: str | None = None) -> dict:
    payload: dict = {"validation_status": validation_status}
    if reason:
        payload["rejection_reason"] = reason
    if validation_status == "applied":
        payload["applied"] = True
        payload["applied_at"] = datetime.now(timezone.utc).isoformat()
    res = _db().table("improvement_proposals").update(payload).eq("id", proposal_id).execute()
    return res.data[0] if res.data else {}


def send_agent_message(
    from_agent: str,
    to_agent: str,
    message: str = "",
    context: dict | None = None,
    thread_id: str | None = None,
    # legado � aceita content dict para compatibilidade
    content: dict | None = None,
) -> dict:
    res = _db().table("agent_messages").insert({
        "from_agent": from_agent,
        "to_agent": to_agent,
        "message": message or (str(content) if content else ""),
        "context": context or content or {},
        "thread_id": thread_id,
        "status": "pending",
    }).execute()
    return res.data[0] if res.data else {}


def send_human_notification(from_agent: str, message: str, context: dict | None = None) -> dict:
    """Envia notifica��o diretamente para o humano (aparece no inbox do frontend)."""
    return send_agent_message(
        from_agent=from_agent,
        to_agent="human",
        message=message,
        context=context or {},
    )


def get_pending_messages(agent_name: str) -> list[dict]:
    res = _db().table("agent_messages").select("*").eq("to_agent", agent_name).eq("status", "pending").order("created_at").execute()
    return res.data or []


def get_human_messages(limit: int = 50, unread_only: bool = False) -> list[dict]:
    """Busca mensagens direcionadas ao humano para o frontend."""
    q = _db().table("agent_messages").select("*").eq("to_agent", "human").order("created_at", desc=True).limit(limit)
    if unread_only:
        q = q.eq("status", "pending")
    return q.execute().data or []


def mark_message_read(message_id: str) -> None:
    _db().table("agent_messages").update({
        "status": "read",
        "read_at": datetime.now(timezone.utc).isoformat(),
    }).eq("id", message_id).execute()


def mark_message_processed(message_id: str) -> None:
    _db().table("agent_messages").update({"status": "processed"}).eq("id", message_id).execute()


def insert_agent_into_db(name: str, description: str, agent_type: str, schedule_type: str, schedule_config: dict, config: dict | None = None) -> dict:
    res = _db().table("agents").insert({
        "name": name,
        "description": description,
        "agent_type": agent_type,
        "schedule_type": schedule_type,
        "schedule_config": schedule_config,
        "config": config or {},
        "enabled": True,
    }).execute()
    return res.data[0] if res.data else {}


def query_agents(enabled: bool | None = None) -> list[dict]:
    q = _db().table("agents").select("*").order("created_at", desc=True)
    if enabled is not None:
        q = q.eq("enabled", enabled)
    return q.execute().data or []


def log_event(level: str, module: str, message: str, detail: str | None = None) -> None:
    _db().table("app_logs").insert({
        "level": level,
        "module": module,
        "message": message,
        "detail": detail,
    }).execute()


# -- Event Bus ----------------------------------------------------------------

def insert_agent_event(event_type: str, source: str, payload: dict, priority: str = "medium") -> dict:
    res = _db().table("agent_events").insert({
        "event_type": event_type,
        "source": source,
        "payload": payload,
        "priority": priority,
        "processed": False,
    }).execute()
    return res.data[0] if res.data else {}


def query_agent_events(event_type: str | None = None, processed: bool | None = None, priority: str | None = None, limit: int = 50) -> list[dict]:
    q = _db().table("agent_events").select("*").order("created_at", desc=True).limit(limit)
    if event_type:
        q = q.eq("event_type", event_type)
    if processed is not None:
        q = q.eq("processed", processed)
    if priority:
        q = q.eq("priority", priority)
    return q.execute().data or []


def get_pending_agent_events(limit: int = 50) -> list[dict]:
    res = (
        _db().table("agent_events")
        .select("*")
        .eq("processed", False)
        .order("created_at")
        .limit(limit)
        .execute()
    )
    return res.data or []


def mark_agent_event_processed(event_id: str) -> None:
    _db().table("agent_events").update({"processed": True}).eq("id", event_id).execute()


# -- Agent Tasks ---------------------------------------------------------------

def insert_agent_task(
    assigned_to: str,
    task_description: str,
    priority: str = "medium",
    context: dict | None = None,
    dispatched_by: str = "cto",
) -> dict:
    res = _db().table("agent_tasks").insert({
        "dispatched_by": dispatched_by,
        "assigned_to": assigned_to,
        "task_description": task_description,
        "priority": priority,
        "context": context or {},
        "status": "pending",
    }).execute()
    return res.data[0] if res.data else {}


def update_agent_task(task_id: str, status: str, result: dict | None = None) -> dict:
    payload: dict = {"status": status}
    if status == "running":
        payload["started_at"] = datetime.now(timezone.utc).isoformat()
    if status in ("completed", "failed"):
        payload["completed_at"] = datetime.now(timezone.utc).isoformat()
    if result is not None:
        payload["result"] = result
    res = _db().table("agent_tasks").update(payload).eq("id", task_id).execute()
    return res.data[0] if res.data else {}


def get_agent_tasks(
    status: str | None = None,
    assigned_to: str | None = None,
    priority: str | None = None,
    limit: int = 50,
) -> list[dict]:
    q = _db().table("agent_tasks").select("*").order("created_at", desc=True).limit(limit)
    if status:
        q = q.eq("status", status)
    if assigned_to:
        q = q.eq("assigned_to", assigned_to)
    if priority:
        q = q.eq("priority", priority)
    return q.execute().data or []


# -- Deployment Windows --------------------------------------------------------

def get_active_deployment_window() -> dict | None:
    res = (
        _db().table("deployment_windows")
        .select("*")
        .eq("active", True)
        .order("started_at", desc=True)
        .limit(1)
        .execute()
    )
    return res.data[0] if res.data else None


def insert_deployment_window(reason: str, started_by: str, expected_end: str | None = None) -> dict:
    res = _db().table("deployment_windows").insert({
        "active": True,
        "reason": reason,
        "started_by": started_by,
        "expected_end": expected_end,
    }).execute()
    return res.data[0] if res.data else {}


def close_deployment_window(window_id: str) -> dict:
    res = _db().table("deployment_windows").update({
        "active": False,
        "ended_at": datetime.now(timezone.utc).isoformat(),
    }).eq("id", window_id).execute()
    return res.data[0] if res.data else {}


def is_deployment_active() -> bool:
    return get_active_deployment_window() is not None


# -- Correction Proposals ------------------------------------------------------

def insert_correction_proposal(
    description: str,
    proposed_fix: str,
    root_cause: str | None = None,
    effort_estimate: str = "medium",
    source_log_id: str | None = None,
    pipeline_run_id: str | None = None,
    source_agent: str = "auto_fix_pipeline",
) -> dict:
    res = _db().table("correction_proposals").insert({
        "source_log_id": source_log_id,
        "pipeline_run_id": pipeline_run_id,
        "source_agent": source_agent,
        "description": description,
        "proposed_fix": proposed_fix,
        "root_cause": root_cause,
        "effort_estimate": effort_estimate,
        "validation_status": "pending",
        "applied": False,
    }).execute()
    return res.data[0] if res.data else {}


def update_correction_proposal(
    proposal_id: str,
    validation_status: str,
    applied: bool = False,
    rejected_reason: str | None = None,
) -> dict:
    payload: dict = {"validation_status": validation_status, "applied": applied}
    if applied:
        payload["applied_at"] = datetime.now(timezone.utc).isoformat()
    if rejected_reason:
        payload["rejected_reason"] = rejected_reason
    res = _db().table("correction_proposals").update(payload).eq("id", proposal_id).execute()
    return res.data[0] if res.data else {}


def get_correction_proposals(validation_status: str | None = None, limit: int = 50) -> list[dict]:
    q = _db().table("correction_proposals").select("*").order("created_at", desc=True).limit(limit)
    if validation_status:
        q = q.eq("validation_status", validation_status)
    return q.execute().data or []


# -- Governance Reports --------------------------------------------------------

def insert_governance_report(
    period: str,
    report_date: str,
    metrics: dict,
    findings_summary: str,
    recommendations: str,
    agents_health: dict | None = None,
) -> dict:
    res = _db().table("governance_reports").insert({
        "period": period,
        "report_date": report_date,
        "metrics": metrics,
        "findings_summary": findings_summary,
        "recommendations": recommendations,
        "agents_health": agents_health or {},
        "generated_by": "cto_agent",
    }).execute()
    return res.data[0] if res.data else {}


def get_latest_governance_report(period: str = "daily") -> dict | None:
    res = (
        _db().table("governance_reports")
        .select("*")
        .eq("period", period)
        .order("report_date", desc=True)
        .limit(1)
        .execute()
    )
    return res.data[0] if res.data else None


# -- Log Intelligence helpers --------------------------------------------------

def query_logs_window(days: int = 7, level: str | None = None, service: str | None = None, limit: int = 2000) -> list[dict]:
    since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    q = _db().table("app_logs").select("*").gte("created_at", since).order("created_at", desc=True).limit(limit)
    if level:
        q = q.eq("level", level)
    if service:
        q = q.eq("module", service)
    return q.execute().data or []


def get_error_frequency_map(days: int = 7, limit: int = 2000) -> dict[str, int]:
    """Retorna mapa de fingerprint ? contagem de erros nos �ltimos N dias."""
    import re as _re
    logs = query_logs_window(days=days, level="error", limit=limit)
    freq: dict[str, int] = {}
    for entry in logs:
        msg = entry.get("message", "")
        # normaliza UUIDs e n�meros para criar fingerprint
        fp = _re.sub(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", "<uuid>", msg, flags=_re.I)
        fp = _re.sub(r"\b\d+\b", "<n>", fp)
        module = entry.get("module", "unknown")
        key = f"{module}|{fp[:100]}"
        freq[key] = freq.get(key, 0) + 1
    return freq
