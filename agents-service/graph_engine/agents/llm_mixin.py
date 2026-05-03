"""
LLM Mixin — capacidade compartilhada de inteligência LLM para todos os agentes.

Qualquer agente pode importar e usar:
    from graph_engine.agents.llm_mixin import analyze_findings_with_llm, consult_llm

Isso dá a cada agente capacidade de:
- Analisar seus próprios findings e gerar insights
- Gerar proposals de melhoria com código
- Consultar o LLM quando encontrar situações inesperadas
- Fazer handoff inteligente para outros agentes
"""
import json
import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


def consult_llm(question: str, context: dict | None = None, timeout_s: int = 45) -> str:
    """
    Consulta o LLM com fallback automático entre todos os providers disponíveis.
    Retorna a resposta como string. Nunca lança exceção — retorna string de erro.
    """
    try:
        from graph_engine.llm import invoke_with_fallback
        from langchain_core.messages import SystemMessage, HumanMessage
        ctx_str = json.dumps(context or {}, ensure_ascii=False, default=str)[:1000]
        response = invoke_with_fallback([
            SystemMessage(content=(
                "Você é um engenheiro de sistemas sênior do sistema Jarvis (Voetur/VTCLog). "
                "Analise a situação e forneça uma resposta concisa, técnica e acionável em português."
            )),
            HumanMessage(content=f"{question}\n\nContexto: {ctx_str}"),
        ], timeout_s=timeout_s)
        return response.content
    except Exception as exc:
        logger.warning("consult_llm: %s", exc)
        return f"[LLM indisponível: {exc}]"


def analyze_findings_with_llm(
    agent_name: str,
    findings: list[dict],
    context: dict | None = None,
    auto_propose: bool = True,
    timeout_s: int = 45,
) -> tuple[list[dict], list[str]]:
    """
    Analisa os findings do agente com LLM e opcionalmente gera proposals automáticas.

    Retorna:
    - extra_findings: lista de findings adicionais do LLM
    - decisions: decisões tomadas (proposals geradas, etc.)
    """
    extra_findings = []
    decisions = []

    if not findings:
        return extra_findings, decisions

    try:
        from graph_engine.llm import invoke_with_fallback
        from langchain_core.messages import SystemMessage, HumanMessage

        findings_str = json.dumps(findings[:5], ensure_ascii=False, default=str)[:2000]
        ctx_str = json.dumps(context or {}, ensure_ascii=False, default=str)[:500]

        system_prompt = (
            f"Você é o agente '{agent_name}' do sistema Jarvis — um engenheiro sênior autônomo. "
            "Analise os findings e identifique:\n"
            "1. Problemas críticos que precisam de ação imediata\n"
            "2. Oportunidades de melhoria não óbvias\n"
            "3. Conexões com outros subsistemas\n\n"
            "Se encontrar algo acionável, retorne JSON:\n"
            '{"insights": [str], "proposals": [{"title": str, "type": str, "description": str, '
            '"proposed_action": str, "proposed_fix": str, "priority": "critical|high|medium|low", '
            '"risk": "low|medium|high", "auto_implementable": bool}]}'
        )

        response = invoke_with_fallback([
            SystemMessage(content=system_prompt),
            HumanMessage(content=f"Findings:\n{findings_str}\n\nContexto: {ctx_str}"),
        ], timeout_s=timeout_s)

        content = response.content

        import re
        match = re.search(r"\{.*\}", content, re.DOTALL)
        if match:
            data = json.loads(match.group())
            insights = data.get("insights", [])
            proposals = data.get("proposals", [])

            if insights:
                extra_findings.append({
                    "agent": agent_name,
                    "llm_insights": insights,
                    "analyzed_at": datetime.now(timezone.utc).isoformat(),
                })

            if auto_propose and proposals:
                from graph_engine.tools.supabase_tools import insert_improvement_proposal
                for p in proposals[:3]:  # máximo 3 proposals por ciclo
                    try:
                        insert_improvement_proposal(
                            source_agent=agent_name,
                            proposal_type=p.get("type", "code_fix"),
                            title=p.get("title", "Melhoria identificada pelo LLM")[:200],
                            description=p.get("description", ""),
                            proposed_action=p.get("proposed_action", ""),
                            proposed_fix=p.get("proposed_fix", ""),
                            priority=p.get("priority", "medium"),
                            risk=p.get("risk", "medium"),
                            auto_implementable=p.get("auto_implementable", False),
                        )
                        decisions.append(f"Proposal LLM criada: {p.get('title','')[:60]}")
                    except Exception as exc:
                        logger.warning("%s: erro ao criar proposal LLM: %s", agent_name, exc)

    except Exception as exc:
        logger.warning("%s: analyze_findings_with_llm: %s", agent_name, exc)

    return extra_findings, decisions


def report_problems_to_cto_and_evolution(
    agent_name: str,
    problems: list[str],
    gaps: list[str],
    opportunities: list[str],
    context: dict | None = None,
) -> None:
    """
    Todos os agentes devem reportar problemas, gaps e oportunidades sem esconder.
    Notifica o CTO diretamente e aciona o evolution_agent para propor melhorias.
    """
    if not (problems or gaps or opportunities):
        return
    try:
        from graph_engine.tools.supabase_tools import send_agent_message
        now = datetime.now(timezone.utc).strftime("%d/%m/%Y %H:%M UTC")

        sections = []
        if problems:
            sections.append("🔴 PROBLEMAS:\n" + "\n".join(f"  • {p}" for p in problems[:5]))
        if gaps:
            sections.append("⚠️ GAPS:\n" + "\n".join(f"  • {g}" for g in gaps[:5]))
        if opportunities:
            sections.append("💡 OPORTUNIDADES:\n" + "\n".join(f"  • {o}" for o in opportunities[:5]))

        message = f"Relatório do agente '{agent_name}' — {now}\n\n" + "\n\n".join(sections)

        # Notifica CTO
        send_agent_message(
            from_agent=agent_name,
            to_agent="cto",
            message=message,
            context={"source_agent": agent_name, "problems": problems, "gaps": gaps, "opportunities": opportunities, **(context or {})},
        )

        # Aciona evolution_agent para propor melhorias se há problemas/gaps
        if problems or gaps:
            send_agent_message(
                from_agent=agent_name,
                to_agent="evolution_agent",
                message=(
                    f"Problemas e gaps detectados pelo agente '{agent_name}':\n"
                    + "\n".join(f"• {p}" for p in (problems + gaps)[:8])
                    + "\n\nSolicito propostas de melhoria e resiliência para esses problemas."
                ),
                context={"source_agent": agent_name, "requires_evolution_proposal": True},
            )
    except Exception as exc:
        logger.warning("report_problems_to_cto_and_evolution (%s): %s", agent_name, exc)


def build_llm_enhanced_agent(original_run_fn, agent_name: str, auto_propose: bool = True):
    """
    Wrapper que adiciona análise LLM e reporting ao CTO/evolution para todos os agentes.
    Todos os problemas, gaps e oportunidades são reportados sem esconder.
    """
    def enhanced_run(state: dict) -> dict:
        result = original_run_fn(state)
        findings = result.get("findings", [])
        decisions = result.get("decisions", [])
        context = result.get("context", {})

        problems = []
        gaps = []
        opportunities = []

        # Extrai problemas e gaps dos findings
        for f in findings:
            ftype = str(f.get("type", ""))
            if any(k in ftype for k in ["down", "error", "fail", "unavail", "break"]):
                problems.append(f.get("detail") or ftype)
            elif any(k in ftype for k in ["missing", "gap", "stale", "warning"]):
                gaps.append(f.get("detail") or ftype)

        # Só consulta LLM se há findings relevantes
        if findings:
            extra, extra_decisions = analyze_findings_with_llm(
                agent_name=agent_name,
                findings=findings,
                context=context,
                auto_propose=auto_propose,
                timeout_s=30,
            )
            findings = findings + extra
            decisions = decisions + extra_decisions

            # Extrai oportunidades do LLM
            for f in extra:
                if "opportunities" in str(f).lower() or "oportunidade" in str(f).lower():
                    opportunities.append(str(f)[:100])

        # Reporta problemas, gaps e oportunidades ao CTO e evolution_agent
        if problems or gaps or opportunities:
            report_problems_to_cto_and_evolution(agent_name, problems, gaps, opportunities, context)

        return {
            **result,
            "findings": findings,
            "decisions": decisions,
        }
    enhanced_run.__name__ = f"enhanced_{agent_name}"
    return enhanced_run
