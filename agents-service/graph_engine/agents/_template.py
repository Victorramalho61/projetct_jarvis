"""
<AGENT_NAME> — <descrição em uma linha>

SLA:
  - Pipeline: <governance|security|monitoring|cicd|dba|evolution|documentation>
  - Tipo: determinístico (sem LLM) | LLM
  - Timeout esperado: <Xs>
  - Findings gerados: <tipo_finding>
  - Decisions geradas: <tipo_decision>
"""
import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


def run(state: dict) -> dict:
    findings = []
    decisions = []

    # --- lógica do agente aqui ---
    # Acesso ao banco:
    #   from db import get_supabase
    #   db = get_supabase()
    #
    # Acesso a ferramentas:
    #   from graph_engine.tools.supabase_tools import query_improvement_proposals
    #
    # Sempre retornar findings e decisions mesmo que vazios
    # Use level="warning" para alertas de negócio, "error" apenas para crashes

    findings.append({
        "type": "<tipo_finding>",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })

    return {"findings": findings, "decisions": decisions}


def build():
    from graph_engine.agents.base import build_deterministic_agent
    return build_deterministic_agent(run)
