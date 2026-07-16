import logging
import time
import uuid
from datetime import date
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, status
from pydantic import BaseModel

from auth import require_role
from db import get_supabase, get_settings
from services.audit import log_action

router = APIRouter(prefix="/api/performance/evaluations")
_logger = logging.getLogger(__name__)

_PERF_ROLES = ("admin", "rh", "gerente", "coordenador_supervisor")
_RH_ADMIN = ("admin", "rh")

# Pausa entre envios em massa — evita rajada que o Office 365 trata como abuso e bloqueia.
EMAIL_PACING_SECONDS = 1.5


def _send_evaluation_tokens_background(to_send: list[dict], cycle_id: str, actor: str) -> None:
    from services.email import send_evaluation_token_email

    sent_emails = 0
    for i, item in enumerate(to_send):
        if i > 0:
            time.sleep(EMAIL_PACING_SECONDS)
        ok = send_evaluation_token_email(
            evaluator_name=item["evaluator_name"], evaluator_email=item["evaluator_email"],
            employee_name=item["employee_name"], employee_cargo=item["employee_cargo"],
            company_name=item["company_name"], branch_name=item["branch_name"],
            cycle_name=item["cycle_name"], token=item["token"], frontend_url=item["frontend_url"],
        )
        if ok:
            sent_emails += 1
    log_action(
        "cycle", cycle_id, "send_tokens_background", None,
        {"sent_emails": sent_emails, "total": len(to_send)},
        actor, None,
    )


# ── Models ────────────────────────────────────────────────────────────────────

class CycleCreate(BaseModel):
    name: str
    period_start: date
    period_end: date
    company_id: str | None = None


class ReopenBody(BaseModel):
    justification: str
    company_id: str | None = None
    period_start: date | None = None
    period_end: date | None = None


class SendTokensBody(BaseModel):
    company_id: str | None = None


# ── Cycles ────────────────────────────────────────────────────────────────────

@router.get("/cycles")
def list_cycles(
    _: Annotated[dict, Depends(require_role(*_PERF_ROLES))],
) -> list[dict]:
    db = get_supabase()
    return db.table("performance_cycles").select("*").order("created_at", desc=True).execute().data


@router.post("/cycles", status_code=status.HTTP_201_CREATED)
def create_cycle(
    body: CycleCreate,
    request: Request,
    current_user: Annotated[dict, Depends(require_role(*_RH_ADMIN))],
) -> dict:
    db = get_supabase()

    # Guard: não pode criar se já existe ciclo 'open'
    open_cycles = db.table("performance_cycles").select("id,name").eq("status", "open").execute().data
    if open_cycles:
        raise HTTPException(
            status_code=400,
            detail=f"Já existe um ciclo em aberto: '{open_cycles[0]['name']}'. Encerre-o antes de criar um novo.",
        )

    payload = {
        "name": body.name,
        "period_start": body.period_start.isoformat(),
        "period_end": body.period_end.isoformat(),
        "status": "draft",
        "created_by": current_user["username"],
    }
    if body.company_id:
        payload["company_id"] = body.company_id

    result = db.table("performance_cycles").insert(payload).execute()
    if not result.data:
        raise HTTPException(status_code=500, detail="Erro ao criar ciclo")
    cycle = result.data[0]
    log_action("cycle", cycle["id"], "create", None, cycle, current_user["username"], request)
    return cycle


@router.post("/cycles/{cycle_id}/open")
def open_cycle(
    cycle_id: str,
    request: Request,
    current_user: Annotated[dict, Depends(require_role(*_RH_ADMIN))],
) -> dict:
    db = get_supabase()
    cycle = db.table("performance_cycles").select("*").eq("id", cycle_id).execute()
    if not cycle.data:
        raise HTTPException(status_code=404, detail="Ciclo não encontrado")
    if cycle.data[0]["status"] != "draft":
        raise HTTPException(status_code=400, detail="Apenas ciclos em rascunho podem ser abertos")

    db.table("performance_cycles").update({"status": "open"}).eq("id", cycle_id).execute()
    log_action("cycle", cycle_id, "open", {"status": "draft"}, {"status": "open"}, current_user["username"], request)
    # Invalida cache do dashboard
    try:
        from routes.admin import _cache_invalidate_prefix
        _cache_invalidate_prefix("dashboard:")
    except Exception:
        pass
    return {"ok": True, "cycle_id": cycle_id, "status": "open"}


@router.post("/cycles/{cycle_id}/close")
def close_cycle(
    cycle_id: str,
    request: Request,
    current_user: Annotated[dict, Depends(require_role(*_RH_ADMIN))],
) -> dict:
    db = get_supabase()
    cycle = db.table("performance_cycles").select("*").eq("id", cycle_id).execute()
    if not cycle.data:
        raise HTTPException(status_code=404, detail="Ciclo não encontrado")
    if cycle.data[0]["status"] != "open":
        raise HTTPException(status_code=400, detail="Apenas ciclos abertos podem ser encerrados")

    # Invalidar todos os tokens não utilizados
    db.table("performance_evaluation_tokens").update({
        "invalidated_at": "now()",
    }).eq("cycle_id", cycle_id).eq("is_used", False).is_("invalidated_at", "null").execute()

    db.table("performance_cycles").update({"status": "closed"}).eq("id", cycle_id).execute()
    log_action("cycle", cycle_id, "close", {"status": "open"}, {"status": "closed"}, current_user["username"], request)
    try:
        from routes.admin import _cache_invalidate_prefix
        _cache_invalidate_prefix("dashboard:")
    except Exception:
        pass
    return {"ok": True, "cycle_id": cycle_id, "status": "closed"}


@router.post("/cycles/{cycle_id}/reopen")
def reopen_cycle(
    cycle_id: str,
    body: ReopenBody,
    request: Request,
    current_user: Annotated[dict, Depends(require_role(*_RH_ADMIN))],
) -> dict:
    if not body.justification.strip():
        raise HTTPException(400, detail="Justificativa é obrigatória para reabrir o ciclo")

    db = get_supabase()
    cycle = db.table("performance_cycles").select("*").eq("id", cycle_id).execute()
    if not cycle.data:
        raise HTTPException(status_code=404, detail="Ciclo não encontrado")
    if cycle.data[0]["status"] != "closed":
        raise HTTPException(status_code=400, detail="Apenas ciclos encerrados podem ser reabertos")

    # Salvar registro de reabertura
    reopen_payload: dict = {
        "cycle_id": cycle_id,
        "justification": body.justification.strip(),
        "reopened_by": current_user["username"],
    }
    if body.company_id:
        reopen_payload["company_id"] = body.company_id
    if body.period_start:
        reopen_payload["period_start"] = body.period_start.isoformat()
    if body.period_end:
        reopen_payload["period_end"] = body.period_end.isoformat()

    db.table("performance_cycle_reopens").insert(reopen_payload).execute()

    # Atualizar ciclo
    cycle_updates: dict = {"status": "open"}
    if body.period_start:
        cycle_updates["period_start"] = body.period_start.isoformat()
    if body.period_end:
        cycle_updates["period_end"] = body.period_end.isoformat()

    db.table("performance_cycles").update(cycle_updates).eq("id", cycle_id).execute()
    log_action("cycle", cycle_id, "reopen", {"status": "closed"}, {"status": "open"}, current_user["username"], request)
    return {"ok": True, "cycle_id": cycle_id, "status": "open"}


@router.post("/cycles/{cycle_id}/send-tokens")
def send_tokens(
    cycle_id: str,
    body: SendTokensBody,
    request: Request,
    background_tasks: BackgroundTasks,
    current_user: Annotated[dict, Depends(require_role(*_RH_ADMIN))],
) -> dict:
    db = get_supabase()
    cycle = db.table("performance_cycles").select("*").eq("id", cycle_id).execute()
    if not cycle.data:
        raise HTTPException(404, detail="Ciclo não encontrado")
    if cycle.data[0]["status"] != "open":
        raise HTTPException(400, detail="O ciclo precisa estar aberto para enviar tokens")

    s = get_settings()
    frontend_url = s.allowed_origins.split(",")[0].strip().rstrip("/")
    cycle_name = cycle.data[0]["name"]

    # Buscar avaliadores: hierarchy_level 1 (Gerente), 2 (Coordenador-Supervisor) e 4 (Diretoria)
    query = db.table("performance_employees").select(
        "*, performance_branches(name), performance_companies(name)"
    ).in_("hierarchy_level", [1, 2, 4]).eq("active", True)

    if body.company_id:
        query = query.eq("company_id", body.company_id)

    evaluators = query.execute().data

    no_email_count = 0
    tokens_created = 0

    from collections import defaultdict as _dd

    # Pre-fetch subordinados e tokens existentes para eliminar N+1 queries
    _eval_ids = [ev["id"] for ev in evaluators]
    _all_subs = db.table("performance_employees").select(
        "id,name,cargo,hierarchy_level,manager_id"
    ).in_("manager_id", _eval_ids).eq("active", True).execute().data or []
    _subs_by_mgr: dict = _dd(list)
    for _s in _all_subs:
        _subs_by_mgr[_s["manager_id"]].append(_s)

    _all_sub_ids = [s["id"] for s in _all_subs]
    _existing_tok_map: dict = {}
    if _eval_ids and _all_sub_ids:
        _tok_rows = db.table("performance_evaluation_tokens").select(
            "evaluator_id,employee_id,token"
        ).eq("cycle_id", cycle_id).eq("is_used", False).is_(
            "invalidated_at", "null"
        ).in_("evaluator_id", _eval_ids).execute().data or []
        for _t in _tok_rows:
            _existing_tok_map[(_t["evaluator_id"], _t["employee_id"])] = _t["token"]

    to_send: list[dict] = []

    for ev in evaluators:
        subs_list = _subs_by_mgr.get(ev["id"], [])
        if not subs_list:
            continue

        branch_name  = ev.get("performance_branches",  {}).get("name", "") if isinstance(ev.get("performance_branches"),  dict) else ""
        company_name = ev.get("performance_companies", {}).get("name", "") if isinstance(ev.get("performance_companies"), dict) else ""

        # Um token por par (avaliador × subordinado) — formulário pré-vinculado
        for emp in subs_list:
            _cached_tok = _existing_tok_map.get((ev["id"], emp["id"]))
            if _cached_tok:
                token_value = _cached_tok
            else:
                token_value = str(uuid.uuid4())
                token_res = db.table("performance_evaluation_tokens").insert({
                    "cycle_id":    cycle_id,
                    "evaluator_id": ev["id"],
                    "employee_id":  emp["id"],
                    "token":        token_value,
                    "is_used":      False,
                    "resend_count": 0,
                }).execute()
                if not token_res.data:
                    continue
                tokens_created += 1

            # Enviar e-mail apenas para avaliadores com e-mail corporativo — feito em
            # background (com pacing) logo abaixo, pra não estourar limite do Office 365
            # nem segurar a resposta HTTP em ciclos com muitos colaboradores.
            if ev.get("has_corporate_email") and ev.get("email"):
                to_send.append({
                    "evaluator_name": ev["name"], "evaluator_email": ev["email"],
                    "employee_name": emp["name"], "employee_cargo": emp.get("cargo", ""),
                    "company_name": company_name, "branch_name": branch_name,
                    "cycle_name": cycle_name, "token": token_value, "frontend_url": frontend_url,
                })
            else:
                no_email_count += 1

    background_tasks.add_task(_send_evaluation_tokens_background, to_send, cycle_id, current_user["username"])

    log_action(
        "cycle", cycle_id, "send_tokens", None,
        {"tokens_created": tokens_created, "destinatarios_estimados": len(to_send), "no_email_count": no_email_count},
        current_user["username"], request,
    )
    return {
        "status": "iniciado",
        "tokens_criados": tokens_created,
        "destinatarios_estimados": len(to_send),
        "sem_email": no_email_count,
    }


@router.post("/cycles/{cycle_id}/resend-token/{evaluator_id}")
def resend_token(
    cycle_id: str,
    evaluator_id: str,
    request: Request,
    current_user: Annotated[dict, Depends(require_role(*_RH_ADMIN))],
) -> dict:
    db = get_supabase()

    cycle = db.table("performance_cycles").select("name,status").eq("id", cycle_id).execute()
    if not cycle.data:
        raise HTTPException(404, detail="Ciclo não encontrado")
    if cycle.data[0]["status"] != "open":
        raise HTTPException(400, detail="O ciclo precisa estar aberto para reenviar tokens")

    token_row = (
        db.table("performance_evaluation_tokens")
        .select("*")
        .eq("cycle_id", cycle_id)
        .eq("evaluator_id", evaluator_id)
        .eq("is_used", False)
        .is_("invalidated_at", "null")
        .execute()
    )
    if not token_row.data:
        raise HTTPException(404, detail="Token não encontrado ou já utilizado")

    t = token_row.data[0]
    token_value = t["token"]

    ev = db.table("performance_employees").select(
        "*, performance_branches(name), performance_companies(name)"
    ).eq("id", evaluator_id).execute()
    if not ev.data:
        raise HTTPException(404, detail="Avaliador não encontrado")
    ev_data = ev.data[0]

    if not ev_data.get("has_corporate_email") or not ev_data.get("email"):
        raise HTTPException(400, detail="Avaliador não possui e-mail corporativo")

    s = get_settings()
    frontend_url = s.allowed_origins.split(",")[0].strip().rstrip("/")
    cycle_name = cycle.data[0]["name"]

    branch_name = ev_data.get("performance_branches", {}).get("name", "") if isinstance(ev_data.get("performance_branches"), dict) else ""
    company_name = ev_data.get("performance_companies", {}).get("name", "") if isinstance(ev_data.get("performance_companies"), dict) else ""

    # Fetch employee info linked to this token
    employee_name = ""
    employee_cargo = ""
    if t.get("employee_id"):
        emp = db.table("performance_employees").select("name,cargo").eq("id", t["employee_id"]).execute()
        if emp.data:
            employee_name = emp.data[0]["name"]
            employee_cargo = emp.data[0].get("cargo", "")

    from services.email import send_evaluation_token_email
    ok = send_evaluation_token_email(
        evaluator_name=ev_data["name"],
        evaluator_email=ev_data["email"],
        employee_name=employee_name,
        employee_cargo=employee_cargo,
        company_name=company_name,
        branch_name=branch_name,
        cycle_name=cycle_name,
        token=token_value,
        frontend_url=frontend_url,
    )

    if ok:
        new_count = (t.get("resend_count") or 0) + 1
        db.table("performance_evaluation_tokens").update({
            "resend_count": new_count,
            "last_resent_at": "now()",
        }).eq("id", t["id"]).execute()

    log_action("token", t["id"], "resend", None, {"evaluator_id": evaluator_id}, current_user["username"], request)
    return {"ok": ok, "evaluator_id": evaluator_id}


# ── Tokens ────────────────────────────────────────────────────────────────────

@router.get("/tokens")
def list_tokens(
    current_user: Annotated[dict, Depends(require_role(*_RH_ADMIN))],
    cycle_id: str,
) -> list[dict]:
    db = get_supabase()
    tokens = (
        db.table("performance_evaluation_tokens")
        .select("*, performance_employees(name, email, has_corporate_email, hierarchy_level)")
        .eq("cycle_id", cycle_id)
        .order("created_at", desc=True)
        .execute()
        .data
    )
    return tokens


# ── Reviews ───────────────────────────────────────────────────────────────────

@router.get("/reviews")
def list_reviews(
    current_user: Annotated[dict, Depends(require_role(*_PERF_ROLES))],
    cycle_id: str | None = None,
    employee_id: str | None = None,
) -> list[dict]:
    db = get_supabase()
    query = db.table("performance_reviews").select("*")

    role = current_user.get("role")
    if role in ("gerente", "coordenador_supervisor"):
        # Filtra pelo manager_id do usuário logado
        emp = db.table("performance_employees").select("id").eq("jarvis_username", current_user.get("username")).execute()
        if emp.data:
            manager_id = emp.data[0]["id"]
            # Busca subordinados diretos
            subs = db.table("performance_employees").select("id").eq("manager_id", manager_id).eq("active", True).execute()
            sub_ids = [s["id"] for s in subs.data] if subs.data else []
            if sub_ids:
                query = query.in_("employee_id", sub_ids)
            else:
                return []
        else:
            return []
    elif employee_id:
        query = query.eq("employee_id", employee_id)

    if cycle_id:
        query = query.eq("cycle_id", cycle_id)

    return query.order("created_at", desc=True).execute().data
