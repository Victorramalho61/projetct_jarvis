"""
NDD Digital — Fetcher de XMLs de NFSe (todas as empresas do portal).

O token NDD é da conta do usuário (Victor Ramalho), não de uma empresa específica.
Uma única autenticação acessa todas as empresas visíveis no portal.

Fluxo:
  1. Lista NFSe por intervalo de data (sem filtro de empresa/município)
  2. Para cada nota, baixa o XML via GET /nfse-api/api/NFSeRecepcao/xml/{id}
  3. Extrai ChaveAcesso e CNPJ do tomador direto do XML para associar à empresa
"""

import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime, timezone, timedelta
from typing import Generator

import requests

_logger = logging.getLogger(__name__)

NDD_BASE = "https://spaceportalprod.e-datacenter.nddigital.com.br"
NDD_API = f"{NDD_BASE}/nfse-api/api/NFSeRecepcao"
PAGE_SIZE        = 100
XML_WORKERS      = 2    # paralelo reduzido para não sobrecarregar a API
INTER_PAGE_SLEEP = 2    # segundos entre páginas OData


def fetch_all_xml(
    token: str,
    data_inicio: date,
    data_fim: date,
    since_dt: datetime | None = None,   # watermark incremental via dataProcessamento
) -> Generator[dict, None, None]:
    """
    Gera dicts com XML e metadados para todas as NFSe do portal no período.

    Yields:
        {
            "ndd_id": int,
            "chave_acesso": str,          # 44 dígitos extraído do XML
            "cnpj_tomador": str,          # 14 dígitos, sem formatação
            "cnpj_prestador": str,
            "data_emissao": str,          # YYYY-MM-DD
            "valor_total": float,
            "municipio_nome": str,
            "uf": str,
            "xml": str,                   # conteúdo XML completo
        }
    """
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
    odata_filter = (
        f"dataEmissao ge {data_inicio.isoformat()}T00:00:00+00:00 "
        f"and dataEmissao le {data_fim.isoformat()}T23:59:59+00:00"
    )
    if since_dt is not None:
        odata_filter += f" and dataProcessamento ge {since_dt.strftime('%Y-%m-%dT%H:%M:%S+00:00')}"

    skip = 0
    total_listados = 0
    total_xml = 0

    while True:
        try:
            resp = requests.get(
                NDD_API,
                headers=headers,
                params={
                    "$filter": odata_filter,
                    "$top": PAGE_SIZE,
                    "$skip": skip,
                    "$orderby": "dataEmissao asc",
                },
                timeout=30,
            )
            resp.raise_for_status()
        except requests.HTTPError as e:
            if e.response is not None and e.response.status_code == 401:
                raise RuntimeError("NDD Digital: token expirado — reconecte via /api/fiscal/{id}/ndd/token")
            raise

        data = resp.json()
        items = data if isinstance(data, list) else data.get("items", data.get("value", []))
        if not items:
            break

        total_listados += len(items)
        _logger.info(
            "NDD Digital: listando %d-%d notas (skip=%d)",
            skip + 1, skip + len(items), skip
        )

        # Baixa XMLs em paralelo
        with ThreadPoolExecutor(max_workers=XML_WORKERS) as pool:
            futures = {
                pool.submit(_fetch_xml, item["id"], headers): item
                for item in items
                if item.get("id")
            }
            for future in as_completed(futures):
                item = futures[future]
                try:
                    xml_str = future.result()
                except Exception as e:
                    _logger.warning("NDD xml/%d falhou: %s", item["id"], e)
                    continue

                if not xml_str:
                    continue

                total_xml += 1
                chave = _extract_chave(xml_str) or ""
                cnpj_tom = _clean_cnpj(item.get("cnpjTomador") or "")
                cnpj_prest = _clean_cnpj(item.get("cnpjPrestador") or "")

                yield {
                    "ndd_id": item["id"],
                    "chave_acesso": chave or f"ndd{item['id']}".ljust(44, "0")[:44],
                    "cnpj_tomador": cnpj_tom,
                    "cnpj_prestador": cnpj_prest,
                    "nome_prestador": item.get("nomePrestador") or "",
                    "nome_tomador": item.get("nomeTomador") or "",
                    "numero": str(item["numero"]) if item.get("numero") else None,
                    "serie": str(item.get("serie") or ""),
                    "data_emissao": (item.get("dataEmissao") or "")[:10] or None,
                    "valor_total": float(item.get("valorTotalServicos") or 0),
                    "valor_iss": float(item.get("valorIss") or 0) or None,
                    "valor_iss_retido": float(item.get("valorIssRetido") or 0) or None,
                    "municipio_nome": item.get("municipio") or "",
                    "uf": item.get("uf") or "",
                    "xml": xml_str,
                }

        if len(items) < PAGE_SIZE:
            break
        skip += PAGE_SIZE
        time.sleep(INTER_PAGE_SLEEP)

    _logger.info(
        "NDD Digital: %d notas listadas, %d XMLs baixados (%s a %s)",
        total_listados, total_xml, data_inicio, data_fim
    )


def _fetch_xml(ndd_id: int, headers: dict) -> str:
    resp = requests.get(
        f"{NDD_API}/xml/{ndd_id}",
        headers=headers,
        timeout=20,
    )
    resp.raise_for_status()
    data = resp.json()
    return data.get("documento") or data.get("xml") or data.get("xmlNfse") or ""


def _extract_chave(xml_str: str) -> str:
    """Extrai ChaveAcesso do XML sem importar lxml/ET (regex simples)."""
    import re
    m = re.search(r"<ChaveAcesso>(\d{44})</ChaveAcesso>", xml_str)
    return m.group(1) if m else ""


def _clean_cnpj(value: str) -> str:
    import re
    return re.sub(r"\D", "", value)[:14]
