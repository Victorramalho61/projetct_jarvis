"""Cliente HTTP para a API do D4Sign (assinatura eletronica).

Referencia: docapi.d4sign.com.br (mais precisa que ajuda.d4sign.com.br,
que tinha nomes de endpoint errados). Testado ao vivo contra a sandbox
em 2026-08-06 (auth confirmada; fluxo completo depende de cofre+template
ainda nao criados no painel).
"""
import hashlib
import hmac
import logging

import httpx

from db import get_settings

log = logging.getLogger(__name__)


class D4SignNaoConfigurado(Exception):
    pass


class D4SignError(Exception):
    def __init__(self, status_code: int, detail: str):
        super().__init__(f"D4Sign {status_code}: {detail}")
        self.status_code = status_code
        self.detail = detail


def _check_configurado():
    s = get_settings()
    if not s.d4sign_configurado:
        raise D4SignNaoConfigurado(
            "Assinatura automatizada ainda nao configurada — falta cofre e/ou template no D4Sign."
        )


def _auth_params() -> dict:
    s = get_settings()
    return {"tokenAPI": s.d4sign_token_api, "cryptKey": s.d4sign_crypt_key}


def _request(method: str, path: str, json: dict | None = None, timeout: float = 30.0) -> dict:
    s = get_settings()
    url = f"{s.d4sign_base_url}{path}"
    try:
        resp = httpx.request(
            method, url, params=_auth_params(), json=json,
            headers={"Accept": "application/json", "Content-Type": "application/json"},
            timeout=timeout,
        )
    except httpx.HTTPError as exc:
        raise D4SignError(0, f"Falha de rede: {exc}")

    if resp.status_code >= 400:
        try:
            detail = resp.json()
        except Exception:
            detail = resp.text
        raise D4SignError(resp.status_code, str(detail)[:500])

    if not resp.content:
        return {}
    try:
        return resp.json()
    except Exception:
        return {"raw": resp.text}


# ── Cofre / templates ─────────────────────────────────────────────────────

def listar_templates() -> list[dict]:
    _check_configurado()
    resp = _request("POST", "/templates")
    return resp if isinstance(resp, list) else resp.get("templates", [])


# ── Documento a partir de template ───────────────────────────────────────

def criar_documento_template(
    template_uuid: str, name_document: str, tokens_gerais: dict[str, str]
) -> str:
    """Gera o documento a partir do template Word, preenchendo as variaveis.
    Retorna o uuid do documento criado."""
    _check_configurado()
    s = get_settings()
    payload = {
        "name_document": name_document,
        template_uuid: {"tokens_gerais": tokens_gerais},
    }
    resp = _request("POST", f"/documents/{s.d4sign_safe_uuid}/makedocumentbytemplateword", json=payload)
    document_uuid = resp.get("uuid") or resp.get("uuidDoc")
    if not document_uuid:
        raise D4SignError(500, f"Resposta sem uuid de documento: {resp}")
    return document_uuid


# ── Signatários ───────────────────────────────────────────────────────────

def cadastrar_signatarios(document_uuid: str, signatarios: list[dict]) -> dict:
    """signatarios: lista de {email, tem_cpf: bool}. Ordem = ordem de assinatura."""
    _check_configurado()
    signers = [
        {"email": s["email"], "act": "1", "foreign": "0" if s.get("tem_cpf", True) else "1"}
        for s in signatarios
    ]
    return _request("POST", f"/documents/{document_uuid}/createlist", json={"signers": signers})


def enviar_para_assinatura(document_uuid: str, sequencial: bool = True, mensagem: str | None = None) -> dict:
    _check_configurado()
    payload = {"skip_email": "0", "workflow": "1" if sequencial else "0"}
    if mensagem:
        payload["message"] = mensagem
    return _request("POST", f"/documents/{document_uuid}/sendtosigner", json=payload)


# ── Cancelamento ──────────────────────────────────────────────────────────

def cancelar_documento(document_uuid: str, comentario: str) -> dict:
    _check_configurado()
    return _request("POST", f"/documents/{document_uuid}/cancel", json={"comment": comentario})


# ── Download ──────────────────────────────────────────────────────────────

def baixar_documento(document_uuid: str) -> dict:
    """Retorna o payload do D4Sign com a URL/base64 do PDF assinado."""
    _check_configurado()
    return _request("POST", f"/documents/{document_uuid}/download")


# ── Webhook (setup unico por cofre) ───────────────────────────────────────

def registrar_webhook_cofre(webhook_url: str) -> dict:
    _check_configurado()
    s = get_settings()
    return _request(
        "POST", "/webhooks/v2/",
        json={"type": "cofre", "uuid": s.d4sign_safe_uuid, "url": webhook_url},
    )


# ── Validação HMAC do webhook recebido ────────────────────────────────────

TYPE_POST_FINALIZADO = "1"
TYPE_POST_EMAIL_FALHOU = "2"
TYPE_POST_CANCELADO = "3"
TYPE_POST_ASSINADO_POR_UM = "4"


def validar_hmac(document_uuid: str, content_hmac_header: str) -> bool:
    s = get_settings()
    if not s.d4sign_secret_key_hmac or not content_hmac_header:
        return False
    recebido = content_hmac_header.split("=", 1)[-1].strip()
    calculado = hmac.new(
        s.d4sign_secret_key_hmac.encode(), document_uuid.encode(), hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(calculado, recebido)
