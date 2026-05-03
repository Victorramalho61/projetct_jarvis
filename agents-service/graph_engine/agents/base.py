"""Base para agentes LangGraph — determinísticos e LLM."""
from typing import Callable

from langchain_core.messages import HumanMessage
from langgraph.graph import END, START, StateGraph

from graph_engine.state import JarvisState


def build_deterministic_agent(run_fn: Callable[[dict], dict]) -> object:
    """Cria grafo LangGraph simples para agentes sem LLM."""

    def agent_node(state: JarvisState) -> dict:
        result = run_fn(state)
        return {
            "findings": state.get("findings", []) + result.get("findings", []),
            "decisions": state.get("decisions", []) + result.get("decisions", []),
            "context": {**state.get("context", {}), **result.get("context", {})},
        }

    graph = StateGraph(JarvisState)
    graph.add_node("agent", agent_node)
    graph.add_edge(START, "agent")
    graph.add_edge("agent", END)
    return graph.compile()


def build_llm_agent(tools: list, system_prompt: str) -> object:
    """Cria agente ReAct com LLM (Ollama/Groq) e ferramentas."""
    from langgraph.prebuilt import create_react_agent
    from graph_engine.llm import get_reasoning_llm

    model = get_reasoning_llm()
    return create_react_agent(model, tools, state_modifier=system_prompt)
