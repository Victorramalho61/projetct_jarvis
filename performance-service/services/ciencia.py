"""Montagem do payload de 'Ciência' (notas, comentários, calibração) — usado tanto
pelo fluxo público por token (routes/public.py) quanto pela visão interna do RH
(routes/admin.py), sem duplicar a lógica entre os dois."""


def build_ciencia_extras(db, rev: dict) -> dict:
    """Busca auto-avaliação e histórico de calibração de uma review, para compor
    a tela de Ciência com os comentários de gestor, colaborador e RH."""
    self_rev = (
        db.table("performance_reviews")
        .select("id,final_score,observations")
        .eq("cycle_id", rev["cycle_id"])
        .eq("employee_id", rev["employee_id"])
        .eq("is_self_evaluation", True)
        .eq("status", "completed")
        .execute()
        .data
    )
    self_rev_data = self_rev[0] if self_rev else None
    self_scores: dict[str, dict] = {}
    if self_rev_data:
        s_scores = (
            db.table("performance_indicator_scores")
            .select("indicator_id,score,justification")
            .eq("review_id", self_rev_data["id"])
            .execute()
            .data
        )
        self_scores = {s["indicator_id"]: s for s in s_scores}

    calibs = (
        db.table("performance_calibrations")
        .select("id,calibrated_by,calibrated_at,notes,original_score,calibrated_score")
        .eq("review_id", rev["id"])
        .order("calibrated_at", desc=True)
        .execute()
        .data
    )
    calib_items_by_indicator: dict[str, dict] = {}
    calibration_notes = None
    if calibs:
        calibration_notes = calibs[0].get("notes")
        calib_ids = [c["id"] for c in calibs]
        items_raw = (
            db.table("performance_calibration_items")
            .select("*")
            .in_("calibration_id", calib_ids)
            .order("created_at", desc=True)
            .execute()
            .data
        )
        # itens mais recentes primeiro — setdefault garante que a última
        # calibração de cada indicador prevaleça caso haja mais de uma sessão.
        for item in items_raw:
            calib_items_by_indicator.setdefault(item["indicator_id"], item)

    return {
        "self_observations": self_rev_data.get("observations") if self_rev_data else None,
        "self_final_score": self_rev_data.get("final_score") if self_rev_data else None,
        "self_scores": self_scores,
        "calibration_items_by_indicator": calib_items_by_indicator,
        "calibration_notes": calibration_notes,
        "was_calibrated": bool(calibs),
    }


def build_ciencia_payload(db, review_id: str) -> dict:
    """Monta o payload completo de Ciência (notas, comentários, calibração,
    nota final combinada) a partir de um review_id — sem depender de token."""
    review = db.table("performance_reviews").select("*").eq("id", review_id).execute()
    if not review.data:
        return None
    rev = review.data[0]

    employee = db.table("performance_employees").select("name,company_id").eq("id", rev["employee_id"]).execute()
    evaluator = db.table("performance_employees").select("name").eq("id", rev.get("evaluator_id")).execute()
    cycle = db.table("performance_cycles").select("name").eq("id", rev["cycle_id"]).execute()

    scores_raw = db.table("performance_indicator_scores").select(
        "*, performance_indicators(name,description)"
    ).eq("review_id", rev["id"]).execute().data
    extras = build_ciencia_extras(db, rev)
    self_scores = extras["self_scores"]
    calib_by_indicator = extras["calibration_items_by_indicator"]
    indicator_scores = []
    for s in scores_raw:
        ind = s.get("performance_indicators", {}) or {}
        self_s = self_scores.get(s["indicator_id"])
        calib = calib_by_indicator.get(s["indicator_id"])
        indicator_scores.append({
            "indicator_id": s["indicator_id"],
            "indicator_name": ind.get("name", ""),
            "indicator_description": ind.get("description", ""),
            "score": s["score"],
            "justification": s.get("justification"),
            "self_score": self_s["score"] if self_s else None,
            "self_justification": self_s.get("justification") if self_s else None,
            "calibrated_score": calib["new_score"] if calib else None,
            "calibrated_justification": calib.get("justification") if calib else None,
        })

    existing_ack = db.table("performance_review_acknowledgments").select("*").eq(
        "review_id", rev["id"]
    ).eq("employee_id", rev["employee_id"]).execute()
    already_acknowledged = bool(existing_ack.data)
    acknowledged_at = existing_ack.data[0]["acknowledged_at"] if already_acknowledged else None

    company_name = ""
    emp_data = employee.data[0] if employee.data else {}
    if emp_data.get("company_id"):
        co = db.table("performance_companies").select("name").eq("id", emp_data["company_id"]).execute()
        company_name = co.data[0]["name"] if co.data else ""

    final_score = rev.get("final_score")
    self_final_score = extras["self_final_score"]
    nota_final_combinada = None
    if final_score is not None and self_final_score is not None:
        nota_final_combinada = round((float(final_score) + float(self_final_score)) / 2, 2)

    return {
        "employee_name": emp_data.get("name", ""),
        "evaluator_name": evaluator.data[0]["name"] if evaluator.data else "",
        "cycle_name": cycle.data[0]["name"] if cycle.data else "",
        "final_score": final_score,
        "observations": rev.get("observations"),
        "indicator_scores": indicator_scores,
        "already_acknowledged": already_acknowledged,
        "acknowledged_at": acknowledged_at,
        "company_name": company_name,
        "self_final_score": self_final_score,
        "self_observations": extras["self_observations"],
        "was_calibrated": extras["was_calibrated"],
        "calibration_notes": extras["calibration_notes"],
        "nota_final_combinada": nota_final_combinada,
    }
