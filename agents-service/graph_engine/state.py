import operator
from typing import Annotated, Literal, Sequence, TypedDict

from langchain_core.messages import BaseMessage


class JarvisState(TypedDict):
    messages: Annotated[Sequence[BaseMessage], operator.add]
    agent_id: str
    thread_id: str
    # Dados coletados pelo agente durante a execu��o
    context: dict
    # Descobertas: erros, anomalias, m�tricas
    findings: list
    # Decis�es tomadas (pelo CTO ou pelo pr�prio agente)
    decisions: list
    # Pr�ximo agente a ser ativado (usado pelo CTO para roteamento)
    next_agent: str

    # --- Orquestra��o v2.0 ---
    # Prioridade da tarefa atual
    priority: Literal["critical", "high", "medium", "low"]
    # Flag de janela de deploy ativa (suspende automa��es de uptime)
    deployment_active: bool
    # Pipeline em execu��o: auto_fix | governance | monitoring | security | manual
    current_pipeline: str
    # Passo atual dentro do pipeline (para rastreamento)
    pipeline_step: int
    # Propostas de corre��o geradas pelo pipeline auto_fix ou log_intelligence
    correction_proposals: list
    # Indica que o problema requer interven��o humana (escalado ao Freshservice)
    escalation_required: bool
    # Contexto acumulado pelo CTO ao longo do ciclo de governan�a
    cto_context: dict
    # Sa�de de cada agente filho: {"log_scanner": "ok", "security": "warning", ...}
    agent_health: dict
    # ID do task no agent_tasks que originou esta execu��o (rastreabilidade)
    task_id: str
