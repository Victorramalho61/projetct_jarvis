"""Cálculo de dias úteis (calendário Brasil, com feriados nacionais) via workalendar."""
from datetime import date

from workalendar.america import Brazil

_CAL = Brazil()


def add_business_days(base: date, dias: int) -> date:
    """Retorna a data `dias` dias úteis após `base` (feriados nacionais e fins de semana excluídos)."""
    return _CAL.add_working_days(base, dias)


def count_business_days(inicio: date, fim: date) -> int:
    """Conta quantos dias úteis existem entre `inicio` (exclusive) e `fim` (inclusive)."""
    if fim <= inicio:
        return 0
    return _CAL.get_working_days_delta(inicio, fim)
