"""Plano de Ação - Feedback — formulários públicos (sem login), acessados por token.

Arquivo isolado de routes/public.py de propósito (não deve ser tocado — sustenta
o fluxo real de avaliação/ciência que não pode sofrer nenhum risco de regressão).
Duplica localmente o helper de validação de UUID em vez de importar de lá.
"""
import logging
import re
import uuid as _uuid_mod
from datetime import date as _date, datetime, timedelta, timezone

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from db import get_supabase
from limiter import limiter, get_real_ip
from services.action_plan_initial import (
    REQUIRED_ITEM_COUNT,
    build_initial_form_payload,
    validate_and_persist_initial_items,
)

router = APIRouter(prefix="/api/performance/public/action-plans")
_logger = logging.getLogger(__name__)

PHASE_PCT = {"total": 25, "parcial": 12.5, "nao_atingida": 0}


def _validate_uuid(token: str, label: str = "Link") -> None:
    try:
        _uuid_mod.UUID(token, version=4)
    except (ValueError, AttributeError):
        raise HTTPException(404, detail=f"{label} inválido ou expirado.")


def _resolve_employees(db, ids: list[str]) -> dict[str, dict]:
    ids = list({i for i in ids if i})
    if not ids:
        return {}
    rows = db.table("performance_employees").select(
        "id,name,cargo,company_id,hierarchy_level,perfil"
    ).in_("id", ids).execute().data or []
    return {r["id"]: r for r in rows}


# ── Preenchimento inicial ───────────────────────────────────────────────────────

@router.get("/inicial/{token}")
@limiter.limit("20/minute")
def get_initial_form(token: str, request: Request) -> dict:
    _validate_uuid(token, "Link de plano de ação")
    db = get_supabase()
    plan = db.table("performance_action_plans").select("*").eq("initial_token", token).execute()
    if not plan.data:
        raise HTTPException(404, detail="Link de plano de ação inválido ou expirado.")
    p = plan.data[0]
    if p.get("initial_token_invalidated_at"):
        raise HTTPException(400, detail="Este link foi invalidado. Procure o RH.")
    if p.get("initial_token_used_at"):
        raise HTTPException(400, detail="Este plano de ação já foi preenchido.")

    return build_initial_form_payload(db, p)


class InitialItemBody(BaseModel):
    indicator_id: str
    situacao_observada: str
    meta_esperada: str
    acoes: str
    responsavel_acompanhamento: str
    como_sera_verificado: str


class InitialFormSubmit(BaseModel):
    items: list[InitialItemBody]
    frequencia_alinhamento: str


@router.post("/inicial/{token}")
@limiter.limit("5/minute")
def submit_initial_form(token: str, body: InitialFormSubmit, request: Request) -> dict:
    _validate_uuid(token, "Link de plano de ação")
    db = get_supabase()
    plan = db.table("performance_action_plans").select("*").eq("initial_token", token).execute()
    if not plan.data:
        raise HTTPException(404, detail="Link de plano de ação inválido.")
    p = plan.data[0]
    if p.get("initial_token_invalidated_at"):
        raise HTTPException(400, detail="Este link foi invalidado. Procure o RH.")
    if p.get("initial_token_used_at"):
        raise HTTPException(400, detail="Este plano de ação já foi preenchido.")

    validate_and_persist_initial_items(db, p, [i.model_dump() for i in body.items], body.frequencia_alinhamento)

    _logger.info("AUDIT action_plan_initial_submitted | token=%s | action_plan_id=%s", token, p["id"])
    return {"ok": True}


# ── Preenchimento pelo colaborador, logo após dar ciência da avaliação ───────────
# Mesma elegibilidade/criação de plano do fluxo em lote do RH (routes/action_plans.py
# ::_build_candidates/_create_action_plan), mas sem e-mail pro gestor: o colaborador
# preenche na hora, na mesma tela em que deu ciência da avaliação. Import local (não
# no topo do arquivo) pra manter routes/action_plans.py como o dono da lógica de
# elegibilidade/criação, sem acoplar os dois módulos no import-time.

def _plan_from_ciencia_eligibility(db, review_id: str, employee_id: str) -> dict:
    """Retorna {"eligible": False[, "reason"]} ou
    {"eligible": True, "plan": <row>, "already_filled": bool}."""
    from routes.action_plans import _build_candidates, _create_action_plan

    review = db.table("performance_reviews").select("cycle_id").eq("id", review_id).execute()
    if not review.data:
        return {"eligible": False}
    cycle_id = review.data[0]["cycle_id"]

    cycle = db.table("performance_cycles").select("action_plan_start_date").eq("id", cycle_id).execute()
    base = cycle.data[0].get("action_plan_start_date") if cycle.data else None
    if not base:
        return {"eligible": False, "reason": "not_configured"}

    existing = (
        db.table("performance_action_plans").select("*")
        .eq("employee_id", employee_id).eq("cycle_id", cycle_id).execute()
    )
    if existing.data:
        plan = existing.data[0]
        return {"eligible": True, "plan": plan, "already_filled": plan["status"] != "pending_manager_fill"}

    candidates = _build_candidates(db, cycle_id, employee_id=employee_id)
    if not candidates:
        return {"eligible": False}

    plan = _create_action_plan(db, cycle_id, candidates[0], _date.fromisoformat(base), actor="colaborador_ciencia")
    if not plan:
        return {"eligible": False}
    return {"eligible": True, "plan": plan, "already_filled": False}


def _plan_from_ciencia_response(db, elig: dict) -> dict:
    plan = elig["plan"]
    if elig["already_filled"]:
        payload = _build_plan_ciencia_payload(db, plan["id"]) or {}
        return {"eligible": True, "already_filled": True, **payload}
    payload = build_initial_form_payload(db, plan)
    return {"eligible": True, "already_filled": False, "plan_id": plan["id"], **payload}


@router.get("/from-ciencia/{ciencia_token}")
@limiter.limit("20/minute")
def get_plan_from_ciencia(ciencia_token: str, request: Request) -> dict:
    _validate_uuid(ciencia_token, "Link de ciência")
    db = get_supabase()
    ack = db.table("performance_acknowledgment_tokens").select("*").eq("token", ciencia_token).execute()
    if not ack.data:
        raise HTTPException(404, detail="Link de ciência inválido.")
    at = ack.data[0]
    if not at.get("used_at"):
        raise HTTPException(400, detail="Dê ciência da avaliação primeiro.")

    elig = _plan_from_ciencia_eligibility(db, at["review_id"], at["employee_id"])
    if not elig["eligible"]:
        return {"eligible": False, "reason": elig.get("reason")}
    return _plan_from_ciencia_response(db, elig)


@router.post("/from-ciencia/{ciencia_token}")
@limiter.limit("5/minute")
def submit_plan_from_ciencia(ciencia_token: str, body: InitialFormSubmit, request: Request) -> dict:
    _validate_uuid(ciencia_token, "Link de ciência")
    db = get_supabase()
    ack = db.table("performance_acknowledgment_tokens").select("*").eq("token", ciencia_token).execute()
    if not ack.data:
        raise HTTPException(404, detail="Link de ciência inválido.")
    at = ack.data[0]
    if not at.get("used_at"):
        raise HTTPException(400, detail="Dê ciência da avaliação primeiro.")

    elig = _plan_from_ciencia_eligibility(db, at["review_id"], at["employee_id"])
    if not elig["eligible"]:
        raise HTTPException(400, detail="Nenhum plano de ação disponível para preenchimento.")
    if elig["already_filled"]:
        raise HTTPException(400, detail="Este plano de ação já foi preenchido.")

    validate_and_persist_initial_items(db, elig["plan"], [i.model_dump() for i in body.items], body.frequencia_alinhamento)
    _logger.info(
        "AUDIT action_plan_filled_by_employee | ciencia_token=%s | action_plan_id=%s",
        ciencia_token, elig["plan"]["id"],
    )
    return {"ok": True}


class FromCienciaPresencialBusca(BaseModel):
    cpf: str
    review_id: str


class FromCienciaPresencialEnviar(BaseModel):
    cpf: str
    review_id: str
    items: list[InitialItemBody]
    frequencia_alinhamento: str


def _resolve_employee_by_cpf_review(db, cpf: str, review_id: str, ip: str) -> dict:
    """Autentica colaborador por CPF (mesmo padrão de ciencia-presencial/confirmar)
    e confirma que a review pertence a ele e que a ciência já foi dada. Levanta
    HTTPException em qualquer falha (e loga tentativa incorreta pro anti-bruteforce)."""
    cpf_clean = re.sub(r"\D", "", cpf.strip())
    employee = db.table("performance_employees").select("id,name").eq("cpf", cpf_clean).eq("active", True).execute()
    if not employee.data:
        db.table("performance_ciencia_attempts").insert({"matricula": cpf_clean, "ip_address": ip}).execute()
        raise HTTPException(404, detail=_DADOS_NAO_ENCONTRADOS)
    emp = employee.data[0]

    review = db.table("performance_reviews").select("id,employee_id").eq("id", review_id).execute()
    if not review.data or review.data[0]["employee_id"] != emp["id"]:
        db.table("performance_ciencia_attempts").insert({"matricula": cpf_clean, "ip_address": ip}).execute()
        raise HTTPException(404, detail="Avaliação não encontrada.")

    ack = (
        db.table("performance_review_acknowledgments").select("id")
        .eq("review_id", review_id).eq("employee_id", emp["id"]).execute()
    )
    if not ack.data:
        raise HTTPException(400, detail="Dê ciência da avaliação primeiro.")
    return emp


@router.post("/from-ciencia-presencial/buscar")
@limiter.limit("10/minute")
def buscar_plan_from_ciencia_presencial(body: FromCienciaPresencialBusca, request: Request) -> dict:
    db = get_supabase()
    ip = get_real_ip(request)
    cutoff = (datetime.now(tz=timezone.utc) - timedelta(minutes=BLOCK_MINUTES)).isoformat()
    attempts = db.table("performance_ciencia_attempts").select("id").eq("ip_address", ip).gte("attempted_at", cutoff).execute()
    if len(attempts.data) >= MAX_ATTEMPTS:
        raise HTTPException(429, detail=f"Muitas tentativas incorretas. Aguarde {BLOCK_MINUTES} minutos.")

    emp = _resolve_employee_by_cpf_review(db, body.cpf, body.review_id, ip)
    elig = _plan_from_ciencia_eligibility(db, body.review_id, emp["id"])
    if not elig["eligible"]:
        return {"eligible": False, "reason": elig.get("reason")}
    return _plan_from_ciencia_response(db, elig)


@router.post("/from-ciencia-presencial/enviar")
@limiter.limit("5/minute")
def enviar_plan_from_ciencia_presencial(body: FromCienciaPresencialEnviar, request: Request) -> dict:
    db = get_supabase()
    ip = get_real_ip(request)
    cutoff = (datetime.now(tz=timezone.utc) - timedelta(minutes=BLOCK_MINUTES)).isoformat()
    attempts = db.table("performance_ciencia_attempts").select("id").eq("ip_address", ip).gte("attempted_at", cutoff).execute()
    if len(attempts.data) >= MAX_ATTEMPTS:
        raise HTTPException(429, detail=f"Muitas tentativas incorretas. Aguarde {BLOCK_MINUTES} minutos.")

    emp = _resolve_employee_by_cpf_review(db, body.cpf, body.review_id, ip)
    elig = _plan_from_ciencia_eligibility(db, body.review_id, emp["id"])
    if not elig["eligible"]:
        raise HTTPException(400, detail="Nenhum plano de ação disponível para preenchimento.")
    if elig["already_filled"]:
        raise HTTPException(400, detail="Este plano de ação já foi preenchido.")

    validate_and_persist_initial_items(db, elig["plan"], [i.model_dump() for i in body.items], body.frequencia_alinhamento)
    _logger.info(
        "AUDIT action_plan_filled_by_employee_presencial | cpf_suffix=%s | action_plan_id=%s",
        re.sub(r"\D", "", body.cpf)[-4:], elig["plan"]["id"],
    )
    return {"ok": True}


# ── Ciência do colaborador sobre o plano de ação ─────────────────────────────
# Mesmo padrão de routes/public.py (ciência da avaliação): token por e-mail +
# fallback presencial por nome+CPF, mesma tabela de anti-bruteforce.

def _build_plan_ciencia_payload(db, action_plan_id: str) -> dict | None:
    plan = db.table("performance_action_plans").select("*").eq("id", action_plan_id).execute()
    if not plan.data:
        return None
    p = plan.data[0]

    emp_map = _resolve_employees(db, [p["employee_id"], p["manager_id"]])
    employee = emp_map.get(p["employee_id"])
    manager = emp_map.get(p["manager_id"])
    cycle = db.table("performance_cycles").select("name").eq("id", p["cycle_id"]).execute()
    cycle_name = cycle.data[0]["name"] if cycle.data else ""

    items = (
        db.table("performance_action_plan_items")
        .select("indicator_id,situacao_observada,meta_esperada,acoes,"
                "responsavel_acompanhamento,como_sera_verificado,performance_indicators(name)")
        .eq("action_plan_id", action_plan_id).execute().data
    ) or []

    existing_ack = db.table("performance_action_plan_acknowledgments").select("*").eq(
        "action_plan_id", action_plan_id
    ).execute()
    already_acknowledged = bool(existing_ack.data)

    return {
        "action_plan_id": p["id"],
        "employee_name": employee["name"] if employee else "",
        "manager_name": manager["name"] if manager else "",
        "cycle_name": cycle_name,
        "frequencia_alinhamento": p.get("frequencia_alinhamento"),
        "items": [
            {
                "indicator_name": (i.get("performance_indicators") or {}).get("name", ""),
                "situacao_observada": i.get("situacao_observada"),
                "meta_esperada": i.get("meta_esperada"),
                "acoes": i.get("acoes"),
                "responsavel_acompanhamento": i.get("responsavel_acompanhamento"),
                "como_sera_verificado": i.get("como_sera_verificado"),
            }
            for i in items
        ],
        "already_acknowledged": already_acknowledged,
        "acknowledged_at": existing_ack.data[0]["acknowledged_at"] if already_acknowledged else None,
    }


@router.get("/ciencia/{token}")
@limiter.limit("20/minute")
def get_plan_ciencia_form(token: str, request: Request) -> dict:
    _validate_uuid(token, "Link de ciência")
    db = get_supabase()
    ack_token = db.table("performance_action_plan_ack_tokens").select("*").eq("token", token).execute()
    if not ack_token.data:
        raise HTTPException(404, detail="Link de ciência inválido.")
    at = ack_token.data[0]
    if not at.get("used_at") and at.get("expires_at"):
        expires = datetime.fromisoformat(at["expires_at"].replace("Z", "+00:00"))
        if datetime.now(tz=timezone.utc) > expires:
            raise HTTPException(400, detail="Este link expirou. Entre em contato com o RH.")

    payload = _build_plan_ciencia_payload(db, at["action_plan_id"])
    if payload is None:
        raise HTTPException(404, detail="Plano de ação não encontrado.")
    return payload


@router.post("/ciencia/{token}")
@limiter.limit("5/minute")
def submit_plan_ciencia(token: str, request: Request) -> dict:
    _validate_uuid(token, "Link de ciência")
    db = get_supabase()
    ack_token = db.table("performance_action_plan_ack_tokens").select("*").eq("token", token).execute()
    if not ack_token.data:
        raise HTTPException(404, detail="Link de ciência inválido.")
    at = ack_token.data[0]
    if at.get("used_at"):
        raise HTTPException(400, detail="Ciência já registrada.")

    existing = db.table("performance_action_plan_acknowledgments").select("id").eq(
        "action_plan_id", at["action_plan_id"]
    ).eq("employee_id", at["employee_id"]).execute()
    if existing.data:
        raise HTTPException(400, detail="Ciência já registrada.")

    try:
        db.table("performance_action_plan_acknowledgments").insert({
            "action_plan_id": at["action_plan_id"],
            "employee_id": at["employee_id"],
            "acknowledged_via": "email",
            "ip_address": request.client.host if request.client else None,
        }).execute()
    except Exception as _ack_err:
        if any(k in str(_ack_err).lower() for k in ("23505", "duplicate", "unique")):
            raise HTTPException(status_code=400, detail="Ciência já registrada.")
        raise

    db.table("performance_action_plan_ack_tokens").update({"used_at": "now()"}).eq("token", token).execute()

    _logger.info(
        "AUDIT action_plan_ciencia_email_confirmed | ip=%s | token=%s | action_plan_id=%s | employee_id=%s",
        request.client.host if request.client else "unknown", token, at["action_plan_id"], at["employee_id"],
    )
    return {"ok": True, "acknowledged_at": datetime.now(tz=timezone.utc).isoformat()}


class CienciaPresencialBusca(BaseModel):
    nome: str
    cpf: str


class CienciaPresencialConfirmar(BaseModel):
    cpf: str
    action_plan_id: str


MAX_ATTEMPTS = 3
BLOCK_MINUTES = 5
_DADOS_NAO_ENCONTRADOS = "Dados não encontrados. Verifique o CPF e o nome e tente novamente."


def _normalize_name(name: str) -> str:
    import unicodedata
    name = unicodedata.normalize("NFKD", name).encode("ASCII", "ignore").decode()
    return " ".join(name.lower().split())


@router.post("/ciencia-presencial/buscar")
@limiter.limit("10/minute")
def buscar_plan_ciencia_presencial(body: CienciaPresencialBusca, request: Request) -> dict:
    db = get_supabase()
    ip = get_real_ip(request)

    cutoff = (datetime.now(tz=timezone.utc) - timedelta(minutes=BLOCK_MINUTES)).isoformat()
    attempts = db.table("performance_ciencia_attempts").select("id").eq("ip_address", ip).gte("attempted_at", cutoff).execute()
    if len(attempts.data) >= MAX_ATTEMPTS:
        raise HTTPException(429, detail=f"Muitas tentativas incorretas. Aguarde {BLOCK_MINUTES} minutos.")

    cpf_clean = re.sub(r"\D", "", body.cpf.strip())
    if len(cpf_clean) != 11:
        raise HTTPException(400, detail="CPF inválido. Informe os 11 dígitos numéricos.")

    def _log_attempt():
        db.table("performance_ciencia_attempts").insert({"matricula": cpf_clean, "ip_address": ip}).execute()

    employees = db.table("performance_employees").select("*").eq("cpf", cpf_clean).eq("active", True).execute().data
    if not employees:
        _log_attempt()
        raise HTTPException(404, detail=_DADOS_NAO_ENCONTRADOS)
    employee = employees[0]

    nome_digitado = _normalize_name(body.nome)
    nome_cadastrado = _normalize_name(employee["name"])
    if nome_digitado != nome_cadastrado:
        _log_attempt()
        raise HTTPException(404, detail=_DADOS_NAO_ENCONTRADOS)

    plans = (
        db.table("performance_action_plans").select("id,status")
        .eq("employee_id", employee["id"]).in_("status", ["active", "completed"])
        .order("created_at", desc=True).execute().data
    ) or []
    if not plans:
        raise HTTPException(404, detail="Nenhum plano de ação disponível para sua ciência no momento.")

    payload = _build_plan_ciencia_payload(db, plans[0]["id"])
    if payload is None:
        raise HTTPException(404, detail="Plano de ação não encontrado.")
    return payload


@router.post("/ciencia-presencial/confirmar")
@limiter.limit("5/minute")
def confirmar_plan_ciencia_presencial(body: CienciaPresencialConfirmar, request: Request) -> dict:
    db = get_supabase()
    ip = get_real_ip(request)

    cutoff = (datetime.now(tz=timezone.utc) - timedelta(minutes=BLOCK_MINUTES)).isoformat()
    attempts = db.table("performance_ciencia_attempts").select("id").eq("ip_address", ip).gte("attempted_at", cutoff).execute()
    if len(attempts.data) >= MAX_ATTEMPTS:
        raise HTTPException(429, detail=f"Muitas tentativas incorretas. Aguarde {BLOCK_MINUTES} minutos.")

    cpf_clean = re.sub(r"\D", "", body.cpf.strip())
    employee = db.table("performance_employees").select("id,name").eq("cpf", cpf_clean).eq("active", True).execute()
    if not employee.data:
        db.table("performance_ciencia_attempts").insert({"matricula": cpf_clean, "ip_address": ip}).execute()
        raise HTTPException(404, detail=_DADOS_NAO_ENCONTRADOS)
    emp = employee.data[0]

    plan = db.table("performance_action_plans").select("id").eq("id", body.action_plan_id).eq("employee_id", emp["id"]).execute()
    if not plan.data:
        db.table("performance_ciencia_attempts").insert({"matricula": cpf_clean, "ip_address": ip}).execute()
        _logger.warning(
            "SECURITY action_plan_id_mismatch | ip=%s | cpf_suffix=%s | action_plan_id=%s | emp_id=%s",
            ip, cpf_clean[-4:], body.action_plan_id, emp["id"],
        )
        raise HTTPException(404, detail="Plano de ação não encontrado.")

    existing = db.table("performance_action_plan_acknowledgments").select("id").eq(
        "action_plan_id", body.action_plan_id
    ).eq("employee_id", emp["id"]).execute()
    if existing.data:
        raise HTTPException(400, detail="Ciência já registrada para este colaborador.")

    now_iso = datetime.now(tz=timezone.utc).isoformat()
    db.table("performance_action_plan_acknowledgments").insert({
        "action_plan_id": body.action_plan_id,
        "employee_id": emp["id"],
        "acknowledged_via": "presencial",
        "ip_address": ip,
    }).execute()

    _logger.info(
        "AUDIT action_plan_ciencia_presencial_confirmed | ip=%s | cpf_suffix=%s | action_plan_id=%s | emp_id=%s",
        ip, cpf_clean[-4:], body.action_plan_id, emp["id"],
    )
    return {"ok": True, "acknowledged_at": now_iso, "employee_name": emp["name"]}


# ── Check-in trimestral ─────────────────────────────────────────────────────────

@router.get("/checkin/{token}")
@limiter.limit("20/minute")
def get_checkin_form(token: str, request: Request) -> dict:
    _validate_uuid(token, "Link de acompanhamento")
    db = get_supabase()
    phase = db.table("performance_action_plan_phases").select("*").eq("token", token).execute()
    if not phase.data:
        raise HTTPException(404, detail="Link de acompanhamento inválido ou expirado.")
    ph = phase.data[0]
    if ph.get("invalidated_at"):
        raise HTTPException(400, detail="Este link foi invalidado. Procure o RH.")
    if ph["status"] == "completed":
        raise HTTPException(400, detail="Este checkpoint já foi respondido.")
    if ph["status"] != "sent":
        raise HTTPException(400, detail="Este checkpoint ainda não foi liberado.")

    plan = db.table("performance_action_plans").select("*").eq("id", ph["action_plan_id"]).execute()
    if not plan.data:
        raise HTTPException(404, detail="Plano de ação não encontrado.")
    p = plan.data[0]

    cycle = db.table("performance_cycles").select("name").eq("id", p["cycle_id"]).execute()
    cycle_name = cycle.data[0]["name"] if cycle.data else ""

    emp_map = _resolve_employees(db, [p["employee_id"]])
    employee = emp_map.get(p["employee_id"])

    items = (
        db.table("performance_action_plan_items")
        .select(
            "id,plan_text,cumulative_pct,meta_esperada,acoes,performance_indicators(name)"
        )
        .eq("action_plan_id", p["id"]).execute().data
    ) or []

    return {
        "employee_name": employee["name"] if employee else "",
        "cycle_name": cycle_name,
        "phase_number": ph["phase_number"],
        "is_final_phase": ph["phase_number"] == 4,
        "due_date": ph["due_date"],
        "items": [
            {
                "item_id": i["id"],
                "indicator_name": (i.get("performance_indicators") or {}).get("name", ""),
                "plan_text": i.get("plan_text") or "",
                "meta_esperada": i.get("meta_esperada"),
                "acoes": i.get("acoes"),
                "cumulative_pct_before": i.get("cumulative_pct", 0),
            }
            for i in items
        ],
    }


class PhaseItemAnswer(BaseModel):
    item_id: str
    result: str  # "total" | "parcial" | "nao_atingida"
    justification: str | None = None
    phase4_override_100: bool | None = None
    phase4_final_justification: str | None = None


class CheckinSubmit(BaseModel):
    items: list[PhaseItemAnswer]


@router.post("/checkin/{token}")
@limiter.limit("5/minute")
def submit_checkin_form(token: str, body: CheckinSubmit, request: Request) -> dict:
    _validate_uuid(token, "Link de acompanhamento")
    db = get_supabase()
    phase = db.table("performance_action_plan_phases").select("*").eq("token", token).execute()
    if not phase.data:
        raise HTTPException(404, detail="Link de acompanhamento inválido.")
    ph = phase.data[0]
    if ph.get("invalidated_at"):
        raise HTTPException(400, detail="Este link foi invalidado. Procure o RH.")
    if ph["status"] == "completed":
        raise HTTPException(400, detail="Este checkpoint já foi respondido.")
    if ph["status"] != "sent":
        raise HTTPException(400, detail="Este checkpoint ainda não foi liberado.")

    plan = db.table("performance_action_plans").select("*").eq("id", ph["action_plan_id"]).execute()
    if not plan.data:
        raise HTTPException(404, detail="Plano de ação não encontrado.")
    p = plan.data[0]
    is_final_phase = ph["phase_number"] == 4

    items = (
        db.table("performance_action_plan_items").select("id,cumulative_pct")
        .eq("action_plan_id", p["id"]).execute().data
    ) or []
    items_map = {i["id"]: i for i in items}

    if not body.items:
        raise HTTPException(400, detail="Informe o resultado de cada competência.")
    sent_ids = {a.item_id for a in body.items}
    if sent_ids != set(items_map.keys()):
        raise HTTPException(400, detail="É necessário responder todas as competências deste plano.")

    for ans in body.items:
        if ans.result not in PHASE_PCT:
            raise HTTPException(400, detail=f"Resultado inválido para o item {ans.item_id}.")
        if ans.result != "total" and not (ans.justification or "").strip():
            raise HTTPException(400, detail="Justificativa é obrigatória quando a meta não foi totalmente atingida.")

    computed: list[dict] = []
    for ans in body.items:
        before = float(items_map[ans.item_id].get("cumulative_pct") or 0)
        pct_awarded = PHASE_PCT[ans.result]
        tentative = min(100.0, before + pct_awarded)
        final_pct = tentative
        override_100 = None
        final_justification = None

        if is_final_phase and tentative < 100:
            if ans.phase4_override_100 is None:
                raise HTTPException(
                    400,
                    detail="Nesta última fase, confirme se o colaborador atingiu 100% da competência "
                           "ou justifique o percentual final.",
                )
            if not (ans.phase4_final_justification or "").strip():
                raise HTTPException(400, detail="Justificativa final é obrigatória na última fase.")
            override_100 = ans.phase4_override_100
            final_justification = ans.phase4_final_justification.strip()
            final_pct = 100.0 if override_100 else tentative

        computed.append({
            "item_id": ans.item_id,
            "result": ans.result,
            "pct_awarded": pct_awarded,
            "justification": (ans.justification or "").strip() or None,
            "phase4_override_100": override_100,
            "phase4_final_justification": final_justification,
            "final_pct": final_pct,
        })

    for c in computed:
        existing_pi = (
            db.table("performance_action_plan_phase_items").select("id")
            .eq("phase_id", ph["id"]).eq("action_plan_item_id", c["item_id"]).execute().data
        )
        payload = {
            "result": c["result"],
            "pct_awarded": c["pct_awarded"],
            "justification": c["justification"],
            "phase4_override_100": c["phase4_override_100"],
            "phase4_final_justification": c["phase4_final_justification"],
            "answered_at": "now()",
        }
        if existing_pi:
            db.table("performance_action_plan_phase_items").update(payload).eq("id", existing_pi[0]["id"]).execute()
        else:
            db.table("performance_action_plan_phase_items").insert({
                **payload, "phase_id": ph["id"], "action_plan_item_id": c["item_id"],
            }).execute()
        db.table("performance_action_plan_items").update(
            {"cumulative_pct": c["final_pct"]}
        ).eq("id", c["item_id"]).execute()

    db.table("performance_action_plan_phases").update({
        "status": "completed", "completed_at": "now()",
    }).eq("id", ph["id"]).execute()

    plan_completed = False
    if is_final_phase:
        db.table("performance_action_plans").update({"status": "completed"}).eq("id", p["id"]).execute()
        plan_completed = True

    _logger.info(
        "AUDIT action_plan_checkin_submitted | token=%s | action_plan_id=%s | phase=%s",
        token, p["id"], ph["phase_number"],
    )
    return {"ok": True, "plan_completed": plan_completed}
