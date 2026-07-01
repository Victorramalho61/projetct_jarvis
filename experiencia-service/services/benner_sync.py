"""Sincronização diária com Benner TH → exp_employees + criação de exp_avaliacoes."""
import logging
from datetime import date, timedelta

log = logging.getLogger(__name__)

# Janela de busca: admitidos nos últimos 100 dias (cobre 45+90 dias com margem)
_JANELA_DIAS = 100

_BENNER_QUERY = """
SELECT
    f.MATRICULA,
    f.NOME                      AS COLABORADOR,
    CAST(f.DATAADMISSAO AS DATE) AS DATAADMISSAO,
    c.TITULO                    AS CARGO,
    h.NOME                      AS SETOR,
    emp.NOMEFANTASIA             AS EMPRESA,
    p.NOME                      AS GESTOR_NOME,
    gs.MATRICULA                AS GESTOR_MATRICULA,
    gs.EMAIL                    AS GESTOR_EMAIL
FROM DO_FUNCIONARIOS f
LEFT JOIN CS_CARGOS        c   ON c.HANDLE  = f.CARGO
LEFT JOIN ADM_HIERARQUIAS  h   ON h.HANDLE  = f.HIERARQUIA
LEFT JOIN ADM_EMPRESAS     emp ON emp.HANDLE = f.EMPRESA
LEFT JOIN RH_PESSOAS       p   ON p.HANDLE  = f.SUPERVISOR
LEFT JOIN DO_FUNCIONARIOS  gs  ON gs.HANDLE = p.HANDLEORIGEM
WHERE f.DATAADMISSAO >= DATEADD(DAY, ?, GETDATE())
ORDER BY f.DATAADMISSAO DESC
"""


def _fetch_from_benner() -> list[dict]:
    from db import get_sql_connection
    conn = get_sql_connection()
    try:
        cur = conn.cursor()
        cur.execute(_BENNER_QUERY, (-_JANELA_DIAS,))
        cols = [d[0].lower() for d in cur.description]
        rows = []
        for row in cur.fetchall():
            r = dict(zip(cols, row))
            # normaliza campos
            r["matricula"] = str(r["matricula"]) if r["matricula"] is not None else None
            r["gestor_matricula"] = str(r["gestor_matricula"]) if r["gestor_matricula"] is not None else None
            if hasattr(r.get("dataadmissao"), "date"):
                r["dataadmissao"] = r["dataadmissao"].date()
            rows.append(r)
        return rows
    finally:
        conn.close()


def _upsert_employee(sb, row: dict) -> str | None:
    """Upsert em exp_employees. Retorna o id do registro."""
    matricula = row.get("matricula")
    if not matricula:
        return None

    payload = {
        "matricula":     matricula,
        "nome":          row.get("colaborador") or "",
        "cargo":         row.get("cargo"),
        "departamento":  row.get("setor"),
        "empresa":       row.get("empresa"),
        "data_admissao": str(row["dataadmissao"]) if row.get("dataadmissao") else None,
        "gestor_nome":   row.get("gestor_nome"),
        "gestor_email":  row.get("gestor_email"),
        "ativo":         True,
        "synced_at":     "now()",
    }

    resp = (
        sb.table("exp_employees")
        .upsert(payload, on_conflict="matricula")
        .execute()
    )
    if resp.data:
        return resp.data[0]["id"]

    # fallback: buscar id existente
    r = sb.table("exp_employees").select("id").eq("matricula", matricula).single().execute()
    return r.data["id"] if r.data else None


def _ensure_avaliacao(sb, employee_id: str, tipo: str, data_admissao: date) -> None:
    """Cria exp_avaliacoes para o tipo se ainda não existir."""
    dias = 45 if tipo == "45_dias" else 90
    data_prevista = str(data_admissao + timedelta(days=dias))

    existing = (
        sb.table("exp_avaliacoes")
        .select("id")
        .eq("employee_id", employee_id)
        .eq("tipo", tipo)
        .execute()
    )
    if existing.data:
        return  # já existe

    sb.table("exp_avaliacoes").insert({
        "employee_id":   employee_id,
        "tipo":          tipo,
        "data_prevista": data_prevista,
        "status":        "pendente",
        "total_envios":  0,
    }).execute()


def run_sync() -> dict:
    """Executa a sincronização completa. Retorna estatísticas."""
    from db import get_supabase
    sb = get_supabase()

    stats = {"benner_rows": 0, "upserted": 0, "avaliacoes_criadas": 0, "erros": 0}

    try:
        rows = _fetch_from_benner()
        stats["benner_rows"] = len(rows)
        log.info("[sync] %d registros do Benner", len(rows))
    except Exception as exc:
        log.error("[sync] Falha ao buscar Benner: %s", exc)
        stats["erros"] += 1
        return stats

    for row in rows:
        try:
            emp_id = _upsert_employee(sb, row)
            if not emp_id:
                continue
            stats["upserted"] += 1

            adm = row.get("dataadmissao")
            if not adm:
                continue

            for tipo in ("45_dias", "90_dias"):
                dias = 45 if tipo == "45_dias" else 90
                data_prev = adm + timedelta(days=dias)
                # só cria avaliação se a data prevista ainda não passou há mais de 30 dias
                if (date.today() - data_prev).days <= 30:
                    before = _count_avaliacoes(sb, emp_id, tipo)
                    _ensure_avaliacao(sb, emp_id, tipo, adm)
                    after = _count_avaliacoes(sb, emp_id, tipo)
                    if after > before:
                        stats["avaliacoes_criadas"] += 1

        except Exception as exc:
            log.error("[sync] Erro processando matrícula %s: %s", row.get("matricula"), exc)
            stats["erros"] += 1

    log.info("[sync] Concluído: %s", stats)
    return stats


def _count_avaliacoes(sb, employee_id: str, tipo: str) -> int:
    r = (
        sb.table("exp_avaliacoes")
        .select("id", count="exact")
        .eq("employee_id", employee_id)
        .eq("tipo", tipo)
        .execute()
    )
    return r.count or 0
