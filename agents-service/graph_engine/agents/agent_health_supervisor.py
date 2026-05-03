"""
Agent Health Supervisor — monitora se todos os agentes estão rodando conforme esperado.
Consulta agent_runs para cada agente registrado, classifica saúde e reporta ao CTO.
Roda no pipeline 'monitoring' (a cada 15 minutos).
"""
import logging
from datetime import datetime, timezone, timedelta

logger = logging.getLogger(__name__)

# Todos os agentes registrados e seus intervalos esperados máximos (em horas).
# Se o agente não rodou dentro desse período, é considerado 'stale'.
_AGENT_EXPECTED_INTERVALS: dict[str, float] = {
    # Pipelines frequentes
    "uptime":                0.5,   # monitoring 15min
    "quality":               0.5,
    "docker_intel":          0.5,
    "backend_agent":         0.5,
    "security":              1.0,   # security 30min
    "code_security":         1.0,
    "cicd_monitor":          0.25,  # cicd 5min
    # Pipelines de médio prazo
    "log_scanner":           2.0,
    "log_improver":          2.0,
    "log_intelligence":      4.0,
    "fix_validator":         4.0,
    "infrastructure":        4.0,
    "db_dba_agent":          5.0,   # dba 4h
    "quality_code_backend":  6.0,
    "quality_code_frontend": 6.0,
    "integration_validator": 6.0,
    "change_validator":      6.0,
    "api_agent":             6.0,
    "scheduling":            6.0,
    "automation":            6.0,
    # Pipelines diários
    "opportunity_scout":     26.0,  # governance diário
    "log_strategic_advisor": 26.0,
    "change_mgmt":           26.0,
    "itil_version":          26.0,
    "docs":                  26.0,
    "quality_validator":     26.0,
    "evolution_agent":       26.0,  # evolution diário
    "frontend_agent":        26.0,
    # Supervisor de proposals
    "proposal_supervisor":   26.0,
    # LLM Manager — monitora saúde e SLA dos LLMs
    "llm_manager_agent":     26.0,
    # Monitoring pipeline agents
    "agent_health_supervisor": 0.25,  # próprio — monitora a si mesmo
    # CTO roda em todos os pipelines
    "cto":                   0.5,
}

_STATUS_NEVER   = "never_run"
_STATUS_OK      = "ok"
_STATUS_STALE   = "stale"       # não rodou no intervalo esperado
_STATUS_ERROR   = "error"       # última run falhou
_STATUS_FAILING = "failing"     # múltiplas falhas consecutivas


def _classify_agent(agent_name: str, runs: list[dict]) -> dict:
    """Classifica a saúde de um agente com base em seus últimos runs."""
    if not runs:
        return {"agent": agent_name, "status": _STATUS_NEVER, "last_run": None, "last_status": None, "consecutive_errors": 0}

    last_run = runs[0]
    last_status = last_run.get("status", "unknown")
    last_time_str = last_run.get("finished_at") or last_run.get("started_at")

    # Contagem de erros consecutivos
    consecutive_errors = 0
    for run in runs:
        if run.get("status") == "error":
            consecutive_errors += 1
        else:
            break

    # Verificar se está dentro do intervalo esperado
    expected_hours = _AGENT_EXPECTED_INTERVALS.get(agent_name, 26.0)
    is_stale = False
    if last_time_str:
        try:
            last_time = datetime.fromisoformat(last_time_str.replace("Z", "+00:00"))
            if last_time.tzinfo is None:
                last_time = last_time.replace(tzinfo=timezone.utc)
            age_hours = (datetime.now(timezone.utc) - last_time).total_seconds() / 3600
            is_stale = age_hours > expected_hours
        except Exception:
            is_stale = True

    if consecutive_errors >= 3:
        health_status = _STATUS_FAILING
    elif last_status == "error":
        health_status = _STATUS_ERROR
    elif is_stale:
        health_status = _STATUS_STALE
    else:
        health_status = _STATUS_OK

    return {
        "agent": agent_name,
        "status": health_status,
        "last_run": last_time_str,
        "last_status": last_status,
        "consecutive_errors": consecutive_errors,
        "expected_interval_hours": expected_hours,
    }


def run(state: dict) -> dict:
    from db import get_supabase
    from graph_engine.tools.supabase_tools import (
        send_agent_message,
        send_human_notification,
        insert_agent_event,
    )

    findings = []
    decisions = []
    db = get_supabase()

    agent_names = list(_AGENT_EXPECTED_INTERVALS.keys())
    health_map: dict[str, dict] = {}

    # Buscar últimos runs de cada agente — uma query por vez (Supabase não tem OR em FK)
    for agent_name in agent_names:
        try:
            rows = (
                db.table("agent_runs")
                .select("agent_id,status,started_at,finished_at,error,pipeline_name,run_type")
                .or_(f"pipeline_name.eq.{agent_name},run_type.eq.agent")
                .order("started_at", desc=True)
                .limit(5)
                .execute()
                .data or []
            )
            # Filtrar runs que realmente pertencem a esse agente
            # Para agents reais: run_type='agent' e agent_id corresponde
            # Para pipelines: usa pipeline_name
            agent_rows = [r for r in rows if r.get("pipeline_name") == agent_name]
            if not agent_rows:
                # Tentar por agentes reais cadastrados na tabela agents
                try:
                    agent_record = (
                        db.table("agents")
                        .select("id")
                        .eq("name", agent_name)
                        .limit(1)
                        .execute()
                        .data
                    )
                    if agent_record:
                        agent_id = agent_record[0]["id"]
                        agent_rows = (
                            db.table("agent_runs")
                            .select("agent_id,status,started_at,finished_at,error")
                            .eq("agent_id", agent_id)
                            .order("started_at", desc=True)
                            .limit(5)
                            .execute()
                            .data or []
                        )
                except Exception:
                    pass
            health_map[agent_name] = _classify_agent(agent_name, agent_rows)
        except Exception as exc:
            logger.warning("agent_health_supervisor: erro ao checar %s: %s", agent_name, exc)
            health_map[agent_name] = {"agent": agent_name, "status": "unknown", "error": str(exc)}

    # Sumarizar
    counts = {s: 0 for s in [_STATUS_OK, _STATUS_STALE, _STATUS_ERROR, _STATUS_FAILING, _STATUS_NEVER, "unknown"]}
    for info in health_map.values():
        counts[info.get("status", "unknown")] = counts.get(info.get("status", "unknown"), 0) + 1

    agents_ok      = [n for n, i in health_map.items() if i["status"] == _STATUS_OK]
    agents_stale   = [n for n, i in health_map.items() if i["status"] == _STATUS_STALE]
    agents_error   = [n for n, i in health_map.items() if i["status"] == _STATUS_ERROR]
    agents_failing = [n for n, i in health_map.items() if i["status"] == _STATUS_FAILING]
    agents_never   = [n for n, i in health_map.items() if i["status"] == _STATUS_NEVER]

    total = len(agent_names)
    findings.append({
        "agent": "agent_health_supervisor",
        "total_agents": total,
        "ok": len(agents_ok),
        "stale": len(agents_stale),
        "error": len(agents_error),
        "failing": len(agents_failing),
        "never_run": len(agents_never),
        "health_map": health_map,
    })

    # Montar relatório
    now_str = datetime.now(timezone.utc).strftime("%d/%m/%Y %H:%M UTC")
    lines = [f"📋 RELATÓRIO DE SAÚDE DOS AGENTES — {now_str}", ""]
    lines.append(f"✅ OK: {len(agents_ok)}/{total}  |  ⚠️ Atrasados: {len(agents_stale)}  |  ❌ Erro: {len(agents_error)}  |  🔴 Falhando: {len(agents_failing)}  |  🆕 Nunca rodou: {len(agents_never)}")
    lines.append("")

    if agents_failing:
        lines.append(f"🔴 FALHANDO REPETIDAMENTE ({len(agents_failing)}):")
        for n in agents_failing:
            info = health_map[n]
            lines.append(f"  • {n} — {info['consecutive_errors']} erros consecutivos, último: {info.get('last_run', 'N/A')}")

    if agents_error:
        lines.append(f"\n❌ ÚLTIMO RUN COM ERRO ({len(agents_error)}):")
        for n in agents_error:
            lines.append(f"  • {n} — último: {health_map[n].get('last_run', 'N/A')}")

    if agents_stale:
        lines.append(f"\n⚠️ NÃO RODA HÁ MAIS TEMPO QUE O ESPERADO ({len(agents_stale)}):")
        for n in agents_stale:
            info = health_map[n]
            lines.append(f"  • {n} — esperado a cada {info['expected_interval_hours']}h, último: {info.get('last_run', 'Nunca')}")

    if agents_never:
        lines.append(f"\n🆕 NUNCA RODARAM ({len(agents_never)}):")
        for n in agents_never:
            lines.append(f"  • {n}")

    if agents_ok:
        lines.append(f"\n✅ OPERACIONAIS: {', '.join(agents_ok)}")

    report = "\n".join(lines)

    # SLA: 100% dos agentes saudáveis
    health_sla_pct = round(100 * len(agents_ok) / max(total, 1), 1)
    try:
        from graph_engine.tools.sla_tracker import report_sla
        report_sla("agent_health_supervisor", "agents_healthy_pct", health_sla_pct)
        report_sla("agent_health_supervisor", "failing_agents_count", len(agents_failing))
        report_sla("agent_health_supervisor", "stale_agents_count", len(agents_stale))
    except Exception:
        pass

    # ── AUTO-RECOVERY ──────────────────────────────────────────────────────────
    # Para agentes falhando (≥3 erros consecutivos): tenta recuperação automática
    recovered = []
    recovery_failed = []
    for agent_name in agents_failing + agents_stale:
        # Identifica qual pipeline contém este agente
        try:
            from services.agent_runner import _PIPELINE_AGENTS
            target_pipeline = next(
                (p for p, agents in _PIPELINE_AGENTS.items() if agent_name in agents),
                None
            )
            if target_pipeline:
                import asyncio, concurrent.futures
                from services.agent_runner import run_langgraph_pipeline
                try:
                    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as ex:
                        future = ex.submit(asyncio.run, run_langgraph_pipeline(target_pipeline))
                        future.result(timeout=120)
                    recovered.append(agent_name)
                    decisions.append(f"Auto-recovery: pipeline '{target_pipeline}' re-executado para {agent_name}")
                except Exception as exc:
                    recovery_failed.append(agent_name)
                    decisions.append(f"Auto-recovery FALHOU {agent_name}: {str(exc)[:80]}")
            else:
                recovery_failed.append(agent_name)
        except Exception as exc:
            logger.warning("agent_health_supervisor: recovery %s: %s", agent_name, exc)
            recovery_failed.append(agent_name)

    if recovered:
        findings.append({"type": "auto_recovery_success", "agents": recovered, "count": len(recovered)})
    if recovery_failed:
        findings.append({"type": "auto_recovery_failed", "agents": recovery_failed, "count": len(recovery_failed)})

    # ── HANDOFF PARA EVOLUTION ──────────────────────────────────────────────────
    # Reporta problemas e gaps ao evolution_agent para que ele proponha melhorias
    if agents_failing or agents_error or recovery_failed:
        try:
            gaps_msg = (
                f"PROBLEMAS E GAPS DETECTADOS — {len(agents_failing + agents_error)} agentes com falha:\n"
                + "\n".join(f"• {n}: {health_map.get(n, {}).get('last_status','?')} | erro: {str(health_map.get(n, {}).get('error','N/A'))[:100]}" for n in (agents_failing + agents_error)[:5])
                + f"\nAuto-recovery falhou em: {', '.join(recovery_failed) or 'nenhum'}\n"
                f"Solicito que você proponha melhorias de resiliência para esses agentes."
            )
            send_agent_message(
                from_agent="agent_health_supervisor",
                to_agent="evolution_agent",
                message=gaps_msg,
                context={"failing": agents_failing, "error": agents_error, "recovery_failed": recovery_failed},
            )
            decisions.append("Gaps e problemas reportados ao evolution_agent")
        except Exception as exc:
            logger.warning("agent_health_supervisor: handoff evolution: %s", exc)

    # Determinar prioridade do alerta
    has_critical = bool(agents_failing or agents_error)
    priority = "high" if has_critical else ("medium" if agents_stale else "low")

    # Adiciona info de SLA e recovery ao relatório
    report += f"\n\n📊 SLA de Saúde: {health_sla_pct}% (meta: 100%)"
    if recovered:
        report += f"\n♻️ Auto-recovery bem-sucedido: {', '.join(recovered)}"
    if recovery_failed:
        report += f"\n⚠️ Auto-recovery falhou: {', '.join(recovery_failed)}"

    # Sempre notifica o CTO com relatório completo
    try:
        send_agent_message(
            from_agent="agent_health_supervisor",
            to_agent="cto",
            message=report,
            context={
                "health_map": health_map,
                "counts": counts,
                "sla_pct": health_sla_pct,
                "recovered": recovered,
                "recovery_failed": recovery_failed,
            },
        )
        decisions.append("Relatório de saúde enviado ao CTO")
    except Exception as exc:
        logger.error("agent_health_supervisor: erro ao enviar ao CTO: %s", exc)

    # Notifica o humano apenas quando há problemas
    if has_critical or agents_stale or agents_never:
        try:
            send_human_notification(
                from_agent="agent_health_supervisor",
                message=report,
                context={
                    "failing": agents_failing,
                    "error": agents_error,
                    "stale": agents_stale,
                    "never_run": agents_never,
                    "ok_count": len(agents_ok),
                    "total": total,
                    "recovered": recovered,
                    "sla_pct": health_sla_pct,
                },
            )
            decisions.append("Notificação enviada ao humano (problemas detectados)")
        except Exception as exc:
            logger.warning("agent_health_supervisor: erro ao notificar humano: %s", exc)

    # Evento crítico se houver agentes falhando
    if agents_failing:
        try:
            insert_agent_event(
                event_type="agents_health_critical",
                source="agent_health_supervisor",
                payload={
                    "failing_agents": agents_failing,
                    "error_agents": agents_error,
                    "recovered": recovered,
                    "sla_pct": health_sla_pct,
                },
                priority="critical",
            )
        except Exception as exc:
            logger.warning("agent_health_supervisor: erro ao inserir evento: %s", exc)

    # Atualiza agent_health no state para o CTO usar no dashboard
    agent_health_state = {
        name: info["status"] for name, info in health_map.items()
    }

    return {
        "findings": findings,
        "decisions": decisions,
        "agent_health": agent_health_state,
        "context": {
            "agent_health_supervisor_run": datetime.now(timezone.utc).isoformat(),
            "health_summary": counts,
        },
        "next_agent": "END",
    }


def build():
    from graph_engine.agents.base import build_deterministic_agent
    return build_deterministic_agent(run)
