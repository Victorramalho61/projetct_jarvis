import logging
import sys
from functools import lru_cache

import pyodbc

from db import get_settings

# ── mapeamento produto → nome amigável ────────────────────────────────────────
_PRODUTO_MAP: dict[str, str] = {
    "flight":        "Aéreo",
    "hotel":         "Hotelaria",
    "pnr":           "PNR",
    "airticket":     "Air Ticket",
    "rodoviario":    "Rodoviário",
    "bus":           "Rodoviário",
    "insurance":     "Seguro",
    "emd":           "EMD",
    "ordem serviço": "Ordem de Serviço",
    "ordem servico": "Ordem de Serviço",
    "pedido":        "Pedido",
    "solicitação":   "Solicitação",
    "solicitacao":   "Solicitação",
    "outros":        "Outros",
}

# Categorias de erro derivadas do campo MENSAGEM
_TIPO_ERRO_LABELS: dict[str, str] = {
    "cliente_nao_identificado":  "Cliente não identificado",
    "fornecedor_nao_localizado": "Fornecedor não localizado",
    "erro_pagamento":            "Erro de pagamento",
    "contrato_nao_localizado":   "Contrato não localizado",
    "erro_formato":              "Formato / dado inválido",
    "outros":                    "Outros",
}


def _classificar_erro(mensagem: str | None) -> str:
    if not mensagem:
        return "outros"
    m = mensagem.lower()
    if ("código do cliente não informado" in m or "getclient" in m
            or "cliente não informado" in m or "obtercliente" in m):
        return "cliente_nao_identificado"
    if "fornecedor" in m and (
        "não foi possível encontrar" in m or "não encontr" in m or "não localiz" in m
    ):
        return "fornecedor_nao_localizado"
    if ("pagament" in m or "obterp" in m) and (
        "null" in m or "não informado" in m
    ):
        return "erro_pagamento"
    if "contrato" in m and (
        "não foi possível localizar" in m or "não localiz" in m
    ):
        return "contrato_nao_localizado"
    if "same key" in m or "input string was not in a correct format" in m:
        return "erro_formato"
    return "outros"


def _map_sistema_origem(produto: str | None, origem: int | None) -> str:
    """Deriva nome amigável do sistema a partir de PRODUTO + ORIGEMFORNECEDOR.
    ORIGEMFORNECEDOR=3 indica integração GDS/OTA externa (sufixo ' GDS').
    """
    key = (produto or "").lower().strip()
    nome = _PRODUTO_MAP.get(key) or (produto or "Benner").strip()
    if origem == 3:
        return f"{nome} GDS"
    return nome

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
            l.HANDLE, l.SITUACAO, l.PRODUTO, l.CODIGORESERVA, l.DATAREENVIO, l.MENSAGEM,
            l.ORIGEMFORNECEDOR,
            COALESCE(e.NOMEFANTASIA, CAST(l.EMPRESA AS VARCHAR(20))) AS CLIENTE
        FROM BB_LOGINTEGRACOES l
        LEFT JOIN EMPRESAS e ON e.HANDLE = l.EMPRESA
        WHERE l.SITUACAO != 1
          AND l.DATAREENVIO >= DATEADD(HOUR, ?, GETDATE())
        ORDER BY l.DATAREENVIO DESC
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
            "sistema": _map_sistema_origem(r[2], r[6]),
            "cliente": r[7],
        }
        for r in cur.fetchall()
    ]

    conn.close()

    produtos: dict[str, dict] = {}
    for row in by_product_raw:
        raw_prod = (row[0] or "Desconhecido").strip()
        produto = _PRODUTO_MAP.get(raw_prod.lower(), raw_prod)
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


def query_categorias_erro(days: int = 7, exemplos_por_cat: int = 30) -> list[dict]:
    """Agrupa erros dos últimos N dias por categoria (conta tudo, amosta exemplos)."""
    conn = get_benner_conn()
    cur = conn.cursor()

    # Contagem real de TODOS os erros por mensagem (sem limite)
    cur.execute(
        """
        SELECT MENSAGEM, COUNT(*) AS QTD
        FROM BB_LOGINTEGRACOES
        WHERE SITUACAO != 1
          AND DATAREENVIO >= DATEADD(DAY, ?, GETDATE())
        GROUP BY MENSAGEM
        ORDER BY QTD DESC
        """,
        (-days,),
    )
    count_rows = cur.fetchall()

    # Exemplos detalhados (até 500 linhas)
    cur.execute(
        """
        SELECT TOP 500
            l.HANDLE, l.SITUACAO, l.PRODUTO, l.CODIGORESERVA,
            l.DATAREENVIO, l.MENSAGEM, l.ORIGEMFORNECEDOR,
            COALESCE(e.NOMEFANTASIA, CAST(l.EMPRESA AS VARCHAR(20))) AS CLIENTE
        FROM BB_LOGINTEGRACOES l
        LEFT JOIN EMPRESAS e ON e.HANDLE = l.EMPRESA
        WHERE l.SITUACAO != 1
          AND l.DATAREENVIO >= DATEADD(DAY, ?, GETDATE())
        ORDER BY l.DATAREENVIO DESC
        """,
        (-days,),
    )
    sample_rows = cur.fetchall()
    conn.close()

    cat_counts: dict[str, int] = {}
    for row in count_rows:
        cat = _classificar_erro(row[0])
        cat_counts[cat] = cat_counts.get(cat, 0) + row[1]

    cat_exemplos: dict[str, list] = {}
    for row in sample_rows:
        cat = _classificar_erro(row[5])
        if cat not in cat_exemplos:
            cat_exemplos[cat] = []
        if len(cat_exemplos[cat]) < exemplos_por_cat:
            cat_exemplos[cat].append({
                "id":       row[0],
                "situacao": row[1],
                "produto":  _PRODUTO_MAP.get((row[2] or "").lower().strip(), row[2] or "—"),
                "reserva":  row[3],
                "data":     row[4].isoformat() if row[4] else None,
                "mensagem": row[5],
                "sistema":  _map_sistema_origem(row[2], row[6]),
                "cliente":  row[7] or "—",
            })

    total_erros = sum(cat_counts.values())
    return sorted(
        [
            {
                "categoria": cat,
                "label":     _TIPO_ERRO_LABELS.get(cat, cat),
                "count":     count,
                "pct":       round(count / total_erros * 100, 1) if total_erros else 0,
                "exemplos":  cat_exemplos.get(cat, []),
            }
            for cat, count in cat_counts.items()
        ],
        key=lambda x: -x["count"],
    )
