"""Webhook público: recebe respostas do Microsoft Forms via Power Automate.

Sem autenticação JWT — protegido por secret compartilhado via query string,
mesmo padrão de support-service/routes/webhook.py (Freshservice). Sempre
retorna {"ok": true} (nunca 4xx/5xx) para evitar retry agressivo do Power Automate.
"""
import logging
from typing import Optional

from fastapi import APIRouter, Query, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from db import get_settings, get_supabase
from routes.admin import ItemInvalido, _aplicar_itens

router = APIRouter(prefix="/api/satisfacao/webhooks", tags=["webhook"])
log = logging.getLogger(__name__)


class MsFormsItem(BaseModel):
    ordem: int
    nota: int
    comentario: Optional[str] = None


class MsFormsPayload(BaseModel):
    ano_campanha: int
    ms_forms_response_id: Optional[str] = None
    email_informado: Optional[str] = None
    empresa_informada: Optional[str] = None
    itens: list[MsFormsItem]


def _log_ms_forms(
    sb,
    *,
    ano_informado: int,
    payload_bruto: dict,
    matched: bool,
    status: str,
    campanha_id: Optional[str] = None,
    resposta_id: Optional[str] = None,
    cliente_id: Optional[str] = None,
    email_informado: Optional[str] = None,
    empresa_informada: Optional[str] = None,
    ms_forms_response_id: Optional[str] = None,
    erro_detalhe: Optional[str] = None,
) -> None:
    try:
        sb.table("sat_ms_forms_log").insert({
            "campanha_id": campanha_id,
            "resposta_id": resposta_id,
            "cliente_id": cliente_id,
            "ano_informado": ano_informado,
            "email_informado": email_informado,
            "empresa_informada": empresa_informada,
            "ms_forms_response_id": ms_forms_response_id,
            "payload_bruto": payload_bruto,
            "matched": matched,
            "status": status,
            "erro_detalhe": erro_detalhe,
        }).execute()
    except Exception as exc:
        log.error("Falha ao gravar sat_ms_forms_log: %s", exc)


@router.post("/ms-forms")
async def ms_forms_webhook(request: Request, secret: str = Query(default="")):
    s = get_settings()
    if s.ms_forms_webhook_secret and secret != s.ms_forms_webhook_secret:
        log.warning("Webhook MS Forms: secret inválido")
        return JSONResponse({"ok": True})

    try:
        raw = await request.json()
        payload = MsFormsPayload(**raw)
    except Exception as exc:
        log.error("Webhook MS Forms: payload inválido: %s", exc)
        return JSONResponse({"ok": True})

    sb = get_supabase()

    # Idempotência: já processamos essa resposta do Forms antes?
    if payload.ms_forms_response_id:
        existente = (
            sb.table("sat_ms_forms_log")
            .select("id")
            .eq("ms_forms_response_id", payload.ms_forms_response_id)
            .execute()
        )
        if existente.data:
            return JSONResponse({"ok": True})

    campanhas = sb.table("sat_campanhas").select("*").eq("ano", payload.ano_campanha).execute().data or []
    campanha = campanhas[0] if campanhas else None
    if not campanha:
        _log_ms_forms(
            sb, ano_informado=payload.ano_campanha, payload_bruto=raw, matched=False, status="erro",
            email_informado=payload.email_informado, empresa_informada=payload.empresa_informada,
            ms_forms_response_id=payload.ms_forms_response_id,
            erro_detalhe=f"Nenhuma campanha encontrada para o ano {payload.ano_campanha}",
        )
        return JSONResponse({"ok": True})

    email_norm = (payload.email_informado or "").strip().lower()
    empresa_norm = (payload.empresa_informada or "").strip().lower()

    todas_respostas = (
        sb.table("sat_respostas")
        .select("*, sat_clientes(*)")
        .eq("campanha_id", campanha["id"])
        .execute()
        .data or []
    )
    disponiveis = [r for r in todas_respostas if r["status"] in ("pendente", "enviado")]

    def _match(rows):
        if email_norm:
            achados = [r for r in rows if ((r.get("sat_clientes") or {}).get("contato_email") or "").strip().lower() == email_norm]
            if achados:
                return achados
        if empresa_norm:
            return [r for r in rows if empresa_norm in ((r.get("sat_clientes") or {}).get("empresa_nome") or "").strip().lower()]
        return []

    candidatos = _match(disponiveis)

    if not candidatos:
        # Cliente já respondeu (duplicata) ou campanha encerrada (atrasada) — log explícito, não silencioso.
        ja_processado = _match(todas_respostas)
        if ja_processado:
            r = ja_processado[0]
            _log_ms_forms(
                sb, campanha_id=campanha["id"], resposta_id=r["id"], cliente_id=r.get("cliente_id"),
                ano_informado=payload.ano_campanha, payload_bruto=raw, matched=False, status="erro",
                email_informado=payload.email_informado, empresa_informada=payload.empresa_informada,
                ms_forms_response_id=payload.ms_forms_response_id,
                erro_detalhe=f"Cliente já está com status '{r['status']}' nesta campanha (duplicata ou resposta atrasada)",
            )
        else:
            _log_ms_forms(
                sb, campanha_id=campanha["id"], ano_informado=payload.ano_campanha, payload_bruto=raw,
                matched=False, status="recebido",
                email_informado=payload.email_informado, empresa_informada=payload.empresa_informada,
                ms_forms_response_id=payload.ms_forms_response_id,
                erro_detalhe="Nenhum cliente convidado encontrado com esse e-mail/empresa",
            )
        return JSONResponse({"ok": True})

    if len(candidatos) > 1:
        _log_ms_forms(
            sb, campanha_id=campanha["id"], ano_informado=payload.ano_campanha, payload_bruto=raw,
            matched=False, status="recebido",
            email_informado=payload.email_informado, empresa_informada=payload.empresa_informada,
            ms_forms_response_id=payload.ms_forms_response_id,
            erro_detalhe=f"{len(candidatos)} clientes encontrados — ambíguo, requer conciliação manual",
        )
        return JSONResponse({"ok": True})

    resposta = candidatos[0]
    cliente = resposta.get("sat_clientes") or {}

    cp_por_ordem = {
        cp["ordem"]: cp["id"] for cp in
        sb.table("sat_campanha_perguntas").select("id, ordem").eq("campanha_id", campanha["id"]).execute().data or []
    }

    itens_resolvidos = []
    for item in payload.itens:
        cp_id = cp_por_ordem.get(item.ordem)
        if not cp_id:
            _log_ms_forms(
                sb, campanha_id=campanha["id"], resposta_id=resposta["id"], cliente_id=resposta.get("cliente_id"),
                ano_informado=payload.ano_campanha, payload_bruto=raw, matched=False, status="erro",
                email_informado=payload.email_informado, empresa_informada=payload.empresa_informada,
                ms_forms_response_id=payload.ms_forms_response_id,
                erro_detalhe=f"Ordem de pergunta inválida: {item.ordem}",
            )
            return JSONResponse({"ok": True})
        itens_resolvidos.append({"campanha_pergunta_id": cp_id, "nota": item.nota, "comentario": item.comentario})

    try:
        _aplicar_itens(sb, resposta["id"], itens_resolvidos, "ms_forms")
    except ItemInvalido as exc:
        _log_ms_forms(
            sb, campanha_id=campanha["id"], resposta_id=resposta["id"], cliente_id=resposta.get("cliente_id"),
            ano_informado=payload.ano_campanha, payload_bruto=raw, matched=False, status="erro",
            email_informado=payload.email_informado, empresa_informada=payload.empresa_informada,
            ms_forms_response_id=payload.ms_forms_response_id, erro_detalhe=str(exc),
        )
        return JSONResponse({"ok": True})

    _log_ms_forms(
        sb, campanha_id=campanha["id"], resposta_id=resposta["id"], cliente_id=resposta.get("cliente_id"),
        ano_informado=payload.ano_campanha, payload_bruto=raw, matched=True, status="conciliado",
        email_informado=payload.email_informado, empresa_informada=payload.empresa_informada,
        ms_forms_response_id=payload.ms_forms_response_id,
    )

    try:
        from services.email_service import send_confirmacao_sgi
        itens_ruins = len([i for i in itens_resolvidos if i["nota"] <= 2])
        send_confirmacao_sgi(cliente, campanha, itens_ruins)
    except Exception as exc:
        log.error("Falha ao enviar confirmação ao SGI: %s", exc)

    return JSONResponse({"ok": True})
