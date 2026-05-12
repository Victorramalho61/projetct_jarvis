from functools import lru_cache

from pydantic_settings import BaseSettings
from supabase import Client, create_client


class Settings(BaseSettings):
    supabase_url: str
    supabase_key: str
    allowed_origins: str = "http://localhost:5173"
    jwt_secret: str
    jwt_expire_minutes: int = 480
    whatsapp_api_url: str = ""
    whatsapp_api_key: str = ""
    whatsapp_instance: str = ""
    freshservice_api_key: str = ""
    freshservice_webhook_secret: str = ""

    model_config = {"env_file": ".env"}


@lru_cache
def get_settings() -> Settings:
    return Settings()


@lru_cache
def get_supabase() -> Client:
    s = get_settings()
    return create_client(s.supabase_url, s.supabase_key)
