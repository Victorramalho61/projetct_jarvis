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

    model_config = {"env_file": ".env"}


@lru_cache
def get_settings() -> Settings:
    return Settings()


@lru_cache
def get_supabase() -> Client:
    s = get_settings()
    return create_client(s.supabase_url, s.supabase_key)
