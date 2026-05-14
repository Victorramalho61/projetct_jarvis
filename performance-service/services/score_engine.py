WEIGHTS = {"goals": 0.50, "competencies": 0.25, "behavior": 0.15, "compliance": 0.10}
COMPLIANCE_BLOCK_THRESHOLD = 2.0
COMPLIANCE_BLOCK_CAP = 2.5


def calculate_scores(goals, competencies, behavior, compliance) -> dict:
    raw = sum([
        (goals or 0)        * WEIGHTS["goals"],
        (competencies or 0) * WEIGHTS["competencies"],
        (behavior or 0)     * WEIGHTS["behavior"],
        (compliance or 0)   * WEIGHTS["compliance"],
    ])
    normalized = round(max(1.0, min(5.0, raw)), 2)
    blocked_by = None
    final = normalized
    if (compliance or 0) < COMPLIANCE_BLOCK_THRESHOLD:
        final = min(normalized, COMPLIANCE_BLOCK_CAP)
        blocked_by = "compliance"
    return {
        "raw_score": round(raw, 2),
        "normalized_score": normalized,
        "final_score": round(final, 2),
        "blocked_by": blocked_by,
    }
