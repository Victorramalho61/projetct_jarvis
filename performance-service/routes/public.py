import logging
import re
import unicodedata
import uuid as _uuid_mod
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from db import get_supabase, get_settings
from limiter import limiter
from services.ciencia import build_ciencia_payload

router = APIRouter(prefix="/api/performance/public")
_logger = logging.getLogger(__name__)

_DADOS_NAO_ENCONTRADOS = (
    "Dados não encontrados. Verifique o CPF e o nome e tente novamente."
)


def _validate_uuid(token: str, label: str = "Link") -> None:
    """Rejeita tokens que não são UUID v4 válidos antes de ir ao banco."""
    try:
        _uuid_mod.UUID(token, version=4)
    except (ValueError, AttributeError):
        raise HTTPException(404, detail=f"{label} inválido ou expirado.")

def _normalize_name(name: str) -> str:
    """Normaliza nome para comparação: lowercase, sem acentos, sem espaços extras"""
    name = unicodedata.normalize("NFKD", name).encode("ASCII", "ignore").decode()
    return " ".join(name.lower().split())



# ── Avaliação por token ────────────────────────────────────────────────────────

@router.get("/avaliar/{token}")
@limiter.limit("20/minute")
def get_evaluation_form(token: str, request: Request) -> dict:
    _validate_uuid(token, "Link de avaliação")
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
    employee = db.table("performance_employees").select("id,name,matricula,cargo,hierarchy_level,perfil").eq("id", employee_id).execute()
    if not employee.data:
        raise HTTPException(404, detail="Colaborador não encontrado.")
    emp = employee.data[0]

    emp_level = emp.get("hierarchy_level") or 3
    emp_perfil = emp.get("perfil") or ""
    ind_q = db.table("performance_indicators").select("id,name,description").eq("active", True).eq("hierarchy_level", emp_level)
    if emp_level == 3 and emp_perfil in ("administrativo", "operacional"):
        ind_q = ind_q.eq("perfil", emp_perfil)
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
    justification: str | None = None  # obrigatório quando score == 1 ou 5


class EvaluationSubmit(BaseModel):
    indicator_scores: list[IndicatorScore]
    observations: str | None = None  # observações gerais do gestor (opcional)


@router.post("/avaliar/{token}")
@limiter.limit("5/minute")
def submit_evaluation(token: str, body: EvaluationSubmit, request: Request) -> dict:
    _validate_uuid(token, "Link de avaliação")
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
    for sc in body.indicator_scores:
        if sc.score < 1 or sc.score > 5:
            raise HTTPException(400, detail=f"Nota {sc.score} inválida. Use valores de 1 a 5.")
        if sc.score in (1.0, 5.0):
            just_words = len((sc.justification or "").split())
            if just_words < 10:
                label = "máxima (EE)" if sc.score == 5 else "mínima (NAE)"
                raise HTTPException(
                    400,
                    detail=f"Justificativa para nota {label} precisa ter pelo menos 10 palavras. "
                           f"Atualmente: {just_words} palavra(s).",
                )

    final_score = round(sum(scores_list) / len(scores_list), 2)

    existing_review = (
        db.table("performance_reviews")
        .select("id,status")
        .eq("cycle_id", t["cycle_id"])
        .eq("employee_id", employee_id)
        .eq("is_self_evaluation", False)
        .execute()
    )
    if existing_review.data:
        rev_status = existing_review.data[0].get("status", "pending")
        if rev_status in ("completed", "calibrated", "acknowledged"):
            raise HTTPException(
                400,
                detail="Esta avaliação já foi submetida e não pode ser alterada. "
                       "Contate o RH caso precise de uma nova avaliação.",
            )
        review_id = existing_review.data[0]["id"]
        db.table("performance_reviews").update({
            "evaluator_id": t["evaluator_id"],
            "status": "completed",
            "final_score": final_score,
            "observations": (body.observations or "").strip() or None,
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
            "observations": (body.observations or "").strip() or None,
            "submitted_at": "now()",
            "is_self_evaluation": False,
        }).execute()
        if not review_res.data:
            raise HTTPException(500, detail="Erro ao salvar avaliação.")
        review_id = review_res.data[0]["id"]

    db.table("performance_indicator_scores").delete().eq("review_id", review_id).execute()
    score_rows = [
        {
            "review_id": review_id,
            "indicator_id": sc.indicator_id,
            "score": sc.score,
            "justification": (sc.justification or "").strip() or None,
        }
        for sc in body.indicator_scores
    ]
    db.table("performance_indicator_scores").insert(score_rows).execute()

    # Marcar token como usado
    db.table("performance_evaluation_tokens").update({"is_used": True, "used_at": "now()"}).eq("token", token).execute()

    # Ciência não é mais disparada automaticamente aqui — o gestor/RH aciona
    # manualmente via "Reenviar Ciência" (routes/my.py resend_ciencia), tipicamente
    # após a calibração do RH.

    _logger.info(
        "AUDIT evaluation_submitted | ip=%s | token=%s | employee_id=%s | score=%s",
        request.client.host if request.client else "unknown", token, employee_id, final_score,
    )
    return {"ok": True}

# ── Ciência por token de e-mail ───────────────────────────────────────────────

@router.get("/ciencia/{token}")
@limiter.limit("20/minute")
def get_ciencia_form(token: str, request: Request) -> dict:
    _validate_uuid(token, "Link de ciência")
    db = get_supabase()
    ack_token = db.table("performance_acknowledgment_tokens").select("*").eq("token", token).execute()
    if not ack_token.data:
        raise HTTPException(404, detail="Link de ciência inválido.")
    at = ack_token.data[0]
    # NÃO bloqueia se token já utilizado — colaborador pode consultar resultado a qualquer momento
    # Verifica expiração apenas se token AINDA não foi utilizado (já utilizado = resultado permanente)
    if not at.get("used_at") and at.get("expires_at"):
        expires = datetime.fromisoformat(at["expires_at"].replace("Z", "+00:00"))
        if datetime.now(tz=timezone.utc) > expires:
            raise HTTPException(400, detail="Este link expirou. Entre em contato com o RH.")

    payload = build_ciencia_payload(db, at["review_id"])
    if payload is None:
        raise HTTPException(404, detail="Avaliação não encontrada.")
    return payload

class AcknowledgeBody(BaseModel):
    feedback_received: bool

@router.post("/ciencia/{token}")
@limiter.limit("5/minute")
def submit_ciencia(token: str, body: AcknowledgeBody, request: Request) -> dict:
    _validate_uuid(token, "Link de ciência")
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

    try:
        db.table("performance_review_acknowledgments").insert({
            "review_id": at["review_id"],
            "employee_id": at["employee_id"],
            "feedback_received": body.feedback_received,
            "acknowledged_via": "email",
            "ip_address": request.client.host if request.client else None,
        }).execute()
    except Exception as _ack_err:
        if any(k in str(_ack_err).lower() for k in ("23505", "duplicate", "unique")):
            raise HTTPException(status_code=400, detail="Ciência já registrada.")
        raise

    db.table("performance_acknowledgment_tokens").update({"used_at": "now()"}).eq("token", token).execute()

    _logger.info(
        "AUDIT ciencia_email_confirmed | ip=%s | token=%s | review_id=%s | employee_id=%s",
        request.client.host if request.client else "unknown", token, at["review_id"], at["employee_id"],
    )
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
@limiter.limit("10/minute")
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
        raise HTTPException(404, detail=_DADOS_NAO_ENCONTRADOS)

    employee = employees[0]

    # Acesso presencial disponível para todos (com ou sem e-mail corporativo)

    nome_digitado = _normalize_name(body.nome)
    nome_cadastrado = _normalize_name(employee["name"])
    if nome_digitado != nome_cadastrado:
        _log_attempt()
        raise HTTPException(404, detail=_DADOS_NAO_ENCONTRADOS)

    open_cycles = db.table("performance_cycles").select("id,name").eq("status", "open").execute().data
    if not open_cycles:
        raise HTTPException(400, detail="Não há ciclo de avaliação aberto no momento. Procure o RH.")

    cycle = open_cycles[0]
    review = (
        db.table("performance_reviews")
        .select("*")
        .eq("employee_id", employee["id"])
        .eq("cycle_id", cycle["id"])
        .eq("is_self_evaluation", False)
        .execute()
    )

    if not review.data:
        raise HTTPException(404, detail="Nenhuma avaliação disponível para sua ciência no momento.")

    rev = review.data[0]

    payload = build_ciencia_payload(db, rev["id"])
    if payload is None:
        raise HTTPException(404, detail="Avaliação não encontrada.")
    return {
        "review_id": rev["id"],
        **payload,
    }


@router.post("/ciencia-presencial/confirmar")
@limiter.limit("5/minute")
def confirmar_ciencia_presencial(body: CienciaPresencialConfirmar, request: Request) -> dict:
    db = get_supabase()
    ip = request.client.host if request.client else "unknown"

    # Reutiliza o mesmo bloqueio por IP que o endpoint buscar usa
    cutoff = (datetime.now(tz=timezone.utc) - timedelta(minutes=BLOCK_MINUTES)).isoformat()
    attempts = db.table("performance_ciencia_attempts").select("id").eq("ip_address", ip).gte("attempted_at", cutoff).execute()
    if len(attempts.data) >= MAX_ATTEMPTS:
        raise HTTPException(429, detail=f"Muitas tentativas incorretas. Aguarde {BLOCK_MINUTES} minutos.")

    cpf_clean = re.sub(r'\D', '', body.cpf.strip())
    employee = db.table("performance_employees").select("id,name").eq("cpf", cpf_clean).eq("has_corporate_email", False).eq("active", True).execute()
    if not employee.data:
        # Conta como tentativa incorreta para bloquear enumeração de CPF
        db.table("performance_ciencia_attempts").insert({"matricula": cpf_clean, "ip_address": ip}).execute()
        raise HTTPException(404, detail=_DADOS_NAO_ENCONTRADOS)
    emp = employee.data[0]

    review = db.table("performance_reviews").select("id").eq("id", body.review_id).eq("employee_id", emp["id"]).execute()
    if not review.data:
        # review_id não pertence a este colaborador — possível tentativa de manipulação
        db.table("performance_ciencia_attempts").insert({"matricula": cpf_clean, "ip_address": ip}).execute()
        _logger.warning(
            "SECURITY review_id_mismatch | ip=%s | cpf_suffix=%s | review_id=%s | emp_id=%s",
            ip, cpf_clean[-4:], body.review_id, emp["id"],
        )
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

    _logger.info(
        "AUDIT ciencia_presencial_confirmed | ip=%s | cpf_suffix=%s | review_id=%s | emp_id=%s",
        ip, cpf_clean[-4:], body.review_id, emp["id"],
    )
    return {"ok": True, "acknowledged_at": now_iso, "employee_name": emp["name"]}


# ── Auto-Avaliação Presencial (sem e-mail, acesso por CPF) ───────────────────

class AutoAvaliacaoPresencialBusca(BaseModel):
    nome: str
    cpf: str


@router.post("/auto-avaliacao-presencial/buscar")
@limiter.limit("10/minute")
def buscar_auto_avaliacao_presencial(body: AutoAvaliacaoPresencialBusca, request: Request) -> dict:
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
        raise HTTPException(404, detail=_DADOS_NAO_ENCONTRADOS)

    employee = employees[0]

    # Acesso presencial disponível para todos (com ou sem e-mail corporativo)

    nome_digitado = _normalize_name(body.nome)
    nome_cadastrado = _normalize_name(employee["name"])
    if nome_digitado != nome_cadastrado:
        _log_attempt()
        raise HTTPException(404, detail=_DADOS_NAO_ENCONTRADOS)

    open_cycles = db.table("performance_cycles").select("id,name").eq("status", "open").execute().data
    if not open_cycles:
        raise HTTPException(400, detail="Não há ciclo de avaliação aberto no momento. Procure o RH.")

    cycle = open_cycles[0]

    # Busca token existente (não invalidado)
    tok_res = (
        db.table("performance_self_evaluation_tokens")
        .select("*")
        .eq("employee_id", employee["id"])
        .eq("cycle_id", cycle["id"])
        .is_("invalidated_at", "null")
        .execute()
        .data
    )

    if tok_res and tok_res[0]["is_used"]:
        company_name = ""
        if employee.get("company_id"):
            co = db.table("performance_companies").select("name").eq("id", employee["company_id"]).execute()
            company_name = co.data[0]["name"] if co.data else ""
        return {
            "token": tok_res[0]["token"],
            "already_completed": True,
            "employee_name": employee["name"],
            "cycle_name": cycle["name"],
            "cargo": employee.get("cargo", ""),
            "company_name": company_name,
            "indicators": [],
        }

    # Criar token se não existe
    if not tok_res:
        import uuid as _uuid
        new_tok = str(_uuid.uuid4())
        ins = db.table("performance_self_evaluation_tokens").insert({
            "token": new_tok,
            "cycle_id": cycle["id"],
            "employee_id": employee["id"],
        }).execute()
        if not ins.data:
            raise HTTPException(500, detail="Erro ao criar link de auto-avaliação. Tente novamente.")
        token_value = new_tok
    else:
        token_value = tok_res[0]["token"]

    # Buscar indicadores pelo nível hierárquico + perfil do colaborador
    emp_level = employee.get("hierarchy_level") or 3
    emp_perfil = employee.get("perfil") or ""
    ind_q = db.table("performance_indicators").select("id,name,description").eq("active", True).eq("hierarchy_level", emp_level)
    if emp_level == 3 and emp_perfil in ("administrativo", "operacional"):
        ind_q = ind_q.eq("perfil", emp_perfil)
    indicators = ind_q.order("created_at").execute().data

    company_name = ""
    if employee.get("company_id"):
        co = db.table("performance_companies").select("name").eq("id", employee["company_id"]).execute()
        company_name = co.data[0]["name"] if co.data else ""

    return {
        "token": token_value,
        "already_completed": False,
        "employee_name": employee["name"],
        "cycle_name": cycle["name"],
        "cargo": employee.get("cargo", ""),
        "company_name": company_name,
        "indicators": indicators,
    }


# ── Auto-avaliação ────────────────────────────────────────────────────────────

class SelfEvalSubmit(BaseModel):
    indicator_scores: list[IndicatorScore]   # justificativa obrigatória para notas 1 e 5
    observations: str | None = None          # sempre opcional, sem mínimo de palavras


@router.get("/auto-avaliar/{token}")
@limiter.limit("20/minute")
def get_self_evaluation_form(token: str, request: Request) -> dict:
    _validate_uuid(token, "Link de auto-avaliação")
    db = get_supabase()
    token_data = db.table("performance_self_evaluation_tokens").select("*").eq("token", token).execute()
    if not token_data.data:
        raise HTTPException(404, detail="Link de auto-avaliação inválido ou expirado.")
    t = token_data.data[0]
    if t["is_used"]:
        raise HTTPException(400, detail="Este link já foi utilizado. Sua auto-avaliação já foi enviada.")
    if t.get("invalidated_at"):
        raise HTTPException(400, detail="Este link foi invalidado.")

    cycle = db.table("performance_cycles").select("*").eq("id", t["cycle_id"]).execute()
    if not cycle.data or cycle.data[0]["status"] != "open":
        raise HTTPException(400, detail="O ciclo de avaliação está encerrado.")

    employee = db.table("performance_employees").select(
        "id,name,matricula,cargo,hierarchy_level,perfil,company_id, performance_companies(name)"
    ).eq("id", t["employee_id"]).execute()
    if not employee.data:
        raise HTTPException(404, detail="Colaborador não encontrado.")
    emp = employee.data[0]

    emp_level = emp.get("hierarchy_level") or 3
    emp_perfil = emp.get("perfil") or ""
    ind_q = db.table("performance_indicators").select("id,name,description").eq("active", True).eq("hierarchy_level", emp_level)
    if emp_level == 3 and emp_perfil in ("administrativo", "operacional"):
        ind_q = ind_q.eq("perfil", emp_perfil)
    indicators = ind_q.order("created_at").execute().data

    company_name = (emp.get("performance_companies") or {}).get("name", "") if isinstance(emp.get("performance_companies"), dict) else ""

    return {
        "cycle_name": cycle.data[0]["name"],
        "cycle_id": t["cycle_id"],
        "employee": {
            "id": emp["id"],
            "name": emp["name"],
            "cargo": emp.get("cargo", ""),
            "hierarchy_level": emp_level,
        },
        "company_name": company_name,
        "indicators": indicators,
    }


@router.post("/auto-avaliar/{token}")
@limiter.limit("5/minute")
def submit_self_evaluation(token: str, body: SelfEvalSubmit, request: Request) -> dict:
    _validate_uuid(token, "Link de auto-avaliação")
    db = get_supabase()
    token_data = db.table("performance_self_evaluation_tokens").select("*").eq("token", token).execute()
    if not token_data.data:
        raise HTTPException(404, detail="Link de auto-avaliação inválido.")
    t = token_data.data[0]
    if t["is_used"]:
        raise HTTPException(400, detail="Este link já foi utilizado.")
    if t.get("invalidated_at"):
        raise HTTPException(400, detail="Este link foi invalidado.")

    cycle = db.table("performance_cycles").select("*").eq("id", t["cycle_id"]).execute()
    if not cycle.data or cycle.data[0]["status"] != "open":
        raise HTTPException(400, detail="O ciclo de avaliação está encerrado.")

    employee_id = t["employee_id"]
    scores_list = [sc.score for sc in body.indicator_scores]
    if not scores_list:
        raise HTTPException(400, detail="Nenhuma nota informada.")
    for sc in body.indicator_scores:
        if sc.score < 1 or sc.score > 5:
            raise HTTPException(400, detail=f"Nota {sc.score} inválida. Use valores de 1 a 5.")
        if sc.score in (1, 5) and not (sc.justification or "").strip():
            label = "NAE (Não Atende)" if sc.score == 1 else "EE (Excede as Expectativas)"
            raise HTTPException(400, detail=f"Justificativa obrigatória para nota {sc.score} — {label}.")

    final_score = round(sum(scores_list) / len(scores_list), 2)
    obs = (body.observations or "").strip() or None

    # Verifica se já existe auto-avaliação para este ciclo
    existing = (
        db.table("performance_reviews")
        .select("id,status")
        .eq("cycle_id", t["cycle_id"])
        .eq("employee_id", employee_id)
        .eq("is_self_evaluation", True)
        .execute()
    )
    if existing.data and existing.data[0].get("status") == "completed":
        raise HTTPException(400, detail="Auto-avaliação já submetida para este ciclo.")

    if existing.data:
        review_id = existing.data[0]["id"]
        db.table("performance_reviews").update({
            "evaluator_id": employee_id,
            "status": "completed",
            "final_score": final_score,
            "observations": obs,
            "submitted_at": "now()",
            "updated_at": "now()",
            "is_self_evaluation": True,
        }).eq("id", review_id).execute()
    else:
        review_res = db.table("performance_reviews").insert({
            "cycle_id": t["cycle_id"],
            "employee_id": employee_id,
            "evaluator_id": employee_id,   # self-eval: avaliador = próprio colaborador
            "status": "completed",
            "final_score": final_score,
            "observations": obs,
            "submitted_at": "now()",
            "is_self_evaluation": True,
        }).execute()
        if not review_res.data:
            raise HTTPException(500, detail="Erro ao salvar auto-avaliação.")
        review_id = review_res.data[0]["id"]

    # Salvar scores
    db.table("performance_indicator_scores").delete().eq("review_id", review_id).execute()
    score_rows = [
        {
            "review_id": review_id,
            "indicator_id": sc.indicator_id,
            "score": sc.score,
            "justification": (sc.justification or "").strip() or None,
        }
        for sc in body.indicator_scores
    ]
    db.table("performance_indicator_scores").insert(score_rows).execute()

    # Marcar token como usado
    db.table("performance_self_evaluation_tokens").update(
        {"is_used": True, "sent_at": "now()"}
    ).eq("token", token).execute()

    _logger.info(
        "AUDIT self_eval_submitted | ip=%s | token=%s | employee_id=%s | score=%s",
        request.client.host if request.client else "unknown", token, employee_id, final_score,
    )
    return {"ok": True, "final_score": final_score}
