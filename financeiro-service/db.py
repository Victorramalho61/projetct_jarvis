from contextlib import contextmanager
from functools import lru_cache
from typing import Any
from urllib.parse import quote as _url_quote

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
    max_period_days: int = 366
    model_config = {"env_file": ".env"}


@lru_cache
def get_settings() -> Settings:
    return Settings()


@lru_cache
def get_supabase() -> Client:
    s = get_settings()
    return create_client(s.supabase_url, s.supabase_key)


def _build_cp850_fix_table() -> dict:
    """Mapa str.translate: caractere recebido do FreeTDS (UTF-8) → caractere CP850 correto.

    Bytes 0x80-0xFF armazenados em CP850 chegam via FreeTDS/UTF-8 de duas formas:
    - CP1252-definidos (ex: 0x80=€, 0xE5=å): mapeados para seu Unicode CP1252.
    - CP1252-indefinidos (0x81, 0x8D, 0x8F, 0x90, 0x9D): passam como controles C1 (U+00XX).
    Em ambos os casos, decodificamos o byte original como CP850."""
    table: dict = {}
    for b in range(0x80, 0x100):
        try:
            cp850_char = bytes([b]).decode("cp850")
        except (UnicodeDecodeError, ValueError):
            continue
        try:
            received_char = bytes([b]).decode("cp1252")  # CP1252-definido
        except (UnicodeDecodeError, ValueError):
            received_char = chr(b)                        # CP1252-indefinido → C1 control
        table[ord(received_char)] = cp850_char
    return table


_CP850_FIX_TABLE = str.maketrans(_build_cp850_fix_table())


def fmt_sql_raw(sql: str, params: list | tuple | None = None) -> str:
    """Como fmt_sql mas sem URL-encode — para concatenar múltiplos SQLs."""
    result = sql.strip()
    if params:
        for p in (list(params) if not isinstance(params, list) else params):
            if isinstance(p, str):
                val = f"'{p}'"
            elif p is None:
                val = "NULL"
            else:
                val = str(p)
            result = result.replace("%s", val, 1)
    return result


def fmt_sql(sql: str, params: list | tuple | None = None) -> str:
    """Formata SQL com parâmetros substituídos para o header X-SQL de debug."""
    return _url_quote(fmt_sql_raw(sql, params))


def _fix_str(v: Any) -> Any:
    if not isinstance(v, str):
        return v
    return v.translate(_CP850_FIX_TABLE)


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
        charset="UTF-8",
    )
    if s.mssql_port and "\\" not in s.mssql_host:
        kwargs["port"] = s.mssql_port
    return _FixedConn(pymssql.connect(**kwargs))
