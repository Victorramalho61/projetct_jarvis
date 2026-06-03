import hashlib
import logging
import time
from datetime import datetime, timedelta, timezone
from typing import Optional

import requests
import zeep
from lxml import etree
from zeep.transports import Transport

_NS_NFE = "http://www.portalfiscal.inf.br/nfe"

# SEFAZ NAN (www1.nfe.fazenda.gov.br) não aceita cUFAutor=91 (nacional) —
# retorna cStat=215 (falha de schema). Deve-se usar o código IBGE do estado da empresa.
_UF_IBGE: dict[str, int] = {
    "AC": 12, "AL": 27, "AM": 13, "AP": 16, "BA": 29, "CE": 23,
    "DF": 53, "ES": 32, "GO": 52, "MA": 21, "MG": 31, "MS": 50,
    "MT": 51, "PA": 15, "PB": 25, "PE": 26, "PI": 22, "PR": 41,
    "RJ": 33, "RN": 24, "RO": 11, "RR": 14, "RS": 43, "SC": 42,
    "SE": 28, "SP": 35, "TO": 17,
}


class _RetWrapper:
    """Normaliza a resposta da SEFAZ: zeep Object (antigo) ou lxml Element (novo xsd:any)."""

    def __init__(self, obj):
        # Descarta envelope: dict {"retDistDFeInt": ...} → usa o filho
        if isinstance(obj, dict):
            obj = obj.get("retDistDFeInt", obj)
        self._obj = obj
        self._is_xml = hasattr(obj, "find")   # lxml Element

    def get(self, field: str, default=None):
        if self._is_xml:
            el = self._obj.find(f"{{{_NS_NFE}}}{field}")
            return el.text if el is not None else default
        return getattr(self._obj, field, default)

    def lote(self):
        if self._is_xml:
            el = self._obj.find(f"{{{_NS_NFE}}}loteDistDFeInt")
            return _LoteWrapper(el) if el is not None else None
        obj = getattr(self._obj, "loteDistDFeInt", None)
        return _LoteWrapper(obj) if obj is not None else None


class _LoteWrapper:
    def __init__(self, obj):
        self._obj = obj
        self._is_xml = hasattr(obj, "findall")

    def doc_zips(self):
        if self._is_xml:
            return [_DocZipWrapper(dz) for dz in self._obj.findall(f"{{{_NS_NFE}}}docZip")]
        raw = getattr(self._obj, "docZip", []) or []
        return [_DocZipWrapper(dz) for dz in raw]


class _DocZipWrapper:
    def __init__(self, obj):
        self._obj = obj
        self._is_xml = hasattr(obj, "get")   # lxml Element usa .get() para atributos

    def schema(self):
        if self._is_xml:
            return self._obj.get("schema") or self._obj.get("{http://www.w3.org/2001/XMLSchema-instance}schema")
        return getattr(self._obj, "schema", None) or (getattr(self._obj, "_value_1", {}) or {}).get("schema")

    def nsu(self):
        if self._is_xml:
            return self._obj.get("NSU")
        return getattr(self._obj, "NSU", None)

    def gz(self):
        if self._is_xml:
            return self._obj.text   # conteúdo base64+gzip fica no text do elemento
        return getattr(self._obj, "_value_1", None) or getattr(self._obj, "value", None) or self._obj


def _ret(resp) -> _RetWrapper:
    return _RetWrapper(resp)


def _build_dist_nsu(tpAmb: int, c_uf: int, cnpj: str, ult_nsu: int) -> etree._Element:
    """Constrói o elemento distDFeInt como lxml Element.

    O WSDL da SEFAZ define nfeDadosMsg como xsd:any (_value_1: ANY),
    portanto zeep não aceita dict com kwargs — requer elemento XML diretamente.
    nsmap={None: NS} força namespace default sem prefixo (SEFAZ rejeita ns0:distDFeInt).
    """
    nsmap = {None: _NS_NFE}
    root = etree.Element(f"{{{_NS_NFE}}}distDFeInt", nsmap=nsmap, versao="1.01")
    etree.SubElement(root, f"{{{_NS_NFE}}}tpAmb").text = str(tpAmb)
    etree.SubElement(root, f"{{{_NS_NFE}}}cUFAutor").text = str(c_uf)
    etree.SubElement(root, f"{{{_NS_NFE}}}CNPJ").text = cnpj
    dist_nsu_el = etree.SubElement(root, f"{{{_NS_NFE}}}distNSU")
    etree.SubElement(dist_nsu_el, f"{{{_NS_NFE}}}ultNSU").text = f"{ult_nsu:015d}"
    return root

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
        uf_autor: Optional[str] = None,
    ):
        self.cnpj     = cnpj
        self.ambiente = int(ambiente)
        # cUFAutor deve ser o IBGE do estado da empresa — www1 rejeita cUFAutor=91
        self.c_uf_autor = _UF_IBGE.get(uf_autor or "", CUF_NACIONAL)

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
                # nfeDadosMsg é complexType com campo _value_1: ANY
                # Passar o element diretamente causaria cStat=215 (zeep não wrappa corretamente)
                resp = self._client.service.nfeDistDFeInteresse(
                    nfeDadosMsg={"_value_1": _build_dist_nsu(self.ambiente, self.c_uf_autor, self.cnpj, nsu_atual)}
                )
            except Exception as exc:
                _logger.error("[%s] SEFAZ NFe: erro SOAP: %s", self.cnpj, exc)
                raise

            # SEFAZ atualizou nfeResultMsg para xsd:any → zeep devolve lxml Element.
            # _ret() normaliza para um wrapper que aceita .get(field) em ambos os casos.
            ret  = _ret(resp)
            code = int(ret.get("cStat") or 0)

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
                                self.cnpj, code, ret.get("xMotivo") or "")
                break

            lote = ret.lote()
            if not lote:
                break

            doc_zips = lote.doc_zips()
            for dz in doc_zips:
                schema_num = int(dz.schema() or 0)
                nsu        = int(dz.nsu() or nsu_atual)
                xml_gz     = dz.gz()
                xml_str    = _decompress(xml_gz) if xml_gz else ""

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

            max_nsu = int(ret.get("maxNSU") or nsu_atual)
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
