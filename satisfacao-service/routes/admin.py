"""Rotas admin/SGI — campanhas, respostas, triagem, planos de ação, dashboard."""
import logging
from datetime import date, datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from auth import require_role
from db import get_supabase
from services.business_days import add_business_days

router = APIRouter(prefix="/api/satisfacao/admin")
log = logging.getLogger(__name__)

_ROLES = ("admin", "sgi")


class ItemInvalido(Exception):
    pass


def _require_acesso(user=Depends(require_role(*_ROLES))):
    return user


def _aplicar_itens(
    sb,
    resposta_id: str,
    itens: list[dict],
    canal_resposta: str,
    lancado_por: Optional[str] = None,
) -> None:
    """Grava as notas/comentários de uma resposta e marca como respondida.

    Reaproveitado por lançamento manual do SGI, conciliação automática do webhook
    do Microsoft Forms e conciliação manual de respostas não identificadas.
    """
    for item in itens:
        if not (1 <= item["nota"] <= 5):
            raise ItemInvalido(f"Nota inválida: {item['nota']}")

    for item in itens:
        triagem_status = "pendente" if item["nota"] <= 2 else "nao_aplicavel"
        sb.table("sat_respostas_itens").insert({
            "resposta_id": resposta_id,
            "campanha_pergunta_id": item["campanha_pergunta_id"],
            "nota": item["nota"],
            "comentario": item.get("comentario"),
            "triagem_status": triagem_status,
        }).execute()

    update = {
        "status": "respondido",
        "canal_resposta": canal_resposta,
        "respondido_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": "now()",
    }
    if lancado_por:
        update["lancado_por"] = lancado_por
    sb.table("sat_respostas").update(update).eq("id", resposta_id).execute()


def _registrar_envio(sb, resposta_id: str, destinatario: str, tipo_email: str, sucesso: bool):
    from services.email_service import log_email
    log_email(sb, resposta_id, destinatario, tipo_email, sucesso)
    if sucesso:
        now = datetime.now(timezone.utc).isoformat()
        r = sb.table("sat_respostas").select("total_envios, primeiro_envio_at").eq("id", resposta_id).single().execute()
        total = (r.data.get("total_envios") or 0) + 1
        update = {
            "status": "enviado",
            "total_envios": total,
            "ultimo_envio_at": now,
            "updated_at": "now()",
        }
        if not r.data.get("primeiro_envio_at"):
            update["primeiro_envio_at"] = now
        sb.table("sat_respostas").update(update).eq("id", resposta_id).execute()


# ── Campanhas ─────────────────────────────────────────────────────────────────

class CampanhaPayload(BaseModel):
    ano: int
    titulo: str
    ms_forms_url: str


class CampanhaUpdatePayload(BaseModel):
    titulo: Optional[str] = None
    ms_forms_url: Optional[str] = None


@router.get("/campanhas")
def list_campanhas(user=Depends(_require_acesso)):
    sb = get_supabase()
    resp = sb.table("sat_campanhas").select("*").order("ano", desc=True).execute()
    campanhas = resp.data or []
    for c in campanhas:
        respostas = sb.table("sat_respostas").select("status").eq("campanha_id", c["id"]).execute()
        rows = respostas.data or []
        c["total_convidados"] = len(rows)
        c["total_respondidos"] = len([r for r in rows if r["status"] == "respondido"])
    return campanhas


@router.post("/campanhas")
def create_campanha(payload: CampanhaPayload, user=Depends(_require_acesso)):
    if not payload.ms_forms_url.strip():
        raise HTTPException(status_code=422, detail="Informe o link do Microsoft Forms")

    sb = get_supabase()

    existente = sb.table("sat_campanhas").select("id").eq("ano", payload.ano).execute()
    if existente.data:
        raise HTTPException(status_code=409, detail=f"Já existe uma campanha para o ano {payload.ano}")

    campanha = sb.table("sat_campanhas").insert({
        "ano": payload.ano,
        "titulo": payload.titulo,
        "ms_forms_url": payload.ms_forms_url.strip(),
        "status": "rascunho",
        "created_by": user.get("username"),
    }).execute().data[0]

    perguntas = sb.table("sat_perguntas").select("*").eq("ativa", True).order("ordem").execute().data or []
    for p in perguntas:
        sb.table("sat_campanha_perguntas").insert({
            "campanha_id": campanha["id"],
            "pergunta_id": p["id"],
            "ordem": p["ordem"],
            "texto_snapshot": p["texto"],
        }).execute()

    clientes = sb.table("sat_clientes").select("id").eq("ativo", True).execute().data or []
    for c in clientes:
        sb.table("sat_respostas").insert({
            "campanha_id": campanha["id"],
            "cliente_id": c["id"],
            "status": "pendente",
        }).execute()

    return campanha


@router.get("/campanhas/{campanha_id}")
def get_campanha(campanha_id: str, user=Depends(_require_acesso)):
    sb = get_supabase()
    resp = sb.table("sat_campanhas").select("*").eq("id", campanha_id).single().execute()
    if not resp.data:
        raise HTTPException(status_code=404, detail="Campanha não encontrada")
    return resp.data


@router.patch("/campanhas/{campanha_id}")
def update_campanha(campanha_id: str, payload: CampanhaUpdatePayload, user=Depends(_require_acesso)):
    sb = get_supabase()
    update = {k: v for k, v in payload.model_dump().items() if v is not None}
    if not update:
        raise HTTPException(status_code=422, detail="Nada para atualizar")
    update["updated_at"] = "now()"
    resp = sb.table("sat_campanhas").update(update).eq("id", campanha_id).execute()
    if not resp.data:
        raise HTTPException(status_code=404, detail="Campanha não encontrada")
    return resp.data[0]


@router.post("/campanhas/{campanha_id}/iniciar")
def iniciar_campanha(campanha_id: str, user=Depends(_require_acesso)):
    sb = get_supabase()
    campanha = sb.table("sat_campanhas").select("*").eq("id", campanha_id).single().execute().data
    if not campanha:
        raise HTTPException(status_code=404, detail="Campanha não encontrada")
    if campanha["status"] != "rascunho":
        raise HTTPException(status_code=409, detail="Campanha já foi iniciada")
    if not (campanha.get("ms_forms_url") or "").strip():
        raise HTTPException(status_code=422, detail="Defina o link do Microsoft Forms antes de iniciar a campanha")

    hoje = date.today()
    prazo = add_business_days(hoje, 15)
    sb.table("sat_campanhas").update({
        "status": "em_andamento",
        "data_inicio": hoje.isoformat(),
        "data_prazo": prazo.isoformat(),
        "data_prazo_original": prazo.isoformat(),
        "updated_at": "now()",
    }).eq("id", campanha_id).execute()

    from services.email_service import send_primeiro_envio
    respostas = (
        sb.table("sat_respostas")
        .select("*, sat_clientes(*)")
        .eq("campanha_id", campanha_id)
        .eq("status", "pendente")
        .execute()
        .data or []
    )
    enviados, erros = 0, 0
    for r in respostas:
        cliente = r.get("sat_clientes") or {}
        if not cliente.get("contato_email"):
            erros += 1
            continue
        ok = send_primeiro_envio(cliente, campanha)
        _registrar_envio(sb, r["id"], cliente["contato_email"], "primeiro_envio", ok)
        enviados += 1 if ok else 0
        erros += 0 if ok else 1

    return {"ok": True, "enviados": enviados, "erros": erros, "data_prazo": prazo.isoformat()}


class PostergarPayload(BaseModel):
    motivo: Optional[str] = None


@router.post("/campanhas/{campanha_id}/postergar")
def postergar_campanha(campanha_id: str, payload: PostergarPayload, user=Depends(_require_acesso)):
    sb = get_supabase()
    campanha = sb.table("sat_campanhas").select("*").eq("id", campanha_id).single().execute().data
    if not campanha:
        raise HTTPException(status_code=404, detail="Campanha não encontrada")
    if campanha["status"] not in ("em_andamento", "postergada"):
        raise HTTPException(status_code=409, detail="Só é possível postergar uma campanha em andamento")
    if not campanha.get("data_prazo"):
        raise HTTPException(status_code=409, detail="Campanha sem prazo definido")

    nova_data_prazo = add_business_days(date.fromisoformat(campanha["data_prazo"]), 10)
    sb.table("sat_campanhas").update({
        "status": "em_andamento",
        "data_prazo": nova_data_prazo.isoformat(),
        "postergada_em": datetime.now(timezone.utc).isoformat(),
        "motivo_postergacao": payload.motivo or "Postergação manual pelo SGI",
        "qtd_postergacoes": (campanha.get("qtd_postergacoes") or 0) + 1,
        "updated_at": "now()",
    }).eq("id", campanha_id).execute()

    from services.email_service import send_reforco_adesao
    pendentes = (
        sb.table("sat_respostas")
        .select("*, sat_clientes(*)")
        .eq("campanha_id", campanha_id)
        .in_("status", ["pendente", "enviado"])
        .execute()
        .data or []
    )
    for r in pendentes:
        cliente = r.get("sat_clientes") or {}
        if not cliente.get("contato_email"):
            continue
        ok = send_reforco_adesao(cliente, campanha, r)
        _registrar_envio(sb, r["id"], cliente["contato_email"], "reforco_adesao", ok)

    return {"ok": True, "data_prazo": nova_data_prazo.isoformat()}


@router.post("/campanhas/{campanha_id}/encerrar")
def encerrar_campanha(campanha_id: str, user=Depends(_require_acesso)):
    sb = get_supabase()
    campanha = sb.table("sat_campanhas").select("*").eq("id", campanha_id).single().execute().data
    if not campanha:
        raise HTTPException(status_code=404, detail="Campanha não encontrada")
    if campanha["status"] not in ("em_andamento", "postergada"):
        raise HTTPException(status_code=409, detail="Campanha não está em andamento")

    sb.table("sat_respostas").update({"status": "expirado", "updated_at": "now()"}).eq(
        "campanha_id", campanha_id
    ).in_("status", ["pendente", "enviado"]).execute()
    sb.table("sat_campanhas").update({
        "status": "encerrada",
        "encerrada_em": datetime.now(timezone.utc).isoformat(),
        "updated_at": "now()",
    }).eq("id", campanha_id).execute()
    return {"ok": True}


# ── Respostas ─────────────────────────────────────────────────────────────────

@router.get("/campanhas/{campanha_id}/respostas")
def list_respostas(
    campanha_id: str,
    status: Optional[str] = Query(None),
    cliente_q: Optional[str] = Query(None),
    user=Depends(_require_acesso),
):
    sb = get_supabase()
    query = sb.table("sat_respostas").select("*, sat_clientes(*)").eq("campanha_id", campanha_id)
    if status:
        query = query.eq("status", status)
    rows = query.execute().data or []
    if cliente_q:
        q_lower = cliente_q.lower()
        rows = [
            r for r in rows
            if q_lower in ((r.get("sat_clientes") or {}).get("empresa_nome") or "").lower()
            or q_lower in ((r.get("sat_clientes") or {}).get("contato_nome") or "").lower()
        ]
    return rows


@router.post("/respostas/{resposta_id}/reenviar")
def reenviar_resposta(resposta_id: str, user=Depends(_require_acesso)):
    sb = get_supabase()
    r = sb.table("sat_respostas").select("*, sat_clientes(*), sat_campanhas(*)").eq("id", resposta_id).single().execute().data
    if not r:
        raise HTTPException(status_code=404, detail="Resposta não encontrada")
    if r["status"] == "respondido":
        raise HTTPException(status_code=409, detail="Cliente já respondeu")

    cliente = r.get("sat_clientes") or {}
    campanha = r.get("sat_campanhas") or {}
    if not cliente.get("contato_email"):
        raise HTTPException(status_code=422, detail="Cliente sem e-mail cadastrado")

    from services.email_service import send_cobranca
    ok = send_cobranca(cliente, campanha, r)
    _registrar_envio(sb, resposta_id, cliente["contato_email"], "cobranca", ok)
    if not ok:
        raise HTTPException(status_code=500, detail="Falha ao enviar e-mail")
    return {"ok": True}


class ItemLancamentoManual(BaseModel):
    campanha_pergunta_id: str
    nota: int
    comentario: Optional[str] = None


class LancarManualPayload(BaseModel):
    itens: list[ItemLancamentoManual]


@router.post("/respostas/{resposta_id}/lancar-manual")
def lancar_resposta_manual(resposta_id: str, payload: LancarManualPayload, user=Depends(_require_acesso)):
    """Fallback: SGI lança resposta recebida fora do sistema (telefone/papel/e-mail avulso)."""
    sb = get_supabase()
    r = sb.table("sat_respostas").select("*").eq("id", resposta_id).single().execute().data
    if not r:
        raise HTTPException(status_code=404, detail="Resposta não encontrada")
    if r["status"] == "respondido":
        raise HTTPException(status_code=409, detail="Resposta já registrada")

    try:
        _aplicar_itens(
            sb, resposta_id,
            [item.model_dump() for item in payload.itens],
            "manual_sgi",
            lancado_por=user.get("username"),
        )
    except ItemInvalido as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    return {"ok": True}


# ── Triagem de notas ruins ────────────────────────────────────────────────────

@router.get("/campanhas/{campanha_id}/triagem")
def list_triagem(campanha_id: str, user=Depends(_require_acesso)):
    sb = get_supabase()
    cp_ids = [
        cp["id"] for cp in
        sb.table("sat_campanha_perguntas").select("id").eq("campanha_id", campanha_id).execute().data or []
    ]
    if not cp_ids:
        return []

    itens = (
        sb.table("sat_respostas_itens")
        .select("*, sat_respostas(id, cliente_id, sat_clientes(empresa_nome, contato_nome)), sat_campanha_perguntas(texto_snapshot, pergunta_id)")
        .in_("campanha_pergunta_id", cp_ids)
        .eq("triagem_status", "pendente")
        .execute()
        .data or []
    )
    return itens


class TriagemPayload(BaseModel):
    ponto_avaliacao_id: str
    observacao: Optional[str] = None


@router.post("/respostas-itens/{item_id}/triagem")
def classificar_triagem(item_id: str, payload: TriagemPayload, user=Depends(_require_acesso)):
    sb = get_supabase()
    resp = sb.table("sat_respostas_itens").update({
        "triagem_status": "classificado",
        "triagem_ponto_id": payload.ponto_avaliacao_id,
        "triagem_observacao": payload.observacao,
        "triagem_por": user.get("username"),
        "triagem_em": datetime.now(timezone.utc).isoformat(),
    }).eq("id", item_id).execute()
    if not resp.data:
        raise HTTPException(status_code=404, detail="Item não encontrado")
    return resp.data[0]


# ── Planos de ação ────────────────────────────────────────────────────────────

class PlanoAcaoPayload(BaseModel):
    pergunta_id: str
    descricao: str
    responsavel: str
    prazo: str


@router.get("/campanhas/{campanha_id}/planos-acao")
def list_planos_acao(campanha_id: str, user=Depends(_require_acesso)):
    sb = get_supabase()
    resp = sb.table("sat_planos_acao").select("*").eq("campanha_id", campanha_id).order("created_at", desc=True).execute()
    return resp.data or []


@router.post("/campanhas/{campanha_id}/planos-acao")
def create_plano_acao(campanha_id: str, payload: PlanoAcaoPayload, user=Depends(_require_acesso)):
    sb = get_supabase()
    from services.dashboard import build_campanha_dashboard
    dashboard = build_campanha_dashboard(sb, campanha_id)
    pct = 0.0
    for p in dashboard.get("perguntas", []):
        if p["pergunta_id"] == payload.pergunta_id:
            pct = p["percentual_ruim"]
            break

    resp = sb.table("sat_planos_acao").insert({
        "campanha_id": campanha_id,
        "pergunta_id": payload.pergunta_id,
        "percentual_notas_ruins": pct,
        "descricao": payload.descricao,
        "responsavel": payload.responsavel,
        "prazo": payload.prazo,
        "criado_por": user.get("username"),
    }).execute()
    return resp.data[0]


class PlanoAcaoUpdatePayload(BaseModel):
    descricao: Optional[str] = None
    responsavel: Optional[str] = None
    prazo: Optional[str] = None
    status: Optional[str] = None
    observacao_conclusao: Optional[str] = None


@router.patch("/planos-acao/{plano_id}")
def update_plano_acao(plano_id: str, payload: PlanoAcaoUpdatePayload, user=Depends(_require_acesso)):
    sb = get_supabase()
    update = {k: v for k, v in payload.model_dump().items() if v is not None}
    if update.get("status") == "concluido":
        update["concluido_em"] = datetime.now(timezone.utc).isoformat()
    update["updated_at"] = "now()"
    resp = sb.table("sat_planos_acao").update(update).eq("id", plano_id).execute()
    if not resp.data:
        raise HTTPException(status_code=404, detail="Plano de ação não encontrado")
    return resp.data[0]


# ── Dashboard ─────────────────────────────────────────────────────────────────

@router.get("/campanhas/{campanha_id}/dashboard")
def get_dashboard(campanha_id: str, user=Depends(_require_acesso)):
    sb = get_supabase()
    from services.dashboard import build_campanha_dashboard
    dashboard = build_campanha_dashboard(sb, campanha_id)
    if not dashboard:
        raise HTTPException(status_code=404, detail="Campanha não encontrada")
    return dashboard


@router.get("/dashboard/historico")
def get_historico(user=Depends(_require_acesso)):
    from services.dashboard import build_historico
    return build_historico()


# ── Microsoft Forms — conciliação manual e log de envios ─────────────────────

@router.get("/campanhas/{campanha_id}/ms-forms-log")
def list_ms_forms_log(campanha_id: str, status: Optional[str] = Query(None), user=Depends(_require_acesso)):
    sb = get_supabase()
    query = (
        sb.table("sat_ms_forms_log")
        .select("*, sat_clientes(empresa_nome, contato_nome)")
        .eq("campanha_id", campanha_id)
    )
    if status:
        query = query.eq("status", status)
    resp = query.order("recebido_em", desc=True).execute()
    return resp.data or []


class ConciliarMsFormsPayload(BaseModel):
    resposta_id: str


@router.post("/ms-forms-log/{log_id}/conciliar")
def conciliar_ms_forms(log_id: str, payload: ConciliarMsFormsPayload, user=Depends(_require_acesso)):
    sb = get_supabase()
    log_row = sb.table("sat_ms_forms_log").select("*").eq("id", log_id).single().execute().data
    if not log_row:
        raise HTTPException(status_code=404, detail="Registro não encontrado")
    if log_row["status"] == "conciliado":
        raise HTTPException(status_code=409, detail="Este registro já foi conciliado")

    resposta = sb.table("sat_respostas").select("*").eq("id", payload.resposta_id).single().execute().data
    if not resposta:
        raise HTTPException(status_code=404, detail="Resposta não encontrada")
    if resposta["status"] == "respondido":
        raise HTTPException(status_code=409, detail="Essa resposta já foi respondida")

    cp_por_ordem = {
        cp["ordem"]: cp["id"] for cp in
        sb.table("sat_campanha_perguntas").select("id, ordem").eq("campanha_id", resposta["campanha_id"]).execute().data or []
    }
    itens_bruto = (log_row.get("payload_bruto") or {}).get("itens", [])
    itens_resolvidos = []
    for item in itens_bruto:
        cp_id = cp_por_ordem.get(item.get("ordem"))
        if not cp_id:
            raise HTTPException(status_code=422, detail=f"Ordem de pergunta inválida no payload: {item.get('ordem')}")
        itens_resolvidos.append({
            "campanha_pergunta_id": cp_id,
            "nota": item.get("nota"),
            "comentario": item.get("comentario"),
        })

    try:
        _aplicar_itens(sb, payload.resposta_id, itens_resolvidos, "ms_forms", lancado_por=user.get("username"))
    except ItemInvalido as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    sb.table("sat_ms_forms_log").update({
        "status": "conciliado",
        "matched": True,
        "resposta_id": payload.resposta_id,
        "cliente_id": resposta["cliente_id"],
        "conciliado_por": user.get("username"),
        "conciliado_em": datetime.now(timezone.utc).isoformat(),
    }).eq("id", log_id).execute()

    return {"ok": True}


@router.post("/ms-forms-log/{log_id}/ignorar")
def ignorar_ms_forms(log_id: str, user=Depends(_require_acesso)):
    sb = get_supabase()
    resp = sb.table("sat_ms_forms_log").update({"status": "ignorado"}).eq("id", log_id).execute()
    if not resp.data:
        raise HTTPException(status_code=404, detail="Registro não encontrado")
    return {"ok": True}


@router.get("/campanhas/{campanha_id}/log-envios")
def list_log_envios(campanha_id: str, user=Depends(_require_acesso)):
    sb = get_supabase()

    respostas = (
        sb.table("sat_respostas")
        .select("id, sat_clientes(empresa_nome, contato_nome)")
        .eq("campanha_id", campanha_id)
        .execute()
        .data or []
    )
    cliente_por_resposta = {r["id"]: (r.get("sat_clientes") or {}) for r in respostas}
    resposta_ids = list(cliente_por_resposta.keys())

    eventos = []

    if resposta_ids:
        email_log = sb.table("sat_email_log").select("*").in_("resposta_id", resposta_ids).execute().data or []
        for e in email_log:
            cliente = cliente_por_resposta.get(e["resposta_id"], {})
            eventos.append({
                "tipo": e["tipo_email"],
                "data": e["enviado_at"],
                "cliente_nome": cliente.get("empresa_nome") or "—",
                "sucesso": e["sucesso"],
                "detalhe": e.get("erro_detalhe"),
            })

    forms_log = (
        sb.table("sat_ms_forms_log")
        .select("*, sat_clientes(empresa_nome)")
        .eq("campanha_id", campanha_id)
        .execute()
        .data or []
    )
    for f in forms_log:
        cliente = f.get("sat_clientes") or {}
        eventos.append({
            "tipo": f"ms_forms_{f['status']}",
            "data": f["recebido_em"],
            "cliente_nome": cliente.get("empresa_nome") or f.get("empresa_informada") or f.get("email_informado") or "—",
            "sucesso": f["status"] == "conciliado",
            "detalhe": f.get("erro_detalhe"),
        })

    eventos.sort(key=lambda e: e["data"], reverse=True)
    return eventos
