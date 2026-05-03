"""
LLM Manager — suporte a múltiplos providers open-source gratuitos.

Cascata de prioridade (mais rápido → mais lento):
1. Cerebras   (cloud.cerebras.ai — free tier, CS-3 chip, ~0.1s/token)
2. Groq       (groq.com — free tier, ultrarrápido, Llama/Mixtral)
3. Together   (api.together.xyz — free tier, OpenAI-compat)
4. OpenRouter (openrouter.ai — free models aggregator, OpenAI-compat)
5. Mistral    (mistral.ai — free tier)
6. HuggingFace (huggingface.co — free inference API, lento)
7. Ollama     (local — sempre disponível, não depende de internet)

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


def _make_cerebras(model: str = "llama-3.3-70b") -> Any | None:
    s = get_settings()
    if not s.cerebras_api_key:
        return None
    try:
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(
            model=model,
            api_key=s.cerebras_api_key,
            base_url="https://api.cerebras.ai/v1",
            temperature=0,
            max_tokens=4096,
        )
    except Exception as e:
        log.warning("Cerebras indisponível: %s", e)
        return None


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


def _make_together(model: str = "meta-llama/Meta-Llama-3.1-8B-Instruct-Turbo") -> Any | None:
    s = get_settings()
    if not s.together_api_key:
        return None
    try:
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(
            model=model,
            api_key=s.together_api_key,
            base_url="https://api.together.xyz/v1",
            temperature=0,
            max_tokens=4096,
        )
    except Exception as e:
        log.warning("Together AI indisponível: %s", e)
        return None


def _make_openrouter(model: str = "meta-llama/llama-3.1-8b-instruct:free") -> Any | None:
    s = get_settings()
    if not s.openrouter_api_key:
        return None
    try:
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(
            model=model,
            api_key=s.openrouter_api_key,
            base_url="https://openrouter.ai/api/v1",
            temperature=0,
            max_tokens=4096,
            default_headers={
                "HTTP-Referer": "https://jarvis.voetur.com.br",
                "X-Title": "Jarvis",
            },
        )
    except Exception as e:
        log.warning("OpenRouter indisponível: %s", e)
        return None


def _make_mistral(model: str = "mistral-small-latest") -> Any | None:
    s = get_settings()
    if not s.mistral_api_key:
        return None
    try:
        from langchain_mistralai import ChatMistralAI
        return ChatMistralAI(model=model, api_key=s.mistral_api_key, temperature=0, max_tokens=4096)
    except Exception as e:
        log.warning("Mistral indisponível: %s", e)
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
    """Melhor LLM disponível para raciocínio. Cascata: Cerebras → Groq 70B → Groq 8B → Together → OpenRouter → Mistral → HF → Ollama."""
    return (
        _make_cerebras("llama-3.3-70b")
        or _make_groq("llama-3.3-70b-versatile")
        or _make_groq("llama-3.1-8b-instant")
        or _make_together("meta-llama/Meta-Llama-3.1-70B-Instruct-Turbo")
        or _make_openrouter("meta-llama/llama-3.1-8b-instruct:free")
        or _make_mistral("mistral-small-latest")
        or _make_huggingface()
        or _make_ollama()
    )


def get_fast_llm() -> Any:
    """LLM mais rápido disponível. Prioriza modelos menores com menor latência."""
    return (
        _make_cerebras("llama-3.1-8b")
        or _make_groq("llama-3.1-8b-instant")
        or _make_groq("gemma2-9b-it")
        or _make_together("meta-llama/Meta-Llama-3.1-8B-Instruct-Turbo")
        or _make_openrouter("meta-llama/llama-3.2-1b-instruct:free")
        or _make_mistral("mistral-small-latest")
        or _make_ollama()
    )


def get_code_llm() -> Any:
    """Melhor LLM para geração de código."""
    return (
        _make_cerebras("llama-3.3-70b")
        or _make_groq("llama-3.3-70b-versatile")
        or _make_groq("llama3-70b-8192")
        or _make_together("Qwen/Qwen2.5-Coder-32B-Instruct")
        or _make_openrouter("qwen/qwen-2.5-coder-32b-instruct:free")
        or _make_mistral("codestral-latest")
        or _make_ollama("codellama:latest")
        or _make_ollama()
    )


def get_all_llms() -> list[Any]:
    """Todos os LLMs configurados e disponíveis, em ordem de prioridade."""
    candidates = [
        _make_cerebras(),
        _make_groq("llama-3.1-8b-instant"),
        _make_together(),
        _make_openrouter(),
        _make_mistral(),
        _make_huggingface(),
        _make_ollama(),
    ]
    return [llm for llm in candidates if llm is not None]


def invoke_llm_with_timeout(llm: Any, messages: list, timeout_s: int = _LLM_TIMEOUT_S) -> Any:
    """Invoca LLM com timeout e circuit breaker."""
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
    Tenta invocar com cascata completa: Cerebras → Groq → Together → OpenRouter → Mistral → HF → Ollama.
    Retorna resposta do primeiro que funcionar. Lança RuntimeError se todos falharem.
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
