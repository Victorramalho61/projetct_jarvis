from datetime import datetime, timedelta
from urllib.parse import quote as _url_quote

import pytz
from fastapi import APIRouter, Depends, Query, Response

from auth import require_role
from cache import cache_get, cache_set
from db import get_mssql, fmt_sql_raw

router = APIRouter(prefix="/api/financeiro", tags=["financeiro"])

_TZ = pytz.timezone("America/Sao_Paulo")


@router.get("/dashboard")
def dashboard(
    response: Response,
    empresa: str = Query(..., min_length=1),
    data_inicio: str | None = Query(None),
    data_fim: str | None = Query(None),
    current_user: dict = Depends(require_role("admin", "user")),
):
    hoje = datetime.now(_TZ).strftime("%Y-%m-%d")
    ini = data_inicio if data_inicio else (datetime.now(_TZ) - timedelta(days=7)).strftime("%Y-%m-%d")
    fim = data_fim if data_fim else hoje

    cache_key = f"empresa={empresa}&ini={ini}&fim={fim}"
    hit = cache_get("dashboard", cache_key)
    if hit is not None:
        return hit

    _sql_entradas = (
        "SELECT SUM(VALOR) AS total, COUNT(*) AS qtd FROM dbo.FN_LANCAMENTOS"
        " WHERE EMPRESA = %s AND DATA BETWEEN %s AND %s AND NATUREZA = 'C'"
    )
    _sql_saidas = (
        "SELECT SUM(VALOR) AS total, COUNT(*) AS qtd FROM dbo.FN_LANCAMENTOS"
        " WHERE EMPRESA = %s AND DATA BETWEEN %s AND %s AND NATUREZA = 'D'"
    )
    _sql_saldo = (
        "SELECT ISNULL(b.NOME,'S/Banco') AS banco, ISNULL(c.NUMEROCONTA,'') AS conta,"
        " SUM(CASE WHEN l.NATUREZA='C' THEN l.VALOR WHEN l.NATUREZA='D' THEN -l.VALOR ELSE 0 END) AS saldo"
        " FROM dbo.FN_LANCAMENTOS l"
        " LEFT JOIN dbo.FN_CONTASTESOURARIA c ON c.HANDLE = l.CONTA"
        " LEFT JOIN dbo.GN_BANCOS b ON b.HANDLE = c.BANCO"
        " WHERE l.EMPRESA = %s AND l.DATA BETWEEN %s AND %s"
        " GROUP BY b.NOME, c.NUMEROCONTA ORDER BY saldo DESC"
    )
    _sql_top_cc = (
        "SELECT TOP 5 ISNULL(cc.NOME,'Sem CC') AS centroCusto, SUM(l.VALOR) AS total"
        " FROM dbo.FN_LANCAMENTOS l"
        " LEFT JOIN dbo.FN_LANCAMENTOCC lcc ON lcc.LANCAMENTO = l.HANDLE"
        " LEFT JOIN dbo.CT_CC cc ON cc.HANDLE = lcc.CENTROCUSTO"
        " WHERE l.EMPRESA = %s AND l.DATA BETWEEN %s AND %s AND l.NATUREZA = 'D'"
        " GROUP BY cc.NOME ORDER BY total DESC"
    )
    _sql_impostos = (
        "SELECT SUM(ISNULL(K_IRRFARECUPERAR,0)) AS irrf, SUM(ISNULL(K_PISARECUPERAR,0)) AS pis,"
        " SUM(ISNULL(K_COFINSARECUPERAR,0)) AS cofins, SUM(ISNULL(K_ISSARECUPERAR,0)) AS iss"
        " FROM dbo.FN_MOVIMENTACOES WHERE EMPRESA = %s AND DATA BETWEEN %s AND %s"
    )
    _p = (empresa, ini, fim)

    with get_mssql() as conn:
        cur = conn.cursor()

        cur.execute(_sql_entradas, _p)
        entradas = cur.fetchone() or {}

        cur.execute(_sql_saidas, _p)
        saidas = cur.fetchone() or {}

        cur.execute(_sql_saldo, _p)
        saldo_por_conta = cur.fetchall()

        cur.execute(_sql_top_cc, _p)
        top_cc = cur.fetchall()

        cur.execute(_sql_impostos, _p)
        impostos = cur.fetchone() or {}

    _debug = "\n\n-- ===\n\n".join([
        f"-- Entradas\n{fmt_sql_raw(_sql_entradas, _p)}",
        f"-- Saidas\n{fmt_sql_raw(_sql_saidas, _p)}",
        f"-- Saldo por conta\n{fmt_sql_raw(_sql_saldo, _p)}",
        f"-- Top centros de custo\n{fmt_sql_raw(_sql_top_cc, _p)}",
        f"-- Impostos retidos\n{fmt_sql_raw(_sql_impostos, _p)}",
    ])
    response.headers["X-SQL"] = _url_quote(_debug)

    result = {
        "periodo": {"inicio": ini, "fim": fim},
        "empresa": empresa,
        "entradas": entradas,
        "saidas": saidas,
        "saldoPorConta": saldo_por_conta,
        "topCentrosCusto": top_cc,
        "impostosRetidos": impostos,
    }
    cache_set("dashboard", cache_key, result)
    return result
