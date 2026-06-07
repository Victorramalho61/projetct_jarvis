from contextlib import contextmanager
from functools import lru_cache
from typing import Any

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


def _fix_str(v: Any) -> Any:
    """Corrige strings de VARCHAR cols armazenados em CP850 mas declarados como iso_1.
    pymssql com charset=cp1252 passa os bytes brutos — re-encode cp1252 → decode cp850."""
    if not isinstance(v, str):
        return v
    try:
        return v.encode("cp1252").decode("cp850")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return v


def _fix_row(row: dict) -> dict:
    return {k: _fix_str(v) for k, v in row.items()}


class _FixedCursor:
    """Cursor proxy que corrige encoding CP850→unicode em todos os resultados."""

    def __init__(self, cursor):
        self._cur = cursor

    def execute(self, sql, params=None):
        if params is not None:
            return self._cur.execute(sql, params)
        return self._cur.execute(sql)

    def fetchone(self):
        row = self._cur.fetchone()
        return _fix_row(row) if row else row

    def fetchall(self):
        return [_fix_row(r) for r in (self._cur.fetchall() or [])]

    @property
    def rowcount(self):
        return self._cur.rowcount

    @property
    def description(self):
        return self._cur.description


class _FixedConn:
    """Connection proxy que injeta _FixedCursor."""

    def __init__(self, conn):
        self._conn = conn

    def cursor(self):
        return _FixedCursor(self._conn.cursor())

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self._conn.__exit__(*args)


def get_mssql() -> _FixedConn:
    """Retorna nova conexão pymssql com correção de encoding CP850.

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
        charset="cp1252",
    )
    if s.mssql_port and "\\" not in s.mssql_host:
        kwargs["port"] = s.mssql_port
    return _FixedConn(pymssql.connect(**kwargs))
