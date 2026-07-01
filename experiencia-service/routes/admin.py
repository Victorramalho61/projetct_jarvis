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
def sync_benner(user=Depends(_require_admin)):
    from services.benner_sync import run_sync
    try:
        stats = run_sync()
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
            q_lower in (r.get("exp_employees") or {}).get("nome", "").lower() or
            q_lower in str((r.get("exp_employees") or {}).get("matricula", "")).lower() or
            q_lower in (r.get("exp_employees") or {}).get("gestor_nome", "").lower()
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
        "colaborador": {
            "id":           emp.get("id"),
            "matricula":    emp.get("matricula"),
            "nome":         emp.get("nome"),
            "cargo":        emp.get("cargo"),
            "departamento": emp.get("departamento"),
            "empresa":      emp.get("empresa"),
            "data_admissao":emp.get("data_admissao"),
            "gestor_nome":  emp.get("gestor_nome"),
            "gestor_email": emp.get("gestor_email"),
        },
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
            q_lower in (r.get("exp_employees") or {}).get("nome", "").lower() or
            q_lower in str((r.get("exp_employees") or {}).get("matricula", "")).lower() or
            q_lower in (r.get("exp_employees") or {}).get("gestor_nome", "").lower()
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
        "colaborador": {
            "matricula":    emp.get("matricula"),
            "nome":         emp.get("nome"),
            "cargo":        emp.get("cargo"),
            "empresa":      emp.get("empresa"),
            "data_admissao":emp.get("data_admissao"),
            "gestor_nome":  emp.get("gestor_nome"),
            "gestor_email": emp.get("gestor_email"),
        },
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
    """Permite RH corrigir e-mail do gestor antes de enviar a avaliação."""
    sb = get_supabase()
    update = {"gestor_email": payload.gestor_email}
    if payload.gestor_nome:
        update["gestor_nome"] = payload.gestor_nome
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
        "Empresa", "Matrícula", "Colaborador", "Cargo", "Setor",
        "Data Admissão", "Tipo", "Data Prevista", "Status",
        "Gestor", "E-mail Gestor",
        "Respondido em", "Assinado em", "Total Envios",
        "Parecer",
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
