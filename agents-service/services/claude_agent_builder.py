import logging

import anthropic

from db import get_supabase

logger = logging.getLogger(__name__)

_DB_SCHEMA_SUMMARY = """
Tabelas disponíveis (acesso read-only via SUPABASE_ANON_KEY):
- profiles: id, username, display_name, email, role, whatsapp_phone
- monitored_systems: id, name, type, url, status, last_checked_at
- system_checks: id, system_id, status, latency_ms, checked_at
- app_logs: id, level, module, message, detail, created_at
- freshservice_tickets: id, subject, status, priority, group_id, responder_id,
    created_at, resolved_at, csat_rating, resolution_time_min, sla_breached
- freshservice_agents: id, name, email
- freshservice_groups: id, name
- freshservice_sync_log: id, sync_type, status, tickets_upserted, started_at, completed_at
- agents: id, name, description, agent_type, config, schedule_type, schedule_config, enabled
- agent_runs: id, agent_id, status, output, error, started_at, finished_at
"""

_SYSTEM = f"""Você é um assistente especializado em criar agentes automáticos para o sistema Jarvis \
(Voetur/VTCLog). Responda sempre em português.

Você pode criar agentes que executam tarefas agendadas. Tipos disponíveis:
- **freshservice_sync**: Dispara o sync diário do Freshservice (sem código Python necessário)
- **script**: Executa código Python personalizado

**Schema do banco de dados:**
{_DB_SCHEMA_SUMMARY}

**Ao gerar código Python para agente 'script':**
- O código roda em subprocess isolado com acesso READ-ONLY ao banco
- Variáveis de ambiente disponíveis: SUPABASE_URL, SUPABASE_ANON_KEY
- Bibliotecas disponíveis: httpx, supabase-py, json, datetime, os
- Use print() para resultados — tudo impresso fica no log de execução
- NÃO disponível: SERVICE_ROLE_KEY, escrita no banco via anon key, acesso ao filesystem

**Tipos de agendamento:**
- manual: só executa quando acionado manualmente
- interval: a cada N minutos (schedule_config: {{"minutes": 30}})
- daily: todo dia em horário fixo BRT (schedule_config: {{"hour": 9, "minute": 0}})
- weekly: dia da semana + hora BRT (schedule_config: {{"day_of_week": "mon", "hour": 9, "minute": 0}})
- monthly: dia do mês + hora BRT (schedule_config: {{"day": 1, "hour": 9, "minute": 0}})

Sempre confirme nome, tipo de agente e agendamento com o usuário antes de chamar create_agent."""

_TOOLS = [
    {
        "name": "create_agent",
        "description": (
            "Cria um novo agente no sistema Jarvis. "
            "Chame apenas após confirmar todos os detalhes com o usuário."
        ),
        "input_schema": {
            "type": "object",
            "required": ["name", "agent_type", "schedule_type"],
            "properties": {
                "name":            {"type": "string", "description": "Nome do agente"},
                "description":     {"type": "string", "description": "Descrição opcional"},
                "agent_type":      {"type": "string", "enum": ["freshservice_sync", "script"]},
                "code":            {
                    "type": "string",
                    "description": "Código Python (obrigatório para agent_type=script)",
                },
                "schedule_type":   {
                    "type": "string",
                    "enum": ["manual", "interval", "daily", "weekly", "monthly"],
                },
                "schedule_config": {
                    "type": "object",
                    "description": "Configuração do agendamento conforme o schedule_type",
                },
            },
        },
    },
]


async def chat(message: str, history: list[dict], user: dict, api_key: str) -> dict:
    client = anthropic.Anthropic(api_key=api_key)
    messages = history + [{"role": "user", "content": message}]

    response = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=1536,
        system=_SYSTEM,
        tools=_TOOLS,
        messages=messages,
    )

    agent_created = None
    text_parts = []

    for block in response.content:
        if block.type == "text":
            text_parts.append(block.text)
        elif block.type == "tool_use" and block.name == "create_agent":
            try:
                agent_created = _do_create_agent(block.input, user)
                text_parts.append(f"\n✅ Agente **{agent_created['name']}** criado com sucesso!")
            except Exception as exc:
                logger.exception("Erro ao criar agente via Claude")
                text_parts.append(f"\n❌ Erro ao criar agente: {exc}")

    return {
        "reply": "\n".join(text_parts),
        "agent_created": agent_created,
        "stop_reason": response.stop_reason,
    }


def _do_create_agent(params: dict, user: dict) -> dict:
    db = get_supabase()
    payload = {
        "name":            params["name"],
        "description":     params.get("description", ""),
        "agent_type":      params["agent_type"],
        "config":          {"code": params.get("code", "")} if params["agent_type"] == "script" else {},
        "schedule_type":   params.get("schedule_type", "manual"),
        "schedule_config": params.get("schedule_config") or {},
        "enabled":         True,
        "created_by":      user["id"],
    }
    agent = db.table("agents").insert(payload).execute().data[0]
    from services.scheduler import reload_agents
    reload_agents()
    return agent
