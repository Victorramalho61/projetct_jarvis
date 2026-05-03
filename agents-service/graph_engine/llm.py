"""
LLM Manager — suporte a múltiplos providers open-source gratuitos.

Cascata de prioridade:
1. Groq     (groq.com — free tier, ultrarrápido, modelos Llama/Mixtral)
2. Together (together.ai — free tier, modelos open-source variados)
3. HuggingFace (huggingface.co — free inference API, mais lento)
4. Ollama   (local — sempre disponível, não depende de internet)

Os agentes podem pedir LLMs por capacidade:
- get_reasoning_llm()  — melhor disponível para raciocínio
- get_fast_llm()       — mais rápido disponível (menor latência)
- get_code_llm()       — melhor para geração de código
- get_all_llms()       — todos disponíveis (para consenso ou fallback manual)
"""
import logging
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeout
from typing import Any

from db import get_settings

log = logging.getLogger(__name__)
_LLM_TIMEOUT_S = 45


def _make_groq(model: str = "llama-3.1-8b-instant") -> Any | None:
    s = get_settings()
    if not s.groq_api_key:
        return None
    try:
        from langchain_groq import ChatGroq
        return ChatGroq(model=model, api_key=s.groq_api_key, temperature=0, max_tokens=4096)
    except Exception as e:
        log.warning("Groq indisponível: %s", e)
        return None


def _make_together(model: str = "meta-llama/Llama-3.2-11B-Vision-Instruct-Turbo") -> Any | None:
    s = get_settings()
    if not s.together_api_key:
        return None
    try:
        from langchain_together import ChatTogether
        return ChatTogether(model=model, together_api_key=s.together_api_key, temperature=0, max_tokens=4096)
    except Exception as e:
        log.warning("Together AI indisponível: %s", e)
        return None


def _make_huggingface(model: str = "HuggingFaceH4/zephyr-7b-beta") -> Any | None:
    s = get_settings()
    if not s.huggingface_api_key:
        return None
    try:
        from langchain_huggingface import HuggingFaceEndpoint
        return HuggingFaceEndpoint(
            repo_id=model,
            huggingfacehub_api_token=s.huggingface_api_key,
            max_new_tokens=2048,
            temperature=0.01,
        )
    except Exception as e:
        log.warning("HuggingFace indisponível: %s", e)
        return None


def _make_ollama(model: str | None = None) -> Any:
    s = get_settings()
    from langchain_ollama import ChatOllama
    return ChatOllama(
        model=model or s.ollama_model,
        base_url=s.ollama_base_url,
        temperature=0,
        num_predict=4096,
    )


def get_reasoning_llm() -> Any:
    """Melhor LLM disponível para raciocínio contextual. Cascata: Groq → Together → HF → Ollama."""
    return (
        _make_groq("llama-3.3-70b-versatile")
        or _make_groq("llama-3.1-8b-instant")
        or _make_together()
        or _make_huggingface()
        or _make_ollama()
    )


def get_fast_llm() -> Any:
    """LLM mais rápido disponível. Prioriza modelos menores com menor latência."""
    return (
        _make_groq("llama-3.1-8b-instant")
        or _make_groq("gemma2-9b-it")
        or _make_together("meta-llama/Meta-Llama-3.1-8B-Instruct-Turbo")
        or _make_ollama()
    )


def get_code_llm() -> Any:
    """Melhor LLM para geração de código. Groq Llama é bom nisso."""
    return (
        _make_groq("llama-3.3-70b-versatile")
        or _make_groq("llama3-70b-8192")
        or _make_together("Qwen/Qwen2.5-Coder-32B-Instruct")
        or _make_ollama("codellama:latest")
        or _make_ollama()
    )


def get_all_llms() -> list[Any]:
    """Todos os LLMs configurados e disponíveis."""
    candidates = [
        _make_groq("llama-3.1-8b-instant"),
        _make_together(),
        _make_huggingface(),
        _make_ollama(),
    ]
    return [l for l in candidates if l is not None]


def invoke_llm_with_timeout(llm: Any, messages: list, timeout_s: int = _LLM_TIMEOUT_S) -> Any:
    """Invoca LLM com timeout. Se falhar, tenta o próximo na cascata."""
    from graph_engine.resilience import get_llm_circuit_breaker
    cb = get_llm_circuit_breaker()

    def _invoke():
        return llm.invoke(messages)

    with ThreadPoolExecutor(max_workers=1) as ex:
        future = ex.submit(cb.call, _invoke)
        try:
            return future.result(timeout=timeout_s)
        except FuturesTimeout:
            future.cancel()
            log.error("LLM timeout após %ds", timeout_s)
            raise TimeoutError(f"LLM não respondeu em {timeout_s}s")


def invoke_with_fallback(messages: list, timeout_s: int = _LLM_TIMEOUT_S) -> Any:
    """
    Tenta invocar com cascata completa de LLMs.
    Retorna resposta do primeiro que funcionar.
    Lança RuntimeError se todos falharem.
    """
    llms = get_all_llms()
    last_exc = None
    for llm in llms:
        try:
            return invoke_llm_with_timeout(llm, messages, timeout_s=timeout_s)
        except Exception as exc:
            log.warning("LLM %s falhou: %s — tentando próximo", type(llm).__name__, exc)
            last_exc = exc
    raise RuntimeError(f"Todos os LLMs falharam. Último erro: {last_exc}")
