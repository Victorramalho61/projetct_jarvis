"""Grafo principal de orquestração LangGraph — todos os agentes sob supervisão do CTO."""
import logging
import os
from typing import Callable

from langgraph.graph import END, START, StateGraph

from graph_engine.state import JarvisState

# LangSmith tracing (opcional — configura via LANGSMITH_API_KEY no .env)
if os.getenv("LANGSMITH_API_KEY"):
    os.environ["LANGCHAIN_TRACING_V2"] = "true"
    os.environ["LANGCHAIN_PROJECT"] = os.getenv("LANGSMITH_PROJECT", "jarvis-orchestration")
    logging.getLogger(__name__).info("LangSmith tracing habilitado")

log = logging.getLogger(__name__)

# Mapeamento nome → função build() de cada agente
_AGENT_REGISTRY: dict[str, str] = {
    "cto":                   "graph_engine.agents.cto_agent",
    "log_scanner":           "graph_engine.agents.log_scanner",
    "log_improver":          "graph_engine.agents.log_improver",
    "log_intelligence":      "graph_engine.agents.log_intelligence",
    "security":              "graph_engine.agents.security",
    "uptime":                "graph_engine.agents.uptime",
    "docker_intel":          "graph_engine.agents.docker_intel",
    "infrastructure":        "graph_engine.agents.infrastructure",
    "quality":               "graph_engine.agents.quality",
    "quality_validator":     "graph_engine.agents.quality_validator",
    "docs":                  "graph_engine.agents.docs",
    "api_agent":             "graph_engine.agents.api_agent",
    "automation":            "graph_engine.agents.automation",
    "scheduling":            "graph_engine.agents.scheduling",
    "backend_agent":         "graph_engine.agents.backend_agent",
    "frontend_agent":        "graph_engine.agents.frontend_agent",
    "code_security":         "graph_engine.agents.code_security",
    "fix_validator":         "graph_engine.agents.fix_validator",
    "change_mgmt":           "graph_engine.agents.change_mgmt",
    "change_validator":      "graph_engine.agents.change_validator",
    "integration_validator": "graph_engine.agents.integration_validator",
    "itil_version":          "graph_engine.agents.itil_version",
    # Supervisor de saúde — monitora todos os outros agentes
    "agent_health_supervisor": "graph_engine.agents.agent_health_supervisor",
    # Supervisor de proposals — garante execução das proposals aprovadas por humanos
    "proposal_supervisor":     "graph_engine.agents.proposal_supervisor",
    # Prioritizer — priorização diária de proposals pendentes via LLM
    "proposal_prioritizer":    "graph_engine.agents.proposal_prioritizer",
    # LLM Manager — monitora saúde dos LLMs e SLA de acesso dos agentes
    "llm_manager_agent":       "graph_engine.agents.llm_manager_agent",
    # CTO Assessor — arquiteto sênior, segunda opinião e crivo final das proposals
    "cto_assessor_agent":      "graph_engine.agents.cto_assessor_agent",
    # Lote 2 — novos agentes de qualidade, DBA, CI/CD e evolução
    "log_strategic_advisor":  "graph_engine.agents.log_strategic_advisor",
    "cicd_monitor":           "graph_engine.agents.cicd_monitor",
    "db_dba_agent":           "graph_engine.agents.db_dba_agent",
    "quality_code_backend":   "graph_engine.agents.quality_code_backend",
    "quality_code_frontend":  "graph_engine.agents.quality_code_frontend",
    "opportunity_scout":      "graph_engine.agents.opportunity_scout",
    "evolution_agent":        "graph_engine.agents.evolution_agent",
    # PayFly
    "payfly_media_monitor":   "graph_engine.agents.payfly_media_monitor",
}


def _load_agent_run_fn(module_path: str) -> Callable:
    """Importa dinamicamente a função run() ou build() de um agente."""
    import importlib
    mod = importlib.import_module(module_path)
    if hasattr(mod, "run"):
        return mod.run
    raise AttributeError(f"Módulo {module_path} não tem função 'run'")


# Agentes que NÃO devem ter LLM auto-enriquecimento (já têm LLM próprio ou são supervisores)
_NO_LLM_ENHANCE = {
    "cto", "evolution_agent", "db_dba_agent", "log_scanner", "log_improver",
    "log_intelligence", "log_strategic_advisor", "proposal_supervisor",
    "agent_health_supervisor",
}


def _make_node(agent_name: str, module_path: str) -> Callable:
    """Cria um nó LangGraph que executa o agente e retorna estado atualizado.
    Agentes sem LLM próprio recebem análise automática via llm_mixin."""
    def node(state: JarvisState) -> dict:
        try:
            run_fn = _load_agent_run_fn(module_path)

            # Aplica enriquecimento LLM para agentes determinísticos
            if agent_name not in _NO_LLM_ENHANCE:
                from graph_engine.agents.llm_mixin import build_llm_enhanced_agent
                run_fn = build_llm_enhanced_agent(run_fn, agent_name, auto_propose=True)

            result = run_fn(state)
            return {
                "findings":  state.get("findings", [])  + result.get("findings", []),
                "decisions": state.get("decisions", []) + result.get("decisions", []),
                "context":   {**state.get("context", {}), **result.get("context", {})},
                "next_agent": result.get("next_agent", "END"),
            }
        except Exception as e:
            log.error("Erro no agente %s: %s", agent_name, e)
            from graph_engine.tools.supabase_tools import log_event
            log_event("error", agent_name, f"Falha na execução do agente: {e}")
            return {"next_agent": "END"}
    node.__name__ = f"node_{agent_name}"
    return node


def _route_by_next_agent(state: JarvisState) -> str:
    """Roteamento condicional: lê next_agent do estado e retorna nó destino."""
    next_agent = state.get("next_agent", "END")
    if not next_agent or next_agent == "END" or next_agent not in _AGENT_REGISTRY:
        return END
    return next_agent


def build_orchestrator_graph() -> object:
    """Constrói e compila o grafo de orquestração completo."""
    graph = StateGraph(JarvisState)

    # Adiciona todos os agentes como nós
    for agent_name, module_path in _AGENT_REGISTRY.items():
        graph.add_node(agent_name, _make_node(agent_name, module_path))

    # CTO é o entry point
    graph.add_edge(START, "cto")

    # Roteamento condicional a partir do CTO
    graph.add_conditional_edges(
        "cto",
        _route_by_next_agent,
        {name: name for name in _AGENT_REGISTRY} | {END: END},
    )

    # Todos os outros agentes retornam ao CTO para avaliação, exceto via END
    for agent_name in _AGENT_REGISTRY:
        if agent_name != "cto":
            graph.add_conditional_edges(
                agent_name,
                _route_by_next_agent,
                {name: name for name in _AGENT_REGISTRY} | {END: END},
            )

    # MemorySaver: persiste estado por thread_id dentro do processo
    # Habilita checkpointing in-memory + LangSmith tracing compatível
    try:
        from langgraph.checkpoint.memory import MemorySaver
        checkpointer = MemorySaver()
        return graph.compile(checkpointer=checkpointer)
    except Exception as e:
        log.warning("MemorySaver não disponível (%s) — compilando sem checkpointer", e)
        return graph.compile()


# Instância singleton compilada (lazy)
_compiled_graph = None


def get_orchestrator() -> object:
    global _compiled_graph
    if _compiled_graph is None:
        _compiled_graph = build_orchestrator_graph()
    return _compiled_graph


def run_agent_by_name(agent_name: str, initial_state: dict | None = None, extra_state: dict | None = None) -> dict:
    """Executa um agente específico de forma isolada (sem passar pelo CTO)."""
    import importlib
    module_path = _AGENT_REGISTRY.get(agent_name)
    if not module_path:
        raise ValueError(f"Agente '{agent_name}' não registrado")
    mod = importlib.import_module(module_path)
    state = {**(initial_state or {}), **(extra_state or {})}
    if hasattr(mod, "run"):
        return mod.run(state)
    if hasattr(mod, "build"):
        compiled = mod.build()
        result = compiled.invoke(state)
        return dict(result)
    raise AttributeError(f"Agente {agent_name} não tem run() nem build()")
