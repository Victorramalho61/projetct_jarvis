import logging
from typing import Optional

import requests
import zeep
from zeep.transports import Transport

_logger = logging.getLogger(__name__)

WSDL_CTE_PROD = "https://www1.cte.fazenda.gov.br/CTeDistribuicaoDFe/CTeDistribuicaoDFe.asmx?WSDL"
WSDL_CTE_HOM  = "https://hom1.cte.fazenda.gov.br/CTeDistribuicaoDFe/CTeDistribuicaoDFe.asmx?WSDL"

CUF_NACIONAL = 91

SCHEMA_PROC_CTE      = 57
SCHEMA_EVENTO_CANCEL = 110111
SCHEMA_CARTA_CORR    = 110110


class CTeDistribuicaoDFe:
    def __init__(self, cnpj: str, cert_path: Optional[str], key_path: Optional[str], ambiente: str = "1"):
        self.cnpj = cnpj
        self.ambiente = int(ambiente)
        wsdl = WSDL_CTE_PROD if ambiente == "1" else WSDL_CTE_HOM

        session = requests.Session()
        if cert_path and key_path:
            session.cert = (cert_path, key_path)
        session.verify = True

        transport = Transport(session=session, timeout=30)
        self._client = zeep.Client(wsdl=wsdl, transport=transport)
        _logger.info("CTeDistribuicaoDFe: CNPJ %s, ambiente %s", cnpj,
                     "produção" if ambiente == "1" else "homologação")

    def dist_dfe_interesse(self, ultimo_nsu: int) -> list[dict]:
        docs = []
        nsu_atual = ultimo_nsu

        while True:
            try:
                resp = self._client.service.cteDistDFeInteresse(
                    cteDadosMsg={
                        "distNSU": {
                            "tpAmb": self.ambiente,
                            "cUFAutor": CUF_NACIONAL,
                            "CNPJ": self.cnpj,
                            "distNSU": {"ultNSU": f"{nsu_atual:015d}"},
                        }
                    }
                )
            except Exception as e:
                _logger.error("SEFAZ CTe: erro na chamada SOAP: %s", e)
                raise

            retDistDFeInt = resp.get("retDistDFeInt") if isinstance(resp, dict) else resp
            code = int(getattr(retDistDFeInt, "cStat", 0))

            if code == 137:
                _logger.info("SEFAZ CTe: sem documentos novos (NSU=%d)", nsu_atual)
                break

            if code not in (138, 100):
                _logger.warning("SEFAZ CTe: cStat=%d xMotivo=%s", code,
                                getattr(retDistDFeInt, "xMotivo", ""))
                break

            lote = getattr(retDistDFeInt, "loteDistDFeInt", None)
            if not lote:
                break

            doc_zips = getattr(lote, "docZip", []) or []
            for dz in doc_zips:
                schema = int(getattr(dz, "schema", 0) or 0)
                nsu = int(getattr(dz, "NSU", nsu_atual))
                xml_gz = getattr(dz, "_value_1", None) or getattr(dz, "value", None) or dz

                tipo = "cancelamento" if schema == SCHEMA_EVENTO_CANCEL else "documento"
                docs.append({
                    "nsu": nsu,
                    "schema": schema,
                    "tipo": tipo,
                    "xml": _decompress(xml_gz) if xml_gz else "",
                })
                nsu_atual = max(nsu_atual, nsu)

            max_nsu = int(getattr(retDistDFeInt, "maxNSU", nsu_atual))
            if nsu_atual >= max_nsu:
                break

        return docs


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
