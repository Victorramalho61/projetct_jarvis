import re
from datetime import date

from fastapi import HTTPException

from db import get_settings

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def validar_periodo(data_inicio: str, data_fim: str, max_days: int | None = None) -> None:
    """Levanta 422 se datas inválidas ou período > max_days (default: MAX_PERIOD_DAYS)."""
    if not _DATE_RE.match(data_inicio) or not _DATE_RE.match(data_fim):
        raise HTTPException(status_code=422, detail="Datas devem estar no formato YYYY-MM-DD")
    try:
        d_ini = date.fromisoformat(data_inicio)
        d_fim = date.fromisoformat(data_fim)
    except ValueError:
        raise HTTPException(status_code=422, detail="Data inválida")
    if d_fim < d_ini:
        raise HTTPException(status_code=422, detail="dataFim deve ser maior ou igual a dataInicio")
    limit = max_days if max_days is not None else get_settings().max_period_days
    if (d_fim - d_ini).days > limit:
        raise HTTPException(status_code=422, detail=f"Período máximo permitido: {limit} dias")
