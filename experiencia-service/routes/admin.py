"""Rotas admin/RH — autenticadas."""
import logging
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from auth import require_role
from db import get_supabase

router = APIRouter(prefix="/api/experiencia/admin")
log = logging.getLogger(__name__)

_ADMIN_ROLES = ("admin", "rh")


def _require_admin(user=Depends(require_role(*_ADMIN_ROLES))):
    return user


# ── Helpers ───────────────────────────────────────────────────────────────────

def _apply_filters(query, empresa: Optional[str], status: Optional[str], q: Optional[str]):
    """Aplica filtros comuns nas queries de avaliação (join com exp_employees já feito)."""
    if empresa:
        query = query.eq("exp_employees.empresa", empresa)
    if status:
        query = query.eq("status", status)
    if q:
        # busca por nome ou matrícula via ILIKE
        query = query.or_(
            f"exp_employees.nome.ilike.%{q}%,"
            f"exp_employees.matricula.ilike.%{q}%,"
            f"exp_employees.gestor_nome.ilike.%{q}%"
        )
    return query


def _gerar_token(avaliacao_id: str, sb) -> str:
    token = secrets.token_urlsafe(32)
    expires = (datetime.now(timezone.utc) + timedelta(days=30)).isoformat()
    sb.table("exp_avaliacoes").update({
        "token":            token,
        "token_expires_at": expires,
    }).eq("id", avaliacao_id).execute()
    return token


def _registrar_envio(sb, avaliacao_id: str, destinatario: str, tipo_email: str, sucesso: bool):
    from services.email_service import log_email
    log_email(sb, avaliacao_id, destinatario, tipo_email, sucesso)
    if sucesso:
        now = datetime.now(timezone.utc).isoformat()
        av = sb.table("exp_avaliacoes").select("total_envios, primeiro_envio_at").eq("id", avaliacao_id).single().execute()
        total = (av.data.get("total_envios") or 0) + 1
        update = {
            "status":         "enviado",
            "total_envios":   total,
            "ultimo_envio_at": now,
            "updated_at":     "now()",
        }
        if not av.data.get("primeiro_envio_at"):
            update["primeiro_envio_at"] = now
        sb.table("exp_avaliacoes").update(update).eq("id", avaliacao_id).execute()


# ── Sync manual ───────────────────────────────────────────────────────────────

@router.post("/sync-benner")
def sync_benner(
    completo: bool = Query(False, description="True = recarga dos admitidos nos últimos 90 dias"),
    dry_run: bool = Query(False, description="Só calcula (gestor/cobertura), sem gravar"),
    user=Depends(_require_admin),
):
    from services.benner_sync import run_sync
    try:
        stats = run_sync(completo=True if completo else None, dry_run=dry_run)
        return {"ok": True, "stats": stats}
    except Exception as exc:
        log.error("Sync manual falhou: %s", exc)
        raise HTTPException(status_code=500, detail=f"Erro na sincronização: {exc}")


# ── Listagens 45/90 dias ──────────────────────────────────────────────────────

def _list_avaliacoes(tipo: str, empresa: Optional[str], status: Optional[str], q: Optional[str]):
    sb = get_supabase()
    query = (
        sb.table("exp_avaliacoes")
        .select("*, exp_employees(*)")
        .eq("tipo", tipo)
        .order("data_prevista", desc=False)
    )
    resp = query.execute()
    rows = resp.data or []

    # Filtragem em Python (Supabase não suporta ILIKE em FK via REST sem RPC)
    if empresa:
        rows = [r for r in rows if (r.get("exp_employees") or {}).get("empresa") == empresa]
    if status:
        rows = [r for r in rows if r.get("status") == status]
    if q:
        q_lower = q.lower()
        rows = [r for r in rows if (
            q_lower in ((r.get("exp_employees") or {}).get("nome") or "").lower() or
            q_lower in str((r.get("exp_employees") or {}).get("matricula") or "").lower() or
            q_lower in ((r.get("exp_employees") or {}).get("gestor_nome") or "").lower()
        )]

    return [_format_avaliacao(r) for r in rows]


def _format_avaliacao(r: dict) -> dict:
    emp = r.get("exp_employees") or {}
    return {
        "id":             r["id"],
        "tipo":           r.get("tipo"),
        "status":         r.get("status"),
        "data_prevista":  r.get("data_prevista"),
        "total_envios":   r.get("total_envios", 0),
        "ultimo_envio_at":r.get("ultimo_envio_at"),
        "primeiro_envio_at": r.get("primeiro_envio_at"),
        "token":          r.get("token"),
        "nota_total":        r.get("nota_total"),
        "nota_percentual":   r.get("nota_percentual"),
        "nota_insuficiente": r.get("nota_insuficiente"),
        "envio_automatico_at": r.get("envio_automatico_at"),
        "colaborador": _colaborador(emp),
    }


def _colaborador(emp: dict) -> dict:
    return {
        "id":                  emp.get("id"),
        "matricula":           emp.get("matricula"),
        "nome":                emp.get("nome"),
        "cargo":               emp.get("cargo"),
        "departamento":        emp.get("departamento"),
        "empresa":             emp.get("empresa"),
        "data_admissao":       emp.get("data_admissao"),
        "gestor_nome":         emp.get("gestor_nome"),
        "gestor_email":        emp.get("gestor_email"),
        "gestor_direto_nome":  emp.get("gestor_direto_nome"),
        "gestor_email_origem": emp.get("gestor_email_origem"),
        "gestor_manual":       emp.get("gestor_manual"),
        "estrutura":           emp.get("estrutura"),
    }


@router.get("/45-dias")
def list_45_dias(
    empresa: Optional[str] = Query(None),
    status:  Optional[str] = Query(None),
    q:       Optional[str] = Query(None),
    user=Depends(_require_admin),
):
    return _list_avaliacoes("45_dias", empresa, status, q)


@router.get("/90-dias")
def list_90_dias(
    empresa: Optional[str] = Query(None),
    status:  Optional[str] = Query(None),
    q:       Optional[str] = Query(None),
    user=Depends(_require_admin),
):
    return _list_avaliacoes("90_dias", empresa, status, q)


# ── Auditoria ─────────────────────────────────────────────────────────────────

@router.get("/auditoria")
def auditoria(
    empresa:     Optional[str] = Query(None),
    tipo:        Optional[str] = Query(None),
    status:      Optional[str] = Query(None),
    q:           Optional[str] = Query(None),
    data_inicio: Optional[str] = Query(None),
    data_fim:    Optional[str] = Query(None),
    user=Depends(_require_admin),
):
    sb = get_supabase()
    query = sb.table("exp_avaliacoes").select("*, exp_employees(*)").order("data_prevista", desc=True)

    if tipo:
        query = query.eq("tipo", tipo)
    if data_inicio:
        query = query.gte("gestor_assinatura_at", data_inicio)
    if data_fim:
        query = query.lte("gestor_assinatura_at", data_fim + "T23:59:59")

    resp = query.execute()
    rows = resp.data or []

    if empresa:
        rows = [r for r in rows if (r.get("exp_employees") or {}).get("empresa") == empresa]
    if status:
        rows = [r for r in rows if r.get("status") == status]
    if q:
        q_lower = q.lower()
        rows = [r for r in rows if (
            q_lower in ((r.get("exp_employees") or {}).get("nome") or "").lower() or
            q_lower in str((r.get("exp_employees") or {}).get("matricula") or "").lower() or
            q_lower in ((r.get("exp_employees") or {}).get("gestor_nome") or "").lower()
        )]

    return [_format_auditoria(r) for r in rows]


def _format_auditoria(r: dict) -> dict:
    emp = r.get("exp_employees") or {}
    return {
        "id":                r["id"],
        "tipo":              r.get("tipo"),
        "status":            r.get("status"),
        "data_prevista":     r.get("data_prevista"),
        "gestor_assinatura_at": r.get("gestor_assinatura_at"),
        "total_envios":      r.get("total_envios", 0),
        "primeiro_envio_at": r.get("primeiro_envio_at"),
        "ultimo_envio_at":   r.get("ultimo_envio_at"),
        "nota_total":        r.get("nota_total"),
        "nota_percentual":   r.get("nota_percentual"),
        "nota_insuficiente": r.get("nota_insuficiente"),
        "colaborador": _colaborador(emp),
    }


@router.get("/auditoria/{avaliacao_id}/detalhes")
def auditoria_detalhes(avaliacao_id: str, user=Depends(_require_admin)):
    sb = get_supabase()

    av = (
        sb.table("exp_avaliacoes")
        .select("*, exp_employees(*)")
        .eq("id", avaliacao_id)
        .single()
        .execute()
    )
    if not av.data:
        raise HTTPException(status_code=404, detail="Avaliação não encontrada")

    logs = (
        sb.table("exp_email_log")
        .select("*")
        .eq("avaliacao_id", avaliacao_id)
        .order("enviado_at", desc=False)
        .execute()
    )

    avaliacao = av.data
    emp = avaliacao.pop("exp_employees", {}) or {}

    from services.formulario import get_formulario
    formulario = get_formulario(avaliacao.get("tipo", "45_dias"))

    return {
        "avaliacao":  avaliacao,
        "colaborador": emp,
        "formulario": formulario,
        "email_log":  logs.data or [],
    }


# ── Envio / cobrança ──────────────────────────────────────────────────────────

@router.post("/enviar/{avaliacao_id}")
def enviar_avaliacao(avaliacao_id: str, user=Depends(_require_admin)):
    """Primeiro envio da avaliação ao gestor."""
    sb = get_supabase()

    av = (
        sb.table("exp_avaliacoes")
        .select("*, exp_employees(*)")
        .eq("id", avaliacao_id)
        .single()
        .execute()
    )
    if not av.data:
        raise HTTPException(status_code=404, detail="Avaliação não encontrada")

    avaliacao = av.data
    emp = avaliacao.get("exp_employees") or {}
    gestor_email = emp.get("gestor_email")

    if not gestor_email:
        raise HTTPException(status_code=422, detail="Gestor sem e-mail cadastrado")

    if avaliacao.get("status") == "respondido":
        raise HTTPException(status_code=409, detail="Avaliação já foi respondida")

    token = avaliacao.get("token") or _gerar_token(avaliacao_id, sb)

    from services.email_service import send_primeiro_envio
    ok = send_primeiro_envio(avaliacao, emp, token)
    _registrar_envio(sb, avaliacao_id, gestor_email, "primeiro_envio", ok)

    if not ok:
        raise HTTPException(status_code=500, detail="Falha ao enviar e-mail")

    return {"ok": True, "token": token}


@router.post("/reenviar/{avaliacao_id}")
def reenviar_avaliacao(avaliacao_id: str, user=Depends(_require_admin)):
    """Cobrança manual: reenvia e-mail ao gestor."""
    sb = get_supabase()

    av = (
        sb.table("exp_avaliacoes")
        .select("*, exp_employees(*)")
        .eq("id", avaliacao_id)
        .single()
        .execute()
    )
    if not av.data:
        raise HTTPException(status_code=404, detail="Avaliação não encontrada")

    avaliacao = av.data
    emp = avaliacao.get("exp_employees") or {}

    if avaliacao.get("status") == "respondido":
        raise HTTPException(status_code=409, detail="Avaliação já foi respondida")

    token = avaliacao.get("token") or _gerar_token(avaliacao_id, sb)

    from services.email_service import send_cobranca
    ok = send_cobranca(avaliacao, emp)
    gestor_email = emp.get("gestor_email", "—")
    _registrar_envio(sb, avaliacao_id, gestor_email, "cobranca", ok)

    if not ok:
        raise HTTPException(status_code=500, detail="Falha ao enviar e-mail de cobrança")

    return {"ok": True}


class DispararCobracasPayload(BaseModel):
    empresa: Optional[str] = None
    tipo:    Optional[str] = None  # '45_dias' | '90_dias' | None = todos


@router.post("/disparar-cobracas")
def disparar_cobracas(payload: DispararCobracasPayload, user=Depends(_require_admin)):
    """Dispara cobranças em lote para todas as avaliações enviadas e não respondidas."""
    sb = get_supabase()

    query = (
        sb.table("exp_avaliacoes")
        .select("*, exp_employees(*)")
        .eq("status", "enviado")
    )
    if payload.tipo:
        query = query.eq("tipo", payload.tipo)

    resp = query.execute()
    rows = resp.data or []

    if payload.empresa:
        rows = [r for r in rows if (r.get("exp_employees") or {}).get("empresa") == payload.empresa]

    from services.email_service import send_cobranca
    enviadas = 0
    erros = 0

    for av in rows:
        emp = av.get("exp_employees") or {}
        if not emp.get("gestor_email"):
            continue
        try:
            ok = send_cobranca(av, emp)
            _registrar_envio(sb, av["id"], emp.get("gestor_email", "—"), "cobranca", ok)
            if ok:
                enviadas += 1
            else:
                erros += 1
        except Exception as exc:
            log.error("Erro disparando cobrança para %s: %s", av.get("id"), exc)
            erros += 1

    return {"ok": True, "enviadas": enviadas, "erros": erros}


# ── Editar e-mail do gestor (antes do envio) ──────────────────────────────────

class UpdateGestorEmailPayload(BaseModel):
    gestor_email: str
    gestor_nome: Optional[str] = None


@router.patch("/colaborador/{employee_id}/gestor-email")
def update_gestor_email(employee_id: str, payload: UpdateGestorEmailPayload, user=Depends(_require_admin)):
    """Permite RH corrigir nome/e-mail do gestor. Marca gestor_manual: o sync diário não sobrescreve."""
    sb = get_supabase()
    email = payload.gestor_email.strip().lower()
    from services.benner_sync import email_corporativo
    if email and not email_corporativo(email):
        raise HTTPException(status_code=422, detail="Use o e-mail corporativo do gestor (domínio do Grupo Voetur)")
    update = {"gestor_email": email or None, "gestor_manual": True, "gestor_email_origem": "manual"}
    if payload.gestor_nome:
        update["gestor_nome"] = payload.gestor_nome.strip()
    sb.table("exp_employees").update(update).eq("id", employee_id).execute()
    # Re-marca avaliações pendentes como 'pendente' (sai de sem_gestor)
    sb.table("exp_avaliacoes").update({"status": "pendente"}).eq("employee_id", employee_id).eq("status", "sem_gestor").execute()
    return {"ok": True}


# ── Exportação CSV ────────────────────────────────────────────────────────────

@router.get("/export")
def export_csv(
    empresa:     Optional[str] = Query(None),
    tipo:        Optional[str] = Query(None),
    status:      Optional[str] = Query(None),
    user=Depends(_require_admin),
):
    import io
    import csv
    from fastapi.responses import StreamingResponse

    sb = get_supabase()
    query = sb.table("exp_avaliacoes").select("*, exp_employees(*)").order("data_prevista")
    if tipo:
        query = query.eq("tipo", tipo)
    if status:
        query = query.eq("status", status)

    resp = query.execute()
    rows = resp.data or []

    if empresa:
        rows = [r for r in rows if (r.get("exp_employees") or {}).get("empresa") == empresa]

    output = io.StringIO()
    writer = csv.writer(output, delimiter=";")
    writer.writerow([
        "Empresa", "Matrícula", "Colaborador", "Cargo", "Departamento",
        "Data Admissão", "Tipo", "Data Prevista", "Status",
        "Gestor", "E-mail Gestor",
        "Respondido em", "Assinado em", "Total Envios",
        "Parecer", "Nota", "Nota %", "Nota insuficiente",
    ])

    for r in rows:
        emp = r.get("exp_employees") or {}
        respostas = r.get("respostas") or {}
        parecer = respostas.get("parecer", "")
        writer.writerow([
            emp.get("empresa", ""),
            emp.get("matricula", ""),
            emp.get("nome", ""),
            emp.get("cargo", ""),
            emp.get("departamento", ""),
            emp.get("data_admissao", ""),
            r.get("tipo", ""),
            r.get("data_prevista", ""),
            r.get("status", ""),
            emp.get("gestor_nome", ""),
            emp.get("gestor_email", ""),
            (r.get("gestor_assinatura_at") or "")[:19].replace("T", " "),
            (r.get("gestor_assinatura_at") or "")[:19].replace("T", " "),
            r.get("total_envios", 0),
            parecer,
            r.get("nota_total") if r.get("nota_total") is not None else "",
            r.get("nota_percentual") if r.get("nota_percentual") is not None else "",
            "SIM" if r.get("nota_insuficiente") else "",
        ])

    output.seek(0)
    filename = "avaliacoes_experiencia.csv"
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv; charset=utf-8-sig",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# ── Lista de empresas disponíveis (para filtro dropdown) ─────────────────────

@router.get("/empresas")
def list_empresas(user=Depends(_require_admin)):
    sb = get_supabase()
    resp = sb.table("exp_employees").select("empresa").execute()
    empresas = sorted({r["empresa"] for r in (resp.data or []) if r.get("empresa")})
    return empresas


# ── Dashboard ────────────────────────────────────────────────────────────────

KPIS_DASHBOARD = [
    ("vencendo_10d",        "Vencendo em até 10 dias"),
    ("pendentes_envio",     "Pendentes de envio"),
    ("aguardando_resposta", "Enviadas, aguardando resposta"),
    ("vencidas",            "Vencidas sem resposta"),
    ("sem_gestor",          "Sem gestor"),
    ("respondidas_prazo",   "Respondidas no prazo"),
    ("respondidas_atraso",  "Respondidas com atraso"),
    ("nota_insuficiente",   "Notas insuficientes (< 50%)"),
]


def _flags(r: dict, hoje) -> list[str]:
    from datetime import date as _date
    st = r.get("status")
    prev = _date.fromisoformat(r["data_prevista"]) if r.get("data_prevista") else None
    aberta = st in ("pendente", "enviado", "sem_gestor")
    f = []
    if aberta and prev and hoje <= prev <= hoje + timedelta(days=10):
        f.append("vencendo_10d")
    if st == "pendente":
        f.append("pendentes_envio")
    if st == "enviado" and prev and prev >= hoje:
        f.append("aguardando_resposta")
    if aberta and prev and prev < hoje:
        f.append("vencidas")
    if st == "sem_gestor":
        f.append("sem_gestor")
    if st == "respondido":
        assinado = (r.get("gestor_assinatura_at") or "")[:10]
        f.append("respondidas_prazo" if prev and assinado and assinado <= prev.isoformat() else "respondidas_atraso")
        if r.get("nota_insuficiente"):
            f.append("nota_insuficiente")
    return f


@router.get("/dashboard")
def dashboard(
    tipo:    Optional[str] = Query(None),
    empresa: Optional[str] = Query(None),
    departamento: Optional[str] = Query(None),
    data_inicio: Optional[str] = Query(None, description="data prevista a partir de"),
    data_fim:    Optional[str] = Query(None, description="data prevista até"),
    user=Depends(_require_admin),
):
    """KPIs da avaliação de experiência + linhas com os KPIs de cada uma (drill-down no front)."""
    from collections import Counter
    from datetime import date as _date

    sb = get_supabase()
    query = sb.table("exp_avaliacoes").select("*, exp_employees(*)").order("data_prevista")
    if tipo:
        query = query.eq("tipo", tipo)
    if data_inicio:
        query = query.gte("data_prevista", data_inicio)
    if data_fim:
        query = query.lte("data_prevista", data_fim)
    rows = query.execute().data or []
    rows = [r for r in rows if (r.get("exp_employees") or {}).get("ativo", True)]
    if empresa:
        rows = [r for r in rows if (r.get("exp_employees") or {}).get("empresa") == empresa]
    if departamento:
        rows = [r for r in rows if (r.get("exp_employees") or {}).get("departamento") == departamento]

    hoje = _date.today()
    linhas = []
    for r in rows:
        item = _format_avaliacao(r)
        item["gestor_assinatura_at"] = r.get("gestor_assinatura_at")
        item["parecer"] = (r.get("respostas") or {}).get("parecer")
        item["kpis"] = _flags(r, hoje)
        linhas.append(item)

    contagem = Counter(k for l in linhas for k in l["kpis"])
    respondidas = [l for l in linhas if l["status"] == "respondido"]
    notas = [float(l["nota_percentual"]) for l in respondidas if l.get("nota_percentual") is not None]

    def _por(chave):
        c = Counter((l["colaborador"].get(chave) or "—") for l in linhas)
        resp = Counter((l["colaborador"].get(chave) or "—") for l in respondidas)
        insuf = Counter((l["colaborador"].get(chave) or "—") for l in linhas if "nota_insuficiente" in l["kpis"])
        return sorted(
            [{"nome": k, "total": v, "respondidas": resp.get(k, 0), "nota_insuficiente": insuf.get(k, 0)} for k, v in c.items()],
            key=lambda x: -x["total"],
        )

    return {
        "kpis": [{"id": k, "label": lbl, "total": contagem.get(k, 0)} for k, lbl in KPIS_DASHBOARD],
        "totais": {
            "avaliacoes": len(linhas),
            "respondidas": len(respondidas),
            "pct_respondidas": round(100 * len(respondidas) / len(linhas), 1) if linhas else None,
            "nota_media_pct": round(sum(notas) / len(notas), 1) if notas else None,
            "por_tipo": dict(Counter(l["tipo"] for l in linhas)),
        },
        "pareceres": dict(Counter(l["parecer"] for l in respondidas if l.get("parecer"))),
        "por_empresa": _por("empresa"),
        "por_departamento": _por("departamento"),
        "linhas": linhas,
    }


@router.get("/departamentos")
def list_departamentos(user=Depends(_require_admin)):
    sb = get_supabase()
    resp = sb.table("exp_employees").select("departamento").execute()
    return sorted({r["departamento"] for r in (resp.data or []) if r.get("departamento")})


# ── E-mails de validação (modelo para o RH aprovar) ──────────────────────────

class EmailsValidacaoPayload(BaseModel):
    destinatarios: list[str]


@router.post("/emails-validacao")
def enviar_emails_validacao(payload: EmailsValidacaoPayload, user=Depends(_require_admin)):
    """Envia os modelos [TESTE] (formulário, alerta D-10, nota insuficiente) com colaborador fictício.
    O link aponta para o formulário de demonstração (/experiencia/avaliar/demo), que não grava nada."""
    from services.email_service import send_alerta_nota_insuficiente, send_primeiro_envio

    emp = {
        "nome": "COLABORADOR EXEMPLO (DEMONSTRAÇÃO)", "cargo": "Analista Administrativo",
        "empresa": "Voetur Turismo", "departamento": "Recursos Humanos", "data_admissao": "01/08/2026",
        "gestor_nome": "Gestor Exemplo", "gestor_email": "exemplo@voetur.com.br",
    }
    av45 = {"tipo": "45_dias", "data_prevista": "2026-10-05"}
    av_ruim = {
        "tipo": "45_dias", "data_prevista": "2026-10-05", "nota_total": 16, "nota_percentual": 44.44,
        "respostas": {"parecer": "interromper", "indicadores": {
            "apresentacao_pessoal": 2, "produtividade": 1, "conhecimento_trabalho": 2, "cooperacao": 2,
            "iniciativa_proatividade": 1, "relacionamento_interpessoal": 2, "aprendizagem": 2,
            "hierarquia_disciplina": 2, "assiduidade_pontualidade": 2}},
    }
    resultado = []
    for email in payload.destinatarios:
        email = email.strip().lower()
        para = (email, email.split("@")[0].replace(".", " ").title())
        resultado.append({
            "destinatario": email,
            "formulario": send_primeiro_envio(av45, emp, "demo", para=para, prefixo="[TESTE] 1/3 "),
            "alerta_10_dias": send_primeiro_envio(av45, emp, "demo", automatico=True, para=para, prefixo="[TESTE] 2/3 "),
            "nota_insuficiente": send_alerta_nota_insuficiente(av_ruim, emp, para=para, prefixo="[TESTE] 3/3 "),
        })
    log.info("E-mails de validação enviados por %s: %s", user.get("username"), resultado)
    return {"ok": True, "resultado": resultado}
