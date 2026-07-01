"""Rotas públicas: formulário via token (sem autenticação JWT)."""
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from db import get_supabase
from services.formulario import get_formulario, validate_respostas

router = APIRouter(prefix="/api/experiencia")
log = logging.getLogger(__name__)


@router.get("/formulario/{token}")
def get_formulario_by_token(token: str):
    """Carrega dados do colaborador + estrutura do formulário para o gestor preencher."""
    sb = get_supabase()

    av = (
        sb.table("exp_avaliacoes")
        .select("*, exp_employees(*)")
        .eq("token", token)
        .single()
        .execute()
    )
    if not av.data:
        raise HTTPException(status_code=404, detail="Link de avaliação não encontrado")

    avaliacao = av.data
    emp = avaliacao.get("exp_employees") or {}

    # Verifica expiração
    expires = avaliacao.get("token_expires_at")
    if expires:
        dt = datetime.fromisoformat(expires.replace("Z", "+00:00"))
        if datetime.now(timezone.utc) > dt:
            raise HTTPException(status_code=410, detail="Link de avaliação expirado")

    # Verifica se já foi respondido
    if avaliacao.get("status") == "respondido":
        raise HTTPException(status_code=409, detail="Avaliação já realizada")

    tipo = avaliacao.get("tipo", "45_dias")
    formulario = get_formulario(tipo)

    return {
        "avaliacao_id":   avaliacao["id"],
        "tipo":           tipo,
        "data_prevista":  avaliacao.get("data_prevista"),
        "colaborador": {
            "nome":          emp.get("nome"),
            "cargo":         emp.get("cargo"),
            "empresa":       emp.get("empresa"),
            "departamento":  emp.get("departamento"),
            "data_admissao": emp.get("data_admissao"),
        },
        "gestor_nome": emp.get("gestor_nome"),
        "formulario":  formulario,
    }


class SubmitPayload(BaseModel):
    respostas: dict
    gestor_concordou: bool
    timestamp_assinatura: str  # ISO8601 enviado pelo frontend


@router.post("/formulario/{token}")
def submit_formulario(token: str, payload: SubmitPayload, request: Request):
    """Salva respostas + assinatura digital do gestor."""
    sb = get_supabase()

    av = (
        sb.table("exp_avaliacoes")
        .select("*, exp_employees(*)")
        .eq("token", token)
        .single()
        .execute()
    )
    if not av.data:
        raise HTTPException(status_code=404, detail="Link de avaliação não encontrado")

    avaliacao = av.data
    emp = avaliacao.get("exp_employees") or {}

    expires = avaliacao.get("token_expires_at")
    if expires:
        dt = datetime.fromisoformat(expires.replace("Z", "+00:00"))
        if datetime.now(timezone.utc) > dt:
            raise HTTPException(status_code=410, detail="Link de avaliação expirado")

    if avaliacao.get("status") == "respondido":
        raise HTTPException(status_code=409, detail="Avaliação já realizada")

    if not payload.gestor_concordou:
        raise HTTPException(status_code=422, detail="É necessário concordar com a declaração para assinar")

    tipo = avaliacao.get("tipo", "45_dias")
    erros = validate_respostas(payload.respostas, tipo)
    if erros:
        raise HTTPException(status_code=422, detail={"erros": erros})

    ip = request.client.host if request.client else "desconhecido"

    sb.table("exp_avaliacoes").update({
        "status":               "respondido",
        "respostas":            payload.respostas,
        "gestor_concordou":     True,
        "gestor_assinatura_at": payload.timestamp_assinatura,
        "gestor_ip":            ip,
        "updated_at":           "now()",
    }).eq("id", avaliacao["id"]).execute()

    # E-mail de confirmação para o RH
    try:
        from services.email_service import send_confirmacao_rh, log_email
        parecer = payload.respostas.get("parecer", "—")
        ok = send_confirmacao_rh(avaliacao, emp, parecer, payload.timestamp_assinatura)
        log_email(sb, avaliacao["id"], "rh@voetur.com.br", "confirmacao_rh", ok)
    except Exception as exc:
        log.error("Falha ao enviar confirmação RH: %s", exc)

    return {"ok": True, "message": "Avaliação registrada com sucesso"}
