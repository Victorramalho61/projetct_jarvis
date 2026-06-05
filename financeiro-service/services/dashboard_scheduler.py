import logging
from datetime import datetime, timedelta

import pytz
from apscheduler.schedulers.background import BackgroundScheduler

from cache import cache_set
from db import get_mssql

_logger = logging.getLogger(__name__)
_TZ = pytz.timezone("America/Sao_Paulo")
_scheduler = BackgroundScheduler(timezone=_TZ)


def start() -> None:
    _scheduler.add_job(_dashboard_nightly, "cron", hour=1, minute=0, id="dashboard_nightly")
    _scheduler.start()
    _logger.info("[DashboardScheduler] Iniciado — job às 01:00 America/Sao_Paulo")


def stop() -> None:
    _scheduler.shutdown(wait=False)
    _logger.info("[DashboardScheduler] Encerrado")


def _calcular_dashboard(empresa: str, data_iso: str) -> dict:
    with get_mssql() as conn:
        cur = conn.cursor()

        cur.execute(
            "SELECT SUM(VALOR) AS total, COUNT(*) AS qtd FROM dbo.FN_MOVIMENTACOES"
            " WHERE EMPRESA=%s AND DATA=%s AND NATUREZA='C'",
            (empresa, data_iso),
        )
        entradas = cur.fetchone() or {}

        cur.execute(
            "SELECT SUM(VALOR) AS total, COUNT(*) AS qtd FROM dbo.FN_MOVIMENTACOES"
            " WHERE EMPRESA=%s AND DATA=%s AND NATUREZA='D'",
            (empresa, data_iso),
        )
        saidas = cur.fetchone() or {}

        cur.execute(
            "SELECT ISNULL(b.NOME,'S/Banco') AS banco, ISNULL(c.NUMEROCONTA,'') AS conta,"
            " SUM(CASE WHEN m.NATUREZA='C' THEN m.VALOR WHEN m.NATUREZA='D' THEN -m.VALOR ELSE 0 END) AS saldo"
            " FROM dbo.FN_MOVIMENTACOES m"
            " LEFT JOIN dbo.FN_CONTASTESOURARIA c ON c.HANDLE=m.CONTACORRENTE"
            " LEFT JOIN dbo.GN_BANCOS b ON b.HANDLE=c.BANCO"
            " WHERE m.EMPRESA=%s AND m.DATA=%s"
            " GROUP BY b.NOME, c.NUMEROCONTA ORDER BY saldo DESC",
            (empresa, data_iso),
        )
        saldo_por_conta = cur.fetchall()

        cur.execute(
            "SELECT TOP 5 ISNULL(cc.NOME,'Sem CC') AS centroCusto, SUM(m.VALOR) AS total"
            " FROM dbo.FN_MOVIMENTACOES m"
            " LEFT JOIN dbo.CT_CC cc ON cc.HANDLE=m.CENTROCUSTO"
            " WHERE m.EMPRESA=%s AND m.DATA=%s AND m.NATUREZA='D'"
            " GROUP BY cc.NOME ORDER BY total DESC",
            (empresa, data_iso),
        )
        top_cc = cur.fetchall()

        cur.execute(
            "SELECT SUM(ISNULL(K_IRRFARECUPERAR,0)) AS irrf, SUM(ISNULL(K_PISARECUPERAR,0)) AS pis,"
            " SUM(ISNULL(K_COFINSARECUPERAR,0)) AS cofins, SUM(ISNULL(K_ISSARECUPERAR,0)) AS iss"
            " FROM dbo.FN_MOVIMENTACOES WHERE EMPRESA=%s AND DATA=%s",
            (empresa, data_iso),
        )
        impostos = cur.fetchone() or {}

    return {
        "referencia": data_iso,
        "empresa": empresa,
        "entradas": entradas,
        "saidas": saidas,
        "saldoPorConta": saldo_por_conta,
        "topCentrosCusto": top_cc,
        "impostosRetidos": impostos,
    }


def _dashboard_nightly() -> None:
    _logger.info("[DashboardScheduler] Iniciando pré-aquecimento do cache do dashboard")
    ontem = (datetime.now(_TZ) - timedelta(days=1)).strftime("%Y-%m-%d")
    try:
        with get_mssql() as conn:
            cur = conn.cursor()
            cur.execute("SELECT HANDLE AS handle FROM dbo.EMPRESAS WHERE ATIVO='S'")
            empresas = cur.fetchall()
    except Exception:
        _logger.exception("[DashboardScheduler] Falha ao listar empresas no Benner")
        return

    for e in empresas:
        handle = e["handle"]
        try:
            dados = _calcular_dashboard(handle, ontem)
            cache_set("dashboard", f"empresa={handle}", dados)
        except Exception:
            _logger.exception("[DashboardScheduler] Falha ao calcular dashboard empresa=%s", handle)

    _logger.info("[DashboardScheduler] Cache pré-aquecido para %d empresas", len(empresas))
