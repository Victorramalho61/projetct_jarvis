from functools import lru_cache

from pydantic_settings import BaseSettings
from supabase import Client, create_client


class Settings(BaseSettings):
    supabase_url: str
    supabase_key: str
    supabase_anon_key: str = ""
    allowed_origins: str = "http://localhost:5173"
    jwt_secret: str
    jwt_expire_minutes: int = 480
    freshservice_service_url: str = "http://freshservice-service:8003"
    expenses_service_url: str = "http://expenses-service:8006"
    # LLM local (Ollama) — agentes de raciocínio
    ollama_base_url: str = "http://ollama:11434"
    ollama_model: str = "llama3.1:8b"
    # LLMs open-source gratuitos — cascata: Cerebras → Groq → Together → OpenRouter → Mistral → HF → Ollama
    cerebras_api_key: str = ""         # cloud.cerebras.ai — free tier, CS-3 chip, ultrarrápido
    groq_api_key: str = ""             # groq.com — free tier, rápido (Llama, Mixtral)
    together_api_key: str = ""         # api.together.xyz — free tier open-source models
    openrouter_api_key: str = ""       # openrouter.ai — free models aggregator
    mistral_api_key: str = ""          # mistral.ai — free tier (mistral-small)
    huggingface_api_key: str = ""      # huggingface.co — free inference API
    nvidia_api_key: str = ""           # build.nvidia.com — NIM free tier (Llama, Mistral, etc.)
    deepinfra_api_key: str = ""        # deepinfra.com — requer saldo, OpenAI-compat
    fireworks_api_key: str = ""        # fireworks.ai — free tier com créditos, OpenAI-compat
    google_api_key: str = ""           # aistudio.google.com — Gemini 2.0 Flash free tier
    # GitHub para agentes de docs/code
    github_token: str = ""
    github_repo: str = ""
    # PostgreSQL direto (db_dba_agent — acesso a pg_stat_*)
    postgres_direct_url: str = ""
    # Intervalos dos pipelines LangGraph (em minutos/horas)
    monitoring_interval_minutes: int = 15
    security_interval_minutes: int = 30
    cicd_interval_minutes: int = 5
    dba_interval_hours: int = 4
    governance_cron_hour: int = 6
    evolution_cron_hour: int = 7
    event_consumer_poll_seconds: int = 60

    model_config = {"env_file": ".env"}


@lru_cache
def get_settings() -> Settings:
    return Settings()


@lru_cache
def get_supabase() -> Client:
    s = get_settings()
    return create_client(s.supabase_url, s.supabase_key)
