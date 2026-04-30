from functools import lru_cache

from pydantic_settings import BaseSettings
from supabase import Client, create_client


class Settings(BaseSettings):
    supabase_url: str
    supabase_key: str
    allowed_origins: str = "http://localhost:5173"
    jwt_secret: str
    jwt_expire_minutes: int = 480
    microsoft_client_id: str = ""
    microsoft_tenant_id: str = ""
    microsoft_client_secret: str = ""
    microsoft_redirect_uri: str = "http://localhost:8000/api/moneypenny/auth/microsoft/callback"
    frontend_url: str = "http://localhost:5173"
    whatsapp_api_url: str = ""
    whatsapp_api_key: str = ""
    whatsapp_instance: str = ""
    monitor_agent_url: str = "http://monitor-agent:9100"
    monitor_agent_tokens: str = ""
    freshservice_api_key: str = ""
    smtp_host: str = "smtp.office365.com"
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from: str = ""

    model_config = {"env_file": ".env"}


@lru_cache
def get_settings() -> Settings:
    return Settings()


@lru_cache
def get_supabase() -> Client:
    s = get_settings()
    return create_client(s.supabase_url, s.supabase_key)
