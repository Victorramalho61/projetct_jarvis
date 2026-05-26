import logging
import re
import unicodedata
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from db import get_supabase, get_settings

router = APIRouter(prefix="/api/performance/public")
_logger = logging.getLogger(__name__)

def _normalize_name(name: str) -> str:
    """Normaliza nome para comparação: lowercase, sem acentos, sem espaços extras"""
    name = unicodedata.normalize("NFKD", name).encode("ASCII", "ignore").decode()
    return " ".join(name.lower().split())

# ── Avaliação por token ────────────────────────────────────────────────────────

@router.get("/avaliar/{token}")
def get_evaluation_form(token: str) -> dict:
    db = get_supabase()
    token_data = db.table("performance_evaluation_tokens").select("*").eq("token", token).execute()
    if not token_data.data:
        raise HTTPException(404, detail="Link de avaliação inválido ou expirado.")
    t = token_data.data[0]
    if t["is_used"]:
        raise HTTPException(400, detail="Este link já foi utilizado. A avaliação já foi submetida.")
    if t.get("invalidated_at"):
        raise HTTPException(400, detail="Este link foi invalidado. O ciclo foi encerrado.")

    cycle = db.table("performance_cycles").select("*").eq("id", t["cycle_id"]).execute()
    if not cycle.data or cycle.data[0]["status"] != "open":
        raise HTTPException(400, detail="O ciclo de avaliação está encerrado.")

    evaluator = db.table("performance_employees").select("*, performance_branches(name), performance_companies(name)").eq("id", t["evaluator_id"]).execute()
    if not evaluator.data:
        raise HTTPException(404, detail="Avaliador não encontrado.")
    ev = evaluator.data[0]

    # Colaborador a ser avaliado (um por token)
    employee_id = t.get("employee_id")
    if not employee_id:
        raise HTTPException(400, detail="Token sem colaborador vinculado. Gere novos tokens.")
    employee = db.table("performance_employees").select("id,name,matricula,cargo,hierarchy_level").eq("id", employee_id).execute()
    if not employee.data:
        raise HTTPException(404, detail="Colaborador não encontrado.")
    emp = employee.data[0]

    emp_level = emp.get("hierarchy_level") or 3
    ind_q = db.table("performance_indicators").select("id,name,description").eq("active", True).eq("hierarchy_level", emp_level)
    indicators = ind_q.order("created_at").execute().data

    branch_name = (ev.get("performance_branches") or {}).get("name", "") if isinstance(ev.get("performance_branches"), dict) else ""
    company_name = (ev.get("performance_companies") or {}).get("name", "") if isinstance(ev.get("performance_companies"), dict) else ""

    return {
        "evaluator_name": ev["name"],
        "company_name": company_name,
        "branch_name": branch_name,
        "cycle_name": cycle.data[0]["name"],
        "cycle_id": t["cycle_id"],
        "employee": {"id": emp["id"], "name": emp["name"], "matricula": emp.get("matricula", ""), "cargo": emp.get("cargo", ""), "hierarchy_level": emp_level},
        "indicators": indicators,
    }


class IndicatorScore(BaseModel):
    indicator_id: str
    score: float


class EvaluationSubmit(BaseModel):
    indicator_scores: list[IndicatorScore]


@router.post("/avaliar/{token}")
def submit_evaluation(token: str, body: EvaluationSubmit, request: Request) -> dict:
    db = get_supabase()
    token_data = db.table("performance_evaluation_tokens").select("*").eq("token", token).execute()
    if not token_data.data:
        raise HTTPException(404, detail="Link de avaliação inválido.")
    t = token_data.data[0]
    if t["is_used"]:
        raise HTTPException(400, detail="Este link já foi utilizado.")
    if t.get("invalidated_at"):
        raise HTTPException(400, detail="Este link foi invalidado. O ciclo foi encerrado.")

    cycle = db.table("performance_cycles").select("*").eq("id", t["cycle_id"]).execute()
    if not cycle.data or cycle.data[0]["status"] != "open":
        raise HTTPException(400, detail="O ciclo de avaliação está encerrado.")

    employee_id = t.get("employee_id")
    if not employee_id:
        raise HTTPException(400, detail="Token sem colaborador vinculado.")

    scores_list = [sc.score for sc in body.indicator_scores]
    if not scores_list:
        raise HTTPException(400, detail="Nenhuma nota informada.")
    for sc in scores_list:
        if sc < 1 or sc > 5:
            raise HTTPException(400, detail=f"Nota {sc} inválida. Use valores de 1 a 5.")

    final_score = round(sum(scores_list) / len(scores_list), 2)

    existing_review = db.table("performance_reviews").select("id").eq("cycle_id", t["cycle_id"]).eq("employee_id", employee_id).execute()
    if existing_review.data:
        review_id = existing_review.data[0]["id"]
        db.table("performance_reviews").update({
            "evaluator_id": t["evaluator_id"],
            "status": "completed",
            "final_score": final_score,
            "submitted_at": "now()",
            "updated_at": "now()",
        }).eq("id", review_id).execute()
    else:
        review_res = db.table("performance_reviews").insert({
            "cycle_id": t["cycle_id"],
            "employee_id": employee_id,
            "evaluator_id": t["evaluator_id"],
            "status": "completed",
            "final_score": final_score,
            "submitted_at": "now()",
        }).execute()
        if not review_res.data:
            raise HTTPException(500, detail="Erro ao salvar avaliação.")
        review_id = review_res.data[0]["id"]

    db.table("performance_indicator_scores").delete().eq("review_id", review_id).execute()
    score_rows = [{"review_id": review_id, "indicator_id": sc.indicator_id, "score": sc.score} for sc in body.indicator_scores]
    db.table("performance_indicator_scores").insert(score_rows).execute()

    # Marcar token como usado
    db.table("performance_evaluation_tokens").update({"is_used": True, "used_at": "now()"}).eq("token", token).execute()

    # Enviar ciência por e-mail se colaborador tem e-mail corporativo
    s = get_settings()
    frontend_url = s.allowed_origins.split(",")[0].strip().rstrip("/")
    employee = db.table("performance_employees").select("*").eq("id", employee_id).execute()
    if employee.data:
        emp = employee.data[0]
        if emp.get("has_corporate_email") and emp.get("email"):
            ack_token_res = db.table("performance_acknowledgment_tokens").insert({
                "review_id": review_id,
                "employee_id": emp["id"],
                "sent_at": "now()",
                "expires_at": (datetime.now(tz=timezone.utc) + timedelta(days=30)).isoformat(),
            }).execute()
            if ack_token_res.data:
                ack_token = ack_token_res.data[0]["token"]
                evaluator = db.table("performance_employees").select("name").eq("id", t["evaluator_id"]).execute()
                evaluator_name = evaluator.data[0]["name"] if evaluator.data else "seu gestor"
                company_name = ""
                if emp.get("company_id"):
                    co = db.table("performance_companies").select("name").eq("id", emp["company_id"]).execute()
                    company_name = co.data[0]["name"] if co.data else ""
                from services.email import send_ciencia_email
                send_ciencia_email(
                    employee_name=emp["name"],
                    employee_email=emp["email"],
                    evaluator_name=evaluator_name,
                    cycle_name=cycle.data[0]["name"],
                    token=str(ack_token),
                    frontend_url=frontend_url,
                    company_name=company_name,
                )

    return {"ok": True}

# ── Ciência por token de e-mail ───────────────────────────────────────────────

@router.get("/ciencia/{token}")
def get_ciencia_form(token: str) -> dict:
    db = get_supabase()
    ack_token = db.table("performance_acknowledgment_tokens").select("*").eq("token", token).execute()
    if not ack_token.data:
        raise HTTPException(404, detail="Link de ciência inválido.")
    at = ack_token.data[0]
    if at.get("used_at"):
        raise HTTPException(400, detail="Este link já foi utilizado. A ciência já foi registrada.")
    if at.get("expires_at"):
        expires = datetime.fromisoformat(at["expires_at"].replace("Z", "+00:00"))
        if datetime.now(tz=timezone.utc) > expires:
            raise HTTPException(400, detail="Este link expirou. Entre em contato com o RH.")

    review = db.table("performance_reviews").select("*").eq("id", at["review_id"]).execute()
    if not review.data:
        raise HTTPException(404, detail="Avaliação não encontrada.")
    rev = review.data[0]

    employee = db.table("performance_employees").select("name").eq("id", at["employee_id"]).execute()
    evaluator = db.table("performance_employees").select("name").eq("id", rev.get("evaluator_id")).execute()
    cycle = db.table("performance_cycles").select("name").eq("id", rev["cycle_id"]).execute()

    # Buscar scores por indicador
    scores_raw = db.table("performance_indicator_scores").select("*, performance_indicators(name,description)").eq("review_id", rev["id"]).execute().data
    indicator_scores = []
    for s in scores_raw:
        ind = s.get("performance_indicators", {}) or {}
        indicator_scores.append({
            "indicator_id": s["indicator_id"],
            "indicator_name": ind.get("name", ""),
            "indicator_description": ind.get("description", ""),
            "score": s["score"],
        })

    # Verificar se já deu ciência
    existing_ack = db.table("performance_review_acknowledgments").select("*").eq("review_id", rev["id"]).eq("employee_id", at["employee_id"]).execute()
    already_acknowledged = bool(existing_ack.data)
    acknowledged_at = existing_ack.data[0]["acknowledged_at"] if already_acknowledged else None

    # Buscar empresa do colaborador para branding correto no frontend
    company_name = ""
    emp_full = db.table("performance_employees").select("company_id").eq("id", at["employee_id"]).execute()
    if emp_full.data and emp_full.data[0].get("company_id"):
        co = db.table("performance_companies").select("name").eq("id", emp_full.data[0]["company_id"]).execute()
        company_name = co.data[0]["name"] if co.data else ""

    return {
        "employee_name": employee.data[0]["name"] if employee.data else "",
        "evaluator_name": evaluator.data[0]["name"] if evaluator.data else "",
        "cycle_name": cycle.data[0]["name"] if cycle.data else "",
        "final_score": rev.get("final_score"),
        "indicator_scores": indicator_scores,
        "already_acknowledged": already_acknowledged,
        "acknowledged_at": acknowledged_at,
        "company_name": company_name,
    }

class AcknowledgeBody(BaseModel):
    feedback_received: bool

@router.post("/ciencia/{token}")
def submit_ciencia(token: str, body: AcknowledgeBody, request: Request) -> dict:
    db = get_supabase()
    ack_token = db.table("performance_acknowledgment_tokens").select("*").eq("token", token).execute()
    if not ack_token.data:
        raise HTTPException(404, detail="Link de ciência inválido.")
    at = ack_token.data[0]
    if at.get("used_at"):
        raise HTTPException(400, detail="Ciência já registrada.")

    # Verificar se já existe ciência para esta review
    existing = db.table("performance_review_acknowledgments").select("id").eq("review_id", at["review_id"]).eq("employee_id", at["employee_id"]).execute()
    if existing.data:
        raise HTTPException(400, detail="Ciência já registrada.")

    db.table("performance_review_acknowledgments").insert({
        "review_id": at["review_id"],
        "employee_id": at["employee_id"],
        "feedback_received": body.feedback_received,
        "acknowledged_via": "email",
        "ip_address": request.client.host if request.client else None,
    }).execute()

    db.table("performance_acknowledgment_tokens").update({"used_at": "now()"}).eq("token", token).execute()

    return {"ok": True, "acknowledged_at": datetime.now(tz=timezone.utc).isoformat()}

# ── Ciência presencial (sem e-mail) ───────────────────────────────────────────

class CienciaPresencialBusca(BaseModel):
    nome: str
    cpf: str  # 11 dígitos numéricos, sem máscara


class CienciaPresencialConfirmar(BaseModel):
    cpf: str
    review_id: str
    feedback_received: bool


MAX_ATTEMPTS = 3
BLOCK_MINUTES = 5


@router.post("/ciencia-presencial/buscar")
def buscar_ciencia_presencial(body: CienciaPresencialBusca, request: Request) -> dict:
    db = get_supabase()
    ip = request.client.host if request.client else "unknown"

    cutoff = (datetime.now(tz=timezone.utc) - timedelta(minutes=BLOCK_MINUTES)).isoformat()
    attempts = db.table("performance_ciencia_attempts").select("id").eq("ip_address", ip).gte("attempted_at", cutoff).execute()
    if len(attempts.data) >= MAX_ATTEMPTS:
        raise HTTPException(429, detail=f"Muitas tentativas incorretas. Aguarde {BLOCK_MINUTES} minutos.")

    cpf_clean = re.sub(r'\D', '', body.cpf.strip())
    if len(cpf_clean) != 11:
        raise HTTPException(400, detail="CPF inválido. Informe os 11 dígitos numéricos.")

    employees = db.table("performance_employees").select("*").eq("cpf", cpf_clean).eq("active", True).execute().data

    def _log_attempt():
        db.table("performance_ciencia_attempts").insert({"matricula": cpf_clean, "ip_address": ip}).execute()

    if not employees:
        _log_attempt()
        raise HTTPException(404, detail="Colaborador não encontrado. Verifique o CPF e tente novamente.")

    employee = employees[0]

    if employee.get("has_corporate_email"):
        _log_attempt()
        raise HTTPException(400, detail="Este colaborador possui e-mail corporativo. Use o link enviado por e-mail para dar sua ciência.")

    nome_digitado = _normalize_name(body.nome)
    nome_cadastrado = _normalize_name(employee["name"])
    if nome_digitado != nome_cadastrado:
        _log_attempt()
        raise HTTPException(404, detail="Dados incorretos. Verifique se o nome está exatamente como registrado pelo RH.")

    open_cycles = db.table("performance_cycles").select("id,name").eq("status", "open").execute().data
    if not open_cycles:
        raise HTTPException(400, detail="Não há ciclo de avaliação aberto no momento. Procure o RH.")

    cycle = open_cycles[0]
    review = db.table("performance_reviews").select("*").eq("employee_id", employee["id"]).eq("cycle_id", cycle["id"]).execute()

    if not review.data:
        raise HTTPException(404, detail="Nenhuma avaliação disponível para sua ciência no momento.")

    rev = review.data[0]

    existing_ack = db.table("performance_review_acknowledgments").select("*").eq("review_id", rev["id"]).eq("employee_id", employee["id"]).execute()
    if existing_ack.data:
        ack = existing_ack.data[0]
        return {
            "already_acknowledged": True,
            "acknowledged_at": ack.get("acknowledged_at"),
            "employee_name": employee["name"],
        }

    evaluator = db.table("performance_employees").select("name").eq("id", rev.get("evaluator_id")).execute()
    scores_raw = db.table("performance_indicator_scores").select("*, performance_indicators(name,description)").eq("review_id", rev["id"]).execute().data

    indicator_scores = []
    for s in scores_raw:
        ind = s.get("performance_indicators") or {}
        indicator_scores.append({
            "indicator_id": s["indicator_id"],
            "indicator_name": ind.get("name", ""),
            "score": s["score"],
        })

    company_name = ""
    if employee.get("company_id"):
        co = db.table("performance_companies").select("name").eq("id", employee["company_id"]).execute()
        company_name = co.data[0]["name"] if co.data else ""

    return {
        "already_acknowledged": False,
        "review_id": rev["id"],
        "employee_name": employee["name"],
        "evaluator_name": evaluator.data[0]["name"] if evaluator.data else "",
        "cycle_name": cycle["name"],
        "final_score": rev.get("final_score"),
        "indicator_scores": indicator_scores,
        "company_name": company_name,
    }


@router.post("/ciencia-presencial/confirmar")
def confirmar_ciencia_presencial(body: CienciaPresencialConfirmar, request: Request) -> dict:
    db = get_supabase()
    ip = request.client.host if request.client else None

    cpf_clean = re.sub(r'\D', '', body.cpf.strip())
    employee = db.table("performance_employees").select("id,name").eq("cpf", cpf_clean).eq("has_corporate_email", False).eq("active", True).execute()
    if not employee.data:
        raise HTTPException(404, detail="Colaborador não encontrado.")
    emp = employee.data[0]

    review = db.table("performance_reviews").select("id").eq("id", body.review_id).eq("employee_id", emp["id"]).execute()
    if not review.data:
        raise HTTPException(404, detail="Avaliação não encontrada.")

    existing = db.table("performance_review_acknowledgments").select("id").eq("review_id", body.review_id).eq("employee_id", emp["id"]).execute()
    if existing.data:
        raise HTTPException(400, detail="Ciência já registrada para este colaborador.")

    now_iso = datetime.now(tz=timezone.utc).isoformat()
    db.table("performance_review_acknowledgments").insert({
        "review_id": body.review_id,
        "employee_id": emp["id"],
        "feedback_received": body.feedback_received,
        "acknowledged_via": "presencial",
        "ip_address": ip,
    }).execute()

    return {"ok": True, "acknowledged_at": now_iso, "employee_name": emp["name"]}
