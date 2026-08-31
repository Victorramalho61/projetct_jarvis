"""Rotas de cadastro: clientes, perguntas do template e pontos de avaliação (causa-raiz)."""
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from auth import require_role
from db import get_supabase

router = APIRouter(prefix="/api/satisfacao/cadastro")
log = logging.getLogger(__name__)

_ROLES = ("admin", "sgi")


def _require_acesso(user=Depends(require_role(*_ROLES))):
    return user


# ── Clientes ──────────────────────────────────────────────────────────────────

class ClientePayload(BaseModel):
    empresa_nome: str
    contato_nome: str
    contato_cargo: Optional[str] = None
    contato_email: str
    contato_telefone: Optional[str] = None
    observacoes: Optional[str] = None


class ClienteUpdatePayload(BaseModel):
    empresa_nome: Optional[str] = None
    contato_nome: Optional[str] = None
    contato_cargo: Optional[str] = None
    contato_email: Optional[str] = None
    contato_telefone: Optional[str] = None
    observacoes: Optional[str] = None
    ativo: Optional[bool] = None


@router.get("/clientes")
def list_clientes(
    ativo: Optional[bool] = Query(None),
    q: Optional[str] = Query(None),
    user=Depends(_require_acesso),
):
    sb = get_supabase()
    query = sb.table("sat_clientes").select("*").order("empresa_nome")
    if ativo is not None:
        query = query.eq("ativo", ativo)
    resp = query.execute()
    rows = resp.data or []
    if q:
        q_lower = q.lower()
        rows = [
            r for r in rows
            if q_lower in (r.get("empresa_nome") or "").lower()
            or q_lower in (r.get("contato_nome") or "").lower()
            or q_lower in (r.get("contato_email") or "").lower()
        ]
    return rows


@router.post("/clientes")
def create_cliente(payload: ClientePayload, user=Depends(_require_acesso)):
    sb = get_supabase()
    resp = sb.table("sat_clientes").insert(payload.model_dump()).execute()
    return resp.data[0]


@router.patch("/clientes/{cliente_id}")
def update_cliente(cliente_id: str, payload: ClienteUpdatePayload, user=Depends(_require_acesso)):
    sb = get_supabase()
    update = {k: v for k, v in payload.model_dump().items() if v is not None}
    update["updated_at"] = "now()"
    resp = sb.table("sat_clientes").update(update).eq("id", cliente_id).execute()
    if not resp.data:
        raise HTTPException(status_code=404, detail="Cliente não encontrado")
    return resp.data[0]


@router.delete("/clientes/{cliente_id}")
def delete_cliente(cliente_id: str, user=Depends(_require_acesso)):
    """Soft delete — cliente pode estar referenciado em respostas de campanhas passadas."""
    sb = get_supabase()
    resp = sb.table("sat_clientes").update({"ativo": False, "updated_at": "now()"}).eq("id", cliente_id).execute()
    if not resp.data:
        raise HTTPException(status_code=404, detail="Cliente não encontrado")
    return {"ok": True}


# ── Perguntas ─────────────────────────────────────────────────────────────────

class PerguntaPayload(BaseModel):
    texto: str
    categoria: Optional[str] = None
    ordem: Optional[int] = None


class PerguntaUpdatePayload(BaseModel):
    texto: Optional[str] = None
    categoria: Optional[str] = None
    ordem: Optional[int] = None
    ativa: Optional[bool] = None


@router.get("/perguntas")
def list_perguntas(user=Depends(_require_acesso)):
    sb = get_supabase()
    resp = sb.table("sat_perguntas").select("*").order("ordem").execute()
    return resp.data or []


@router.post("/perguntas")
def create_pergunta(payload: PerguntaPayload, user=Depends(_require_acesso)):
    sb = get_supabase()
    ordem = payload.ordem
    if ordem is None:
        existentes = sb.table("sat_perguntas").select("ordem").order("ordem", desc=True).limit(1).execute()
        ordem = (existentes.data[0]["ordem"] + 1) if existentes.data else 1
    resp = sb.table("sat_perguntas").insert({
        "texto": payload.texto,
        "categoria": payload.categoria,
        "ordem": ordem,
    }).execute()
    return resp.data[0]


def _pergunta_em_campanha_ativa(sb, pergunta_id: str) -> bool:
    resp = (
        sb.table("sat_campanha_perguntas")
        .select("id, sat_campanhas(status)")
        .eq("pergunta_id", pergunta_id)
        .execute()
    )
    for row in (resp.data or []):
        if (row.get("sat_campanhas") or {}).get("status") in ("em_andamento", "postergada"):
            return True
    return False


@router.patch("/perguntas/{pergunta_id}")
def update_pergunta(pergunta_id: str, payload: PerguntaUpdatePayload, user=Depends(_require_acesso)):
    sb = get_supabase()
    update = {k: v for k, v in payload.model_dump().items() if v is not None}
    if "texto" in update and _pergunta_em_campanha_ativa(sb, pergunta_id):
        raise HTTPException(status_code=409, detail="Pergunta em uso por campanha em andamento — não é possível editar o texto")
    update["updated_at"] = "now()"
    resp = sb.table("sat_perguntas").update(update).eq("id", pergunta_id).execute()
    if not resp.data:
        raise HTTPException(status_code=404, detail="Pergunta não encontrada")
    return resp.data[0]


@router.delete("/perguntas/{pergunta_id}")
def delete_pergunta(pergunta_id: str, user=Depends(_require_acesso)):
    sb = get_supabase()
    if _pergunta_em_campanha_ativa(sb, pergunta_id):
        raise HTTPException(status_code=409, detail="Pergunta em uso por campanha em andamento — não é possível desativar")
    resp = sb.table("sat_perguntas").update({"ativa": False, "updated_at": "now()"}).eq("id", pergunta_id).execute()
    if not resp.data:
        raise HTTPException(status_code=404, detail="Pergunta não encontrada")
    return {"ok": True}


# ── Pontos de avaliação (taxonomia de causa-raiz) ────────────────────────────

class PontoAvaliacaoPayload(BaseModel):
    titulo: str
    descricao: str
    ordem: Optional[int] = None


class PontoAvaliacaoUpdatePayload(BaseModel):
    titulo: Optional[str] = None
    descricao: Optional[str] = None
    ordem: Optional[int] = None
    ativo: Optional[bool] = None


@router.get("/perguntas/{pergunta_id}/pontos-avaliacao")
def list_pontos_avaliacao(pergunta_id: str, user=Depends(_require_acesso)):
    sb = get_supabase()
    resp = (
        sb.table("sat_pontos_avaliacao")
        .select("*")
        .eq("pergunta_id", pergunta_id)
        .order("ordem")
        .execute()
    )
    return resp.data or []


@router.post("/perguntas/{pergunta_id}/pontos-avaliacao")
def create_ponto_avaliacao(pergunta_id: str, payload: PontoAvaliacaoPayload, user=Depends(_require_acesso)):
    sb = get_supabase()
    ordem = payload.ordem
    if ordem is None:
        existentes = (
            sb.table("sat_pontos_avaliacao")
            .select("ordem")
            .eq("pergunta_id", pergunta_id)
            .order("ordem", desc=True)
            .limit(1)
            .execute()
        )
        ordem = (existentes.data[0]["ordem"] + 1) if existentes.data else 1
    resp = sb.table("sat_pontos_avaliacao").insert({
        "pergunta_id": pergunta_id,
        "titulo": payload.titulo,
        "descricao": payload.descricao,
        "ordem": ordem,
    }).execute()
    return resp.data[0]


@router.patch("/pontos-avaliacao/{ponto_id}")
def update_ponto_avaliacao(ponto_id: str, payload: PontoAvaliacaoUpdatePayload, user=Depends(_require_acesso)):
    sb = get_supabase()
    update = {k: v for k, v in payload.model_dump().items() if v is not None}
    resp = sb.table("sat_pontos_avaliacao").update(update).eq("id", ponto_id).execute()
    if not resp.data:
        raise HTTPException(status_code=404, detail="Ponto de avaliação não encontrado")
    return resp.data[0]


@router.delete("/pontos-avaliacao/{ponto_id}")
def delete_ponto_avaliacao(ponto_id: str, user=Depends(_require_acesso)):
    sb = get_supabase()
    resp = sb.table("sat_pontos_avaliacao").update({"ativo": False}).eq("id", ponto_id).execute()
    if not resp.data:
        raise HTTPException(status_code=404, detail="Ponto de avaliação não encontrado")
    return {"ok": True}
