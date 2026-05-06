"""
Governança de Contratos — lógica de negócio.

Fontes:
  - Benner SQL Server (read-only): descoberta de contratos, pagamentos históricos
  - Supabase (read/write): contratos cadastrados, itens, ocorrências, SLAs, documentos
"""
import logging
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any

from db import get_sql_connection, get_supabase

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────

def _to_float(v: Any) -> float | None:
    if v is None:
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _iso_date(v: Any) -> str | None:
    if v is None:
        return None
    if isinstance(v, (date, datetime)):
        return v.isoformat()[:10]
    return str(v)[:10]


# ──────────────────────────────────────────────────────────────────────────────
# Benner — descoberta de contratos
# ──────────────────────────────────────────────────────────────────────────────

_DISCOVERY_QUERY = """
SELECT
  RF.CONTRATO                              AS BENNER_HANDLE,
  DOC.DOCUMENTODIGITADO                    AS NUM_CONTRATO,
  PES.HANDLE                               AS FORNECEDOR_HANDLE,
  PES.NOME                                 AS FORNECEDOR,
  MIN(PAR.DATAVENCIMENTO)                  AS PRIMEIRA_PARCELA,
  MAX(PAR.DATAVENCIMENTO)                  AS ULTIMA_PARCELA,
  COUNT(PAR.HANDLE)                        AS QTD_PARCELAS,
  SUM(PAR.VALOR)                           AS TOTAL_VALOR,
  MAX(PAR.DATALIQUIDACAO)                  AS ULTIMA_LIQUIDACAO
FROM FN_PARCELAS PAR WITH (NOLOCK)
  INNER JOIN FN_DOCUMENTOS DOC WITH (NOLOCK) ON DOC.HANDLE = PAR.DOCUMENTO
  INNER JOIN GN_PESSOAS    PES WITH (NOLOCK) ON PES.HANDLE = DOC.PESSOA
  INNER JOIN CP_RECEBIMENTOFISICO RF WITH (NOLOCK)
      ON RF.RECEBIMENTOFISICOPAI = DOC.RECEBIMENTOFISICO
WHERE PAR.EMPRESA = 1
  AND DOC.GRUPOASSINATURAS IN (
        SELECT HANDLE FROM CP_GRUPOALCADAS WITH (NOLOCK) WHERE K_GESTOR = 23)
  AND DOC.ENTRADASAIDA IN ('I', 'E')
  AND DOC.ABRANGENCIA <> 'R'
  AND RF.CONTRATO IS NOT NULL
GROUP BY RF.CONTRATO, DOC.DOCUMENTODIGITADO, PES.HANDLE, PES.NOME
ORDER BY ULTIMA_PARCELA DESC
"""

_PAYMENTS_BY_CONTRATO_QUERY = """
SELECT
  PAR.HANDLE                                                          AS AP,
  LEFT(CONVERT(VARCHAR, PAR.DATAVENCIMENTO, 120), 7)                 AS MES,
  PAR.DATAVENCIMENTO,
  PAR.DATALIQUIDACAO,
  PAR.VALOR,
  CASE WHEN PAR.DATALIQUIDACAO IS NOT NULL THEN 'pago' ELSE 'pendente' END AS STATUS_PAR,
  DOC.HISTORICO,
  FIL.NOME                                                            AS FILIAL
FROM FN_PARCELAS PAR WITH (NOLOCK)
  INNER JOIN FN_DOCUMENTOS DOC WITH (NOLOCK) ON DOC.HANDLE = PAR.DOCUMENTO
  INNER JOIN FILIAIS         FIL WITH (NOLOCK) ON FIL.HANDLE = PAR.FILIAL
  INNER JOIN CP_RECEBIMENTOFISICO RF WITH (NOLOCK)
      ON RF.RECEBIMENTOFISICOPAI = DOC.RECEBIMENTOFISICO
WHERE PAR.EMPRESA = 1
  AND RF.CONTRATO = ?
ORDER BY PAR.DATAVENCIMENTO
"""

_PAYMENTS_BY_DOCMATCH_QUERY = """
SELECT
  PAR.HANDLE                                                          AS AP,
  LEFT(CONVERT(VARCHAR, PAR.DATAVENCIMENTO, 120), 7)                 AS MES,
  PAR.DATAVENCIMENTO,
  PAR.DATALIQUIDACAO,
  PAR.VALOR,
  CASE WHEN PAR.DATALIQUIDACAO IS NOT NULL THEN 'pago' ELSE 'pendente' END AS STATUS_PAR,
  DOC.HISTORICO,
  FIL.NOME                                                            AS FILIAL
FROM FN_PARCELAS PAR WITH (NOLOCK)
  INNER JOIN FN_DOCUMENTOS DOC WITH (NOLOCK) ON DOC.HANDLE = PAR.DOCUMENTO
  INNER JOIN FILIAIS         FIL WITH (NOLOCK) ON FIL.HANDLE = PAR.FILIAL
  INNER JOIN CP_RECEBIMENTOFISICO RF WITH (NOLOCK)
      ON RF.RECEBIMENTOFISICOPAI = DOC.RECEBIMENTOFISICO
WHERE PAR.EMPRESA = 1
  AND DOC.DOCUMENTODIGITADO LIKE ?
ORDER BY PAR.DATAVENCIMENTO
"""


def fetch_benner_contracts_discovery() -> list[dict]:
    """Descobre contratos ativos no Benner via CP_RECEBIMENTOFISICO.CONTRATO."""
    conn = get_sql_connection()
    try:
        cur = conn.cursor()
        cur.execute(_DISCOVERY_QUERY)
        cols = [d[0].lower() for d in cur.description]
        rows = []
        for row in cur.fetchall():
            r = dict(zip(cols, row))
            rows.append({
                "benner_handle":    r.get("benner_handle"),
                "num_contrato":     r.get("num_contrato"),
                "fornecedor_handle": r.get("fornecedor_handle"),
                "fornecedor":       r.get("fornecedor"),
                "primeira_parcela": _iso_date(r.get("primeira_parcela")),
                "ultima_parcela":   _iso_date(r.get("ultima_parcela")),
                "qtd_parcelas":     r.get("qtd_parcelas"),
                "total_valor":      _to_float(r.get("total_valor")),
                "ultima_liquidacao": _iso_date(r.get("ultima_liquidacao")),
            })
        return rows
    finally:
        conn.close()


def fetch_contract_payments_by_handle(benner_handle: int) -> list[dict]:
    """Pagamentos Benner de um contrato pelo handle CP_RECEBIMENTOFISICO.CONTRATO."""
    conn = get_sql_connection()
    try:
        cur = conn.cursor()
        cur.execute(_PAYMENTS_BY_CONTRATO_QUERY, (benner_handle,))
        cols = [d[0].lower() for d in cur.description]
        rows = []
        for row in cur.fetchall():
            r = dict(zip(cols, row))
            rows.append({
                "ap":             r.get("ap"),
                "mes":            r.get("mes"),
                "datavencimento": _iso_date(r.get("datavencimento")),
                "dataliquidacao": _iso_date(r.get("dataliquidacao")),
                "valor":          _to_float(r.get("valor")),
                "status_par":     r.get("status_par"),
                "historico":      r.get("historico"),
                "filial":         r.get("filial"),
            })
        return rows
    finally:
        conn.close()


def fetch_contract_payments_by_docmatch(doc_match: str) -> list[dict]:
    """Pagamentos Benner de um contrato pelo padrão DOCUMENTODIGITADO (LIKE)."""
    conn = get_sql_connection()
    try:
        cur = conn.cursor()
        pattern = doc_match if "%" in doc_match else f"%{doc_match}%"
        cur.execute(_PAYMENTS_BY_DOCMATCH_QUERY, (pattern,))
        cols = [d[0].lower() for d in cur.description]
        rows = []
        for row in cur.fetchall():
            r = dict(zip(cols, row))
            rows.append({
                "ap":             r.get("ap"),
                "mes":            r.get("mes"),
                "datavencimento": _iso_date(r.get("datavencimento")),
                "dataliquidacao": _iso_date(r.get("dataliquidacao")),
                "valor":          _to_float(r.get("valor")),
                "status_par":     r.get("status_par"),
                "historico":      r.get("historico"),
                "filial":         r.get("filial"),
            })
        return rows
    finally:
        conn.close()


# ──────────────────────────────────────────────────────────────────────────────
# Supabase — contratos
# ──────────────────────────────────────────────────────────────────────────────

def _days_until(date_str: str | None) -> int | None:
    if not date_str:
        return None
    try:
        d = date.fromisoformat(str(date_str)[:10])
        return (d - date.today()).days
    except ValueError:
        return None


def _enrich_contract(c: dict) -> dict:
    c["dias_para_vencer"] = _days_until(c.get("data_fim"))
    return c


def list_contracts(status: str | None = None) -> list[dict]:
    db = get_supabase()
    q = db.table("contracts").select("*").order("data_fim")
    if status:
        q = q.eq("status", status)
    res = q.execute()
    return [_enrich_contract(r) for r in (res.data or [])]


def get_contract(contract_id: str) -> dict | None:
    db = get_supabase()
    res = (
        db.table("contracts")
        .select("*, contract_items(*), contract_occurrences(*), contract_sla_violations(*)")
        .eq("id", contract_id)
        .limit(1)
        .execute()
    )
    if not res.data:
        return None
    c = res.data[0]
    _enrich_contract(c)

    # Fetch Benner payments if linked
    payments = []
    if c.get("fornecedor_benner_handle"):
        try:
            payments = fetch_contract_payments_by_handle(int(c["fornecedor_benner_handle"]))
        except Exception:
            logger.warning("Falha ao buscar pagamentos Benner para contrato %s", contract_id)
    elif c.get("benner_documento_match"):
        try:
            payments = fetch_contract_payments_by_docmatch(c["benner_documento_match"])
        except Exception:
            logger.warning("Falha ao buscar pagamentos Benner (doc_match) para contrato %s", contract_id)

    c["benner_payments"] = payments
    c["total_pago_benner"] = sum(p["valor"] or 0 for p in payments)
    return c


def create_contract(data: dict) -> dict:
    db = get_supabase()
    now = datetime.now(timezone.utc).isoformat()
    data["created_at"] = now
    data["updated_at"] = now
    res = db.table("contracts").insert(data).execute()
    return _enrich_contract(res.data[0])


def update_contract(contract_id: str, data: dict) -> dict:
    db = get_supabase()
    data["updated_at"] = datetime.now(timezone.utc).isoformat()
    res = db.table("contracts").update(data).eq("id", contract_id).execute()
    return _enrich_contract(res.data[0])


# ──────────────────────────────────────────────────────────────────────────────
# Divergência — confronto Benner vs cadastrado
# ──────────────────────────────────────────────────────────────────────────────

def compute_contract_divergences(contract_id: str) -> dict:
    """
    Confronta parcelas cadastradas (valor_mensal × qtd) vs pagamentos realizados (Benner).
    Retorna mapa mensal com delta e classificação.
    """
    db = get_supabase()
    res = db.table("contracts").select("*").eq("id", contract_id).limit(1).execute()
    if not res.data:
        return {"status": "not_found", "divergencias": []}

    c = res.data[0]
    valor_mensal: float = float(c.get("valor_mensal") or 0)

    # Buscar pagamentos Benner
    payments: list[dict] = []
    if c.get("fornecedor_benner_handle"):
        payments = fetch_contract_payments_by_handle(int(c["fornecedor_benner_handle"]))
    elif c.get("benner_documento_match"):
        payments = fetch_contract_payments_by_docmatch(c["benner_documento_match"])

    # Agrupar pagamentos por mês
    pago_por_mes: dict[str, float] = {}
    for p in payments:
        mes = (p.get("mes") or "")[:7]
        if mes:
            pago_por_mes[mes] = pago_por_mes.get(mes, 0) + (p["valor"] or 0)

    # Gerar meses esperados (data_inicio → data_fim)
    try:
        d_ini = date.fromisoformat(str(c["data_inicio"])[:10])
        d_fim = date.fromisoformat(str(c["data_fim"])[:10])
    except (KeyError, ValueError):
        return {"status": "sem_datas", "divergencias": []}

    divergencias = []
    all_months: set[str] = set()

    # Expected months from contract
    cur_year, cur_month = d_ini.year, d_ini.month
    while (cur_year, cur_month) <= (d_fim.year, d_fim.month):
        mes_str = f"{cur_year:04d}-{cur_month:02d}"
        all_months.add(mes_str)
        pago = pago_por_mes.get(mes_str, 0.0)
        delta = pago - valor_mensal
        if abs(delta) < 0.01:
            tipo = "ok"
        elif pago == 0:
            tipo = "nao_pago"
        elif delta > 0:
            tipo = "a_maior"
        else:
            tipo = "a_menor"
        divergencias.append({
            "mes":      mes_str,
            "previsto": valor_mensal,
            "pago":     pago,
            "delta":    round(delta, 2),
            "tipo":     tipo,
        })
        cur_month += 1
        if cur_month > 12:
            cur_month = 1
            cur_year += 1

    # Extra months: paid but not expected
    for mes, pago in pago_por_mes.items():
        if mes not in all_months:
            divergencias.append({
                "mes":      mes,
                "previsto": 0.0,
                "pago":     pago,
                "delta":    round(pago, 2),
                "tipo":     "extra",
            })

    divergencias.sort(key=lambda x: x["mes"])
    total_previsto = sum(d["previsto"] for d in divergencias if d["tipo"] != "extra")
    total_pago = sum(d["pago"] for d in divergencias)
    has_divergence = any(d["tipo"] not in ("ok",) for d in divergencias)

    return {
        "status":         "divergente" if has_divergence else "ok",
        "total_previsto": round(total_previsto, 2),
        "total_pago":     round(total_pago, 2),
        "delta_total":    round(total_pago - total_previsto, 2),
        "divergencias":   divergencias,
    }


# ──────────────────────────────────────────────────────────────────────────────
# Ocorrências
# ──────────────────────────────────────────────────────────────────────────────

def create_occurrence(contract_id: str, data: dict) -> dict:
    db = get_supabase()
    now = datetime.now(timezone.utc).isoformat()
    data["contract_id"] = contract_id
    data["created_at"] = now
    data["updated_at"] = now
    res = db.table("contract_occurrences").insert(data).execute()
    return res.data[0]


def update_occurrence(occurrence_id: str, data: dict) -> dict:
    db = get_supabase()
    data["updated_at"] = datetime.now(timezone.utc).isoformat()
    res = db.table("contract_occurrences").update(data).eq("id", occurrence_id).execute()
    return res.data[0]


def list_occurrences(contract_id: str | None = None, status: str | None = None) -> list[dict]:
    db = get_supabase()
    q = db.table("contract_occurrences").select("*").order("created_at", desc=True)
    if contract_id:
        q = q.eq("contract_id", contract_id)
    if status:
        q = q.eq("status", status)
    return (q.execute().data or [])


# ──────────────────────────────────────────────────────────────────────────────
# SLA Violations
# ──────────────────────────────────────────────────────────────────────────────

def create_sla_violation(contract_id: str, data: dict) -> dict:
    db = get_supabase()
    data["contract_id"] = contract_id
    data["created_at"] = datetime.now(timezone.utc).isoformat()
    res = db.table("contract_sla_violations").insert(data).execute()
    return res.data[0]


def list_sla_violations(contract_id: str | None = None) -> list[dict]:
    db = get_supabase()
    q = db.table("contract_sla_violations").select("*").order("created_at", desc=True)
    if contract_id:
        q = q.eq("contract_id", contract_id)
    return (q.execute().data or [])


# ──────────────────────────────────────────────────────────────────────────────
# Aderência — verificação automática de pagamentos vs contrato
# ──────────────────────────────────────────────────────────────────────────────

def check_payment_adherence(contract_id: str) -> dict:
    """
    Verifica aderência dos pagamentos Benner ao contrato cadastrado.
    Auto-registra ocorrências para divergências ainda não registradas.
    Retorna: total_executado, total_pago, a_pagar, novas_ocorrencias, divergencias.
    """
    db = get_supabase()
    res = db.table("contracts").select("*").eq("id", contract_id).limit(1).execute()
    if not res.data:
        return {"status": "not_found"}

    c = res.data[0]
    valor_mensal = float(c.get("valor_mensal") or 0)
    valor_total  = float(c.get("valor_total")  or 0)

    payments: list[dict] = []
    if c.get("fornecedor_benner_handle"):
        payments = fetch_contract_payments_by_handle(int(c["fornecedor_benner_handle"]))
    elif c.get("benner_documento_match"):
        payments = fetch_contract_payments_by_docmatch(c["benner_documento_match"])

    total_executado = sum(p["valor"] or 0 for p in payments)
    total_pago      = sum(p["valor"] or 0 for p in payments if p.get("status_par") == "pago")
    a_pagar         = max(0.0, valor_total - total_pago)

    if not payments or valor_mensal <= 0:
        return {
            "status":            "sem_dados",
            "total_executado":   round(total_executado, 2),
            "total_pago":        round(total_pago, 2),
            "a_pagar":           round(a_pagar, 2),
            "novas_ocorrencias": 0,
            "divergencias":      [],
        }

    # Agrupar por mês
    pago_por_mes: dict[str, float] = {}
    for p in payments:
        mes = (p.get("mes") or "")[:7]
        if mes:
            pago_por_mes[mes] = pago_por_mes.get(mes, 0) + (p["valor"] or 0)

    # Ocorrências já registradas (evitar duplicatas)
    existing = (
        db.table("contract_occurrences")
        .select("competencia,tipo")
        .eq("contract_id", contract_id)
        .in_("tipo", ["divergencia_valor_maior", "divergencia_valor_menor"])
        .execute()
        .data or []
    )
    existing_keys = {(o["competencia"], o["tipo"]) for o in existing}

    now = datetime.now(timezone.utc).isoformat()
    tolerancia = valor_mensal * 0.02  # 2% de tolerância
    divergencias = []
    novas_ocorrencias = 0

    for mes, pago in sorted(pago_por_mes.items()):
        delta = pago - valor_mensal
        if abs(delta) <= tolerancia:
            tipo_div = "ok"
        elif delta > 0:
            tipo_div = "a_maior"
        else:
            tipo_div = "a_menor"

        divergencias.append({
            "mes":      mes,
            "previsto": valor_mensal,
            "pago":     round(pago, 2),
            "delta":    round(delta, 2),
            "tipo":     tipo_div,
        })

        if tipo_div == "ok":
            continue

        occ_tipo = "divergencia_valor_maior" if tipo_div == "a_maior" else "divergencia_valor_menor"
        key = (mes, occ_tipo)
        if key in existing_keys:
            continue

        sinal = f"+{delta:.2f}" if delta > 0 else f"{delta:.2f}"
        desc = (
            f"Pagamento {mes}: R$ {pago:.2f} | Previsto: R$ {valor_mensal:.2f} | "
            f"Diferença: R$ {sinal} ({'acima' if delta > 0 else 'abaixo'} do contrato)"
        )
        try:
            db.table("contract_occurrences").insert({
                "contract_id":    contract_id,
                "tipo":           occ_tipo,
                "descricao":      desc,
                "data_ocorrencia": f"{mes}-01",
                "competencia":    mes,
                "valor":          round(delta, 2),
                "status":         "pendente",
                "created_at":     now,
                "updated_at":     now,
            }).execute()
            novas_ocorrencias += 1
            existing_keys.add(key)
        except Exception as exc:
            logger.warning("Falha ao criar ocorrência aderência %s/%s: %s", contract_id, mes, exc)

    has_divergence = any(d["tipo"] != "ok" for d in divergencias)
    return {
        "status":            "divergente" if has_divergence else "ok",
        "total_executado":   round(total_executado, 2),
        "total_pago":        round(total_pago, 2),
        "a_pagar":           round(a_pagar, 2),
        "novas_ocorrencias": novas_ocorrencias,
        "divergencias":      divergencias,
    }


# ──────────────────────────────────────────────────────────────────────────────
# KPIs gerenciais (para cache + dashboard)
# ──────────────────────────────────────────────────────────────────────────────

def get_governance_kpis() -> dict:
    """
    KPIs gerenciais de governança.
    Usado pelo /governance/dashboard e pelo sync periódico para cache.
    """
    db = get_supabase()
    today = date.today()

    contracts_res = db.table("contracts").select("id,status,data_fim,valor_mensal,valor_total").execute()
    contracts = contracts_res.data or []

    total = len(contracts)
    vigentes = sum(1 for c in contracts if c.get("status") == "vigente")

    def days(c: dict) -> int | None:
        return _days_until(c.get("data_fim"))

    vencendo_30  = sum(1 for c in contracts if c.get("status") == "vigente" and 0 <= (days(c) or 999) <= 30)
    vencendo_60  = sum(1 for c in contracts if c.get("status") == "vigente" and 0 <= (days(c) or 999) <= 60)
    vencendo_90  = sum(1 for c in contracts if c.get("status") == "vigente" and 0 <= (days(c) or 999) <= 90)
    valor_total  = sum(float(c.get("valor_total") or 0) for c in contracts if c.get("status") == "vigente")

    occ_res = (
        db.table("contract_occurrences")
        .select("id,tipo,valor,status")
        .eq("status", "pendente")
        .execute()
    )
    occurrences = occ_res.data or []
    ocorrencias_pendentes = len(occurrences)
    valor_glosas = sum(
        abs(float(o.get("valor") or 0))
        for o in occurrences
        if o.get("tipo") in ("glosa", "multa", "desconto")
    )

    sla_res = (
        db.table("contract_sla_violations")
        .select("id")
        .in_("status", ["registrado", "notificado"])
        .execute()
    )
    sla_abertas = len(sla_res.data or [])

    # Top 10 contratos urgentes (vencendo mais cedo entre vigentes)
    urgent = sorted(
        [c for c in contracts if c.get("status") == "vigente" and days(c) is not None],
        key=lambda c: days(c) or 9999,
    )[:10]
    for c in urgent:
        c["dias_para_vencer"] = days(c)

    return {
        "total_contratos":        total,
        "contratos_vigentes":     vigentes,
        "vencendo_30d":           vencendo_30,
        "vencendo_60d":           vencendo_60,
        "vencendo_90d":           vencendo_90,
        "ocorrencias_pendentes":  ocorrencias_pendentes,
        "valor_glosas_pendentes": round(valor_glosas, 2),
        "sla_violations_abertas": sla_abertas,
        "valor_total_contratos":  round(valor_total, 2),
        "contracts":              urgent,
    }
