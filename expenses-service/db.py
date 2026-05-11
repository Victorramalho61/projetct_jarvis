from functools import lru_cache

import pyodbc
from pydantic_settings import BaseSettings
from supabase import Client, create_client


class Settings(BaseSettings):
    supabase_url: str
    supabase_key: str
    jwt_secret: str
    jwt_expire_minutes: int = 480
    allowed_origins: str = "http://localhost:5173"
    sql_server_host: str = ""
    sql_server_port: int = 1433
    sql_server_db: str = ""
    sql_server_user: str = ""
    sql_server_password: str = ""
    sql_server_driver: str = "ODBC Driver 17 for SQL Server"
    # LLM para classificação de mídia
    google_api_key: str = ""
    groq_api_key: str = ""
    # Webhook de crise (opcional)
    crisis_webhook_url: str = ""

    model_config = {"env_file": ".env"}


@lru_cache
def get_settings() -> Settings:
    return Settings()


@lru_cache
def get_supabase() -> Client:
    s = get_settings()
    return create_client(s.supabase_url, s.supabase_key)


def get_sql_connection() -> pyodbc.Connection:
    from services.resilience import get_benner_circuit_breaker, sql_retry

    s = get_settings()
    conn_str = (
        f"DRIVER={{{s.sql_server_driver}}};"
        f"SERVER={s.sql_server_host},{s.sql_server_port};"
        f"DATABASE={s.sql_server_db};"
        f"UID={s.sql_server_user};PWD={s.sql_server_password};"
        f"TrustServerCertificate=yes;"
    )

    @sql_retry
    def _connect():
        return pyodbc.connect(conn_str, timeout=15)

    return get_benner_circuit_breaker().call(_connect)
