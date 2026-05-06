"""
CTO Agent — CTO sênior autoritário e infalível do sistema Jarvis.

RESPONSABILIDADES ABSOLUTAS:
1. Supervisionar 100% dos agentes — nenhum pode falhar sem ação do CTO
2. Cobrar reports de todos os agentes — omissões são tratadas como falhas
3. Avaliar todos os SLAs do sistema e tomar medidas imediatas
4. Acionar evolution_agent para toda falha, gap ou oportunidade
5. Despachar agentes para auto-resolução de problemas
6. Propor melhorias ao humano de forma organizada e massiva
7. Usar os melhores LLMs disponíveis (cascata automática)
8. Conhecer todos os agentes e auxiliá-los da melhor maneira
9. NÃO pode falhar, omitir ou se esquivar de responsabilidades
10. Garantir que desenvolvimento/evolução aprovados sejam seguidos

SLA do CTO: 100% dos agentes com qualidade garantida
"""
import json
import logging
from datetime import datetime, timezone

from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.graph import END, START, StateGraph

from graph_engine.state import JarvisState
from graph_engine.llm import invoke_with_fallback, get_reasoning_llm, invoke_llm_with_timeout
from graph_engine.agents.deterministic_router import route as deterministic_route
from graph_engine.tools.supabase_tools import (
    get_pending_agent_events,
    get_pending_messages,
    is_deployment_active,
    log_event,
    mark_agent_event_processed,
    mark_message_processed,
    query_improvement_proposals,
    send_agent_message,
    send_human_notification,
    insert_agent_event,
)
from graph_engine.tools.cto_tools import (
    approve_proposal,
    dispatch_agent,
    escalate_to_human,
    generate_governance_report,
    get_system_health_summary,
    list_pending_tasks,
    reject_proposal,
    review_pending_proposals,
    set_deployment_window,
)

log = logging.getLogger(__name__)

_PRIORITY_ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3}

# Conhecimento completo de todos os agentes: nome → descrição + pipeline + skill
_AGENT_KNOWLEDGE = {
    "cto":                  ("Manual",     "CTO supervisor — orquestra todos os agentes"),
    "log_scanner":          ("Monitoring", "Escaneia logs de erros e anomalias"),
    "log_improver":         ("Governance", "Propõe melhorias para logs problemáticos"),
    "log_intelligence":     ("Governance", "Análise profunda de padrões em logs"),
    "log_strategic_advisor":("Governance", "Advisor estratégico baseado em logs"),
    "security":             ("Security",   "Monitora segurança e intrusões"),
    "code_security":        ("Security",   "Análise de segurança no código"),
    "uptime":               ("Monitoring", "Verifica uptime de todos os serviços"),
    "docker_intel":         ("Monitoring", "Inteligência de containers Docker"),
    "infrastructure":       ("Monitoring", "Saúde e capacidade da infraestrutura"),
    "quality":              ("Monitoring", "Métricas de qualidade do sistema"),
    "quality_validator":    ("Governance", "Valida qualidade de mudanças"),
    "quality_code_backend": ("Governance", "Qualidade de código backend"),
    "quality_code_frontend":("Governance", "Qualidade de código frontend"),
    "docs":                 ("Governance", "Mantém documentação atualizada"),
    "api_agent":            ("Monitoring", "Valida contratos e endpoints de APIs"),
    "automation":           ("Governance", "Identifica e executa automações"),
    "scheduling":           ("Governance", "Gerencia agendamentos e tarefas"),
    "backend_agent":        ("Monitoring", "Monitora saúde do backend"),
    "frontend_agent":       ("Evolution",  "Monitora saúde do frontend"),
    "cicd_monitor":         ("CICD",       "Monitora pipelines CI/CD"),
    "fix_validator":        ("Governance", "Valida correções propostas"),
    "change_mgmt":          ("Governance", "Gestão de mudanças ITIL"),
    "change_validator":     ("Governance", "Valida change requests"),
    "integration_validator":("Governance", "Valida integrações externas"),
    "itil_version":         ("Governance", "Controle de versão ITIL"),
    "agent_health_supervisor":("Monitoring","Monitora saúde de todos os agentes"),
    "proposal_supervisor":  ("Governance", "Garante execução das proposals aprovadas"),
    "llm_manager_agent":    ("Governance", "Gerencia SLAs e saúde dos LLMs"),
    "log_strategic_advisor":("Governance", "Advisor estratégico baseado em logs"),
    "db_dba_agent":         ("DBA",        "DBA PostgreSQL — saúde, índices, backups"),
    "opportunity_scout":    ("Governance", "Radar de oportunidades e melhorias"),
    "evolution_agent":      ("Evolution",  "Propõe inovações e novos agentes"),
    "governance":           ("Expenses",   "Governança de contratos TI — confronto Benner vs contratos cadastrados, SLAs, glosas"),
}

_SYSTEM_PROMPT = """Você é o CTO Agent do sistema Jarvis — o supervisor infalível e autoritário de TI da Voetur/VTCLog.

PERFIL:
Você é um CTO sênior com 20+ anos de experiência em infraestrutura, DevOps, segurança, IA e gestão de sistemas críticos.
Você conhece profundamente todos os seus agentes, suas responsabilidades e limitações.
Você é direto, crítico, orientado a resultados e NUNCA se omite.

RESPONSABILIDADES INEGOCIÁVEIS:
1. Avaliar o estado de TODOS os agentes a cada ciclo — nenhum pode passar despercebido
2. Cobrar agentes que não reportaram — silêncio = problema
3. Despachar agentes para auto-resolver problemas sem esperar autorização humana
4. Acionar evolution_agent para todo gap, falha ou oportunidade identificada
5. Propor ao humano melhorias organizadas por prioridade e impacto
6. Garantir que proposals aprovadas sejam executadas (cobrar proposal_supervisor)
7. Verificar SLAs de todos os agentes e escalar quando breachados
8. Buscar alternativas nas LLMs para qualquer problema sem solução clara
9. Coordenar handoffs entre agentes de forma eficiente

REGRAS DE DECISÃO:
- auto_implementable=true + risk=low → aprovar automaticamente
- risk=high ou impacto produção → escalar para humano + criar change_request
- Agente com 3+ erros consecutivos → acionar auto-recovery + evolution
- Proposta aprovada por humano há >24h sem execução → cobrar proposal_supervisor
- SLA breachado → despachar agente responsável + notificar humano
- Durante deploy → NÃO acionar restarts automáticos (exceto emergências críticas)

FORMATO DE RESPONSE PARA HUMANO:
Organize sempre em seções: 🚨 CRÍTICO | ⚠️ ALERTAS | ✅ OK | 💡 OPORTUNIDADES | 📋 AÇÕES TOMADAS
"""


def _collect_full_context(state: JarvisState) -> dict:
    """Coleta contexto completo: eventos, mensagens, SLAs, health, proposals."""
    from graph_engine.tools.sla_tracker import get_system_sla_overview

    events    = get_pending_agent_events(limit=30)
    messages  = get_pending_messages("cto")
    proposals = query_improvement_proposals(status="pending_cto", limit=15)
    deployment = is_deployment_active()

    # Busca propostas aprovadas aguardando execução
    try:
        from db import get_supabase
        db = get_supabase()
        approved_pending = db.table("improvement_proposals").select("id,title,approved_at,priority").eq("validation_status","approved").eq("applied",False).order("approved_at").limit(10).execute().data or []
        # Agentes que não reportaram nas últimas 2 horas
        from datetime import timedelta
        cutoff = (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat()
        recent_runs = db.table("agent_runs").select("pipeline_name,status,started_at").gt("started_at", cutoff).execute().data or []
        reported_agents = {r["pipeline_name"] for r in recent_runs if r.get("pipeline_name")}
        all_agents = set(_AGENT_KNOWLEDGE.keys()) - {"cto"}
        silent_agents = list(all_agents - reported_agents)
    except Exception as exc:
        log.warning("CTO: falha ao coletar contexto estendido: %s", exc)
        approved_pending = []
        silent_agents = []

    # SLA overview
    sla_overview = {}
    try:
        sla_overview = get_system_sla_overview()
    except Exception:
        pass

    events_sorted = sorted(events, key=lambda e: _PRIORITY_ORDER.get(e.get("priority", "medium"), 2))

    ctx = {
        "pending_events": events_sorted,
        "pending_messages": messages,
        "pending_proposals": proposals,
        "approved_pending_execution": approved_pending,
        "silent_agents": silent_agents,
        "sla_overview": sla_overview,
        "deployment_active": deployment,
        "collected_at": datetime.now(timezone.utc).isoformat(),
        "agent_knowledge": {k: v[1] for k, v in _AGENT_KNOWLEDGE.items()},
    }

    return {
        "deployment_active": deployment,
        "cto_context": ctx,
        "context": {**state.get("context", {}), "cto_pending": len(events_sorted)},
    }


def _accountability_check(cto_ctx: dict, decisions: list, findings: list) -> None:
    """
    Cobra agentes que não reportaram nas últimas 2h.
    Aciona auto-recovery e notifica evolution_agent.
    """
    silent = cto_ctx.get("silent_agents", [])
    if not silent:
        return

    findings.append({
        "type": "agents_silent",
        "count": len(silent),
        "agents": silent,
        "message": "Agentes sem report nas últimas 2h — investigando",
    })

    # Aciona auto-recovery para agentes silenciosos
    from services.agent_runner import _PIPELINE_AGENTS
    for agent in silent[:5]:
        pipeline = next((p for p, agents in _PIPELINE_AGENTS.items() if agent in agents), None)
        if pipeline:
            try:
                import asyncio, concurrent.futures
                from services.agent_runner import run_langgraph_pipeline
                with concurrent.futures.ThreadPoolExecutor(max_workers=1) as ex:
                    ex.submit(asyncio.run, run_langgraph_pipeline(pipeline)).result(timeout=60)
                decisions.append(f"CTO acionou auto-recovery: {agent} via pipeline '{pipeline}'")
            except Exception as exc:
                decisions.append(f"CTO: auto-recovery falhou para {agent}: {str(exc)[:60]}")

    # Aciona evolution_agent para propor melhorias de resiliência
    try:
        send_agent_message(
            from_agent="cto",
            to_agent="evolution_agent",
            message=(
                f"CTO ALERTA: {len(silent)} agentes não reportaram nas últimas 2h: {', '.join(silent[:8])}\n"
                "Proponha melhorias de resiliência e auto-healing para esses agentes. "
                "Prioridade: garantir que nenhum agente possa ficar silencioso sem auto-recovery."
            ),
            context={"silent_agents": silent, "requires_evolution": True},
        )
        decisions.append(f"Handoff ao evolution_agent: {len(silent)} agentes silenciosos")
    except Exception as exc:
        log.warning("CTO: handoff evolution silenciosos: %s", exc)


def _sla_enforcement(cto_ctx: dict, decisions: list, findings: list) -> None:
    """Verifica SLAs e aciona medidas para breaches."""
    overview = cto_ctx.get("sla_overview", {})
    agents_in_breach = overview.get("agents_in_breach", [])
    compliance = overview.get("compliance_pct", 100)

    if agents_in_breach:
        findings.append({
            "type": "sla_breach",
            "agents_in_breach": agents_in_breach,
            "system_compliance_pct": compliance,
        })
        # Aciona evolution para cada agente em breach
        try:
            send_agent_message(
                from_agent="cto",
                to_agent="evolution_agent",
                message=(
                    f"CTO: SLA BREACHADO em {len(agents_in_breach)} agentes: {', '.join(agents_in_breach[:5])}\n"
                    f"Compliance geral: {compliance}% (meta: 100%)\n"
                    "Proponha imediatamente melhorias específicas para cada agente em breach."
                ),
                context={"agents_in_breach": agents_in_breach, "compliance": compliance},
            )
            decisions.append(f"SLA breach reportado ao evolution_agent: {len(agents_in_breach)} agentes")
        except Exception:
            pass


def _proposal_accountability(cto_ctx: dict, decisions: list) -> None:
    """Cobra proposal_supervisor sobre proposals aprovadas há muito tempo sem execução."""
    pending = cto_ctx.get("approved_pending_execution", [])
    if not pending:
        return

    from datetime import timedelta
    old_proposals = []
    for p in pending:
        approved_at = p.get("approved_at")
        if approved_at:
            try:
                approved_dt = datetime.fromisoformat(approved_at.replace("Z", "+00:00"))
                age_h = (datetime.now(timezone.utc) - approved_dt).total_seconds() / 3600
                if age_h > 24:
                    old_proposals.append({"title": p.get("title","")[:60], "age_h": round(age_h, 1)})
            except Exception:
                pass

    if old_proposals:
        try:
            msg = (
                f"CTO COBRANÇA: {len(old_proposals)} proposals aprovadas por humano há >24h sem execução:\n"
                + "\n".join(f"• {p['title']} ({p['age_h']}h atrás)" for p in old_proposals[:5])
                + "\nExecute IMEDIATAMENTE. Proposals aprovadas por humano são prioridade máxima."
            )
            send_agent_message(from_agent="cto", to_agent="proposal_supervisor", message=msg, context={"urgent": True})
            decisions.append(f"CTO cobrou proposal_supervisor: {len(old_proposals)} proposals atrasadas")
        except Exception as exc:
            log.warning("CTO: cobrança proposal_supervisor: %s", exc)


def _llm_supervisor(state: JarvisState) -> dict:
    """Supervisor principal: avalia estado, toma decisões, usa LLM com fallback completo."""
    cto_ctx = state.get("cto_context", {})
    pending_events    = cto_ctx.get("pending_events", [])
    pending_proposals = cto_ctx.get("pending_proposals", [])
    current_pipeline  = state.get("current_pipeline", "")
    findings = list(state.get("findings", []))
    decisions = list(state.get("decisions", []))

    # Accountability: cobra agentes silenciosos
    _accountability_check(cto_ctx, decisions, findings)

    # SLA enforcement
    _sla_enforcement(cto_ctx, decisions, findings)

    # Proposal accountability
    _proposal_accountability(cto_ctx, decisions)

    # Se sem trabalho pendente: idling gracioso mas ainda verifica SLAs
    if not pending_events and not pending_proposals:
        log_event("info", "cto_agent", "Sistema estável — nenhum evento crítico pendente")
        return {
            "findings": findings,
            "decisions": decisions + [{"action": "idle", "reason": "no_pending_work"}],
            "next_agent": "END",
        }

    # Roteamento determinístico primeiro (sem gastar LLM)
    det_agent = deterministic_route(pending_events, current_pipeline)
    if det_agent == "END":
        log_event("info", "cto_agent", "DeterministicRouter → END")
        return {"findings": findings, "decisions": decisions + [{"action": "idle"}], "next_agent": "END"}
    if det_agent is not None:
        log_event("info", "cto_agent", f"DeterministicRouter → {det_agent}")
        return {"findings": findings, "decisions": decisions + [{"action": "route", "agent": det_agent}], "next_agent": det_agent}

    # LLM supervisor — com cascata multi-LLM para não falhar
    sla_summary = cto_ctx.get("sla_overview", {})
    summary = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "pending_events": len(pending_events),
        "top_events": [{"type": e.get("event_type"), "priority": e.get("priority"), "source": e.get("source")} for e in pending_events[:5]],
        "pending_proposals_cto": len(pending_proposals),
        "approved_pending_exec": len(cto_ctx.get("approved_pending_execution", [])),
        "silent_agents": cto_ctx.get("silent_agents", []),
        "sla_compliance_pct": sla_summary.get("compliance_pct", "?"),
        "agents_in_sla_breach": sla_summary.get("agents_in_breach", []),
        "deployment_active": cto_ctx.get("deployment_active", False),
        "agent_knowledge": {k: v[1] for k, v in list(_AGENT_KNOWLEDGE.items())[:15]},
    }

    tools = [
        dispatch_agent,
        set_deployment_window,
        get_system_health_summary,
        list_pending_tasks,
        escalate_to_human,
        review_pending_proposals,
        approve_proposal,
        reject_proposal,
        generate_governance_report,
    ]

    llm_decisions = []
    human_report_sections = {"critical": [], "alerts": [], "ok": [], "opportunities": [], "actions": []}

    try:
        # Usa invoke_with_fallback para garantir que o CTO NUNCA falha por LLM
        llm = get_reasoning_llm()
        try:
            llm_bound = llm.bind_tools(tools)
            response = invoke_llm_with_timeout(llm_bound, [
                SystemMessage(content=_SYSTEM_PROMPT),
                HumanMessage(content=f"Estado do sistema:\n{json.dumps(summary, indent=2, default=str)}\n\nMensagens recentes:\n{json.dumps([{'from': m.get('from_agent'), 'msg': m.get('message','')[:200]} for m in cto_ctx.get('pending_messages', [])[:5]], ensure_ascii=False)}"),
            ], timeout_s=45)
        except Exception:
            # Fallback: usa cascata de LLMs sem tool binding
            response = invoke_with_fallback([
                SystemMessage(content=_SYSTEM_PROMPT),
                HumanMessage(content=f"Estado do sistema:\n{json.dumps(summary, indent=2, default=str)}\nNão use ferramentas. Apenas descreva o que faria e por quê."),
            ], timeout_s=45)

        # Executa tool calls
        if hasattr(response, "tool_calls") and response.tool_calls:
            for tc in response.tool_calls:
                tool_name = tc.get("name", "")
                tool_args = tc.get("args", {})
                try:
                    result = _invoke_tool(tool_name, tool_args, tools)
                    llm_decisions.append({"tool": tool_name, "args": tool_args, "result": result})
                    human_report_sections["actions"].append(f"{tool_name}({json.dumps(tool_args, ensure_ascii=False)[:80]})")
                except Exception as e:
                    log.warning("CTO tool %s: %s", tool_name, e)
                    llm_decisions.append({"tool": tool_name, "error": str(e)})

        # Analisa conteúdo textual do LLM para extrair ações e relatório
        if hasattr(response, "content") and response.content:
            content = response.content
            for line in content.split("\n"):
                l = line.strip()
                if any(k in l.lower() for k in ["crítico", "crítica", "emergência", "urgente"]):
                    human_report_sections["critical"].append(l[:120])
                elif any(k in l.lower() for k in ["alerta", "warning", "atenção", "problema"]):
                    human_report_sections["alerts"].append(l[:120])
                elif any(k in l.lower() for k in ["oportunidade", "melhoria", "proposta"]):
                    human_report_sections["opportunities"].append(l[:120])
                elif any(k in l.lower() for k in ["ok", "operacional", "saudável", "normal"]):
                    human_report_sections["ok"].append(l[:80])

    except Exception as e:
        log.error("CTO Agent LLM error: %s", e)
        log_event("error", "cto_agent", f"LLM error (modo degradado): {e}")
        # Modo degradado: CTO toma ações básicas sem LLM
        llm_decisions.append({"action": "degraded_mode", "error": str(e)})
        # Ainda assim cobra agentes e notifica humano
        human_report_sections["critical"].append(f"CTO em modo degradado: {str(e)[:100]}")

    # Monta relatório organizado para o humano
    _send_organized_report(human_report_sections, cto_ctx, findings)

    # Processa e marca eventos/mensagens
    for event in pending_events:
        try:
            mark_agent_event_processed(event["id"])
        except Exception:
            pass
    for msg in cto_ctx.get("pending_messages", []):
        try:
            mark_message_processed(msg["id"])
        except Exception:
            pass

    decisions.extend(llm_decisions)
    return {"findings": findings, "decisions": decisions, "next_agent": "END"}


def _send_organized_report(sections: dict, ctx: dict, findings: list) -> None:
    """Monta e envia relatório organizado para o humano via notificação."""
    try:
        now = datetime.now(timezone.utc).strftime("%d/%m/%Y %H:%M UTC")
        parts = [f"📊 RELATÓRIO CTO — {now}\n"]

        if sections["critical"]:
            parts.append("🚨 CRÍTICO:\n" + "\n".join(f"  • {l}" for l in sections["critical"][:5]))
        if sections["alerts"]:
            parts.append("⚠️ ALERTAS:\n" + "\n".join(f"  • {l}" for l in sections["alerts"][:5]))
        if sections["ok"]:
            parts.append("✅ OK:\n" + "\n".join(f"  • {l}" for l in sections["ok"][:3]))
        if sections["opportunities"]:
            parts.append("💡 OPORTUNIDADES:\n" + "\n".join(f"  • {l}" for l in sections["opportunities"][:3]))
        if sections["actions"]:
            parts.append("📋 AÇÕES TOMADAS:\n" + "\n".join(f"  • {a}" for a in sections["actions"][:5]))

        silent = ctx.get("silent_agents", [])
        if silent:
            parts.append(f"🔇 AGENTES SEM REPORT ({len(silent)}): {', '.join(silent[:8])}")

        sla = ctx.get("sla_overview", {})
        if sla:
            parts.append(f"📈 SLA Sistema: {sla.get('compliance_pct', '?')}% | Agentes em breach: {len(sla.get('agents_in_breach', []))}")

        report = "\n\n".join(parts)

        # Notifica humano apenas se há algo a reportar
        if sections["critical"] or sections["alerts"] or silent or (sla.get("agents_in_breach") or []):
            send_human_notification(
                from_agent="cto",
                message=report,
                context={
                    "critical_count": len(sections["critical"]),
                    "alerts_count": len(sections["alerts"]),
                    "silent_agents": silent,
                    "sla_compliance": sla.get("compliance_pct"),
                },
            )

        findings.append({
            "agent": "cto",
            "report_sections": {k: len(v) for k, v in sections.items()},
            "silent_agents": len(silent),
            "sla_compliance": sla.get("compliance_pct"),
        })
    except Exception as exc:
        log.warning("CTO: send_organized_report: %s", exc)


def _invoke_tool(tool_name: str, args: dict, tools: list):
    tool_map = {t.name: t for t in tools}
    t = tool_map.get(tool_name)
    if not t:
        raise ValueError(f"Tool '{tool_name}' não encontrada")
    return t.invoke(args)


def _route_next(state: JarvisState) -> str:
    return state.get("next_agent", "END") or "END"


def build():
    graph = StateGraph(JarvisState)
    graph.add_node("collect_work", _collect_full_context)
    graph.add_node("llm_supervisor", _llm_supervisor)
    graph.add_edge(START, "collect_work")
    graph.add_edge("collect_work", "llm_supervisor")
    graph.add_edge("llm_supervisor", END)
    return graph.compile()
