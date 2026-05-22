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

# Formato real da API ADN (gov.br/nfse):
# {"StatusProcessamento": "DOCUMENTOS_LOCALIZADOS",
#  "LoteDFe": [{"NSU": 1, "ChaveAcesso": "...", "TipoDocumento": "NFSE", "ArquivoXml": "base64gz"}]}
STATUS_LOCALIZADOS = "DOCUMENTOS_LOCALIZADOS"


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
        Retorna list[dict] com: nsu, schema, tipo, tipo_schema, xml, xml_hash, fonte, chave_acesso.
        """
        if not self._cert:
            raise RuntimeError(
                f"[{self.cnpj}] Certificado digital ausente. "
                "Faça upload via POST /api/fiscal/{id}/certificates"
            )

        docs: list[dict] = []
        nsu_atual = ultimo_nsu

        while True:
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

            if resp.status_code == 404:
                _logger.info("[%s] ADN HTTP 404 — fim da fila, NSU=%d", self.cnpj, nsu_atual)
                break

            if resp.status_code == 429:
                retry_after = resp.headers.get("Retry-After", "3600")
                _logger.warning(
                    "[%s] ADN HTTP 429 — limite de req/hora atingido (Retry-After: %ss). "
                    "Retornando %d docs coletados até NSU=%d.",
                    self.cnpj, retry_after, len(docs), nsu_atual,
                )
                break   # retorna o que já coletou; NSU será salvo pelo scheduler

            resp.raise_for_status()
            payload = resp.json()

            # Formato ADN: StatusProcessamento + LoteDFe[]
            status_proc = payload.get("StatusProcessamento", "")
            lote_dfe    = payload.get("LoteDFe") or []

            if status_proc != STATUS_LOCALIZADOS or not lote_dfe:
                _logger.info(
                    "[%s] ADN StatusProcessamento=%r (fim da fila), NSU=%d",
                    self.cnpj, status_proc, nsu_atual,
                )
                break

            req_count = getattr(self, "_req_count", 0) + 1
            self._req_count = req_count
            if req_count % 10 == 1 or req_count <= 3:
                _logger.info("[%s] ADN req #%d NSU=%d docs_acumulados=%d",
                             self.cnpj, req_count, nsu_atual, len(docs))

            nsu_antes = nsu_atual
            for item in lote_dfe:
                nsu        = int(item.get("NSU", nsu_atual))
                tipo_doc   = str(item.get("TipoDocumento", ""))
                chave      = str(item.get("ChaveAcesso", ""))
                xml_str    = _decompress(item.get("ArquivoXml") or "")

                if not xml_str:
                    _logger.warning("[%s] ADN NSU=%d ArquivoXml vazio/inválido", self.cnpj, nsu)
                    continue

                tipo        = "cancelamento" if "CANCEL" in tipo_doc.upper() else "documento"
                tipo_schema = "completo"   # Portal Nacional retorna NFS-e completa

                docs.append({
                    "nsu":          nsu,
                    "schema":       tipo_doc,
                    "tipo":         tipo,
                    "tipo_schema":  tipo_schema,
                    "xml":          xml_str,
                    "xml_hash":     hashlib.sha256(xml_str.encode("utf-8")).hexdigest(),
                    "fonte":        "portal_nacional",
                    "chave_acesso": chave,
                })
                nsu_atual = max(nsu_atual, nsu)

            # Se NSU não avançou não há mais documentos — evita loop infinito
            if nsu_atual <= nsu_antes:
                break

            time.sleep(2)   # 2s entre requisições — limite 256/hora do ADN

        _logger.info(
            "[%s] ADN: %d docs baixados (NSU %d → %d)",
            self.cnpj, len(docs), ultimo_nsu, nsu_atual,
        )
        return docs

    # ------------------------------------------------------------------
    # Distribuição incremental por NSU — versão generator (save-as-you-go)
    # ------------------------------------------------------------------
    def iter_dfe_interesse(self, ultimo_nsu: int):
        """
        Generator: baixa uma página por vez do ADN e yield (batch, nsu_atual).
        Permite save incremental sem acumular tudo em RAM.
        """
        if not self._cert:
            raise RuntimeError(
                f"[{self.cnpj}] Certificado digital ausente. "
                "Faça upload via POST /api/fiscal/{id}/certificates"
            )

        nsu_atual = ultimo_nsu
        req_count = 0

        while True:
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

            if resp.status_code == 404:
                _logger.info(
                    "[%s] ADN HTTP 404 — fim da fila, NSU=%d",
                    self.cnpj, nsu_atual,
                )
                return

            if resp.status_code == 429:
                retry_after = resp.headers.get("Retry-After", "3600")
                _logger.warning(
                    "[%s] ADN HTTP 429 — limite de req/hora atingido (Retry-After: %ss). "
                    "Interrompendo em NSU=%d.",
                    self.cnpj, retry_after, nsu_atual,
                )
                return

            resp.raise_for_status()
            payload = resp.json()

            status_proc = payload.get("StatusProcessamento", "")
            lote_dfe    = payload.get("LoteDFe") or []

            if status_proc != STATUS_LOCALIZADOS or not lote_dfe:
                _logger.info(
                    "[%s] ADN StatusProcessamento=%r (fim da fila), NSU=%d",
                    self.cnpj, status_proc, nsu_atual,
                )
                return

            req_count += 1
            if req_count % 10 == 1 or req_count <= 3:
                _logger.info("[%s] ADN req #%d NSU=%d", self.cnpj, req_count, nsu_atual)

            nsu_antes = nsu_atual
            batch: list[dict] = []
            for item in lote_dfe:
                nsu        = int(item.get("NSU", nsu_atual))
                tipo_doc   = str(item.get("TipoDocumento", ""))
                chave      = str(item.get("ChaveAcesso", ""))
                xml_str    = _decompress(item.get("ArquivoXml") or "")

                if not xml_str:
                    _logger.warning("[%s] ADN NSU=%d ArquivoXml vazio/inválido", self.cnpj, nsu)
                    continue

                tipo        = "cancelamento" if "CANCEL" in tipo_doc.upper() else "documento"
                tipo_schema = "completo"

                batch.append({
                    "nsu":          nsu,
                    "schema":       tipo_doc,
                    "tipo":         tipo,
                    "tipo_schema":  tipo_schema,
                    "xml":          xml_str,
                    "xml_hash":     hashlib.sha256(xml_str.encode("utf-8")).hexdigest(),
                    "fonte":        "portal_nacional",
                    "chave_acesso": chave,
                })
                nsu_atual = max(nsu_atual, nsu)

            if nsu_atual <= nsu_antes:
                return

            yield batch, nsu_atual
            time.sleep(2)

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
