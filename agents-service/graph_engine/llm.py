"""
LLM Router — roteamento dinâmico multi-provider com failover automático.

Cascata padrão (mais rápido → mais lento):
1. Cerebras   (cloud.cerebras.ai — CS-3 chip, ~0.1s/token)
2. Groq       (groq.com — free tier ultrarrápido)
3. Nvidia NIM (build.nvidia.com — free tier, modelos grandes)
4. Together   (api.together.xyz — free tier, OpenAI-compat)
5. OpenRouter (openrouter.ai — free models aggregator)
6. Mistral    (mistral.ai — free tier)
7. HuggingFace (huggingface.co — free inference API)
8. Ollama     (local — sempre disponível, sem internet)

O LLMRouter monitora latência em tempo real e reordena a cascata
automaticamente: se um provider está lento ou acumulando fila,
é rebaixado e o próximo saudável assume.
"""
import logging
import threading
import time
from collections import deque
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeout
from typing import Any

from db import get_settings

log = logging.getLogger(__name__)
_LLM_TIMEOUT_S = 45


# ── Fábrica de clientes ────────────────────────────────────────────────────────

def _make_cerebras(model: str = "llama3.3-70b") -> Any | None:
    s = get_settings()
    if not s.cerebras_api_key:
        return None
    try:
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(
            model=model, api_key=s.cerebras_api_key,
            base_url="https://api.cerebras.ai/v1",
            temperature=0, max_tokens=4096,
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


def _make_nvidia(model: str = "meta/llama-3.1-8b-instruct") -> Any | None:
    s = get_settings()
    if not s.nvidia_api_key:
        return None
    try:
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(
            model=model, api_key=s.nvidia_api_key,
            base_url="https://integrate.api.nvidia.com/v1",
            temperature=0, max_tokens=4096,
        )
    except Exception as e:
        log.warning("Nvidia NIM indisponível: %s", e)
        return None


def _make_together(model: str = "meta-llama/Meta-Llama-3.1-8B-Instruct-Turbo") -> Any | None:
    s = get_settings()
    if not s.together_api_key:
        return None
    try:
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(
            model=model, api_key=s.together_api_key,
            base_url="https://api.together.xyz/v1",
            temperature=0, max_tokens=4096,
        )
    except Exception as e:
        log.warning("Together AI indisponível: %s", e)
        return None


def _make_openrouter(model: str = "qwen/qwen-2.5-7b-instruct:free") -> Any | None:
    s = get_settings()
    if not s.openrouter_api_key:
        return None
    try:
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(
            model=model, api_key=s.openrouter_api_key,
            base_url="https://openrouter.ai/api/v1",
            temperature=0, max_tokens=4096,
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


def _make_deepinfra(model: str = "meta-llama/Meta-Llama-3.1-8B-Instruct") -> Any | None:
    s = get_settings()
    if not s.deepinfra_api_key:
        return None
    try:
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(
            model=model,
            api_key=s.deepinfra_api_key,
            base_url="https://api.deepinfra.com/v1/openai",
            temperature=0,
            max_tokens=4096,
        )
    except Exception as e:
        log.warning("DeepInfra indisponível: %s", e)
        return None


def _make_fireworks(model: str = "accounts/fireworks/models/llama-v3p3-70b-instruct") -> Any | None:
    s = get_settings()
    if not s.fireworks_api_key:
        return None
    try:
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(
            model=model,
            api_key=s.fireworks_api_key,
            base_url="https://api.fireworks.ai/inference/v1",
            temperature=0,
            max_tokens=4096,
        )
    except Exception as e:
        log.warning("Fireworks AI indisponível: %s", e)
        return None


def _make_huggingface(model: str = "mistralai/Mistral-7B-Instruct-v0.3") -> Any | None:
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


def _make_google(model: str = "gemini-2.5-flash") -> Any | None:
    """Usa o endpoint OpenAI-compat do Google AI Studio (mais estável que langchain-google-genai)."""
    s = get_settings()
    if not s.google_api_key:
        return None
    try:
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(
            model=model,
            api_key=s.google_api_key,
            base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
            temperature=0,
            max_tokens=4096,
        )
    except Exception as e:
        log.warning("Google Gemini indisponível: %s", e)
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


# ── Roteador dinâmico ──────────────────────────────────────────────────────────

class _ProviderStats:
    """Rastreia latência e falhas de um provider em janela deslizante."""

    def __init__(self, name: str):
        self.name = name
        self._lock = threading.Lock()
        self._latencies: deque[float] = deque(maxlen=10)  # últimas 10 respostas (ms)
        self._failures: int = 0
        self._consecutive_failures: int = 0
        self._last_failure_ts: float = 0.0
        self._cooldown_s: float = 60.0  # tempo de penalidade após falha

    def record_success(self, latency_ms: float) -> None:
        with self._lock:
            self._latencies.append(latency_ms)
            self._consecutive_failures = 0

    def record_failure(self) -> None:
        with self._lock:
            self._failures += 1
            self._consecutive_failures += 1
            self._last_failure_ts = time.monotonic()

    @property
    def avg_latency_ms(self) -> float:
        with self._lock:
            return sum(self._latencies) / len(self._latencies) if self._latencies else 9999.0

    @property
    def in_cooldown(self) -> bool:
        with self._lock:
            if self._consecutive_failures >= 3:
                return (time.monotonic() - self._last_failure_ts) < self._cooldown_s
            return False

    @property
    def score(self) -> float:
        """Menor é melhor: avg_latency penalizado por falhas consecutivas."""
        if self.in_cooldown:
            return float("inf")
        return self.avg_latency_ms * (1 + self._consecutive_failures * 0.5)


class LLMRouter:
    """
    Roteador dinâmico: mantém estatísticas de cada provider e reordena
    a cascata em tempo real. Se um provider acumula fila (alta latência)
    ou falha 3× seguidas, é colocado em cooldown de 60s.
    """

    def __init__(self):
        self._stats: dict[str, _ProviderStats] = {}
        self._lock = threading.Lock()

    def _get_stats(self, name: str) -> _ProviderStats:
        with self._lock:
            if name not in self._stats:
                self._stats[name] = _ProviderStats(name)
            return self._stats[name]

    def _provider_name(self, llm: Any) -> str:
        cls = type(llm).__name__
        base = getattr(llm, "openai_api_base", None) or getattr(llm, "base_url", None) or ""
        base = str(base)
        if "cerebras" in base:
            return "cerebras"
        if "generativelanguage" in base or "google" in cls.lower() or "genai" in cls.lower():
            return "google"
        if "nvidia" in base:
            return "nvidia"
        if "together" in base:
            return "together"
        if "openrouter" in base:
            return "openrouter"
        if "groq" in cls.lower() or "groq" in base:
            return "groq"
        if "mistral" in cls.lower():
            return "mistral"
        if "huggingface" in cls.lower() or "hugging" in base:
            return "huggingface"
        return "ollama"

    def sorted_llms(self, llms: list[Any]) -> list[Any]:
        """Reordena LLMs pelo score atual (mais rápido e saudável primeiro)."""
        def _score(llm: Any) -> float:
            return self._get_stats(self._provider_name(llm)).score
        return sorted(llms, key=_score)

    def invoke(self, llms: list[Any], messages: list, timeout_s: int = _LLM_TIMEOUT_S) -> Any:
        """
        Tenta cada LLM em ordem de score (melhor primeiro).
        Registra latência em caso de sucesso, falha em caso de erro.
        Muda automaticamente se latência > timeout_s ou 3 falhas consecutivas.
        """
        from graph_engine.resilience import get_llm_circuit_breaker
        cb = get_llm_circuit_breaker()

        ordered = self.sorted_llms(llms)
        last_exc: Exception | None = None

        for llm in ordered:
            name = self._provider_name(llm)
            stats = self._get_stats(name)

            if stats.in_cooldown:
                log.info("LLMRouter: %s em cooldown — pulando", name)
                continue

            t0 = time.monotonic()

            def _invoke(_llm=llm):
                return _llm.invoke(messages)

            with ThreadPoolExecutor(max_workers=1) as ex:
                future = ex.submit(cb.call, _invoke)
                try:
                    result = future.result(timeout=timeout_s)
                    latency_ms = (time.monotonic() - t0) * 1000
                    stats.record_success(latency_ms)
                    if name != "ollama":
                        log.info("LLMRouter: %s OK (%.0fms)", name, latency_ms)
                    return result
                except FuturesTimeout:
                    future.cancel()
                    latency_ms = (time.monotonic() - t0) * 1000
                    stats.record_failure()
                    log.warning("LLMRouter: %s timeout após %ds — próximo", name, timeout_s)
                    last_exc = TimeoutError(f"{name} timeout {timeout_s}s")
                except Exception as exc:
                    stats.record_failure()
                    log.warning("LLMRouter: %s falhou: %s — próximo", name, exc)
                    last_exc = exc

        raise RuntimeError(f"Todos os LLMs falharam. Último erro: {last_exc}")

    def get_status(self) -> list[dict]:
        """Retorna status de todos os providers monitorados."""
        with self._lock:
            return [
                {
                    "provider": name,
                    "avg_latency_ms": round(s.avg_latency_ms),
                    "consecutive_failures": s._consecutive_failures,
                    "total_failures": s._failures,
                    "in_cooldown": s.in_cooldown,
                    "score": round(s.score, 1) if s.score != float("inf") else "inf",
                }
                for name, s in sorted(self._stats.items(), key=lambda x: x[1].score)
            ]


# Instância global — compartilhada entre todos os agentes
_router = LLMRouter()


# ── API pública ────────────────────────────────────────────────────────────────

def get_reasoning_llm() -> Any:
    """Cascata: Cerebras → Google → Groq 70B → Nvidia → Together → OpenRouter → Mistral → Fireworks → DeepInfra → HF → Ollama."""
    return (
        _make_cerebras("llama3.3-70b")
        or _make_google("gemini-2.5-flash")
        or _make_groq("llama-3.3-70b-versatile")
        or _make_groq("llama-3.1-8b-instant")
        or _make_nvidia("meta/llama-3.1-70b-instruct")
        or _make_together("meta-llama/Meta-Llama-3.1-70B-Instruct-Turbo")
        or _make_openrouter("qwen/qwen-2.5-7b-instruct:free")
        or _make_mistral("mistral-small-latest")
        or _make_fireworks("accounts/fireworks/models/llama-v3p3-70b-instruct")
        or _make_deepinfra("meta-llama/Meta-Llama-3.1-70B-Instruct")
        or _make_huggingface()
        or _make_ollama()
    )


def get_fast_llm() -> Any:
    """LLM mais rápido disponível."""
    return (
        _make_cerebras("llama3.1-8b")
        or _make_google("gemini-2.0-flash")
        or _make_groq("llama-3.1-8b-instant")
        or _make_groq("gemma2-9b-it")
        or _make_nvidia("meta/llama-3.1-8b-instruct")
        or _make_together("meta-llama/Meta-Llama-3.1-8B-Instruct-Turbo")
        or _make_openrouter("google/gemma-2-9b-it:free")
        or _make_mistral("mistral-small-latest")
        or _make_fireworks("accounts/fireworks/models/llama-v3p3-70b-instruct")
        or _make_deepinfra("meta-llama/Meta-Llama-3.1-8B-Instruct")
        or _make_ollama()
    )


def get_code_llm() -> Any:
    """Melhor LLM para geração de código."""
    return (
        _make_cerebras("llama3.3-70b")
        or _make_google("gemini-2.5-flash")
        or _make_groq("llama-3.3-70b-versatile")
        or _make_nvidia("qwen/qwen2.5-coder-32b-instruct")
        or _make_together("Qwen/Qwen2.5-Coder-32B-Instruct")
        or _make_openrouter("qwen/qwen-2.5-coder-7b-instruct:free")
        or _make_mistral("codestral-latest")
        or _make_fireworks("accounts/fireworks/models/qwen2p5-coder-32b-instruct-v0-2")
        or _make_deepinfra("Qwen/Qwen2.5-Coder-32B-Instruct")
        or _make_groq("llama3-70b-8192")
        or _make_ollama("codellama:latest")
        or _make_ollama()
    )


def get_all_llms() -> list[Any]:
    """Todos os LLMs configurados e disponíveis, em ordem de prioridade base."""
    candidates = [
        _make_cerebras(),
        _make_google(),
        _make_groq("llama-3.1-8b-instant"),
        _make_nvidia(),
        _make_together(),
        _make_openrouter(),
        _make_mistral(),
        _make_fireworks(),
        _make_deepinfra(),
        _make_huggingface(),
        _make_ollama(),
    ]
    return [llm for llm in candidates if llm is not None]


def invoke_llm_with_timeout(llm: Any, messages: list, timeout_s: int = _LLM_TIMEOUT_S) -> Any:
    """Invoca um LLM específico com timeout e circuit breaker."""
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
    Cascata completa com roteamento dinâmico.
    O router reordena os LLMs pelo score atual (latência + falhas).
    Se um acumula fila (timeout), o próximo assume automaticamente.
    """
    llms = get_all_llms()
    return _router.invoke(llms, messages, timeout_s=timeout_s)


def get_router_status() -> list[dict]:
    """Retorna status atual do roteador (latências, cooldowns, scores)."""
    return _router.get_status()
