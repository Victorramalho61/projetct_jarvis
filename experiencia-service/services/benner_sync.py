"""Sincronização com Benner RH → exp_employees + criação de exp_avaliacoes.

Gestor imediato (revisado 2026-09-24, a pedido do RH/Victor):
- Vem da **estrutura de supervisão** (`SUP_SUPERVISORES`), não mais de `DO_FUNCIONARIOS.SUPERVISOR`.
  Cada pessoa tem um nó; `NIVELSUPERIOR` aponta para o nó do chefe; `RESPONSAVEL` →
  `Z_GRUPOUSUARIOS` (`K_FUNCIONARIO` = `DO_FUNCIONARIOS.HANDLE`). Só nós `TIPO=1` ativos — os
  `TIPO=2` (árvore `001.xxxx`) são administrativos do DP e são ignorados.
- O e-mail precisa ser **corporativo** (domínios do grupo, sem caixas genéricas). Se o chefe
  direto não tem, sobe a estrutura (chefe do chefe...) até achar; o nome do chefe direto fica em
  `gestor_direto_nome` e `gestor_email_origem` diz de onde veio o e-mail.
- Colaborador fora da estrutura: tenta o supervisor do cadastro (`RH_PESSOAS`) só para localizar
  o nó do chefe (fallback). Sem nada → sem gestor; o RH corrige pelo lápis (`gestor_manual`).

Carga: inicial = admitidos nos últimos 90 dias; diária (04:00) = admitidos ontem + re-sync de
quem ainda tem avaliação em aberto. ANARAC (28) e BSB Empreendimentos (31) ficam fora.
A matrícula se repete entre empresas — a chave é `benner_handle` (`DO_FUNCIONARIOS.HANDLE`).
"""
import logging
from collections import defaultdict
from datetime import date, timedelta

log = logging.getLogger(__name__)

JANELA_CARGA_INICIAL_DIAS = 90
EMPRESAS_EXCLUIDAS = (28, 31)  # ANARAC EMPREENDIMENTOS, BRASILIA EMPREENDIMENTOS IMOBILIARIOS
DOMINIOS_CORPORATIVOS = ("voetur.com.br", "vtclog.com.br", "vipcargas.com.br", "vipserviceclub.com.br", "payfly.com.br")
CAIXAS_GENERICAS = ("departamentopessoal@", "no-reply@", "noreply@", "sistemas@", "rh@")

_SELECT_FUNC = f"""
SELECT
    f.HANDLE                       AS BENNER_HANDLE,
    f.MATRICULA,
    f.NOME                         AS COLABORADOR,
    CAST(f.DATAADMISSAO AS DATE)   AS DATAADMISSAO,
    CAST(f.DEMISSAODATA AS DATE)   AS DATADEMISSAO,
    c.TITULO                       AS CARGO,
    h.NOME                         AS DEPARTAMENTO,
    f.EMPRESA                      AS EMPRESA_HANDLE,
    emp.NOMEFANTASIA               AS EMPRESA,
    p.HANDLEORIGEM                 AS SUPERVISOR_FUNC
FROM DO_FUNCIONARIOS f
LEFT JOIN CS_CARGOS        c   ON c.HANDLE   = f.CARGO
LEFT JOIN ADM_HIERARQUIAS  h   ON h.HANDLE   = f.HIERARQUIA
LEFT JOIN ADM_EMPRESAS     emp ON emp.HANDLE = f.EMPRESA
LEFT JOIN RH_PESSOAS       p   ON p.HANDLE   = f.SUPERVISOR
WHERE f.EMPRESA NOT IN ({",".join(str(e) for e in EMPRESAS_EXCLUIDAS)})
"""

_SELECT_ESTRUTURA = """
SELECT s.HANDLE, s.NIVELSUPERIOR, s.ESTRUTURA, u.NOME, u.EMAIL, u.K_FUNCIONARIO
FROM SUP_SUPERVISORES s
LEFT JOIN Z_GRUPOUSUARIOS u ON u.HANDLE = s.RESPONSAVEL
WHERE s.ATIVO = 'S' AND s.TIPO = 1
"""


def email_corporativo(email: str | None) -> bool:
    e = (email or "").strip().lower()
    return bool(e) and e.split("@")[-1] in DOMINIOS_CORPORATIVOS and not e.startswith(CAIXAS_GENERICAS)


class Estrutura:
    """Árvore de supervisão (nós TIPO=1 ativos) carregada uma vez por sync."""

    def __init__(self, linhas):
        self.nos = {r["handle"]: r for r in linhas}
        self.por_func = defaultdict(list)
        for n in self.nos.values():
            if n.get("k_funcionario"):
                self.por_func[n["k_funcionario"]].append(n)

    def no_do_funcionario(self, func_handle):
        lista = self.por_func.get(func_handle) or []
        return max(lista, key=lambda n: n["handle"]) if lista else None  # nó mais recente

    def primeiro_corporativo(self, no):
        """Sobe a partir de `no` (inclusive) até achar e-mail corporativo. Retorna (no, niveis_subidos)."""
        nivel, visitados = 0, set()
        while no and no["handle"] not in visitados:
            visitados.add(no["handle"])
            if email_corporativo(no.get("email")):
                return no, nivel
            no, nivel = self.nos.get(no.get("nivelsuperior")), nivel + 1
        return None, nivel

    def resolver_gestor(self, func_handle, supervisor_func=None) -> dict:
        no = self.no_do_funcionario(func_handle)
        if no:
            pai = self.nos.get(no.get("nivelsuperior"))
            alvo, subidos = self.primeiro_corporativo(pai)
            return {
                "estrutura": no.get("estrutura"),
                "gestor_direto_nome": (pai or {}).get("nome"),
                "gestor_nome": alvo["nome"] if alvo else (pai or {}).get("nome"),
                "gestor_email": alvo["email"].strip().lower() if alvo else None,
                "gestor_email_origem": ("direto" if subidos == 0 else "superior") if alvo else None,
            }
        # Fora da estrutura: usa o supervisor do cadastro só para achar o nó do chefe
        no_sup = self.no_do_funcionario(supervisor_func) if supervisor_func else None
        alvo, _ = self.primeiro_corporativo(no_sup)
        return {
            "estrutura": None,
            "gestor_direto_nome": (no_sup or {}).get("nome"),
            "gestor_nome": alvo["nome"] if alvo else (no_sup or {}).get("nome"),
            "gestor_email": alvo["email"].strip().lower() if alvo else None,
            "gestor_email_origem": "fallback_supervisor" if alvo else None,
        }


def _rows(cur) -> list[dict]:
    cols = [d[0].lower() for d in cur.description]
    return [dict(zip(cols, r)) for r in cur.fetchall()]


def _fetch_from_benner(completo: bool, handles_abertos: list[int]) -> tuple[list[dict], Estrutura]:
    from db import get_sql_connection

    conn = get_sql_connection()
    try:
        cur = conn.cursor()
        cur.execute(_SELECT_ESTRUTURA)
        estrutura = Estrutura(_rows(cur))

        if completo:
            cur.execute(_SELECT_FUNC + " AND f.DATAADMISSAO >= DATEADD(DAY, ?, CAST(GETDATE() AS DATE))",
                        (-JANELA_CARGA_INICIAL_DIAS,))
            rows = _rows(cur)
        else:
            # admitidos ontem (e hoje, se o DP já lançou) + quem tem avaliação em aberto
            cur.execute(_SELECT_FUNC + " AND f.DATAADMISSAO >= DATEADD(DAY, -1, CAST(GETDATE() AS DATE))")
            rows = _rows(cur)
            vistos = {r["benner_handle"] for r in rows}
            pendentes = [h for h in handles_abertos if h not in vistos]
            for i in range(0, len(pendentes), 500):
                lote = pendentes[i:i + 500]
                cur.execute(_SELECT_FUNC + f" AND f.HANDLE IN ({','.join('?' * len(lote))})", lote)
                rows += _rows(cur)
        for r in rows:
            r["matricula"] = str(r["matricula"]) if r.get("matricula") is not None else None
            for k in ("dataadmissao", "datademissao"):
                if hasattr(r.get(k), "date") and not isinstance(r.get(k), date):
                    r[k] = r[k].date()
        return rows, estrutura
    finally:
        conn.close()


def _handles_em_aberto(sb) -> list[int]:
    """benner_handle de quem tem avaliação ainda não respondida (re-sync diário)."""
    rows = (
        sb.table("exp_avaliacoes")
        .select("exp_employees(benner_handle)")
        .in_("status", ["pendente", "sem_gestor", "enviado"])
        .execute()
        .data or []
    )
    return sorted({(r.get("exp_employees") or {}).get("benner_handle") for r in rows} - {None})


def _upsert_employee(sb, row: dict, gestor: dict) -> tuple[str | None, bool]:
    """Grava o colaborador. Retorna (id, tem_gestor_valido)."""
    handle = row.get("benner_handle")
    if not handle:
        return None, False

    existente = sb.table("exp_employees").select("id,gestor_manual,gestor_email").eq("benner_handle", handle).execute().data
    if not existente:
        # registro antigo (antes da v2), identificado só por matrícula + empresa
        existente = (
            sb.table("exp_employees").select("id,gestor_manual,gestor_email")
            .eq("matricula", row.get("matricula")).eq("empresa", row.get("empresa"))
            .is_("benner_handle", "null").execute().data
        )

    payload = {
        "benner_handle":  handle,
        "matricula":      row.get("matricula"),
        "nome":           row.get("colaborador") or "",
        "cargo":          row.get("cargo"),
        "departamento":   row.get("departamento"),
        "empresa":        row.get("empresa"),
        "empresa_handle": row.get("empresa_handle"),
        "data_admissao":  str(row["dataadmissao"]) if row.get("dataadmissao") else None,
        "ativo":          not row.get("datademissao"),
        "estrutura":      gestor.get("estrutura"),
        "synced_at":      "now()",
    }
    manual = bool(existente and existente[0].get("gestor_manual"))
    if not manual:
        payload.update({
            "gestor_direto_nome":  gestor.get("gestor_direto_nome"),
            "gestor_nome":         gestor.get("gestor_nome"),
            "gestor_email":        gestor.get("gestor_email"),
            "gestor_email_origem": gestor.get("gestor_email_origem"),
        })
    tem_gestor = bool(existente[0].get("gestor_email")) if manual else bool(gestor.get("gestor_email"))

    if existente:
        sb.table("exp_employees").update(payload).eq("id", existente[0]["id"]).execute()
        return existente[0]["id"], tem_gestor
    resp = sb.table("exp_employees").insert(payload).execute()
    return (resp.data[0]["id"] if resp.data else None), tem_gestor


def _ensure_avaliacao(sb, employee_id: str, tipo: str, data_admissao: date) -> bool:
    """Cria exp_avaliacoes para o tipo se ainda não existir. Retorna True se criou."""
    dias = 45 if tipo == "45_dias" else 90
    existing = sb.table("exp_avaliacoes").select("id").eq("employee_id", employee_id).eq("tipo", tipo).execute()
    if existing.data:
        return False
    sb.table("exp_avaliacoes").insert({
        "employee_id":   employee_id,
        "tipo":          tipo,
        "data_prevista": str(data_admissao + timedelta(days=dias)),
        "status":        "pendente",
        "total_envios":  0,
    }).execute()
    return True


def _ajustar_status_gestor(sb, employee_id: str, tem_gestor: bool) -> None:
    """pendente ⇄ sem_gestor conforme o colaborador tenha e-mail de gestor válido."""
    if tem_gestor:
        sb.table("exp_avaliacoes").update({"status": "pendente"}).eq("employee_id", employee_id).eq("status", "sem_gestor").execute()
    else:
        sb.table("exp_avaliacoes").update({"status": "sem_gestor"}).eq("employee_id", employee_id).eq("status", "pendente").execute()


def run_sync(completo: bool | None = None, dry_run: bool = False) -> dict:
    """completo=True: carga dos últimos 90 dias. None: automático (completo se ainda não houve
    carga v2, senão incremental). dry_run: só calcula e devolve o relatório, sem gravar."""
    from db import get_supabase

    sb = get_supabase()
    if completo is None:
        ja_carregado = sb.table("exp_employees").select("id", count="exact").not_.is_("benner_handle", "null").limit(0).execute().count
        completo = not ja_carregado

    stats = {"modo": "completo" if completo else "incremental", "benner_rows": 0, "upserted": 0,
             "avaliacoes_criadas": 0, "erros": 0, "gestor_origem": defaultdict(int)}
    try:
        rows, estrutura = _fetch_from_benner(completo, [] if completo else _handles_em_aberto(sb))
        stats["benner_rows"] = len(rows)
    except Exception as exc:
        log.error("[sync] Falha ao buscar Benner: %s", exc)
        stats["erros"] += 1
        return stats

    for row in rows:
        try:
            gestor = estrutura.resolver_gestor(row["benner_handle"], row.get("supervisor_func"))
            stats["gestor_origem"][gestor.get("gestor_email_origem") or "sem_gestor"] += 1
            if dry_run:
                continue
            emp_id, tem_gestor = _upsert_employee(sb, row, gestor)
            if not emp_id:
                continue
            stats["upserted"] += 1
            adm = row.get("dataadmissao")
            if adm and not row.get("datademissao"):
                for tipo, dias in (("45_dias", 45), ("90_dias", 90)):
                    # só cria se a data prevista não passou há mais de 30 dias
                    if (date.today() - (adm + timedelta(days=dias))).days <= 30:
                        stats["avaliacoes_criadas"] += int(_ensure_avaliacao(sb, emp_id, tipo, adm))
            _ajustar_status_gestor(sb, emp_id, tem_gestor)
        except Exception as exc:
            log.error("[sync] Erro processando handle %s: %s", row.get("benner_handle"), exc)
            stats["erros"] += 1

    stats["gestor_origem"] = dict(stats["gestor_origem"])
    log.info("[sync] Concluído: %s", stats)
    return stats
