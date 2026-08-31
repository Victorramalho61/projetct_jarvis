"""Rotas públicas: formulário de pesquisa via token (sem autenticação JWT)."""
import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from db import get_supabase

router = APIRouter(prefix="/api/satisfacao")
log = logging.getLogger(__name__)


def _carregar_resposta(token: str):
    sb = get_supabase()
    r = (
        sb.table("sat_respostas")
        .select("*, sat_clientes(*), sat_campanhas(*)")
        .eq("token", token)
        .single()
        .execute()
    )
    if not r.data:
        raise HTTPException(status_code=404, detail="Link da pesquisa não encontrado")

    resposta = r.data
    expires = resposta.get("token_expires_at")
    if expires:
        dt = datetime.fromisoformat(expires.replace("Z", "+00:00"))
        if datetime.now(timezone.utc) > dt:
            raise HTTPException(status_code=410, detail="Link da pesquisa expirado")

    if resposta.get("status") == "respondido":
        raise HTTPException(status_code=409, detail="Pesquisa já foi respondida")

    return sb, resposta


@router.get("/formulario/{token}")
def get_formulario_by_token(token: str):
    sb, resposta = _carregar_resposta(token)
    campanha_id = resposta["campanha_id"]
    cliente = resposta.get("sat_clientes") or {}
    campanha = resposta.get("sat_campanhas") or {}

    perguntas = (
        sb.table("sat_campanha_perguntas")
        .select("id, ordem, texto_snapshot")
        .eq("campanha_id", campanha_id)
        .order("ordem")
        .execute()
        .data or []
    )

    return {
        "resposta_id": resposta["id"],
        "campanha_titulo": campanha.get("titulo"),
        "cliente": {
            "empresa_nome": cliente.get("empresa_nome"),
            "contato_nome": cliente.get("contato_nome"),
        },
        "perguntas": [
            {"campanha_pergunta_id": p["id"], "ordem": p["ordem"], "texto": p["texto_snapshot"]}
            for p in perguntas
        ],
    }


class RespostaItemPayload(BaseModel):
    campanha_pergunta_id: str
    nota: int
    comentario: Optional[str] = None


class SubmitPayload(BaseModel):
    itens: list[RespostaItemPayload]


@router.post("/formulario/{token}")
def submit_formulario(token: str, payload: SubmitPayload, request: Request):
    sb, resposta = _carregar_resposta(token)
    campanha_id = resposta["campanha_id"]

    perguntas_validas = {
        p["id"] for p in
        sb.table("sat_campanha_perguntas").select("id").eq("campanha_id", campanha_id).execute().data or []
    }
    if not payload.itens:
        raise HTTPException(status_code=422, detail="É necessário responder ao menos uma pergunta")

    itens_ruins = 0
    for item in payload.itens:
        if item.campanha_pergunta_id not in perguntas_validas:
            raise HTTPException(status_code=422, detail="Pergunta inválida para esta campanha")
        if not (1 <= item.nota <= 5):
            raise HTTPException(status_code=422, detail="Nota deve estar entre 1 e 5")
        triagem_status = "pendente" if item.nota <= 2 else "nao_aplicavel"
        if item.nota <= 2:
            itens_ruins += 1
        sb.table("sat_respostas_itens").insert({
            "resposta_id": resposta["id"],
            "campanha_pergunta_id": item.campanha_pergunta_id,
            "nota": item.nota,
            "comentario": item.comentario,
            "triagem_status": triagem_status,
        }).execute()

    ip = request.client.host if request.client else "desconhecido"
    sb.table("sat_respostas").update({
        "status": "respondido",
        "canal_resposta": "formulario_link",
        "respondido_at": datetime.now(timezone.utc).isoformat(),
        "respondente_ip": ip,
        "updated_at": "now()",
    }).eq("id", resposta["id"]).execute()

    try:
        from services.email_service import send_confirmacao_sgi
        cliente = resposta.get("sat_clientes") or {}
        campanha = resposta.get("sat_campanhas") or {}
        send_confirmacao_sgi(cliente, campanha, itens_ruins)
    except Exception as exc:
        log.error("Falha ao enviar confirmação ao SGI: %s", exc)

    return {"ok": True, "message": "Obrigado por responder. Sua opinião é muito importante para nós."}
