def calculate_final_score(indicator_scores: list[float]) -> float:
    """Calcula nota final como média aritmética simples dos indicadores (escala 1-5)"""
    if not indicator_scores:
        return 0.0
    return round(sum(indicator_scores) / len(indicator_scores), 2)
