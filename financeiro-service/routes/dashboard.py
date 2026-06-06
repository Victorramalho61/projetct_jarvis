from datetime import datetime, timedelta

import pytz
from fastapi import APIRouter, Depends, Query

from auth import require_role
from cache import cache_get, cache_set
from db import get_mssql

router = APIRouter(prefix="/api/financeiro", tags=["financeiro"])

_TZ = pytz.timezone("America/Sao_Paulo")


@router.get("/dashboard")
def dashboard(
    empresa: str = Query(..., min_length=1),
    current_user: dict = Depends(require_role("admin", "user")),
):
    cache_key = f"empresa={empresa}"
    hit = cache_get("dashboard", cache_key)
    if hit is not None:
        return hit

    ontem = (datetime.now(_TZ) - timedelta(days=1)).strftime("%Y-%m-%d")

    with get_mssql() as conn:
        cur = conn.cursor()

        cur.execute(
            "SELECT SUM(VALOR) AS total, COUNT(*) AS qtd FROM dbo.FN_LANCAMENTOS"
            " WHERE EMPRESA = %s AND DATA = %s AND NATUREZA = 'C'",
            (empresa, ontem),
        )
        entradas = cur.fetchone() or {}

        cur.execute(
            "SELECT SUM(VALOR) AS total, COUNT(*) AS qtd FROM dbo.FN_LANCAMENTOS"
            " WHERE EMPRESA = %s AND DATA = %s AND NATUREZA = 'D'",
            (empresa, ontem),
        )
        saidas = cur.fetchone() or {}

        cur.execute(
            "SELECT ISNULL(b.NOME,'S/Banco') AS banco, ISNULL(c.NUMEROCONTA,'') AS conta,"
            " SUM(CASE WHEN l.NATUREZA='C' THEN l.VALOR WHEN l.NATUREZA='D' THEN -l.VALOR ELSE 0 END) AS saldo"
            " FROM dbo.FN_LANCAMENTOS l"
            " LEFT JOIN dbo.FN_CONTASTESOURARIA c ON c.HANDLE = l.CONTA"
            " LEFT JOIN dbo.GN_BANCOS b ON b.HANDLE = c.BANCO"
            " WHERE l.EMPRESA = %s AND l.DATA = %s"
            " GROUP BY b.NOME, c.NUMEROCONTA ORDER BY saldo DESC",
            (empresa, ontem),
        )
        saldo_por_conta = cur.fetchall()

        cur.execute(
            "SELECT TOP 5 ISNULL(cc.NOME,'Sem CC') AS centroCusto, SUM(l.VALOR) AS total"
            " FROM dbo.FN_LANCAMENTOS l"
            " LEFT JOIN dbo.FN_LANCAMENTOCC lcc ON lcc.LANCAMENTO = l.HANDLE"
            " LEFT JOIN dbo.CT_CC cc ON cc.HANDLE = lcc.CENTROCUSTO"
            " WHERE l.EMPRESA = %s AND l.DATA = %s AND l.NATUREZA = 'D'"
            " GROUP BY cc.NOME ORDER BY total DESC",
            (empresa, ontem),
        )
        top_cc = cur.fetchall()

        # impostos retidos ficam em FN_MOVIMENTACOES (colunas K_*)
        cur.execute(
            "SELECT SUM(ISNULL(K_IRRFARECUPERAR,0)) AS irrf, SUM(ISNULL(K_PISARECUPERAR,0)) AS pis,"
            " SUM(ISNULL(K_COFINSARECUPERAR,0)) AS cofins, SUM(ISNULL(K_ISSARECUPERAR,0)) AS iss"
            " FROM dbo.FN_MOVIMENTACOES WHERE EMPRESA = %s AND DATA = %s",
            (empresa, ontem),
        )
        impostos = cur.fetchone() or {}

    result = {
        "referencia": ontem,
        "empresa": empresa,
        "entradas": entradas,
        "saidas": saidas,
        "saldoPorConta": saldo_por_conta,
        "topCentrosCusto": top_cc,
        "impostosRetidos": impostos,
    }
    cache_set("dashboard", cache_key, result)
    return result
