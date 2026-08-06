"""Fase 2 do módulo de RH — assinatura eletrônica via D4Sign (submenu
"Assinatura Automatizada", separado do fluxo de impressão)."""
import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from auth import require_role
from db import get_settings, get_supabase
from services import d4sign_client
from services.d4sign_client import D4SignError, D4SignNaoConfigurado

router = APIRouter(prefix="/api/rh/vagas")
log = logging.getLogger(__name__)

_ROLES = ("admin", "rh")
_PAPEIS = ("solicitante", "rh", "depto_pessoal", "diretoria")


def _require_rh(user=Depends(require_role(*_ROLES))):
    return user


class Signatario(BaseModel):
    papel: str = Field(pattern="^(solicitante|rh|depto_pessoal|diretoria)$")
    nome: str
    email: str
    cargo: str


class EnviarPayload(BaseModel):
    signatarios: list[Signatario]


class AditivoPayload(BaseModel):
    tipo: str = Field(pattern="^(CANCELAMENTO|ALTERACAO)$")
    justificativa: str
    signatarios: list[Signatario]


def _validar_4_signatarios(signatarios: list[Signatario]):
    papeis = {s.papel for s in signatarios}
    if papeis != set(_PAPEIS):
        raise HTTPException(status_code=400, detail=f"Envie os 4 papéis: {', '.join(_PAPEIS)}")


def _buscar_vaga(sb, vaga_id: str) -> dict:
    from routes.vagas import _SELECT, _serialize

    resp = sb.table("rh_vagas").select(_SELECT).eq("id", vaga_id).execute()
    if not resp.data:
        raise HTTPException(status_code=404, detail="Vaga não encontrada")
    return _serialize(resp.data[0])


def _assinatura_atual(sb, vaga_id: str) -> Optional[dict]:
    """Última linha 'principal' (não-aditivo) de rh_assinaturas para a vaga."""
    resp = (
        sb.table("rh_assinaturas")
        .select("*")
        .eq("vaga_id", vaga_id)
        .is_("aditivo_de_id", "null")
        .order("created_at", desc=True)
        .limit(1)
        .execute()
    )
    return resp.data[0] if resp.data else None


def _ultimo_aditivo_ou_original(sb, vaga_id: str) -> Optional[dict]:
    """Registro 'ativo' mais recente (original ou último aditivo) — usado
    pra decidir se dá pra criar um novo aditivo (precisa estar CONCLUIDO)."""
    resp = (
        sb.table("rh_assinaturas")
        .select("*")
        .eq("vaga_id", vaga_id)
        .order("created_at", desc=True)
        .limit(1)
        .execute()
    )
    return resp.data[0] if resp.data else None


def _build_tokens_gerais(vaga: dict, signatarios: list[Signatario], extra: Optional[dict] = None) -> dict:
    tokens = {
        "solicitante": vaga.get("requisitante") or "",
        "data_recebimento": vaga.get("data_recebimento") or "",
        "numero_requisicao": vaga.get("numero_requisicao") or "",
        "centro_custo": vaga.get("centro_custo") or "",
        "empresa": vaga.get("empresa") or "",
        "hierarquia": vaga.get("hierarquia") or "",
        "alocacao_real": vaga.get("alocacao") or "",
        "cargo": vaga.get("cargo") or "",
        "carga_horaria": vaga.get("carga_horaria") or "",
        "horario_trabalho": vaga.get("horario_trabalho") or "",
        "modalidade": vaga.get("modalidade") or "",
        "salario": str(vaga.get("salario") or ""),
        "tipo_vaga": vaga.get("tipo_vaga") or "",
        "justificativa": vaga.get("justificativa") or "",
        "candidato": vaga.get("candidato") or "",
        "data_admissao": vaga.get("data_admissao") or "",
    }
    for s in signatarios:
        tokens[f"nome_{s.papel}"] = s.nome
        tokens[f"cargo_{s.papel}"] = s.cargo
    if extra:
        tokens.update(extra)
    return tokens


def _signatarios_para_registro(signatarios: list[Signatario]) -> list[dict]:
    return [
        {"papel": s.papel, "nome": s.nome, "email": s.email, "cargo": s.cargo, "status": "pendente"}
        for s in signatarios
    ]


def _serialize_assinatura(row: dict) -> dict:
    return {
        "id": row["id"],
        "vaga_id": row["vaga_id"],
        "status": row["status"],
        "signatarios": row.get("signatarios") or [],
        "aditivo_de_id": row.get("aditivo_de_id"),
        "tipo_aditivo": row.get("tipo_aditivo"),
        "justificativa_aditivo": row.get("justificativa_aditivo"),
        "documento_assinado": bool(row.get("documento_assinado")),
        "created_at": row.get("created_at"),
        "updated_at": row.get("updated_at"),
    }


# ── Consulta de status ────────────────────────────────────────────────────

@router.get("/{vaga_id}/assinatura")
def status_assinatura(vaga_id: str, user=Depends(_require_rh)):
    sb = get_supabase()
    s = get_settings()
    atual = _assinatura_atual(sb, vaga_id)

    aditivos = (
        sb.table("rh_assinaturas")
        .select("*")
        .eq("vaga_id", vaga_id)
        .not_.is_("aditivo_de_id", "null")
        .order("created_at")
        .execute()
    ).data or []

    return {
        "configurado": s.d4sign_configurado,
        "atual": _serialize_assinatura(atual) if atual else {"status": "PRE_ENVIO", "signatarios": []},
        "aditivos": [_serialize_assinatura(a) for a in aditivos],
    }


# ── Enviar (envio inicial ou reenvio após "alterar assinadores") ─────────

@router.post("/{vaga_id}/assinatura/enviar")
def enviar_assinatura(vaga_id: str, payload: EnviarPayload, user=Depends(_require_rh)):
    _validar_4_signatarios(payload.signatarios)
    sb = get_supabase()
    s = get_settings()

    if not s.d4sign_configurado:
        raise HTTPException(status_code=503, detail="Assinatura automatizada ainda não configurada")

    vaga = _buscar_vaga(sb, vaga_id)
    atual = _assinatura_atual(sb, vaga_id)
    if atual and atual["status"] == "CONCLUIDO":
        raise HTTPException(status_code=409, detail="Esta vaga já tem um processo de assinatura concluído — use o aditivo")
    if atual and atual["status"] in ("ENVIADO", "PARCIAL"):
        raise HTTPException(status_code=409, detail="Já existe um envio em andamento — use 'Alterar assinadores' ou 'Cancelar envio'")

    tokens = _build_tokens_gerais(vaga, payload.signatarios)
    try:
        document_uuid = d4sign_client.criar_documento_template(
            s.d4sign_template_uuid, f"Requisicao_{vaga.get('numero_requisicao', vaga_id)}", tokens
        )
        # ordem = ordem de assinatura sequencial: solicitante -> rh -> depto_pessoal -> diretoria
        ordem = {p: i for i, p in enumerate(_PAPEIS)}
        signatarios_ordenados = sorted(payload.signatarios, key=lambda s: ordem[s.papel])
        d4sign_client.cadastrar_signatarios(
            document_uuid, [{"email": sg.email, "tem_cpf": True} for sg in signatarios_ordenados]
        )
        d4sign_client.enviar_para_assinatura(document_uuid, sequencial=True)
    except D4SignError as exc:
        raise HTTPException(status_code=502, detail=f"Erro no D4Sign: {exc.detail}")

    row = {
        "vaga_id": vaga_id,
        "d4sign_document_uuid": document_uuid,
        "status": "ENVIADO",
        "signatarios": _signatarios_para_registro(payload.signatarios),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    if atual and atual["status"] in ("PRE_ENVIO", "EM_ALTERACAO"):
        sb.table("rh_assinaturas").update(row).eq("id", atual["id"]).execute()
        assinatura_id = atual["id"]
    else:
        row["created_by"] = user.get("id")
        resp = sb.table("rh_assinaturas").insert(row).execute()
        assinatura_id = resp.data[0]["id"]

    return {"ok": True, "assinatura_id": assinatura_id, "document_uuid": document_uuid}


# ── Alterar assinadores ────────────────────────────────────────────────────

@router.post("/{vaga_id}/assinatura/alterar")
def alterar_assinadores(vaga_id: str, user=Depends(_require_rh)):
    sb = get_supabase()
    atual = _assinatura_atual(sb, vaga_id)
    if not atual or atual["status"] not in ("ENVIADO", "PARCIAL"):
        raise HTTPException(status_code=409, detail="Só é possível alterar assinadores de um envio em andamento")

    try:
        d4sign_client.cancelar_documento(atual["d4sign_document_uuid"], "Alteração de signatários solicitada pelo RH")
    except D4SignError as exc:
        raise HTTPException(status_code=502, detail=f"Erro ao cancelar no D4Sign: {exc.detail}")

    historico = list(atual.get("historico_documentos") or [])
    historico.append({
        "document_uuid": atual["d4sign_document_uuid"],
        "motivo": "alterar_assinadores",
        "cancelado_em": datetime.now(timezone.utc).isoformat(),
    })
    sb.table("rh_assinaturas").update({
        "status": "EM_ALTERACAO",
        "d4sign_document_uuid": None,
        "historico_documentos": historico,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }).eq("id", atual["id"]).execute()

    return {"ok": True, "signatarios_anteriores": atual.get("signatarios") or []}


# ── Cancelar envio ─────────────────────────────────────────────────────────

@router.post("/{vaga_id}/assinatura/cancelar")
def cancelar_envio(vaga_id: str, user=Depends(_require_rh)):
    sb = get_supabase()
    atual = _assinatura_atual(sb, vaga_id)
    if not atual:
        raise HTTPException(status_code=409, detail="Não há envio ativo pra cancelar")
    if atual["status"] == "CONCLUIDO":
        raise HTTPException(status_code=403, detail="Documento finalizado é imutável no D4Sign — não pode ser cancelado. Use o aditivo.")
    if atual["status"] == "PRE_ENVIO":
        raise HTTPException(status_code=409, detail="Não há envio ativo pra cancelar")

    historico = list(atual.get("historico_documentos") or [])
    if atual.get("d4sign_document_uuid"):
        try:
            d4sign_client.cancelar_documento(atual["d4sign_document_uuid"], "Envio cancelado pelo RH")
        except D4SignError as exc:
            raise HTTPException(status_code=502, detail=f"Erro ao cancelar no D4Sign: {exc.detail}")
        historico.append({
            "document_uuid": atual["d4sign_document_uuid"],
            "motivo": "cancelar_envio",
            "cancelado_em": datetime.now(timezone.utc).isoformat(),
        })

    sb.table("rh_assinaturas").update({
        "status": "PRE_ENVIO",
        "d4sign_document_uuid": None,
        "signatarios": [],
        "historico_documentos": historico,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }).eq("id", atual["id"]).execute()

    return {"ok": True}


# ── Aditivo (cancelamento/alteração pós-conclusão) ────────────────────────

_STATUS_ADITIVO = {"CANCELAMENTO": "CANCELADO"}


@router.post("/{vaga_id}/assinatura/aditivo")
def criar_aditivo(vaga_id: str, payload: AditivoPayload, user=Depends(_require_rh)):
    _validar_4_signatarios(payload.signatarios)
    sb = get_supabase()
    s = get_settings()

    if not s.d4sign_template_aditivo_uuid:
        raise HTTPException(status_code=503, detail="Template de aditivo ainda não configurado")

    referencia = _ultimo_aditivo_ou_original(sb, vaga_id)
    if not referencia or referencia["status"] != "CONCLUIDO":
        raise HTTPException(status_code=409, detail="Só é possível criar aditivo de um processo já concluído")

    vaga = _buscar_vaga(sb, vaga_id)
    tokens = _build_tokens_gerais(vaga, payload.signatarios, extra={
        "tipo_aditivo": payload.tipo,
        "justificativa_aditivo": payload.justificativa,
    })

    try:
        document_uuid = d4sign_client.criar_documento_template(
            s.d4sign_template_aditivo_uuid,
            f"Aditivo_{vaga.get('numero_requisicao', vaga_id)}",
            tokens,
        )
        ordem = {p: i for i, p in enumerate(_PAPEIS)}
        signatarios_ordenados = sorted(payload.signatarios, key=lambda s: ordem[s.papel])
        d4sign_client.cadastrar_signatarios(
            document_uuid, [{"email": sg.email, "tem_cpf": True} for sg in signatarios_ordenados]
        )
        d4sign_client.enviar_para_assinatura(document_uuid, sequencial=True)
    except D4SignError as exc:
        raise HTTPException(status_code=502, detail=f"Erro no D4Sign: {exc.detail}")

    resp = sb.table("rh_assinaturas").insert({
        "vaga_id": vaga_id,
        "d4sign_document_uuid": document_uuid,
        "status": "ENVIADO",
        "signatarios": _signatarios_para_registro(payload.signatarios),
        "aditivo_de_id": referencia["id"],
        "tipo_aditivo": payload.tipo,
        "justificativa_aditivo": payload.justificativa,
        "created_by": user.get("id"),
    }).execute()

    return {"ok": True, "assinatura_id": resp.data[0]["id"], "document_uuid": document_uuid}
