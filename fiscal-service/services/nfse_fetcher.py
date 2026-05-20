import logging
from datetime import date
from typing import Optional

import requests
import zeep
from zeep.transports import Transport

from services.nfse_city_registry import NFSE_CITY_REGISTRY

_logger = logging.getLogger(__name__)


class NFSeFetcher:
    def __init__(self, cnpj: str, cert_path: Optional[str], key_path: Optional[str]):
        self.cnpj = cnpj
        self.cert_path = cert_path
        self.key_path = key_path

    def fetch_municipio(self, ibge: str, data_inicio: date, data_fim: date) -> list[dict]:
        city = NFSE_CITY_REGISTRY.get(ibge)
        if not city:
            _logger.warning(
                "NFSe: município IBGE %s não mapeado. Verifique cadastro na prefeitura.", ibge
            )
            return []

        dispatch = {
            "nacional":   self._fetch_portal_nacional,
            "abrasf":     self._fetch_abrasf,
            "paulistana": self._fetch_paulistana,
            "carioca":    self._fetch_carioca,
            "df":         self._fetch_df,
        }
        return dispatch[city["tipo"]](ibge, city["url"], data_inicio, data_fim)

    def _make_session(self) -> requests.Session:
        session = requests.Session()
        if self.cert_path and self.key_path:
            session.cert = (self.cert_path, self.key_path)
        session.verify = True
        return session

    def _fetch_abrasf(self, ibge: str, url: str, data_inicio: date, data_fim: date) -> list[dict]:
        session = self._make_session()
        transport = Transport(session=session, timeout=30)

        # ABRASF usa WSDL do próprio endpoint ou padrão ABRASF 2.02
        wsdl = url if url.endswith("?wsdl") or url.endswith(".asmx") else f"{url}?wsdl"
        try:
            client = zeep.Client(wsdl=wsdl, transport=transport)
        except Exception as e:
            _logger.error("NFSe ABRASF %s: falha ao carregar WSDL: %s", ibge, e)
            raise

        xml_consulta = f"""<ConsultarNfseServicoPrestadoEnvio xmlns="http://www.abrasf.org.br/nfse.xsd">
  <Prestador>
    <CpfCnpj><Cnpj>{self.cnpj}</Cnpj></CpfCnpj>
  </Prestador>
  <PeriodoEmissao>
    <DataInicial>{data_inicio.isoformat()}</DataInicial>
    <DataFinal>{data_fim.isoformat()}</DataFinal>
  </PeriodoEmissao>
</ConsultarNfseServicoPrestadoEnvio>"""

        try:
            resp = client.service.ConsultarNfseServicoPrestado(
                nfseConsultarServicoPrestadoEnvio=xml_consulta
            )
        except Exception as e:
            _logger.error("NFSe ABRASF %s: erro SOAP: %s", ibge, e)
            raise

        return _parse_abrasf_response(resp, ibge)

    def _fetch_portal_nacional(self, ibge: str, url: str, data_inicio: date, data_fim: date) -> list[dict]:
        # Portal Nacional usa REST com Bearer token (requer cadastro prévio na SEFAZ)
        _logger.info("NFSe Portal Nacional %s: chamando API REST", ibge)
        try:
            resp = requests.get(
                f"{url}/nfse",
                params={
                    "cnpjPrestador": self.cnpj,
                    "codigoMunicipio": ibge,
                    "dataInicial": data_inicio.strftime("%Y-%m-%d"),
                    "dataFinal": data_fim.strftime("%Y-%m-%d"),
                },
                cert=(self.cert_path, self.key_path) if self.cert_path else None,
                timeout=30,
            )
            resp.raise_for_status()
            data = resp.json()
            return _parse_portal_nacional_response(data, ibge)
        except Exception as e:
            _logger.error("NFSe Portal Nacional %s: erro: %s", ibge, e)
            raise

    def _fetch_paulistana(self, ibge: str, url: str, data_inicio: date, data_fim: date) -> list[dict]:
        session = self._make_session()
        transport = Transport(session=session, timeout=30)
        wsdl = f"{url}?wsdl" if "?" not in url else url
        try:
            client = zeep.Client(wsdl=wsdl, transport=transport)
            xml_lote = f"""<p1:PedidoConsultaNFe xmlns:p1="http://www.prefeitura.sp.gov.br/nfe">
  <Cabecalho Versao="1">
    <CPFCNPJRemetente><CNPJ>{self.cnpj}</CNPJ></CPFCNPJRemetente>
    <dtInicio>{data_inicio.strftime("%Y-%m-%d")}</dtInicio>
    <dtFim>{data_fim.strftime("%Y-%m-%d")}</dtFim>
    <pagina>1</pagina>
  </Cabecalho>
</p1:PedidoConsultaNFe>"""
            resp = client.service.ConsultaNFe(VersaoSchema="1", MensagemXML=xml_lote)
            return _parse_paulistana_response(resp, ibge)
        except Exception as e:
            _logger.error("NFSe Paulistana %s: erro: %s", ibge, e)
            raise

    def _fetch_carioca(self, ibge: str, url: str, data_inicio: date, data_fim: date) -> list[dict]:
        # Nota Carioca usa API REST com certificado
        try:
            resp = requests.get(
                url,
                params={
                    "cnpjPrestador": self.cnpj,
                    "dataInicial": data_inicio.strftime("%d/%m/%Y"),
                    "dataFinal": data_fim.strftime("%d/%m/%Y"),
                },
                cert=(self.cert_path, self.key_path) if self.cert_path else None,
                timeout=30,
            )
            resp.raise_for_status()
            return _parse_carioca_response(resp.json(), ibge)
        except Exception as e:
            _logger.error("NFSe Carioca %s: erro: %s", ibge, e)
            raise

    def _fetch_df(self, ibge: str, url: str, data_inicio: date, data_fim: date) -> list[dict]:
        session = self._make_session()
        transport = Transport(session=session, timeout=30)
        wsdl = f"{url}?wsdl" if "?" not in url else url
        try:
            client = zeep.Client(wsdl=wsdl, transport=transport)
            resp = client.service.ConsultarNfseServicoPrestado(
                Prestador={"Cnpj": self.cnpj},
                PeriodoEmissao={"DataInicial": data_inicio.isoformat(), "DataFinal": data_fim.isoformat()},
            )
            return _parse_abrasf_response(resp, ibge)
        except Exception as e:
            _logger.error("NFSe DF %s: erro: %s", ibge, e)
            raise


def _parse_abrasf_response(resp, ibge: str) -> list[dict]:
    docs = []
    try:
        nfses = getattr(resp, "ListaNfse", None) or getattr(resp, "CompNfse", [])
        if not nfses:
            return docs
        items = nfses if isinstance(nfses, list) else [nfses]
        for item in items:
            nfse = getattr(item, "Nfse", item)
            inf = getattr(nfse, "InfNfse", nfse)
            numero = str(getattr(inf, "Numero", "") or "")
            valor = float(getattr(inf, "ValoresNfse", {}).get("ValorLiquidoNfse", 0) or 0)
            data_emit = str(getattr(inf, "DataEmissao", "") or "")[:10]
            docs.append({
                "tipo": "NFSe",
                "numero": numero,
                "chave_acesso": f"{ibge}{numero}".ljust(44, "0")[:44],
                "data_emissao": data_emit or None,
                "valor_total": valor,
                "status": "pendente",
            })
    except Exception as e:
        _logger.warning("NFSe ABRASF parse erro (%s): %s", ibge, e)
    return docs


def _parse_portal_nacional_response(data, ibge: str) -> list[dict]:
    docs = []
    try:
        items = data.get("nfse", data.get("items", [data] if isinstance(data, dict) else data))
        for item in (items or []):
            docs.append({
                "tipo": "NFSe",
                "numero": str(item.get("numero", "")),
                "chave_acesso": item.get("chaveAcesso", "").ljust(44, "0")[:44],
                "data_emissao": item.get("dataEmissao", "")[:10] or None,
                "valor_total": float(item.get("valorLiquidoNfse", 0) or 0),
                "status": "pendente",
            })
    except Exception as e:
        _logger.warning("NFSe Portal Nacional parse erro (%s): %s", ibge, e)
    return docs


def _parse_paulistana_response(resp, ibge: str) -> list[dict]:
    docs = []
    try:
        import xml.etree.ElementTree as ET
        xml_str = str(resp)
        root = ET.fromstring(xml_str) if xml_str.startswith("<") else None
        if root is None:
            return docs
        ns = {"p": "http://www.prefeitura.sp.gov.br/nfe"}
        for nfe in root.findall(".//p:NFe", ns):
            numero = nfe.findtext("p:NumeroNFe", namespaces=ns, default="")
            valor = float(nfe.findtext("p:ValorTotal", namespaces=ns, default="0") or 0)
            data_emit = nfe.findtext("p:DataEmissaoNFe", namespaces=ns, default="")[:10]
            docs.append({
                "tipo": "NFSe",
                "numero": numero,
                "chave_acesso": f"{ibge}{numero}".ljust(44, "0")[:44],
                "data_emissao": data_emit or None,
                "valor_total": valor,
                "status": "pendente",
            })
    except Exception as e:
        _logger.warning("NFSe Paulistana parse erro (%s): %s", ibge, e)
    return docs


def _parse_carioca_response(data, ibge: str) -> list[dict]:
    docs = []
    try:
        items = data if isinstance(data, list) else data.get("nfes", [])
        for item in items:
            docs.append({
                "tipo": "NFSe",
                "numero": str(item.get("numero", "")),
                "chave_acesso": item.get("codigoVerificacao", "").ljust(44, "0")[:44],
                "data_emissao": item.get("dataEmissao", "")[:10] or None,
                "valor_total": float(item.get("valorServicos", 0) or 0),
                "status": "pendente",
            })
    except Exception as e:
        _logger.warning("NFSe Carioca parse erro (%s): %s", ibge, e)
    return docs
