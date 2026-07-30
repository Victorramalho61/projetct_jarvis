"""Plano de Ação - Feedback — formulários públicos (sem login), acessados por token.

Arquivo isolado de routes/public.py de propósito (não deve ser tocado — sustenta
o fluxo real de avaliação/ciência que não pode sofrer nenhum risco de regressão).
Duplica localmente o helper de validação de UUID em vez de importar de lá.
"""
import logging
import uuid as _uuid_mod

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from db import get_supabase
from limiter import limiter

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
    rows = db.table("performance_employees").select("id,name,company_id").in_("id", ids).execute().data or []
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

    cycle = db.table("performance_cycles").select("name").eq("id", p["cycle_id"]).execute()
    cycle_name = cycle.data[0]["name"] if cycle.data else ""

    emp_map = _resolve_employees(db, [p["employee_id"], p["manager_id"]])
    employee = emp_map.get(p["employee_id"])
    manager = emp_map.get(p["manager_id"])
    if not employee:
        raise HTTPException(404, detail="Colaborador não encontrado.")

    company_name = ""
    if employee.get("company_id"):
        co = db.table("performance_companies").select("name").eq("id", employee["company_id"]).execute()
        company_name = co.data[0]["name"] if co.data else ""

    items = (
        db.table("performance_action_plan_items")
        .select("id,original_score,performance_indicators(name,description)")
        .eq("action_plan_id", p["id"]).execute().data
    ) or []

    return {
        "employee_name": employee["name"],
        "cycle_name": cycle_name,
        "company_name": company_name,
        "manager_name": manager["name"] if manager else "",
        "items": [
            {
                "item_id": i["id"],
                "indicator_name": (i.get("performance_indicators") or {}).get("name", ""),
                "indicator_description": (i.get("performance_indicators") or {}).get("description", ""),
                "original_score": i["original_score"],
            }
            for i in items
        ],
    }


class InitialItemBody(BaseModel):
    item_id: str
    plan_text: str


class InitialFormSubmit(BaseModel):
    items: list[InitialItemBody]


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

    existing_items = (
        db.table("performance_action_plan_items").select("id").eq("action_plan_id", p["id"]).execute().data
    ) or []
    existing_ids = {i["id"] for i in existing_items}
    if not body.items:
        raise HTTPException(400, detail="Informe o plano de ação para cada competência.")

    sent_ids = {i.item_id for i in body.items}
    if sent_ids != existing_ids:
        raise HTTPException(400, detail="É necessário preencher o plano de ação de todas as competências listadas.")
    for item in body.items:
        if not item.plan_text.strip():
            raise HTTPException(400, detail="O plano de ação não pode ficar em branco para nenhuma competência.")

    for item in body.items:
        db.table("performance_action_plan_items").update(
            {"plan_text": item.plan_text.strip()}
        ).eq("id", item.item_id).execute()

    db.table("performance_action_plans").update({
        "status": "active",
        "initial_token_used_at": "now()",
        "initial_form_filled_at": "now()",
    }).eq("id", p["id"]).execute()

    _logger.info("AUDIT action_plan_initial_submitted | token=%s | action_plan_id=%s", token, p["id"])
    return {"ok": True}


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
        .select("id,plan_text,cumulative_pct,performance_indicators(name)")
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
