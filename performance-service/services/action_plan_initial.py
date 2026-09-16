"""Preenchimento inicial do Plano de Ação (2 competências + 5 campos cada) —
lógica compartilhada entre o fluxo do gestor (routes/action_plans_public.py,
via initial_token de e-mail), o fluxo do colaborador (mesmo arquivo, logo após
dar ciência da avaliação) e o fallback manual do RH (routes/action_plans.py).

Extraído de routes/action_plans_public.py::get_initial_form/submit_initial_form
sem mudar nenhuma regra — só recebe o registro do plano já carregado em vez do
token, pra quem chama decidir como autentica/autoriza.
"""
from fastapi import HTTPException

REQUIRED_ITEM_COUNT = 2  # exatamente 2 competências, de todo o catálogo


def build_initial_form_payload(db, plan_row: dict) -> dict:
    p = plan_row

    cycle = db.table("performance_cycles").select("name,period_start,period_end").eq("id", p["cycle_id"]).execute()
    cyc = cycle.data[0] if cycle.data else {}

    emp_ids = list({i for i in (p["employee_id"], p["manager_id"]) if i})
    emp_rows = db.table("performance_employees").select(
        "id,name,cargo,company_id,hierarchy_level,perfil"
    ).in_("id", emp_ids).execute().data or []
    emp_map = {r["id"]: r for r in emp_rows}
    employee = emp_map.get(p["employee_id"])
    manager = emp_map.get(p["manager_id"])
    if not employee:
        raise HTTPException(404, detail="Colaborador não encontrado.")

    company_name = ""
    if employee.get("company_id"):
        co = db.table("performance_companies").select("name").eq("id", employee["company_id"]).execute()
        company_name = co.data[0]["name"] if co.data else ""

    # Catálogo completo de competências aplicáveis ao nível/perfil do colaborador —
    # quem preenche escolhe livremente 2 dentre todas (não só as de nota baixa).
    emp_level = employee.get("hierarchy_level") or 3
    emp_perfil = employee.get("perfil") or ""
    ind_q = db.table("performance_indicators").select("id,name,description").eq("active", True).eq("hierarchy_level", emp_level)
    if emp_level == 3 and emp_perfil in ("administrativo", "operacional"):
        ind_q = ind_q.eq("perfil", emp_perfil)
    indicators = ind_q.order("name").execute().data or []

    scores = (
        db.table("performance_indicator_scores").select("indicator_id,score")
        .eq("review_id", p["review_id"]).execute().data
    ) or []
    score_by_indicator = {s["indicator_id"]: s["score"] for s in scores}

    phase1 = (
        db.table("performance_action_plan_phases").select("due_date")
        .eq("action_plan_id", p["id"]).eq("phase_number", 1).execute().data
    )
    phase4 = (
        db.table("performance_action_plan_phases").select("due_date")
        .eq("action_plan_id", p["id"]).eq("phase_number", 4).execute().data
    )

    return {
        "employee_name": employee["name"],
        "employee_cargo": employee.get("cargo", ""),
        "cycle_name": cyc.get("name", ""),
        "period_start": cyc.get("period_start"),
        "period_end": cyc.get("period_end"),
        "company_name": company_name,
        "manager_name": manager["name"] if manager else "",
        "manager_cargo": manager.get("cargo", "") if manager else "",
        "next_review_date": phase1[0]["due_date"] if phase1 else None,
        "final_review_date": phase4[0]["due_date"] if phase4 else None,
        "required_item_count": REQUIRED_ITEM_COUNT,
        "indicators": [
            {
                "indicator_id": ind["id"],
                "name": ind["name"],
                "description": ind.get("description", ""),
                "original_score": score_by_indicator.get(ind["id"]),
            }
            for ind in indicators
        ],
    }


def validate_and_persist_initial_items(db, plan_row: dict, items: list[dict], frequencia_alinhamento: str) -> None:
    """Valida e grava o preenchimento inicial. `items` é uma lista de dicts com as
    chaves de InitialItemBody (indicator_id, situacao_observada, meta_esperada,
    acoes, responsavel_acompanhamento, como_sera_verificado).

    Sempre marca `initial_token_used_at` (mesmo quando quem preencheu não usou o
    link do gestor) — invalida esse link pra qualquer preenchimento posterior,
    não importa por qual caminho o plano foi preenchido primeiro."""
    p = plan_row

    if len(items) != REQUIRED_ITEM_COUNT:
        raise HTTPException(400, detail=f"Escolha exatamente {REQUIRED_ITEM_COUNT} competências prioritárias.")
    indicator_ids = [i["indicator_id"] for i in items]
    if len(set(indicator_ids)) != len(indicator_ids):
        raise HTTPException(400, detail="As competências escolhidas devem ser diferentes entre si.")
    for item in items:
        for field_name in (
            "situacao_observada", "meta_esperada", "acoes",
            "responsavel_acompanhamento", "como_sera_verificado",
        ):
            if not (item.get(field_name) or "").strip():
                raise HTTPException(400, detail="Preencha todos os campos de cada competência escolhida.")
    if not (frequencia_alinhamento or "").strip():
        raise HTTPException(400, detail="Informe a frequência de alinhamento (combinados de acompanhamento).")

    valid_indicators = db.table("performance_indicators").select("id").in_("id", indicator_ids).execute().data or []
    if len(valid_indicators) != len(set(indicator_ids)):
        raise HTTPException(400, detail="Uma ou mais competências escolhidas são inválidas.")

    scores = (
        db.table("performance_indicator_scores").select("indicator_id,score")
        .eq("review_id", p["review_id"]).in_("indicator_id", indicator_ids).execute().data
    ) or []
    score_by_indicator = {s["indicator_id"]: s["score"] for s in scores}

    items_payload = [
        {
            "action_plan_id": p["id"],
            "indicator_id": item["indicator_id"],
            "original_score": score_by_indicator.get(item["indicator_id"]),
            "situacao_observada": item["situacao_observada"].strip(),
            "meta_esperada": item["meta_esperada"].strip(),
            "acoes": item["acoes"].strip(),
            "responsavel_acompanhamento": item["responsavel_acompanhamento"].strip(),
            "como_sera_verificado": item["como_sera_verificado"].strip(),
        }
        for item in items
    ]
    db.table("performance_action_plan_items").insert(items_payload).execute()

    db.table("performance_action_plans").update({
        "status": "active",
        "frequencia_alinhamento": frequencia_alinhamento.strip(),
        "initial_token_used_at": "now()",
        "initial_form_filled_at": "now()",
    }).eq("id", p["id"]).execute()
