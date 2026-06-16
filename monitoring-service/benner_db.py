import logging
import sys
from functools import lru_cache

import pyodbc

from db import get_settings

logger = logging.getLogger(__name__)

_DRIVER_WIN = "{SQL Server}"
_DRIVER_LINUX = "{ODBC Driver 18 for SQL Server}"


def _pick_driver() -> str:
    available = pyodbc.drivers()
    if "ODBC Driver 18 for SQL Server" in available:
        return _DRIVER_LINUX
    if "ODBC Driver 17 for SQL Server" in available:
        return "{ODBC Driver 17 for SQL Server}"
    return _DRIVER_WIN


@lru_cache
def _conn_str() -> str:
    s = get_settings()
    driver = _pick_driver()
    return (
        f"DRIVER={driver};"
        f"SERVER={s.sql_server_host},{s.sql_server_port};"
        f"DATABASE={s.sql_server_db};"
        f"UID={s.sql_server_user};"
        f"PWD={s.sql_server_password};"
        f"TrustServerCertificate=yes;"
        f"Connection Timeout=10;"
    )


def get_benner_conn() -> pyodbc.Connection:
    return pyodbc.connect(_conn_str())


def query_summary(hours: int = 24) -> dict:
    conn = get_benner_conn()
    cur = conn.cursor()

    cur.execute(
        """
        SELECT
            COUNT(*) AS total,
            SUM(CASE WHEN SITUACAO = 1 THEN 1 ELSE 0 END) AS ok,
            SUM(CASE WHEN SITUACAO != 1 THEN 1 ELSE 0 END) AS erros
        FROM BB_LOGINTEGRACOES
        WHERE DATAREENVIO >= DATEADD(HOUR, ?, GETDATE())
        """,
        (-hours,),
    )
    row = cur.fetchone()
    total, ok, erros = row[0] or 0, row[1] or 0, row[2] or 0

    cur.execute(
        """
        SELECT PRODUTO, SITUACAO, COUNT(*) AS QTD
        FROM BB_LOGINTEGRACOES
        WHERE DATAREENVIO >= DATEADD(HOUR, ?, GETDATE())
        GROUP BY PRODUTO, SITUACAO
        ORDER BY QTD DESC
        """,
        (-hours,),
    )
    by_product_raw = cur.fetchall()

    cur.execute(
        """
        SELECT TOP 50
            HANDLE, SITUACAO, PRODUTO, CODIGORESERVA, DATAREENVIO, MENSAGEM
        FROM BB_LOGINTEGRACOES
        WHERE SITUACAO != 1
          AND DATAREENVIO >= DATEADD(HOUR, ?, GETDATE())
        ORDER BY DATAREENVIO DESC
        """,
        (-hours,),
    )
    recent_errors = [
        {
            "id": r[0],
            "situacao": r[1],
            "produto": r[2],
            "reserva": r[3],
            "data": r[4].isoformat() if r[4] else None,
            "mensagem": r[5],
        }
        for r in cur.fetchall()
    ]

    conn.close()

    produtos: dict[str, dict] = {}
    for row in by_product_raw:
        produto = row[0] or "Desconhecido"
        if produto not in produtos:
            produtos[produto] = {"ok": 0, "erros": 0}
        if row[1] == 1:
            produtos[produto]["ok"] += row[2]
        else:
            produtos[produto]["erros"] += row[2]

    return {
        "periodo_horas": hours,
        "total": total,
        "ok": ok,
        "erros": erros,
        "taxa_erro_pct": round(erros / total * 100, 1) if total else 0,
        "por_produto": produtos,
        "ultimos_erros": recent_errors,
    }


def query_logs(
    page: int = 1,
    limit: int = 50,
    situacao: int | None = None,
    produto: str | None = None,
    horas: int = 24,
) -> dict:
    conn = get_benner_conn()
    cur = conn.cursor()

    where = ["DATAREENVIO >= DATEADD(HOUR, ?, GETDATE())"]
    params: list = [-horas]

    if situacao is not None:
        where.append("SITUACAO = ?")
        params.append(situacao)
    if produto:
        where.append("PRODUTO = ?")
        params.append(produto)

    where_sql = " AND ".join(where)
    offset = (page - 1) * limit

    cur.execute(
        f"SELECT COUNT(*) FROM BB_LOGINTEGRACOES WHERE {where_sql}", params
    )
    total = cur.fetchone()[0]

    cur.execute(
        f"""
        SELECT HANDLE, SITUACAO, PRODUTO, CODIGORESERVA, DATARESERVA,
               DATAREENVIO, MENSAGEM, TIPOERRO, EMPRESA
        FROM BB_LOGINTEGRACOES
        WHERE {where_sql}
        ORDER BY DATAREENVIO DESC
        OFFSET ? ROWS FETCH NEXT ? ROWS ONLY
        """,
        params + [offset, limit],
    )
    rows = [
        {
            "id": r[0],
            "situacao": r[1],
            "produto": r[2],
            "reserva": r[3],
            "data_reserva": r[4].isoformat() if r[4] else None,
            "data_processamento": r[5].isoformat() if r[5] else None,
            "mensagem": r[6],
            "tipo_erro": r[7],
            "empresa": r[8],
        }
        for r in cur.fetchall()
    ]
    conn.close()

    return {"total": total, "page": page, "limit": limit, "items": rows}


def query_new_errors(minutes: int = 15) -> list[dict]:
    conn = get_benner_conn()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT HANDLE, SITUACAO, PRODUTO, CODIGORESERVA, DATAREENVIO, MENSAGEM
        FROM BB_LOGINTEGRACOES
        WHERE SITUACAO != 1
          AND DATAREENVIO >= DATEADD(MINUTE, ?, GETDATE())
        ORDER BY DATAREENVIO DESC
        """,
        (-minutes,),
    )
    rows = [
        {
            "id": r[0],
            "situacao": r[1],
            "produto": r[2],
            "reserva": r[3],
            "data": r[4].isoformat() if r[4] else None,
            "mensagem": r[5],
        }
        for r in cur.fetchall()
    ]
    conn.close()
    return rows
