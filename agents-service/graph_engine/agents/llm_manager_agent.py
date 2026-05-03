"""
LLM Manager Agent — orquestrador de inteligência do sistema.

Responsabilidades:
1. Monitorar saúde de todos os providers LLM (Groq, Together, HuggingFace, Ollama)
2. Aprender qual LLM funciona melhor para cada agente (routing adaptativo)
3. Detectar agentes com falhas de LLM e fazer handoff de correção
4. Organizar a fila de requisições para evitar rate limiting
5. Redirecionar automaticamente quando um LLM falha
6. Reportar SLAs e métricas ao CTO

SLAs:
- 100% dos agentes com pelo menos 1 LLM funcional disponível
- 100% das requisições de LLM com resposta (via fallback)
- Latência P95 < 60s para qualquer agente
- Detecção de falha LLM em < 15 min (ciclo do health supervisor)
"""
import json
import logging
import time
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

# Definição de todos os providers e modelos monitorados
_PROVIDERS = [
    {"provider": "cerebras",     "model": "llama-3.3-70b",           "key_field": "cerebras_api_key"},
    {"provider": "groq",         "model": "llama-3.1-8b-instant",    "key_field": "groq_api_key"},
    {"provider": "groq",         "model": "llama-3.3-70b-versatile", "key_field": "groq_api_key"},
    {"provider": "together",     "model": "meta-llama/Meta-Llama-3.1-8B-Instruct-Turbo", "key_field": "together_api_key"},
    {"provider": "openrouter",   "model": "meta-llama/llama-3.1-8b-instruct:free", "key_field": "openrouter_api_key"},
    {"provider": "mistral",      "model": "mistral-small-latest",    "key_field": "mistral_api_key"},
    {"provider": "huggingface",  "model": "HuggingFaceH4/zephyr-7b-beta", "key_field": "huggingface_api_key"},
    {"provider": "ollama",       "model": None, "key_field": None},  # sempre disponível localmente
]

# Capacidade esperada por tipo de tarefa → provider preferido
_TASK_ROUTING = {
    "reasoning":    ["cerebras", "groq_70b", "groq_8b", "together", "openrouter", "mistral", "ollama"],
    "code":         ["cerebras", "groq_70b", "together_coder", "openrouter_qwen", "mistral_codestral", "ollama_code", "ollama"],
    "fast":         ["cerebras", "groq_8b", "together", "openrouter", "mistral", "ollama"],
    "embedding":    ["huggingface", "ollama"],
    "default":      ["cerebras", "groq_8b", "together", "openrouter", "mistral", "huggingface", "ollama"],
}

_TEST_PROMPT = "Responda em 5 palavras: qual é a capital do Brasil?"


def _check_provider(provider: str, model: str | None, key_field: str | None) -> dict:
    """Testa um provider LLM com prompt simples. Retorna status, latência e erro."""
    from db import get_settings
    s = get_settings()

    if key_field and not getattr(s, key_field, ""):
        return {"provider": provider, "model": model or "default", "status": "no_key", "latency_ms": 0, "error": f"{key_field} não configurado"}

    t0 = time.monotonic()
    try:
        from langchain_core.messages import HumanMessage

        if provider == "cerebras":
            from langchain_openai import ChatOpenAI
            llm = ChatOpenAI(model=model, api_key=s.cerebras_api_key, base_url="https://api.cerebras.ai/v1", temperature=0, max_tokens=50)
        elif provider == "groq":
            from langchain_groq import ChatGroq
            llm = ChatGroq(model=model, api_key=s.groq_api_key, temperature=0, max_tokens=50)
        elif provider == "together":
            from langchain_openai import ChatOpenAI
            llm = ChatOpenAI(model=model, api_key=s.together_api_key, base_url="https://api.together.xyz/v1", temperature=0, max_tokens=50)
        elif provider == "openrouter":
            from langchain_openai import ChatOpenAI
            llm = ChatOpenAI(
                model=model, api_key=s.openrouter_api_key, base_url="https://openrouter.ai/api/v1",
                temperature=0, max_tokens=50,
                default_headers={"HTTP-Referer": "https://jarvis.voetur.com.br", "X-Title": "Jarvis"},
            )
        elif provider == "mistral":
            from langchain_mistralai import ChatMistralAI
            llm = ChatMistralAI(model=model, api_key=s.mistral_api_key, temperature=0, max_tokens=50)
        elif provider == "huggingface":
            from langchain_huggingface import HuggingFaceEndpoint
            llm = HuggingFaceEndpoint(repo_id=model, huggingfacehub_api_token=s.huggingface_api_key, max_new_tokens=50)
        elif provider == "ollama":
            from langchain_ollama import ChatOllama
            llm = ChatOllama(model=model or s.ollama_model, base_url=s.ollama_base_url, temperature=0, num_predict=50)
        else:
            return {"provider": provider, "model": model or "?", "status": "unknown_provider", "latency_ms": 0, "error": ""}

        llm.invoke([HumanMessage(content=_TEST_PROMPT)])
        latency_ms = int((time.monotonic() - t0) * 1000)
        return {"provider": provider, "model": model or "default", "status": "ok", "latency_ms": latency_ms, "error": None}

    except Exception as exc:
        latency_ms = int((time.monotonic() - t0) * 1000)
        return {"provider": provider, "model": model or "default", "status": "error", "latency_ms": latency_ms, "error": str(exc)[:300]}


def _save_health_metrics(db, results: list[dict]) -> None:
    for r in results:
        try:
            db.table("llm_health_metrics").insert({
                "provider":   r["provider"],
                "model":      r["model"],
                "status":     r["status"],
                "latency_ms": r.get("latency_ms"),
                "error":      r.get("error"),
                "checked_at": datetime.now(timezone.utc).isoformat(),
            }).execute()
        except Exception as exc:
            logger.warning("llm_manager: save_health %s: %s", r["provider"], exc)


def _get_agents_with_llm_failures(db) -> list[dict]:
    """Busca agentes com falhas de LLM nas últimas 6 horas — verifica agent_runs E app_logs."""
    from datetime import timedelta
    llm_error_keywords = [
        "LLM", "llm", "timeout", "Connection refused", "ConnectError",
        "ChatGroq", "Ollama", "ChatOpenAI", "Cerebras", "OpenRouter", "Mistral",
        "não respondeu", "não disponível", "fallback",
    ]
    failing = []
    seen: set[str] = set()
    six_hours_ago = (datetime.now(timezone.utc) - timedelta(hours=6)).isoformat()

    # 1. Falhas em agent_runs (erros que abortaram o pipeline)
    try:
        runs = (
            db.table("agent_runs")
            .select("pipeline_name,error,started_at")
            .eq("status", "error")
            .not_.is_("error", "null")
            .gte("started_at", six_hours_ago)
            .order("started_at", desc=True)
            .limit(300)
            .execute()
            .data or []
        )
        for r in runs:
            err = r.get("error", "") or ""
            if any(k in err for k in llm_error_keywords):
                agent = r.get("pipeline_name") or "pipeline_unknown"
                if agent not in seen:
                    seen.add(agent)
                    failing.append({"agent": agent, "error": err[:200], "last_seen": r.get("started_at", ""), "source": "agent_runs"})
    except Exception as exc:
        logger.warning("llm_manager: get_failing_agents (agent_runs): %s", exc)

    # 2. Falhas em app_logs — captura timeouts do code_generator e erros internos de LLM
    try:
        logs = (
            db.table("app_logs")
            .select("module,message,created_at")
            .eq("level", "error")
            .gte("created_at", six_hours_ago)
            .order("created_at", desc=True)
            .limit(300)
            .execute()
            .data or []
        )
        for log_entry in logs:
            msg = log_entry.get("message", "") or ""
            if any(k in msg for k in llm_error_keywords):
                agent = log_entry.get("module") or "unknown_module"
                if agent not in seen:
                    seen.add(agent)
                    failing.append({"agent": agent, "error": msg[:200], "last_seen": log_entry.get("created_at", ""), "source": "app_logs"})
    except Exception as exc:
        logger.warning("llm_manager: get_failing_agents (app_logs): %s", exc)

    return failing


def _update_routing_preference(db, agent_name: str, provider: str, model: str, success: bool, latency_ms: int) -> None:
    """Atualiza as preferências de routing para um agente."""
    try:
        existing = (
            db.table("llm_routing_preferences")
            .select("id,success_count,failure_count,avg_latency_ms")
            .eq("agent_name", agent_name)
            .eq("provider", provider)
            .eq("model", model)
            .limit(1)
            .execute()
            .data
        )
        if existing:
            row = existing[0]
            new_success = row["success_count"] + (1 if success else 0)
            new_failure = row["failure_count"] + (0 if success else 1)
            old_avg = row.get("avg_latency_ms") or 0
            total = new_success + new_failure
            new_avg = int((old_avg * (total - 1) + latency_ms) / total) if total > 0 else latency_ms
            db.table("llm_routing_preferences").update({
                "success_count": new_success,
                "failure_count": new_failure,
                "avg_latency_ms": new_avg,
                "last_used": datetime.now(timezone.utc).isoformat(),
            }).eq("id", row["id"]).execute()
        else:
            db.table("llm_routing_preferences").insert({
                "agent_name":    agent_name,
                "provider":      provider,
                "model":         model,
                "success_count": 1 if success else 0,
                "failure_count": 0 if success else 1,
                "avg_latency_ms": latency_ms,
            }).execute()
    except Exception as exc:
        logger.warning("llm_manager: update_routing %s: %s", agent_name, exc)


def _get_best_llm_for_agent(db, agent_name: str, healthy_providers: list[str]) -> str:
    """Retorna o provider mais eficiente historicamente para um agente específico."""
    try:
        prefs = (
            db.table("llm_routing_preferences")
            .select("provider,model,success_count,failure_count,avg_latency_ms")
            .eq("agent_name", agent_name)
            .order("success_count", desc=True)
            .limit(5)
            .execute()
            .data or []
        )
        for p in prefs:
            provider = p["provider"]
            success_rate = p["success_count"] / max(p["success_count"] + p["failure_count"], 1)
            if provider in healthy_providers and success_rate > 0.7:
                return f"{provider}/{p['model']}"
    except Exception as exc:
        logger.warning("llm_manager: get_best_llm %s: %s", agent_name, exc)
    return healthy_providers[0] if healthy_providers else "ollama"


def run(state: dict) -> dict:
    from graph_engine.llm import invoke_with_fallback
    from graph_engine.tools.supabase_tools import send_agent_message, insert_agent_event, log_event
    from langchain_core.messages import SystemMessage, HumanMessage

    findings = []
    decisions = []
    db = __import__("db").get_supabase()

    # 1. Verificar saúde de todos os providers
    logger.info("llm_manager: checando %d providers...", len(_PROVIDERS))
    health_results = []
    for p_cfg in _PROVIDERS:
        result = _check_provider(p_cfg["provider"], p_cfg["model"], p_cfg["key_field"])
        health_results.append(result)
        logger.info("llm_manager: %s/%s → %s (%dms)", result["provider"], result["model"], result["status"], result.get("latency_ms", 0))

    _save_health_metrics(db, health_results)

    healthy = [r for r in health_results if r["status"] == "ok"]
    down    = [r for r in health_results if r["status"] == "error"]
    no_key  = [r for r in health_results if r["status"] == "no_key"]

    healthy_providers = list({r["provider"] for r in healthy})
    healthy_count     = len(healthy)
    total_count       = len(health_results)

    findings.append({
        "agent": "llm_manager_agent",
        "providers_checked": total_count,
        "providers_healthy": healthy_count,
        "providers_down":    len(down),
        "providers_no_key":  len(no_key),
        "healthy_list": [f"{r['provider']}/{r['model']} ({r['latency_ms']}ms)" for r in healthy],
        "down_list":    [f"{r['provider']}/{r['model']}: {r.get('error','')[:80]}" for r in down],
    })

    # 2. Detectar agentes com falhas de LLM
    failing_agents = _get_agents_with_llm_failures(db)
    if failing_agents:
        findings.append({
            "agent": "llm_manager_agent",
            "type": "agents_with_llm_failures",
            "count": len(failing_agents),
            "agents": [a["agent"] for a in failing_agents],
        })

    # 3. Handoff para agentes com falhas — envia melhor LLM disponível
    for fa in failing_agents[:5]:
        best = _get_best_llm_for_agent(db, fa["agent"], healthy_providers)
        try:
            send_agent_message(
                from_agent="llm_manager_agent",
                to_agent=fa["agent"],
                message=(
                    f"Detectada falha de LLM no seu último run.\n"
                    f"Erro: {fa['error']}\n"
                    f"LLM recomendado para seu próximo ciclo: {best}\n"
                    f"Providers atualmente saudáveis: {', '.join(healthy_providers) or 'apenas Ollama'}\n"
                    f"Ação: seu próximo run usará fallback automático via invoke_with_fallback()."
                ),
                context={"recommended_llm": best, "healthy_providers": healthy_providers},
            )
            decisions.append(f"Handoff enviado para {fa['agent']} → usar {best}")
        except Exception as exc:
            logger.warning("llm_manager: handoff %s: %s", fa["agent"], exc)

    # 4. Calcular SLAs
    # Todos os agentes devem ter pelo menos 1 LLM funcional
    all_agent_names = list(state.get("context", {}).get("active_agents", [])) or [
        "cto", "log_scanner", "security", "api_agent", "evolution_agent",
        "db_dba_agent", "proposal_supervisor", "docker_intel", "infrastructure",
        "uptime", "quality", "backend_agent", "frontend_agent",
    ]
    sla_llm_available = 100.0 if healthy_count > 0 else 0.0  # se 1+ LLM ok, todos os agentes têm acesso
    sla_response_rate = round(100 * healthy_count / max(total_count, 1), 1)

    findings.append({
        "agent": "llm_manager_agent",
        "sla_llm_available_pct":  sla_llm_available,
        "sla_response_rate_pct":  sla_response_rate,
        "agents_with_llm_failure": len(failing_agents),
        "target_sla": 100.0,
    })

    # 5. Consultar LLM para análise e recomendações de routing
    llm_analysis = ""
    try:
        summary = {
            "healthy": [f"{r['provider']}/{r['model']} {r['latency_ms']}ms" for r in healthy],
            "down": [f"{r['provider']}: {r.get('error','')[:50]}" for r in down],
            "failing_agents": [a["agent"] for a in failing_agents],
            "sla_response_rate": sla_response_rate,
        }
        response = invoke_with_fallback([
            SystemMessage(content=(
                "Você é o LLM Manager do sistema Jarvis — especialista em otimização de AI pipelines. "
                "Analise o estado dos LLMs e dê 3 recomendações técnicas concretas para:\n"
                "1. Melhorar disponibilidade e routing de LLMs\n"
                "2. Reduzir falhas nos agentes\n"
                "3. Configurar novos LLMs gratuitos/open-source se necessário\n"
                "Resposta em PT-BR, máximo 200 palavras."
            )),
            HumanMessage(content=f"Estado atual:\n{json.dumps(summary, ensure_ascii=False)}"),
        ], timeout_s=45)
        llm_analysis = response.content[:600]
    except Exception as exc:
        llm_analysis = f"Análise indisponível: {exc}"
        logger.warning("llm_manager: análise LLM: %s", exc)

    # 6. Relatório ao CTO
    now_str = datetime.now(timezone.utc).strftime("%d/%m/%Y %H:%M UTC")
    healthy_str = ", ".join(f"{r['provider']}/{r['model']} ({r['latency_ms']}ms)" for r in healthy) or "NENHUM"
    down_str = ", ".join(f"{r['provider']}/{r['model']}" for r in down) or "nenhum"

    report = (
        f"🤖 LLM MANAGER — {now_str}\n\n"
        f"✅ Providers saudáveis ({healthy_count}/{total_count}): {healthy_str}\n"
        f"❌ Providers fora: {down_str}\n"
        f"🔑 Sem chave configurada: {len(no_key)} providers\n\n"
        f"📊 SLAs:\n"
        f"  Disponibilidade LLM: {sla_llm_available}% (meta: 100%)\n"
        f"  Taxa de resposta: {sla_response_rate}% (meta: 100%)\n"
        f"  Agentes com falha de LLM: {len(failing_agents)}\n\n"
        f"💡 Análise:\n{llm_analysis[:400]}"
    )

    try:
        send_agent_message(
            from_agent="llm_manager_agent",
            to_agent="cto",
            message=report,
            context={
                "healthy_providers": healthy_providers,
                "sla_available": sla_llm_available,
                "sla_response": sla_response_rate,
                "failing_agents": [a["agent"] for a in failing_agents],
            },
        )
        decisions.append("Relatório enviado ao CTO")
    except Exception as exc:
        logger.warning("llm_manager: envio CTO: %s", exc)

    # 7. Evento crítico se SLA abaixo de 100%
    if sla_llm_available < 100 or len(failing_agents) > 3:
        try:
            insert_agent_event(
                event_type="llm_sla_critical",
                source="llm_manager_agent",
                payload={
                    "sla_available": sla_llm_available,
                    "failing_agents": [a["agent"] for a in failing_agents],
                    "down_providers": [r["provider"] for r in down],
                },
                priority="high",
            )
        except Exception:
            pass

    log_event(
        "info" if sla_llm_available >= 100 else "warning",
        "llm_manager_agent",
        f"SLA: {sla_llm_available}% disponibilidade | {healthy_count}/{total_count} providers ok | {len(failing_agents)} agentes com falha",
    )

    return {
        "findings": findings,
        "decisions": decisions,
        "context": {
            "llm_manager_run": datetime.now(timezone.utc).isoformat(),
            "healthy_providers": healthy_providers,
            "sla_available": sla_llm_available,
            "sla_response_rate": sla_response_rate,
        },
        "next_agent": "END",
    }


def build():
    from graph_engine.agents.base import build_deterministic_agent
    return build_deterministic_agent(run)
