"""Webhook público do D4Sign — recebe eventos de assinatura.

Sem autenticação JWT (D4Sign não manda Bearer token nosso) — protegido
pelo header Content-Hmac (ver services/d4sign_client.validar_hmac).
Mesmo padrão de rota pública já usado em support-service/routes/webhook.py
pro Freshservice.
"""
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Request

from db import get_supabase
from services import d4sign_client
from services.d4sign_client import (
    TYPE_POST_ASSINADO_POR_UM,
    TYPE_POST_CANCELADO,
    TYPE_POST_EMAIL_FALHOU,
    TYPE_POST_FINALIZADO,
)

router = APIRouter(prefix="/api/rh/webhooks")
log = logging.getLogger(__name__)


async def _parse_payload(request: Request) -> dict:
    content_type = request.headers.get("content-type", "")
    if "application/json" in content_type:
        return await request.json()
    form = await request.form()
    return dict(form)


def _extrair_email_signatario(payload: dict) -> str | None:
    for chave in ("email", "signer_email", "email_signatario"):
        if payload.get(chave):
            return payload[chave]
    signers = payload.get("signers") or payload.get("signatarios")
    if isinstance(signers, list) and signers:
        return signers[0].get("email")
    return None


@router.post("/d4sign")
async def webhook_d4sign(request: Request):
    payload = await _parse_payload(request)
    document_uuid = payload.get("uuid") or payload.get("uuid_documento") or payload.get("document_uuid")
    type_post = str(payload.get("type_post", ""))

    if not document_uuid:
        raise HTTPException(status_code=400, detail="Payload sem uuid de documento")

    content_hmac = request.headers.get("content-hmac", "")
    if not d4sign_client.validar_hmac(document_uuid, content_hmac):
        log.warning("Webhook D4Sign com HMAC inválido para documento %s", document_uuid)
        raise HTTPException(status_code=401, detail="HMAC inválido")

    sb = get_supabase()
    resp = sb.table("rh_assinaturas").select("*").eq("d4sign_document_uuid", document_uuid).execute()
    if not resp.data:
        log.info("Webhook D4Sign pra documento não rastreado: %s", document_uuid)
        return {"ok": True}
    assinatura = resp.data[0]

    agora = datetime.now(timezone.utc).isoformat()

    if type_post == TYPE_POST_ASSINADO_POR_UM:
        email_assinante = _extrair_email_signatario(payload)
        signatarios = list(assinatura.get("signatarios") or [])
        for sg in signatarios:
            if email_assinante and sg.get("email") == email_assinante and sg.get("status") == "pendente":
                sg["status"] = "assinado"
                sg["assinado_em"] = agora
                break
        else:
            for sg in signatarios:
                if sg.get("status") == "pendente":
                    sg["status"] = "assinado"
                    sg["assinado_em"] = agora
                    break
        novo_status = "CONCLUIDO" if all(sg.get("status") == "assinado" for sg in signatarios) else "PARCIAL"
        sb.table("rh_assinaturas").update({
            "signatarios": signatarios, "status": novo_status, "updated_at": agora,
        }).eq("id", assinatura["id"]).execute()

    elif type_post == TYPE_POST_FINALIZADO:
        try:
            resultado = d4sign_client.baixar_documento(document_uuid)
            pdf_base64 = resultado.get("base64_pdf") or resultado.get("base64") or resultado.get("arquivo")
        except Exception as exc:
            log.error("Falha ao baixar documento assinado %s: %s", document_uuid, exc)
            pdf_base64 = None

        sb.table("rh_assinaturas").update({
            "status": "CONCLUIDO",
            "documento_assinado": pdf_base64,
            "updated_at": agora,
        }).eq("id", assinatura["id"]).execute()

        if assinatura.get("tipo_aditivo") == "CANCELAMENTO":
            vaga = sb.table("rh_vagas").select("id").eq("id", assinatura["vaga_id"]).execute()
            if vaga.data:
                cancelado = sb.table("rh_status_vaga").select("id").eq("nome", "CANCELADO").single().execute()
                if cancelado.data:
                    sb.table("rh_vagas").update({"status_id": cancelado.data["id"]}).eq("id", assinatura["vaga_id"]).execute()

    elif type_post == TYPE_POST_CANCELADO:
        log.info("D4Sign confirmou cancelamento do documento %s", document_uuid)

    elif type_post == TYPE_POST_EMAIL_FALHOU:
        log.warning("Falha de entrega de e-mail no documento %s: %s", document_uuid, payload.get("message"))

    return {"ok": True}
