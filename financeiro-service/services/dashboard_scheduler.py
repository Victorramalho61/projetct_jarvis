from datetime import datetime, timedelta

import pytz
from apscheduler.schedulers.background import BackgroundScheduler

from cache import cache_set
from db import get_mssql

_TZ = pytz.timezone("America/Sao_Paulo")
_scheduler = BackgroundScheduler(timezone=_TZ)


def start():
    _scheduler.add_job(_dashboard_nightly, "cron", hour=1, minute=0, id="dashboard_nightly")
    _scheduler.start()


def stop():
    _scheduler.shutdown(wait=False)


def _calcular_dashboard(empresa_handle: int, data: str) -> dict:
    with get_mssql() as conn:
        cur = conn.cursor()

        cur.execute(
            "SELECT SUM(VALOR) AS total, COUNT(*) AS qtd FROM dbo.FN_LANCAMENTOS"
            " WHERE EMPRESA = %s AND DATA = %s AND NATUREZA = 'C'",
            (empresa_handle, data),
        )
        entradas = cur.fetchone() or {}

        cur.execute(
            "SELECT SUM(VALOR) AS total, COUNT(*) AS qtd FROM dbo.FN_LANCAMENTOS"
            " WHERE EMPRESA = %s AND DATA = %s AND NATUREZA = 'D'",
            (empresa_handle, data),
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
            (empresa_handle, data),
        )
        saldo_por_conta = cur.fetchall()

        cur.execute(
            "SELECT TOP 5 ISNULL(cc.NOME,'Sem CC') AS centroCusto, SUM(l.VALOR) AS total"
            " FROM dbo.FN_LANCAMENTOS l"
            " LEFT JOIN dbo.FN_LANCAMENTOCC lcc ON lcc.LANCAMENTO = l.HANDLE"
            " LEFT JOIN dbo.CT_CC cc ON cc.HANDLE = lcc.CENTROCUSTO"
            " WHERE l.EMPRESA = %s AND l.DATA = %s AND l.NATUREZA = 'D'"
            " GROUP BY cc.NOME ORDER BY total DESC",
            (empresa_handle, data),
        )
        top_cc = cur.fetchall()

        cur.execute(
            "SELECT SUM(ISNULL(K_IRRFARECUPERAR,0)) AS irrf, SUM(ISNULL(K_PISARECUPERAR,0)) AS pis,"
            " SUM(ISNULL(K_COFINSARECUPERAR,0)) AS cofins, SUM(ISNULL(K_ISSARECUPERAR,0)) AS iss"
            " FROM dbo.FN_MOVIMENTACOES WHERE EMPRESA = %s AND DATA = %s",
            (empresa_handle, data),
        )
        impostos = cur.fetchone() or {}

    return {
        "referencia": data,
        "empresa": str(empresa_handle),
        "entradas": entradas,
        "saidas": saidas,
        "saldoPorConta": saldo_por_conta,
        "topCentrosCusto": top_cc,
        "impostosRetidos": impostos,
    }


def _dashboard_nightly():
    ontem = (datetime.now(_TZ) - timedelta(days=1)).strftime("%Y-%m-%d")
    with get_mssql() as conn:
        cur = conn.cursor()
        cur.execute("SELECT HANDLE AS handle FROM dbo.EMPRESAS WHERE EMPRATIVA='S'")
        empresas = cur.fetchall()

    for e in empresas:
        try:
            dados = _calcular_dashboard(e["handle"], ontem)
            cache_set("dashboard", f"empresa={e['handle']}", dados)
        except Exception:
            pass
