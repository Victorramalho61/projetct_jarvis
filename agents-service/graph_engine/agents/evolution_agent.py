"""
Evolution Agent — o agente mais estratégico do sistema.
Pensa como CTO visionário: estuda o sistema, identifica gaps, propõe novas
funcionalidades e agentes, gera scaffolds de código com Ollama, envia briefing
diário ao CTO e motiva os demais agentes. Usa apenas Groq/Ollama (sem Anthropic).
"""
import json
import logging
import re
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

_AGENT_REGISTRY = [
    "cto", "log_scanner", "log_improver", "log_strategic_advisor",
    "security", "code_security", "uptime", "docker_intel", "infrastructure",
    "quality", "quality_validator", "docs", "api_agent", "automation",
    "scheduling", "backend_agent", "frontend_agent", "fix_validator",
    "change_mgmt", "change_validator", "integration_validator", "itil_version",
    "log_intelligence", "cicd_monitor", "db_dba_agent", "quality_code_backend",
    "quality_code_frontend", "opportunity_scout", "evolution_agent",
]


def _read_system_state() -> dict:
    from graph_engine.tools.supabase_tools import (
        query_improvement_proposals,
        query_agent_runs,
        query_quality_metrics,
        query_agent_events,
    )
    proposals = query_improvement_proposals(status="pending", limit=30)
    runs = query_agent_runs(limit=50)
    metrics = query_quality_metrics(since_hours=24)
    events = query_agent_events(limit=20)
    return {
        "pending_proposals": proposals,
        "recent_runs": runs,
        "quality_metrics": metrics,
        "recent_events": events,
        "active_agents": _AGENT_REGISTRY,
    }


def _study_knowledge_base() -> str:
    context_parts = []
    try:
        from graph_engine.tools.github_tools import read_file
        arch = read_file("docs/arquitetura.md") or ""
        if arch:
            context_parts.append(f"ARQUITETURA:\n{arch[:2000]}")
    except Exception:
        pass

    try:
        from db import get_supabase
        db = get_supabase()
        reports = (
            db.table("governance_reports")
            .select("period,report_date,findings_summary,recommendations")
            .order("report_date", desc=True)
            .limit(3)
            .execute()
            .data
        )
        if reports:
            context_parts.append(f"RELATÓRIOS RECENTES:\n{json.dumps(reports, ensure_ascii=False, default=str)[:1500]}")
    except Exception as exc:
        logger.warning("evolution_agent: erro ao ler governance_reports: %s", exc)

    return "\n\n".join(context_parts)


def _get_opportunity_context(state: dict) -> list[dict]:
    return state.get("context", {}).get("opportunities", [])


def _parse_innovations(text: str) -> list[dict]:
    match = re.search(r"\[.*\]", text, re.DOTALL)
    if not match:
        return []
    try:
        return json.loads(match.group())
    except Exception:
        return []


def _generate_agent_scaffold(agent_name: str, description: str, llm) -> str:
    try:
        from langchain_core.messages import SystemMessage, HumanMessage
        prompt = (
            f"Gere o código Python completo para um agente LangGraph chamado '{agent_name}'. "
            f"Descrição: {description}\n\n"
            "Siga EXATAMENTE este padrão:\n"
            "```python\n"
            "import logging\n"
            "from datetime import datetime, timezone\n"
            "logger = logging.getLogger(__name__)\n\n"
            "def run(state: dict) -> dict:\n"
            "    findings = []\n"
            "    decisions = []\n"
            "    # TODO: implementar lógica\n"
            "    return {'findings': findings, 'decisions': decisions, 'next_agent': 'END'}\n\n"
            "def build():\n"
            "    from graph_engine.agents.base import build_deterministic_agent\n"
            "    return build_deterministic_agent(run)\n"
            "```\n"
            "Retorne APENAS o código Python, sem explicações."
        )
        response = llm.invoke([SystemMessage(content="Você é um engenheiro Python sênior especialista em LangGraph."),
                               HumanMessage(content=prompt)])
        code = response.content
        code_match = re.search(r"```python\n(.*?)```", code, re.DOTALL)
        if code_match:
            return code_match.group(1)
        return code
    except Exception as exc:
        logger.error("evolution_agent: erro ao gerar scaffold: %s", exc)
        return ""


def _motivate_agents(state: dict) -> str:
    runs = state.get("recent_runs", [])
    agent_success: dict = {}
    for run in runs:
        if run.get("status") == "success":
            aid = str(run.get("agent_id", ""))[:20]
            agent_success[aid] = agent_success.get(aid, 0) + 1

    if not agent_success:
        return "Todos os agentes estão se preparando para entregar resultados excelentes!"

    top = max(agent_success, key=agent_success.get)
    return (
        f"Parabéns ao agente '{top}' pelo desempenho excepcional! "
        f"Com {agent_success[top]} execuções bem-sucedidas, provando que a automação "
        f"inteligente é o futuro da Voetur/VTCLog. Vamos continuar evoluindo juntos!"
    )


def run(state: dict) -> dict:
    from graph_engine.llm import get_reasoning_llm
    from graph_engine.tools.supabase_tools import (
        insert_improvement_proposal,
        insert_agent_event,
        send_agent_message,
        send_human_notification,
    )
    from db import get_supabase
    from langchain_core.messages import SystemMessage, HumanMessage

    findings = []
    decisions = []

    system_state = _read_system_state()
    knowledge_context = _study_knowledge_base()
    opportunities = _get_opportunity_context(state) or []

    pending_proposals = system_state.get("pending_proposals", [])
    recurring_types = {}
    for p in pending_proposals:
        pt = p.get("proposal_type", "other")
        recurring_types[pt] = recurring_types.get(pt, 0) + 1

    findings.append({
        "agent": "evolution_agent",
        "pending_proposals": len(pending_proposals),
        "recurring_proposal_types": recurring_types,
        "opportunities_received": len(opportunities),
        "active_agents_count": len(_AGENT_REGISTRY),
    })

    system_prompt = (
        "Você é um CTO visionário e Tech Lead sênior com foco em inovação e automação. "
        "Seu papel é estudar o sistema Jarvis da Voetur/VTCLog (empresa de transporte e logística) e identificar:\n"
        "1. Oportunidades de automação dos processos da empresa\n"
        "2. Novas funcionalidades que agregariam valor imediato ao negócio\n"
        "3. Novos agentes IA que cobririam gaps identificados\n"
        "4. Modernizações tecnológicas aplicáveis\n"
        "5. Processos manuais que podem ser automatizados\n\n"
        "Seja proativo, motivador e orientado a resultado. "
        "Pense em ROI, velocidade de entrega e qualidade. "
        "Retorne SOMENTE um array JSON com até 5 inovações:\n"
        '[{"category": "new_agent|new_feature|automation|modernization|process", '
        '"title": str, "vision": str, "proposed_implementation": str, '
        '"agent_name": str (se new_agent, snake_case), '
        '"effort": "horas|dias|semanas|meses", '
        '"business_value": str, "priority": "critical|high|medium|low", '
        '"motivational_note": str}]'
    )

    user_content = (
        f"Estado atual do sistema:\n"
        f"- Agentes ativos: {len(_AGENT_REGISTRY)}\n"
        f"- Proposals pendentes: {len(pending_proposals)}\n"
        f"- Tipos recorrentes: {json.dumps(recurring_types, ensure_ascii=False)}\n"
        f"- Oportunidades mapeadas: {json.dumps(opportunities[:5], ensure_ascii=False)}\n\n"
        f"{knowledge_context}"
    )

    innovations = []
    llm = get_reasoning_llm()
    try:
        response = llm.invoke([
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_content),
        ])
        innovations = _parse_innovations(response.content)
    except Exception as exc:
        logger.error("evolution_agent: erro LLM inovações: %s", exc)

    # Semeie os SLAs pré-definidos se ainda não existem
    try:
        from graph_engine.tools.sla_tracker import seed_predefined_slas, PREDEFINED_SLAS
        seeded = seed_predefined_slas()
        if seeded:
            decisions.append(f"SLAs pré-definidos: {seeded} SLAs registrados para {len(PREDEFINED_SLAS)} agentes")
    except Exception as exc:
        logger.warning("evolution_agent: seed SLAs: %s", exc)

    briefing_items = []
    for innovation in innovations[:5]:
        agent_scaffold = ""
        agent_slas_generated = 0

        if innovation.get("category") == "new_agent" and innovation.get("agent_name"):
            agent_name = innovation["agent_name"]
            agent_scaffold = _generate_agent_scaffold(agent_name, innovation.get("vision", ""), llm)

            # Gera 3 SLAs específicos para o novo agente via LLM
            try:
                sla_prompt = (
                    f"Gere exatamente 3 SLAs de execução para o agente '{agent_name}' do sistema Jarvis.\n"
                    f"Skill do agente: {innovation.get('vision', '')}\n\n"
                    f"REGRAS:\n"
                    f"- NÃO inclua SLA de health (esse pertence ao agent_health_supervisor)\n"
                    f"- SLAs devem medir a QUALIDADE e RESULTADO do trabalho do agente\n"
                    f"- Cada SLA deve ser mensurável e específico\n"
                    f"- Use unidades realistas: %, ms, count, hours, min\n\n"
                    f"Retorne JSON:\n"
                    '[{"name": str, "description": str, "target": float, '
                    '"operator": ">=|<=|>|<|=", "unit": "%|ms|count|ratio|hours|min", '
                    '"warning_threshold": float}]'
                )
                sla_response = llm.invoke([
                    SystemMessage(content="Você é um SRE sênior especialista em SLAs e observabilidade de sistemas de IA."),
                    HumanMessage(content=sla_prompt),
                ])
                import re as _re
                import json as _json
                match = _re.search(r"\[.*\]", sla_response.content, _re.DOTALL)
                if match:
                    sla_list = _json.loads(match.group())
                    from graph_engine.tools.sla_tracker import define_slas_for_agent
                    slas_to_create = [
                        {
                            "name": s["name"],
                            "description": s.get("description", ""),
                            "target": s.get("target", 90.0),
                            "operator": s.get("operator", ">="),
                            "unit": s.get("unit", "%"),
                            "warning_threshold": s.get("warning_threshold"),
                            "source": "evolution_agent",
                        }
                        for s in sla_list[:3]  # máximo 3 SLAs
                    ]
                    agent_slas_generated = define_slas_for_agent(agent_name, slas_to_create)
                    decisions.append(f"SLAs gerados para {agent_name}: {agent_slas_generated} SLAs")
            except Exception as exc:
                logger.warning("evolution_agent: geração de SLAs para %s: %s", agent_name, exc)

        try:
            insert_improvement_proposal(
                source_agent="evolution_agent",
                proposal_type=innovation.get("category", "new_feature"),
                title=innovation.get("title", "Inovação")[:150],
                description=innovation.get("vision", ""),
                proposed_action=innovation.get("proposed_implementation", ""),
                proposed_fix=agent_scaffold if agent_scaffold else None,
                business_value=innovation.get("business_value", ""),
                motivational_note=innovation.get("motivational_note", ""),
                priority=innovation.get("priority", "medium"),
                risk="low",
                estimated_effort=innovation.get("effort", ""),
                auto_implementable=False,
            )
            briefing_items.append(
                f"• [{innovation.get('priority','?').upper()}] {innovation.get('title','')}: "
                f"{innovation.get('business_value', '')}"
                + (f" | SLAs: {agent_slas_generated}" if agent_slas_generated else "")
            )
            decisions.append(f"Inovação proposta: {innovation.get('title', '')[:60]}")
        except Exception as exc:
            logger.error("evolution_agent: erro ao inserir innovation: %s", exc)

    motivational = _motivate_agents(system_state)
    briefing = (
        f"🚀 EVOLUTION BRIEFING — {datetime.now(timezone.utc).strftime('%d/%m/%Y')}\n\n"
        f"📊 Estado: {len(_AGENT_REGISTRY)} agentes ativos, {len(pending_proposals)} proposals pendentes\n\n"
        f"💡 Inovações de hoje:\n" + "\n".join(briefing_items or ["Analisando oportunidades..."]) +
        f"\n\n🏆 {motivational}"
    )

    try:
        insert_agent_event(
            event_type="evolution_briefing_ready",
            source="evolution_agent",
            payload={"briefing_preview": briefing[:500], "innovations_count": len(innovations)},
            priority="medium",
        )
        # Envia ao CTO agent para processamento interno
        send_agent_message(
            from_agent="evolution_agent",
            to_agent="cto",
            message=briefing,
            context={"innovations": innovations, "opportunities": opportunities},
        )
        # Envia ao humano para leitura no inbox do frontend
        send_human_notification(
            from_agent="evolution_agent",
            message=briefing,
            context={
                "innovations_count": len(innovations),
                "opportunities_count": len(opportunities),
                "innovations": [{"title": i.get("title"), "priority": i.get("priority"), "business_value": i.get("business_value")} for i in innovations[:5]],
            },
        )
        decisions.append("Briefing diário enviado ao CTO e ao humano")
    except Exception as exc:
        logger.error("evolution_agent: erro ao enviar briefing: %s", exc)

    try:
        db = get_supabase()
        db.table("governance_reports").insert({
            "period": "daily",
            "report_date": datetime.now(timezone.utc).date().isoformat(),
            "metrics": {
                "active_agents": len(_AGENT_REGISTRY),
                "pending_proposals": len(pending_proposals),
                "innovations_proposed": len(innovations),
                "opportunities_analyzed": len(opportunities),
            },
            "findings_summary": "\n".join(f"- {o.get('title', '')}" for o in opportunities[:5]),
            "recommendations": "\n".join(f"- {i.get('title', '')}: {i.get('proposed_implementation', '')[:100]}" for i in innovations[:3]),
            "agents_health": {},
            "generated_by": "evolution_agent",
        }).execute()
    except Exception as exc:
        logger.warning("evolution_agent: erro ao salvar governance_report: %s", exc)

    return {
        "findings": findings,
        "decisions": decisions,
        "context": {
            "evolution_briefing": briefing[:300],
            "evolution_agent_run": datetime.now(timezone.utc).isoformat(),
            "innovations_count": len(innovations),
        },
        "next_agent": "END",
    }


def build():
    from graph_engine.agents.base import build_deterministic_agent
    return build_deterministic_agent(run)
