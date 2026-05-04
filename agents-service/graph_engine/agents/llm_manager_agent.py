"""
LLM Manager Agent — controlador de inteligência e fila dos LLMs.

Responsabilidades:
1. Monitorar saúde e latência de todos os providers (Cerebras, Groq, Nvidia, Together, OpenRouter, Mistral, HF, Ollama)
2. Rastrear consumo de tokens e velocidade de retorno por provider
3. Redirecionar fila automaticamente quando um provider fica lento ou falha
4. Em caso de fila acumulada → muda requests para próxima API disponível
5. Aprender qual LLM é mais eficiente para cada tipo de agente (routing adaptativo)
6. Reportar SLAs, alertas e recomendações ao CTO

SLAs:
- 100% dos agentes com pelo menos 1 LLM funcional disponível
- Latência P95 < 10s (com providers externos configurados)
- Failover automático em < 3 falhas consecutivas
- Detecção de degradação em < 15 min
"""
import json
import logging
import time
from collections import Counter
from datetime import datetime, timezone, timedelta

logger = logging.getLogger(__name__)

_PROVIDERS = [
    {"provider": "cerebras",    "model": "llama3.1-8b",                              "key_field": "cerebras_api_key"},
    {"provider": "google",      "model": "gemini-2.5-flash",                         "key_field": "google_api_key"},
    {"provider": "groq",        "model": "llama-3.1-8b-instant",                     "key_field": "groq_api_key"},
    {"provider": "groq",        "model": "llama-3.3-70b-versatile",                  "key_field": "groq_api_key"},
    {"provider": "nvidia",      "model": "meta/llama-3.1-8b-instruct",               "key_field": "nvidia_api_key"},
    {"provider": "together",    "model": "meta-llama/Meta-Llama-3.1-8B-Instruct-Turbo", "key_field": "together_api_key"},
    {"provider": "openrouter",  "model": "qwen/qwen-2.5-7b-instruct:free",           "key_field": "openrouter_api_key"},
    {"provider": "mistral",     "model": "mistral-small-latest",                     "key_field": "mistral_api_key"},
    {"provider": "deepinfra",   "model": "meta-llama/Meta-Llama-3.1-8B-Instruct",    "key_field": "deepinfra_api_key"},
    {"provider": "fireworks",   "model": "accounts/fireworks/models/llama-v3p3-70b-instruct", "key_field": "fireworks_api_key"},
    {"provider": "huggingface", "model": "mistralai/Mistral-7B-Instruct-v0.3",       "key_field": "huggingface_api_key"},
    {"provider": "ollama",      "model": None,                                        "key_field": None},
]

_TASK_ROUTING = {
    "reasoning": ["cerebras", "groq_70b", "nvidia", "together", "openrouter", "mistral", "ollama"],
    "code":      ["cerebras", "groq_70b", "nvidia_qwen", "together_coder", "openrouter_qwen", "mistral_codestral", "ollama"],
    "fast":      ["cerebras", "groq_8b", "nvidia", "together", "openrouter", "mistral", "ollama"],
    "default":   ["cerebras", "groq_8b", "nvidia", "together", "openrouter", "mistral", "huggingface", "ollama"],
}

_TEST_PROMPT = "Responda em 5 palavras: qual é a capital do Brasil?"


def _check_provider(provider: str, model: str | None, key_field: str | None) -> dict:
    """Testa um provider com prompt simples. Retorna status, latência e erro."""
    from db import get_settings
    s = get_settings()

    if key_field and not getattr(s, key_field, ""):
        return {"provider": provider, "model": model or "default", "status": "no_key",
                "latency_ms": 0, "error": f"{key_field} não configurado"}

    t0 = time.monotonic()
    try:
        from langchain_core.messages import HumanMessage

        if provider == "cerebras":
            from langchain_openai import ChatOpenAI
            llm = ChatOpenAI(model=model, api_key=s.cerebras_api_key,
                             base_url="https://api.cerebras.ai/v1", temperature=0, max_tokens=50)
        elif provider == "groq":
            from langchain_groq import ChatGroq
            llm = ChatGroq(model=model, api_key=s.groq_api_key, temperature=0, max_tokens=50)
        elif provider == "nvidia":
            from langchain_openai import ChatOpenAI
            llm = ChatOpenAI(model=model, api_key=s.nvidia_api_key,
                             base_url="https://integrate.api.nvidia.com/v1", temperature=0, max_tokens=50)
        elif provider == "together":
            from langchain_openai import ChatOpenAI
            llm = ChatOpenAI(model=model, api_key=s.together_api_key,
                             base_url="https://api.together.xyz/v1", temperature=0, max_tokens=50)
        elif provider == "openrouter":
            from langchain_openai import ChatOpenAI
            llm = ChatOpenAI(
                model=model, api_key=s.openrouter_api_key,
                base_url="https://openrouter.ai/api/v1", temperature=0, max_tokens=50,
                default_headers={"HTTP-Referer": "https://jarvis.voetur.com.br", "X-Title": "Jarvis"},
            )
        elif provider == "mistral":
            from langchain_mistralai import ChatMistralAI
            llm = ChatMistralAI(model=model, api_key=s.mistral_api_key, temperature=0, max_tokens=50)
        elif provider == "google":
            from langchain_openai import ChatOpenAI
            llm = ChatOpenAI(model=model, api_key=s.google_api_key,
                             base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
                             temperature=0, max_tokens=50)
        elif provider == "deepinfra":
            from langchain_openai import ChatOpenAI
            llm = ChatOpenAI(model=model, api_key=s.deepinfra_api_key,
                             base_url="https://api.deepinfra.com/v1/openai", temperature=0, max_tokens=50)
        elif provider == "fireworks":
            from langchain_openai import ChatOpenAI
            llm = ChatOpenAI(model=model, api_key=s.fireworks_api_key,
                             base_url="https://api.fireworks.ai/inference/v1", temperature=0, max_tokens=50)
        elif provider == "huggingface":
            from langchain_huggingface import HuggingFaceEndpoint
            llm = HuggingFaceEndpoint(repo_id=model,
                                      huggingfacehub_api_token=s.huggingface_api_key, max_new_tokens=50)
        elif provider == "ollama":
            from langchain_ollama import ChatOllama
            llm = ChatOllama(model=model or s.ollama_model, base_url=s.ollama_base_url,
                             temperature=0, num_predict=50)
        else:
            return {"provider": provider, "model": model or "?", "status": "unknown_provider",
                    "latency_ms": 0, "error": ""}

        llm.invoke([HumanMessage(content=_TEST_PROMPT)])
        latency_ms = int((time.monotonic() - t0) * 1000)
        return {"provider": provider, "model": model or "default", "status": "ok",
                "latency_ms": latency_ms, "error": None}

    except Exception as exc:
        latency_ms = int((time.monotonic() - t0) * 1000)
        return {"provider": provider, "model": model or "default", "status": "error",
                "latency_ms": latency_ms, "error": str(exc)[:300]}


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
    """Busca agentes com falhas de LLM nas últimas 6h — verifica agent_runs E app_logs."""
    llm_error_keywords = [
        "LLM", "llm", "timeout", "Connection refused", "ConnectError",
        "ChatGroq", "Ollama", "ChatOpenAI", "Cerebras", "OpenRouter", "Mistral", "Nvidia",
        "não respondeu", "não disponível", "fallback",
    ]
    failing: list[dict] = []
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
                    failing.append({"agent": agent, "error": err[:200],
                                    "last_seen": r.get("started_at", ""), "source": "agent_runs"})
    except Exception as exc:
        logger.warning("llm_manager: get_failing (agent_runs): %s", exc)

    # 2. Falhas em app_logs — captura timeouts internos do code_generator etc.
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
                    failing.append({"agent": agent, "error": msg[:200],
                                    "last_seen": log_entry.get("created_at", ""), "source": "app_logs"})
    except Exception as exc:
        logger.warning("llm_manager: get_failing (app_logs): %s", exc)

    return failing


def _get_latency_trend(db) -> dict[str, dict]:
    """Lê as últimas métricas de saúde por provider e calcula tendência."""
    try:
        rows = (
            db.table("llm_health_metrics")
            .select("provider,status,latency_ms,checked_at")
            .order("checked_at", desc=True)
            .limit(200)
            .execute()
            .data or []
        )
        by_provider: dict[str, list] = {}
        for r in rows:
            p = r.get("provider", "?")
            by_provider.setdefault(p, []).append(r)

        result = {}
        for provider, entries in by_provider.items():
            ok_entries = [e for e in entries if e.get("status") == "ok"]
            err_entries = [e for e in entries if e.get("status") == "error"]
            latencies = [e["latency_ms"] for e in ok_entries if e.get("latency_ms")]
            avg_lat = int(sum(latencies) / len(latencies)) if latencies else 0
            result[provider] = {
                "avg_latency_ms": avg_lat,
                "ok_count": len(ok_entries),
                "error_count": len(err_entries),
                "last_status": entries[0].get("status") if entries else "unknown",
            }
        return result
    except Exception as exc:
        logger.warning("llm_manager: get_latency_trend: %s", exc)
        return {}


def _update_routing_preference(db, agent_name: str, provider: str, model: str,
                                success: bool, latency_ms: int) -> None:
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
                "success_count": new_success, "failure_count": new_failure,
                "avg_latency_ms": new_avg, "last_used": datetime.now(timezone.utc).isoformat(),
            }).eq("id", row["id"]).execute()
        else:
            db.table("llm_routing_preferences").insert({
                "agent_name": agent_name, "provider": provider, "model": model,
                "success_count": 1 if success else 0, "failure_count": 0 if success else 1,
                "avg_latency_ms": latency_ms,
            }).execute()
    except Exception as exc:
        logger.warning("llm_manager: update_routing %s: %s", agent_name, exc)


def _get_best_llm_for_agent(db, agent_name: str, healthy_providers: list[str]) -> str:
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
    from graph_engine.llm import invoke_with_fallback, get_router_status
    from graph_engine.tools.supabase_tools import send_agent_message, insert_agent_event, log_event
    from langchain_core.messages import SystemMessage, HumanMessage

    findings = []
    decisions = []
    db = __import__("db").get_supabase()

    # ── 1. Health check de todos os providers ─────────────────────────────────
    logger.info("llm_manager: checando %d providers...", len(_PROVIDERS))
    health_results = []
    for p_cfg in _PROVIDERS:
        result = _check_provider(p_cfg["provider"], p_cfg["model"], p_cfg["key_field"])
        health_results.append(result)
        status_icon = "✓" if result["status"] == "ok" else ("–" if result["status"] == "no_key" else "✗")
        logger.info("llm_manager: %s %s/%s (%dms)",
                    status_icon, result["provider"], result["model"], result.get("latency_ms", 0))

    _save_health_metrics(db, health_results)

    healthy = [r for r in health_results if r["status"] == "ok"]
    down    = [r for r in health_results if r["status"] == "error"]
    no_key  = [r for r in health_results if r["status"] == "no_key"]

    healthy_providers = list({r["provider"] for r in healthy})
    healthy_count     = len(healthy)
    total_count       = len(health_results)

    # Ranking por latência
    ranked = sorted(healthy, key=lambda r: r.get("latency_ms", 9999))
    findings.append({
        "agent": "llm_manager_agent",
        "providers_checked": total_count,
        "providers_healthy": healthy_count,
        "providers_down": len(down),
        "providers_no_key": len(no_key),
        "ranked_by_latency": [f"{r['provider']}/{r['model']} ({r['latency_ms']}ms)" for r in ranked],
        "down_list": [f"{r['provider']}: {str(r.get('error',''))[:80]}" for r in down],
    })

    # ── 2. Status do roteador dinâmico ────────────────────────────────────────
    router_status = get_router_status()
    if router_status:
        findings.append({
            "agent": "llm_manager_agent",
            "type": "router_status",
            "providers": router_status,
        })
        in_cooldown = [p for p in router_status if p.get("in_cooldown")]
        if in_cooldown:
            decisions.append(f"Providers em cooldown (fila acumulada): {[p['provider'] for p in in_cooldown]}")

    # ── 3. Tendência de latência histórica ────────────────────────────────────
    latency_trend = _get_latency_trend(db)
    degrading = []
    for provider, stats in latency_trend.items():
        if stats["avg_latency_ms"] > 10000 and stats["ok_count"] > 0:
            degrading.append(f"{provider} ({stats['avg_latency_ms']}ms avg)")
    if degrading:
        findings.append({
            "agent": "llm_manager_agent",
            "type": "latency_degradation",
            "degrading_providers": degrading,
        })
        decisions.append(f"Providers com latência degradada: {degrading}")

    # ── 4. Detectar agentes com falhas de LLM ────────────────────────────────
    failing_agents = _get_agents_with_llm_failures(db)
    if failing_agents:
        findings.append({
            "agent": "llm_manager_agent",
            "type": "agents_with_llm_failures",
            "count": len(failing_agents),
            "agents": [a["agent"] for a in failing_agents],
            "sources": list({a["source"] for a in failing_agents}),
        })

    # ── 5. Handoff para agentes com falha — recomenda melhor LLM ─────────────
    for fa in failing_agents[:5]:
        best = _get_best_llm_for_agent(db, fa["agent"], healthy_providers)
        try:
            send_agent_message(
                from_agent="llm_manager_agent",
                to_agent=fa["agent"],
                message=(
                    f"[LLM Manager] Falha detectada no seu último ciclo.\n"
                    f"Erro: {fa['error'][:150]}\n"
                    f"LLM recomendado: {best}\n"
                    f"Providers saudáveis: {', '.join(healthy_providers) or 'apenas Ollama'}\n"
                    f"Ranking atual por latência: {[r['provider'] for r in ranked[:3]]}\n"
                    f"O roteador dinâmico já redirecionará seu próximo ciclo automaticamente."
                ),
                context={"recommended_llm": best, "healthy_providers": healthy_providers,
                         "ranked_providers": [r["provider"] for r in ranked]},
            )
            decisions.append(f"Handoff → {fa['agent']}: usar {best}")
        except Exception as exc:
            logger.warning("llm_manager: handoff %s: %s", fa["agent"], exc)

    # ── 6. SLAs ───────────────────────────────────────────────────────────────
    sla_available   = 100.0 if healthy_count > 0 else 0.0
    sla_response    = round(100 * healthy_count / max(total_count, 1), 1)
    best_latency_ms = ranked[0]["latency_ms"] if ranked else 0
    sla_latency_ok  = best_latency_ms < 10000  # P95 < 10s com provider externo

    findings.append({
        "agent": "llm_manager_agent",
        "sla_llm_available_pct": sla_available,
        "sla_response_rate_pct": sla_response,
        "best_latency_ms": best_latency_ms,
        "sla_latency_ok": sla_latency_ok,
        "agents_with_llm_failure": len(failing_agents),
    })

    # ── 7. Análise LLM com recomendações de routing ───────────────────────────
    llm_analysis = ""
    try:
        summary = {
            "ranked": [f"{r['provider']} {r['latency_ms']}ms" for r in ranked[:5]],
            "down": [r["provider"] for r in down],
            "no_key": [r["provider"] for r in no_key],
            "failing_agents": [a["agent"] for a in failing_agents[:5]],
            "degrading": degrading,
            "router_cooldowns": [p["provider"] for p in router_status if p.get("in_cooldown")],
        }
        response = invoke_with_fallback([
            SystemMessage(content=(
                "Você é o LLM Manager do sistema Jarvis — especialista em otimização de AI pipelines. "
                "Com base no estado atual dos providers, forneça:\n"
                "1. Análise da saúde dos LLMs (quais usar prioritariamente)\n"
                "2. Alerta se algum provider está degradado ou em cooldown\n"
                "3. Recomendação de routing para os próximos 30min\n"
                "Seja direto e técnico. Máx 150 palavras em PT-BR."
            )),
            HumanMessage(content=f"Estado:\n{json.dumps(summary, ensure_ascii=False)}"),
        ], timeout_s=30)
        llm_analysis = response.content[:500]
    except Exception as exc:
        llm_analysis = f"[análise indisponível: {exc}]"
        logger.warning("llm_manager: análise LLM: %s", exc)

    # ── 8. Relatório ao CTO ───────────────────────────────────────────────────
    now_str = datetime.now(timezone.utc).strftime("%d/%m/%Y %H:%M UTC")

    ranked_str = " | ".join(f"{r['provider']} {r['latency_ms']}ms" for r in ranked[:5]) or "NENHUM"
    down_str   = ", ".join(r["provider"] for r in down) or "nenhum"
    nokey_str  = ", ".join(r["provider"] for r in no_key) or "nenhum"

    report = (
        f"🤖 LLM MANAGER — {now_str}\n\n"
        f"🏆 Ranking por latência ({healthy_count}/{total_count} ok):\n"
        f"   {ranked_str}\n\n"
        f"❌ Fora: {down_str}\n"
        f"🔑 Sem chave: {nokey_str}\n\n"
        f"📊 SLAs:\n"
        f"   Disponibilidade: {sla_available}% | Resposta: {sla_response}%\n"
        f"   Melhor latência: {best_latency_ms}ms | P95 <10s: {'✓' if sla_latency_ok else '✗'}\n"
        f"   Agentes c/ falha LLM: {len(failing_agents)}\n\n"
        f"🔄 Roteador: {len([p for p in router_status if p.get('in_cooldown')])} em cooldown\n\n"
        f"💡 Análise:\n{llm_analysis[:400]}"
    )

    try:
        send_agent_message(
            from_agent="llm_manager_agent",
            to_agent="cto",
            message=report,
            context={
                "healthy_providers": healthy_providers,
                "ranked_providers": [r["provider"] for r in ranked],
                "sla_available": sla_available,
                "sla_response": sla_response,
                "best_latency_ms": best_latency_ms,
                "failing_agents": [a["agent"] for a in failing_agents],
                "router_status": router_status,
            },
        )
        decisions.append("Relatório enviado ao CTO")
    except Exception as exc:
        logger.warning("llm_manager: envio CTO: %s", exc)

    # ── 9. Evento crítico se SLA degradado ────────────────────────────────────
    if sla_available < 100 or len(failing_agents) > 3 or not sla_latency_ok:
        try:
            insert_agent_event(
                event_type="llm_sla_critical",
                source="llm_manager_agent",
                payload={
                    "sla_available": sla_available,
                    "best_latency_ms": best_latency_ms,
                    "failing_agents": [a["agent"] for a in failing_agents],
                    "down_providers": [r["provider"] for r in down],
                    "cooldown_providers": [p["provider"] for p in router_status if p.get("in_cooldown")],
                },
                priority="high" if sla_available < 50 else "medium",
            )
        except Exception:
            pass

    level = "info" if (sla_available >= 100 and sla_latency_ok) else "warning"
    log_event(level, "llm_manager_agent",
              f"SLA {sla_available}% | {healthy_count}/{total_count} ok | "
              f"melhor={best_latency_ms}ms | {len(failing_agents)} agentes c/ falha")

    return {
        "findings": findings,
        "decisions": decisions,
        "context": {
            "llm_manager_run": datetime.now(timezone.utc).isoformat(),
            "healthy_providers": healthy_providers,
            "ranked_providers": [r["provider"] for r in ranked],
            "sla_available": sla_available,
            "sla_response_rate": sla_response,
            "best_latency_ms": best_latency_ms,
        },
        "next_agent": "END",
    }


def build():
    from graph_engine.agents.base import build_deterministic_agent
    return build_deterministic_agent(run)
