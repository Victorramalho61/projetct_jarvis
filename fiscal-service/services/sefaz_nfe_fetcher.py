import hashlib
import logging
import time
from datetime import datetime, timedelta, timezone
from typing import Optional

import requests
import zeep
from zeep.transports import Transport

_logger = logging.getLogger(__name__)

WSDL_NFE_PROD    = "https://www1.nfe.fazenda.gov.br/NFeDistribuicaoDFe/NFeDistribuicaoDFe.asmx?WSDL"
WSDL_NFE_HOM     = "https://hom1.nfe.fazenda.gov.br/NFeDistribuicaoDFe/NFeDistribuicaoDFe.asmx?WSDL"
WSDL_SVC_AN_PROD = "https://www.nfe.fazenda.gov.br/NFeDistribuicaoDFe/NFeDistribuicaoDFe.asmx?WSDL"

CUF_NACIONAL = 91

CODE_SEM_NOVOS = 137
CODE_OK        = 138
CODE_CONSUMIDOR = 656
CODE_PARALISADO = 108

SCHEMA_RESUMO_NFE    = 15      # resNFe — chave + situação, sem XML completo
SCHEMA_PROC_NFE      = 55      # procNFe — NF-e completa com protocolo
SCHEMA_EVENTO_CANCEL = 110111  # procEventoNFe — cancelamento

# Mapa cUF (primeiros 2 dígitos da chave) → URL NfeConsulta2 para busca por chave
_NF_CONSULTA_URL: dict[str, str] = {
    "11": "https://www.sefaznet.ro.gov.br/nfe/services/NfeConsulta2",
    "12": "https://www.sefaz.ac.gov.br/nfe/services/NfeConsulta2",
    "13": "https://nfe.sefaz.am.gov.br/services2/NfeConsulta2",
    "14": "https://nfe.sefaz.rr.gov.br/services/NfeConsulta2",
    "15": "https://appnfe.sefaz.pa.gov.br/nfe/services/NfeConsulta2",
    "16": "https://nfe.sefaz.ap.gov.br/nfe/services/NfeConsulta2",
    "17": "https://nfe.sefaz.to.gov.br/nfe/services/NfeConsulta2",
    "21": "https://www.sefaz.ma.gov.br/nfe/services/NfeConsulta2",
    "22": "https://nfe.sefaz.pi.gov.br/nfe/services/NfeConsulta2",
    "23": "https://nfe.sefaz.ce.gov.br/nfe/services/NfeConsulta2",
    "24": "https://nfe.set.rn.gov.br/nfe/services/NfeConsulta2",
    "25": "https://nfe.sefaz.pb.gov.br/nfe/services/NfeConsulta2",
    "26": "https://nfe.sefaz.pe.gov.br/nfe/services/NfeConsulta2",
    "27": "https://nfe.sefaz.al.gov.br/nfe/services/NfeConsulta2",
    "28": "https://nfe.sefaz.se.gov.br/nfe/services/NfeConsulta2",
    "29": "https://nfe.sefaz.ba.gov.br/nfe/services/NfeConsulta2",
    "31": "https://nfe.fazenda.mg.gov.br/nfe2/services/NfeConsulta2",
    "32": "https://nfe.sefaz.es.gov.br/nfe/services/NfeConsulta2",
    "33": "https://nfe.fazenda.rj.gov.br/nfe/services/NfeConsulta2",
    "35": "https://nfe.fazenda.sp.gov.br/nfe/services/NfeConsulta2",
    "41": "https://nfe.fazenda.pr.gov.br/nfe/services/NfeConsulta2",
    "42": "https://nfe.sef.sc.gov.br/nfe/services/NfeConsulta2",
    "43": "https://nfe.fazenda.rs.gov.br/nfe/services/NfeConsulta2",
    "50": "https://nfe.sefaz.ms.gov.br/nfe/services/NfeConsulta2",
    "51": "https://nfe.sefaz.mt.gov.br/nfe/services/NfeConsulta2",
    "52": "https://nfe.sefaz.go.gov.br/nfe/services/NfeConsulta2",
    "53": "https://nfe.fazenda.df.gov.br/nfe/services/NfeConsulta2",
}
_NF_CONSULTA_SVCAN = "https://www.nfe.fazenda.gov.br/NFeConsulta2/NFeConsulta2.asmx"


class NFeDistribuicaoDFe:
    def __init__(
        self,
        cnpj: str,
        cert_path: Optional[str],
        key_path: Optional[str],
        ambiente: str = "1",
        usar_svc_an: bool = False,
    ):
        self.cnpj     = cnpj
        self.ambiente = int(ambiente)

        if usar_svc_an and ambiente == "1":
            wsdl = WSDL_SVC_AN_PROD
        elif ambiente == "1":
            wsdl = WSDL_NFE_PROD
        else:
            wsdl = WSDL_NFE_HOM

        session = requests.Session()
        if cert_path and key_path:
            session.cert = (cert_path, key_path)
        session.verify = True

        transport = Transport(session=session, timeout=30)
        self._client = zeep.Client(wsdl=wsdl, transport=transport)
        _logger.info(
            "NFeDistribuicaoDFe: CNPJ %s, ambiente %s, SVC-AN=%s",
            cnpj,
            "produção" if ambiente == "1" else "homologação",
            usar_svc_an,
        )

    def dist_dfe_interesse(self, ultimo_nsu: int) -> tuple[list[dict], dict]:
        """
        Retorna (docs, flags).
        flags pode conter: bloqueado=True + bloqueado_ate (cStat 656),
                           paralisado=True (cStat 108),
                           ultima_consulta (sempre presente).
        """
        docs: list[dict] = []
        nsu_atual = ultimo_nsu
        flags: dict = {"ultima_consulta": datetime.now(timezone.utc).isoformat()}

        while True:
            try:
                resp = self._client.service.nfeDistDFeInteresse(
                    nfeDadosMsg={
                        "distNSU": {
                            "tpAmb":    self.ambiente,
                            "cUFAutor": CUF_NACIONAL,
                            "CNPJ":     self.cnpj,
                            "distNSU":  {"ultNSU": f"{nsu_atual:015d}"},
                        }
                    }
                )
            except Exception as exc:
                _logger.error("[%s] SEFAZ NFe: erro SOAP: %s", self.cnpj, exc)
                raise

            ret  = resp.get("retDistDFeInt") if isinstance(resp, dict) else resp
            code = int(getattr(ret, "cStat", 0))

            # Atualiza timestamp da última consulta bem-sucedida (mesmo sem docs)
            flags["ultima_consulta"] = datetime.now(timezone.utc).isoformat()

            if code == CODE_SEM_NOVOS:
                _logger.info("[%s] SEFAZ NFe: sem documentos novos (NSU=%d)", self.cnpj, nsu_atual)
                break

            if code == CODE_CONSUMIDOR:
                bloqueado_ate = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
                _logger.error("[%s] SEFAZ NFe: cStat 656 — consumo excessivo, bloqueado até %s",
                              self.cnpj, bloqueado_ate)
                flags["bloqueado"]     = True
                flags["bloqueado_ate"] = bloqueado_ate
                break

            if code == CODE_PARALISADO:
                _logger.warning("[%s] SEFAZ NFe: cStat 108 — SEFAZ paralisada", self.cnpj)
                flags["paralisado"] = True
                break

            if code not in (CODE_OK, 100):
                _logger.warning("[%s] SEFAZ NFe: cStat=%d xMotivo=%s",
                                self.cnpj, code, getattr(ret, "xMotivo", ""))
                break

            lote = getattr(ret, "loteDistDFeInt", None)
            if not lote:
                break

            doc_zips = getattr(lote, "docZip", []) or []
            for dz in doc_zips:
                schema_num = int(
                    getattr(dz, "_value_1", {}).get("schema", 0)
                    or getattr(dz, "schema", 0)
                    or 0
                )
                nsu     = int(getattr(dz, "NSU", nsu_atual))
                xml_gz  = getattr(dz, "_value_1", None) or getattr(dz, "value", None) or dz
                xml_str = _decompress(xml_gz) if xml_gz else ""

                tipo        = "cancelamento" if schema_num == SCHEMA_EVENTO_CANCEL else "documento"
                tipo_schema = "resumo"       if schema_num == SCHEMA_RESUMO_NFE    else "completo"

                docs.append({
                    "nsu":         nsu,
                    "schema":      schema_num,
                    "tipo":        tipo,
                    "tipo_schema": tipo_schema,
                    "xml":         xml_str,
                    "xml_hash":    hashlib.sha256(xml_str.encode("utf-8")).hexdigest() if xml_str else None,
                    "fonte":       "sefaz",
                })
                nsu_atual = max(nsu_atual, nsu)

            max_nsu = int(getattr(ret, "maxNSU", nsu_atual))
            if nsu_atual >= max_nsu:
                break

            time.sleep(3)   # SEFAZ: 20 req/hora + 600 req/5min — sleep 3s ≈ 20/min, bem abaixo

        return docs, flags


def fetch_nfe_by_key(
    chave: str,
    cert_path: Optional[str],
    key_path: Optional[str],
    ambiente: str = "1",
) -> Optional[str]:
    """
    Busca NF-e por chave de acesso via NfeConsultaProtocolo (serviço estadual).
    Extrai cUF dos 2 primeiros dígitos da chave para selecionar URL do estado.
    Retorna XML string da NF-e ou None.
    """
    if not cert_path or not key_path:
        _logger.warning("fetch_nfe_by_key: certificado ausente, busca ignorada")
        return None

    c_uf = chave[:2]
    wsdl_base = _NF_CONSULTA_URL.get(c_uf, _NF_CONSULTA_SVCAN)
    if ambiente != "1":
        # Homologação usa SVAN/SVC-AN nacional
        wsdl_base = "https://hom1.nfe.fazenda.gov.br/NFeConsulta2/NFeConsulta2.asmx"

    wsdl = wsdl_base + "?wsdl"

    try:
        session = requests.Session()
        session.cert   = (cert_path, key_path)
        session.verify = True

        transport = Transport(session=session, timeout=20)
        client    = zeep.Client(wsdl=wsdl, transport=transport)

        resp = client.service.nfeConsultaNF(
            nfeCons={
                "tpAmb":  int(ambiente),
                "xServ":  "CONSULTAR",
                "chNFe":  chave,
            }
        )

        ret  = resp.get("retConsSitNFe") if isinstance(resp, dict) else resp
        code = int(getattr(ret, "cStat", 0))

        if code == 100:  # Autorizada
            proc_nfe = getattr(ret, "protNFe", None)
            if proc_nfe:
                xml_bytes = getattr(proc_nfe, "xml", None) or getattr(proc_nfe, "xmlDoc", None)
                if isinstance(xml_bytes, bytes):
                    return xml_bytes.decode("utf-8")
                if isinstance(xml_bytes, str):
                    return xml_bytes
        _logger.info("fetch_nfe_by_key: chave=%s cStat=%d", chave[:20], code)

    except Exception as exc:
        _logger.warning("fetch_nfe_by_key erro (cUF=%s): %s", c_uf, exc)

    return None


def _decompress(data) -> str:
    import base64
    import gzip
    try:
        if isinstance(data, str):
            data = base64.b64decode(data)
        return gzip.decompress(data).decode("utf-8")
    except Exception:
        if isinstance(data, (bytes, bytearray)):
            return data.decode("utf-8", errors="replace")
        return str(data)
