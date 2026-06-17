import logging
from typing import Any

import httpx

from db import get_settings

logger = logging.getLogger(__name__)

_BASE_URL = "https://voeturomni.freshdesk.com/api/v2"
_SEARCH_MAX_PAGES = 10  # Freshdesk search API hard limit


def _client() -> httpx.Client:
    api_key = get_settings().freshdesk_api_key
    return httpx.Client(
        auth=(api_key, "X"),
        headers={"Content-Type": "application/json"},
        timeout=30,
    )


def search_tickets_by_empresa(
    empresa: str,
    page: int = 1,
) -> dict[str, Any]:
    """Search Freshdesk tickets where cf_empresa matches the given value.

    Returns {"results": [...], "total": int, "page": int, "has_more": bool}.
    Freshdesk search API allows max 10 pages × 30 results = 300 tickets.
    """
    if page < 1 or page > _SEARCH_MAX_PAGES:
        raise ValueError(f"page must be between 1 and {_SEARCH_MAX_PAGES}")

    query = f"cf_empresa:'{empresa}'"
    params = {"query": f'"{query}"', "page": page}

    with _client() as client:
        resp = client.get(f"{_BASE_URL}/search/tickets", params=params)
        resp.raise_for_status()
        body = resp.json()

    raw_results: list[dict] = body.get("results") or []
    total: int = body.get("total") or len(raw_results)

    tickets = [_map_ticket(t) for t in raw_results]

    return {
        "results": tickets,
        "total": total,
        "page": page,
        "has_more": len(raw_results) == 30 and page < _SEARCH_MAX_PAGES,
    }


def _map_ticket(t: dict) -> dict:
    cf = t.get("custom_fields") or {}
    return {
        "id": t.get("id"),
        "subject": t.get("subject"),
        "status": t.get("status"),
        "type": t.get("type"),
        "created_at": t.get("created_at"),
        "updated_at": t.get("updated_at"),
        "empresa": cf.get("cf_empresa"),
        "localizador": cf.get("cf_localizador"),
        "mercado": cf.get("cf_mercado"),
        "tipo_servico": cf.get("cf_ipo_de_servio") or cf.get("cf_tipo_de_servio763654"),
        "produtos": cf.get("cf_produtos"),
        "nome_passageiro": cf.get("cf_nome_do_passageiro"),
        "nome_solicitante": cf.get("cf_nome_do_solicitante"),
        "data_viagem": cf.get("cf_data_da_viagem428258") or cf.get("cf_data_viagem"),
        "tipo_demanda": cf.get("cf_tipo_de_demanda"),
        "reference_number": cf.get("cf_reference_number"),
        "vip": cf.get("cf_vip"),
    }
