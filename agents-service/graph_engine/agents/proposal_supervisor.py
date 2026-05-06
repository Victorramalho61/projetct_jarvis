"""
Proposal Supervisor — engenheiro de sistemas sênior autônomo.
Meta: 100% das proposals aprovadas por humanos executadas com sucesso.

Ciclo de trabalho:
1. Busca todas as proposals com validation_status='approved' e applied=False
2. Para cada uma, classifica se é auto-executável ou precisa de handoff
3. Tenta implementar as auto-executáveis (SQL, config, VACUUM, ANALYZE)
4. Envia as demais ao agente responsável via mensagem ou evento
5. Consulta o LLM para verificar falsos positivos e recomendar próximos passos
6. Reporta métricas e progresso ao CTO
"""
import json
import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

# Mapeamento tipo de proposal → agente responsável pela implementação
_TYPE_TO_AGENT = {
    "index":          "db_dba_agent",
    "vacuum":         "db_dba_agent",
    "config":         "infrastructure",
    "infrastructure": "infrastructure",
    "code_fix":       "fix_validator",
    "refactoring":    "fix_validator",
    "new_feature":    "evolution_agent",
    "new_agent":      "evolution_agent",
    "automation":     "automation",
    "process":        "change_mgmt",
    "monitoring":     "uptime",
    "container_stats":"docker_intel",
    "container_update":"docker_intel",
}

_AUTO_EXECUTABLE_TYPES = {"index", "vacuum"}


def _get_metrics(db) -> dict:
    """Calcula métricas de execução de proposals."""
    total = db.table("improvement_proposals").select("id", count="exact").execute().count or 0
    approved = db.table("improvement_proposals").select("id", count="exact").eq("validation_status", "approved").execute().count or 0
    in_progress = db.table("improvement_proposals").select("id", count="exact").eq("validation_status", "auto_implementing").execute().count or 0
    applied = db.table("improvement_proposals").select("id", count="exact").eq("validation_status", "applied").execute().count or 0
    failed = db.table("improvement_proposals").select("id", count="exact").eq("validation_status", "implementation_failed").execute().count or 0
    pending = db.table("improvement_proposals").select("id", count="exact").eq("validation_status", "pending").execute().count or 0
    pending_cto = db.table("improvement_proposals").select("id", count="exact").eq("validation_status", "pending_cto").execute().count or 0
    return {
        "total": total,
        "pending": pending + pending_cto,
        "approved_waiting": approved,
        "in_progress": in_progress,
        "applied_success": applied,
        "implementation_failed": failed,
        "execution_rate_pct": round(100 * applied / max(approved + in_progress + applied + failed, 1), 1),
        "failure_rate_pct": round(100 * failed / max(approved + in_progress + applied + failed, 1), 1),
    }


def _try_auto_execute(proposal: dict, decisions: list, db) -> bool:
    """Tenta executar automaticamente proposals de SQL (index/vacuum). Retorna True se executou."""
    sql = proposal.get("sql_proposal", "")
    ptype = proposal.get("proposal_type", "")
    if ptype not in _AUTO_EXECUTABLE_TYPES or not sql:
        return False

    sql_upper = sql.strip().upper()
    safe_prefixes = ("ANALYZE", "CREATE INDEX CONCURRENTLY", "REINDEX CONCURRENTLY", "VACUUM ANALYZE")
    if not any(sql_upper.startswith(p) for p in safe_prefixes):
        return False

    try:
        from graph_engine.tools.db_admin_tools import execute_safe_sql
        result = execute_safe_sql(sql)
        db.table("improvement_proposals").update({
            "validation_status": "applied",
            "applied": True,
            "applied_at": datetime.now(timezone.utc).isoformat(),
            "implementation_error": None,
        }).eq("id", proposal["id"]).execute()
        decisions.append(f"Auto-executada proposal '{proposal.get('title','')[:60]}': {result[:80]}")
        logger.info("proposal_supervisor: auto-exec OK — %s", proposal["id"])
        return True
    except Exception as exc:
        db.table("improvement_proposals").update({
            "validation_status": "implementation_failed",
            "applied": False,
            "implementation_error": str(exc)[:500],
        }).eq("id", proposal["id"]).execute()
        decisions.append(f"Auto-exec FALHOU '{proposal.get('title','')[:60]}': {str(exc)[:80]}")
        logger.error("proposal_supervisor: auto-exec FALHOU %s: %s", proposal["id"], exc)
        return True  # processou (com falha)


def _execute_proposal_with_llm(proposal: dict, decisions: list, db) -> bool:
    """
    Gera plano de implementação com LLM e tenta executar automaticamente.
    Para proposals aprovadas por humano — executa com maior autonomia.
    Retorna True se processou (sucesso ou falha), False se deve tentar outro método.
    """
    from graph_engine.tools.code_generator import generate_implementation_plan, save_plan_to_proposal

    pid = proposal["id"]
    title = proposal.get("title", "")

    try:
        plan = generate_implementation_plan(
            proposal_title=title,
            proposal_description=proposal.get("description", ""),
            proposal_type=proposal.get("proposal_type", ""),
            proposed_action=proposal.get("proposed_action", ""),
            proposed_fix=proposal.get("proposed_fix", ""),
            timeout_s=45,
        )

        if plan.get("plan_summary", "").startswith("Falha"):
            return False

        # Salva o plano na proposal
        save_plan_to_proposal(pid, plan)
        decisions.append(f"Plano LLM gerado: {title[:50]}")

        # Tenta auto-execução se o LLM marcou como seguro
        if plan.get("can_auto_execute") and plan.get("auto_execute_sql"):
            sql = plan["auto_execute_sql"]
            sql_upper = sql.strip().upper()
            safe_prefixes = ("ANALYZE", "CREATE INDEX CONCURRENTLY", "REINDEX CONCURRENTLY", "VACUUM")
            if any(sql_upper.startswith(p) for p in safe_prefixes):
                try:
                    from graph_engine.tools.db_admin_tools import execute_safe_sql
                    result = execute_safe_sql(sql)
                    db.table("improvement_proposals").update({
                        "validation_status": "applied",
                        "applied": True,
                        "applied_at": datetime.now(timezone.utc).isoformat(),
                        "implementation_error": None,
                    }).eq("id", pid).execute()
                    decisions.append(f"Executada via plano LLM: {title[:50]} → {result[:60]}")
                    logger.info("proposal_supervisor: exec LLM OK %s", pid)
                    return True
                except Exception as exc:
                    db.table("improvement_proposals").update({
                        "validation_status": "implementation_failed",
                        "applied": False,
                        "implementation_error": f"SQL do plano LLM falhou: {str(exc)[:300]}",
                    }).eq("id", pid).execute()
                    decisions.append(f"Exec LLM FALHOU: {title[:40]}: {str(exc)[:60]}")
                    return True

        return False  # plano gerado mas não auto-executável — vai para routing

    except Exception as exc:
        logger.warning("proposal_supervisor: exec LLM %s: %s", pid, exc)
        return False


def _route_to_agent(proposal: dict, decisions: list, db=None) -> None:
    """Envia a proposal (com plano de implementação) para o agente responsável e muda status."""
    from graph_engine.tools.supabase_tools import send_agent_message
    ptype = proposal.get("proposal_type", "code_fix")
    target = _TYPE_TO_AGENT.get(ptype, "fix_validator")
    plan_info = (proposal.get("proposed_fix") or "")[:300]
    try:
        send_agent_message(
            from_agent="proposal_supervisor",
            to_agent=target,
            message=(
                f"Proposal APROVADA POR HUMANO — execução obrigatória.\n"
                f"Título: {proposal.get('title','')}\n"
                f"Tipo: {ptype} | Prioridade: {proposal.get('priority','medium')}\n"
                f"Ação: {proposal.get('proposed_action','')}\n"
                f"Plano de implementação:\n{plan_info}\n"
                f"ID: {proposal['id']}\n"
                f"AÇÃO REQUERIDA: implemente esta proposta e marque como aplicada."
            ),
            context={
                "proposal_id": proposal["id"],
                "proposal_type": ptype,
                "priority": proposal.get("priority", "medium"),
                "mandatory": True,
                "approved_by_human": True,
            },
        )
        decisions.append(f"Proposal aprovada → {target}: {proposal.get('title','')[:50]}")
    except Exception as exc:
        logger.warning("proposal_supervisor: handoff %s → %s: %s", proposal["id"], target, exc)

    # Muda status para auto_implementing para sair da fila de "aprovadas aguardando"
    if db:
        try:
            db.table("improvement_proposals").update({
                "validation_status": "auto_implementing",
                "implementation_error": f"Roteada para agente '{target}' em {datetime.now(timezone.utc).isoformat()}",
            }).eq("id", proposal["id"]).execute()
        except Exception as exc:
            logger.warning("proposal_supervisor: update status após routing %s: %s", proposal["id"], exc)

    # Notifica quality_validator para validar pós-implementação
    try:
        send_agent_message(
            from_agent="proposal_supervisor",
            to_agent="quality_validator",
            message=(
                f"QA REQUERIDO PÓS-IMPLEMENTAÇÃO\n"
                f"Proposta '{proposal.get('title','')}' (ID: {proposal['id']}) foi roteada para '{target}'.\n"
                f"Tipo: {ptype} | Prioridade: {proposal.get('priority','medium')}\n"
                f"Valide após implementação: endpoints afetados, integridade do banco, logs de erro, SLOs."
            ),
            context={
                "proposal_id": proposal["id"],
                "proposal_type": ptype,
                "target_agent": target,
                "qa_required": True,
            },
        )
    except Exception as exc:
        logger.debug("proposal_supervisor: notif quality_validator: %s", exc)


def run(state: dict) -> dict:
    from graph_engine.llm import get_reasoning_llm, invoke_llm_with_timeout
    from graph_engine.tools.supabase_tools import send_agent_message, insert_agent_event, log_event
    from langchain_core.messages import SystemMessage, HumanMessage

    findings = []
    decisions = []
    db_raw = __import__("db").get_supabase()

    metrics = _get_metrics(db_raw)
    findings.append({"agent": "proposal_supervisor", "metrics": metrics})

    # Busca proposals aprovadas e não aplicadas
    pending_approved = (
        db_raw.table("improvement_proposals")
        .select("*")
        .eq("validation_status", "approved")
        .eq("applied", False)
        .order("created_at")
        .limit(200)
        .execute()
        .data or []
    )

    processed = 0
    for proposal in pending_approved:
        # Passo 1: Tenta auto-execução direta (SQL já existente e seguro)
        if _try_auto_execute(proposal, decisions, db_raw):
            processed += 1
            continue

        # Passo 2: Gera plano via LLM e tenta executar
        if _execute_proposal_with_llm(proposal, decisions, db_raw):
            processed += 1
            # Verifica se foi realmente aplicada ou falhou
            status = db_raw.table("improvement_proposals").select("validation_status").eq("id", proposal["id"]).limit(1).execute().data
            if status and status[0].get("validation_status") == "applied":
                continue  # aplicada com sucesso, não precisa de routing

        # Passo 3: Roteia para agente especializado (com o plano LLM já no proposed_fix)
        _route_to_agent(proposal, decisions, db_raw)
        processed += 1

    # Verifica falsos positivos: proposals "applied" mas sem resultado concreto recente
    applied_recent = (
        db_raw.table("improvement_proposals")
        .select("id,title,proposal_type,applied_at,source_agent")
        .eq("validation_status", "applied")
        .order("applied_at", desc=True)
        .limit(10)
        .execute()
        .data or []
    )

    # Consulta LLM para análise e recomendações
    llm_analysis = ""
    try:
        llm = get_reasoning_llm()
        metrics_str = json.dumps(metrics, ensure_ascii=False)
        summary = (
            f"Proposals aprovadas aguardando: {len(pending_approved)}\n"
            f"Processadas neste ciclo: {processed}\n"
            f"Métricas: {metrics_str}\n"
            f"Applied recentes: {[p.get('title','')[:40] for p in applied_recent[:5]]}"
        )
        response = invoke_llm_with_timeout(llm, [
            SystemMessage(content=(
                "Você é um engenheiro de sistemas sênior responsável por garantir que 100% das proposals "
                "aprovadas por humanos sejam executadas. Analise o estado atual e identifique: "
                "1) Bloqueios na execução, 2) Falsos positivos suspeitos, 3) Próximos passos prioritários. "
                "Responda em 3-5 bullets concisos em português."
            )),
            HumanMessage(content=summary),
        ], timeout_s=45)
        llm_analysis = response.content
    except Exception as exc:
        logger.warning("proposal_supervisor: LLM analysis: %s", exc)
        llm_analysis = f"Análise LLM indisponível: {exc}"

    findings.append({
        "agent": "proposal_supervisor",
        "pending_approved_count": len(pending_approved),
        "processed_this_cycle": processed,
        "llm_analysis": llm_analysis[:500],
    })

    # Relatório para o CTO
    now_str = datetime.now(timezone.utc).strftime("%d/%m/%Y %H:%M UTC")
    exec_rate = metrics["execution_rate_pct"]
    report = (
        f"📊 SUPERVISOR DE PROPOSALS — {now_str}\n\n"
        f"Taxa de execução: {exec_rate}% "
        f"({metrics['applied_success']} aplicadas / {metrics['applied_success'] + metrics['approved_waiting'] + metrics['implementation_failed']} total aprovadas)\n"
        f"Aprovadas aguardando: {metrics['approved_waiting']}\n"
        f"Falhas: {metrics['implementation_failed']}\n"
        f"Processadas neste ciclo: {processed}\n\n"
        f"Análise:\n{llm_analysis[:400]}"
    )

    try:
        send_agent_message(
            from_agent="proposal_supervisor",
            to_agent="cto",
            message=report,
            context={"metrics": metrics, "processed": processed},
        )
        decisions.append("Relatório enviado ao CTO")
    except Exception as exc:
        logger.warning("proposal_supervisor: envio CTO: %s", exc)

    # Evento crítico se taxa de execução < 50%
    if exec_rate < 50 and metrics["approved_waiting"] > 5:
        try:
            insert_agent_event(
                event_type="proposals_backlog_critical",
                source="proposal_supervisor",
                payload={"metrics": metrics, "pending": len(pending_approved)},
                priority="high",
            )
        except Exception:
            pass

    log_event(
        "info" if exec_rate >= 80 else "warning",
        "proposal_supervisor",
        f"Ciclo concluído: {exec_rate}% execução, {len(pending_approved)} aprovadas pendentes",
    )

    return {
        "findings": findings,
        "decisions": decisions,
        "context": {
            "proposal_supervisor_run": datetime.now(timezone.utc).isoformat(),
            "metrics": metrics,
            "processed": processed,
        },
        "next_agent": "END",
    }


def build():
    from graph_engine.agents.base import build_deterministic_agent
    return build_deterministic_agent(run)
