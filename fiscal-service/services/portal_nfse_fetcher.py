"""
Fetcher do ADN — Ambiente de Distribuição Nacional de NFS-e (adn.nfse.gov.br).
Autenticação: mTLS com certificado ICP-Brasil A1/A3 (sem headers extras).
Endpoint: GET /contribuintes/DFe/{NSU:015d}
Limite: 256 req/hora — sleep 2s entre requisições para respeitar.
cStat 137 = sem novos; 138 = ok; 656 = bloqueado 1h.
"""
import base64
import gzip
import hashlib
import logging
import time
from typing import Optional

import requests

from services.retry_utils import with_backoff

_logger = logging.getLogger(__name__)

ADN_PROD = "https://adn.nfse.gov.br/contribuintes"
ADN_HOM  = "https://adn.producaorestrita.nfse.gov.br/contribuintes"

CSTAT_OK        = 138
CSTAT_SEM_NOVOS = 137


class PortalNFSeFetcher:
    def __init__(
        self,
        cnpj: str,
        cert_path: Optional[str],
        key_path: Optional[str],
        ambiente: str = "1",
    ):
        self.cnpj  = cnpj
        self._cert = (cert_path, key_path) if cert_path and key_path else None
        self._base = ADN_PROD if ambiente == "1" else ADN_HOM
        _logger.info(
            "PortalNFSeFetcher: CNPJ=%s base=%s cert=%s",
            cnpj,
            self._base,
            "ok" if self._cert else "AUSENTE",
        )

    # ------------------------------------------------------------------
    # Distribuição incremental por NSU
    # ------------------------------------------------------------------
    def dist_dfe_interesse(self, ultimo_nsu: int) -> list[dict]:
        """
        Puxa todos os DFe a partir de ultimo_nsu.
        Retorna list[dict] com: nsu, schema, tipo, tipo_schema, xml, xml_hash, fonte.
        """
        if not self._cert:
            raise RuntimeError(
                f"[{self.cnpj}] Certificado digital ausente. "
                "Faça upload via POST /api/fiscal/{id}/certificates"
            )

        docs: list[dict] = []
        nsu_atual = ultimo_nsu

        while True:
            # Captura nsu_atual no closure para evitar late-binding
            nsu_snap = nsu_atual

            def _get():
                return requests.get(
                    f"{self._base}/DFe/{nsu_snap:015d}",
                    cert=self._cert,
                    verify=True,
                    timeout=30,
                    headers={"Accept": "application/json"},
                )

            try:
                resp = with_backoff(_get)
            except requests.exceptions.SSLError as exc:
                _logger.error("[%s] ADN SSL error: %s", self.cnpj, exc)
                raise

            if resp.status_code in (401, 403):
                raise RuntimeError(
                    f"[{self.cnpj}] ADN acesso negado (HTTP {resp.status_code}). "
                    "Verifique certificado e registro em gov.br/nfse."
                )

            resp.raise_for_status()
            payload = resp.json()
            c_stat  = int(payload.get("cStat", 0))

            if c_stat == CSTAT_SEM_NOVOS:
                _logger.info("[%s] ADN cStat=137 (sem novos), NSU=%d", self.cnpj, nsu_atual)
                break

            if c_stat not in (CSTAT_OK, 100):
                _logger.warning(
                    "[%s] ADN cStat=%d xMotivo=%s",
                    self.cnpj,
                    c_stat,
                    payload.get("xMotivo", ""),
                )
                break

            lote     = payload.get("loteDistDFeInt") or {}
            doc_zips = lote.get("docZip") or []
            if not doc_zips:
                break

            for item in doc_zips:
                nsu     = int(item.get("NSU", nsu_atual))
                schema  = str(item.get("schema", ""))
                xml_str = _decompress(item.get("xmlZip") or "")

                if not xml_str:
                    _logger.warning("[%s] ADN NSU=%d xmlZip vazio/inválido", self.cnpj, nsu)
                    continue

                tipo_schema = "resumo"    if schema.startswith("res")    else "completo"
                tipo        = "cancelamento" if "Evento" in schema       else "documento"

                docs.append({
                    "nsu":         nsu,
                    "schema":      schema,
                    "tipo":        tipo,
                    "tipo_schema": tipo_schema,
                    "xml":         xml_str,
                    "xml_hash":    hashlib.sha256(xml_str.encode("utf-8")).hexdigest(),
                    "fonte":       "portal_nacional",
                })
                nsu_atual = max(nsu_atual, nsu)

            max_nsu = int(payload.get("maxNSU", nsu_atual))
            if nsu_atual >= max_nsu:
                break

            time.sleep(2)   # 2s entre requisições — limite 256/hora do ADN

        _logger.info(
            "[%s] ADN: %d docs baixados (NSU %d → %d)",
            self.cnpj,
            len(docs),
            ultimo_nsu,
            nsu_atual,
        )
        return docs

    # ------------------------------------------------------------------
    # Busca on-demand por chave de acesso
    # ------------------------------------------------------------------
    def consulta_por_chave(self, chave_acesso: str) -> Optional[str]:
        """
        Busca XML individual por chave de acesso.
        Endpoint: GET /contribuintes/NFSe/{chave_acesso}
        Retorna XML string ou None.
        """
        if not self._cert:
            return None
        try:
            resp = requests.get(
                f"{self._base}/NFSe/{chave_acesso}",
                cert=self._cert,
                verify=True,
                timeout=20,
                headers={"Accept": "application/json"},
            )
            if resp.ok:
                payload = resp.json()
                return _decompress(payload.get("xmlZip") or payload.get("xml") or "")
        except Exception as exc:
            _logger.warning(
                "[%s] ADN consulta_por_chave %s: %s",
                self.cnpj,
                chave_acesso,
                exc,
            )
        return None


# ------------------------------------------------------------------
# Utilitário
# ------------------------------------------------------------------
def _decompress(data: str) -> str:
    """Base64 decode + gzip decompress → UTF-8 sem BOM."""
    if not data:
        return ""
    try:
        raw = base64.b64decode(data)
        return gzip.decompress(raw).decode("utf-8")
    except Exception as exc:
        _logger.warning("ADN decompress erro: %s", exc)
        return ""
