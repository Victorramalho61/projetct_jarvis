from functools import lru_cache

import pymssql
from pydantic_settings import BaseSettings
from supabase import Client, create_client


class Settings(BaseSettings):
    supabase_url: str
    supabase_key: str
    jwt_secret: str
    jwt_expire_minutes: int = 480
    allowed_origins: str = "http://localhost:5173"
    mssql_host: str                          # aceita "ip\instancia" ou "ip"
    mssql_port: int | None = None            # None = deixar SQL Server Browser resolver (instância nomeada)
    mssql_user: str
    mssql_password: str
    mssql_database: str = "BennerSistemaCorporativo"
    max_period_days: int = 31
    model_config = {"env_file": ".env"}


@lru_cache
def get_settings() -> Settings:
    return Settings()


@lru_cache
def get_supabase() -> Client:
    s = get_settings()
    return create_client(s.supabase_url, s.supabase_key)


def get_mssql() -> pymssql.Connection:
    """Retorna nova conexão pymssql. Usar como context manager: with get_mssql() as conn.

    Quando MSSQL_HOST contém instância nomeada (ex: '10.x.x.x\\VOETUR'), porta não é
    passada — o SQL Server Browser (UDP 1434) resolve a porta da instância automaticamente.
    """
    s = get_settings()
    kwargs: dict = dict(
        server=s.mssql_host,
        user=s.mssql_user,
        password=s.mssql_password,
        database=s.mssql_database,
        timeout=120,
        as_dict=True,
        charset="UTF-8",
    )
    # Porta explícita apenas quando não há instância nomeada no host
    if s.mssql_port and "\\" not in s.mssql_host:
        kwargs["port"] = s.mssql_port
    return pymssql.connect(**kwargs)
