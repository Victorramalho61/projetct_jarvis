import logging
import threading
from datetime import date, datetime, timezone, timedelta
from typing import Optional

import requests
import zeep
from zeep.transports import Transport

from services.nfse_city_registry import NFSE_CITY_REGISTRY, NDD_BASE, NDD_IDENTITY

_logger = logging.getLogger(__name__)

# ── ND Digital token — lê do banco, renova via refresh_token se disponível ────
_ndd_token_lock = threading.Lock()
NDD_CLIENT_ID = "ndd-identity-space-gateway"


def _get_ndd_token(company_id: str) -> str:
    """
    Retorna access_token válido para o ND Digital portal.
    Prioridade:
      1. access_token no DB ainda válido → retorna direto
      2. refresh_token no DB → troca por novo access_token
      3. Nenhum → levanta erro (admin deve reconectar via /ndd/authorize ou /ndd/token)
    """
    from db import get_supabase
    with _ndd_token_lock:
        sb = get_supabase()
        row = sb.table("fiscal_companies").select(
            "ndd_access_token,ndd_refresh_token,ndd_token_expires_at"
        ).eq("id", company_id).execute()

        if not row.data:
            raise ValueError(f"Empresa {company_id} não encontrada")

        r = row.data[0]
        access_token = r.get("ndd_access_token") or ""
        refresh_token = r.get("ndd_refresh_token") or ""
        expires_at_str = r.get("ndd_token_expires_at") or ""

        # Verifica se access_token ainda é válido (com 60s de margem)
        if access_token and expires_at_str:
            try:
                exp = datetime.fromisoformat(expires_at_str)
                if exp.tzinfo is None:
                    exp = exp.replace(tzinfo=timezone.utc)
                if datetime.now(timezone.utc) < exp - timedelta(seconds=60):
                    return access_token
            except ValueError:
                pass

        # Tenta renovar com refresh_token
        if refresh_token:
            try:
                resp = requests.post(
                    f"{NDD_IDENTITY}/connect/token",
                    data={
                        "grant_type": "refresh_token",
                        "client_id": NDD_CLIENT_ID,
                        "refresh_token": refresh_token,
                    },
                    timeout=15,
                )
                resp.raise_for_status()
                data = resp.json()
                new_access = data["access_token"]
                new_refresh = data.get("refresh_token", refresh_token)
                expires_in = int(data.get("expires_in", 1800))
                new_expires = (datetime.now(timezone.utc) + timedelta(seconds=expires_in)).isoformat()

                sb.table("fiscal_companies").update({
                    "ndd_access_token": new_access,
                    "ndd_refresh_token": new_refresh,
                    "ndd_token_expires_at": new_expires,
                }).eq("id", company_id).execute()

                _logger.info("NDD Digital empresa %s: token renovado via refresh_token", company_id)
                return new_access
            except Exception as e:
                _logger.error("NDD Digital: falha ao renovar token via refresh_token: %s", e)

        raise RuntimeError(
            f"NDD Digital: token expirado para empresa {company_id}. "
            "Admin deve reconectar via POST /api/fiscal/{id}/ndd/token "
            "ou GET /api/fiscal/{id}/ndd/authorize"
        )


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
            "nddigital":  self._fetch_nddigital,
        }
        return dispatch[city["tipo"]](ibge, city["url"], data_inicio, data_fim)

    def _fetch_nddigital(self, ibge: str, _url: str, data_inicio: date, data_fim: date) -> list[dict]:
        # company_id é o CNPJ — não temos acesso direto aqui, então usamos o CNPJ
        # para encontrar o company_id no banco
        from db import get_supabase
        sb = get_supabase()
        company_row = sb.table("fiscal_companies").select("id").eq("cnpj", self.cnpj).execute()
        if not company_row.data:
            _logger.warning("NDD Digital: empresa CNPJ %s não encontrada no banco", self.cnpj)
            return []
        company_id = company_row.data[0]["id"]

        try:
            token = _get_ndd_token(company_id)
        except RuntimeError as e:
            _logger.warning("%s", e)
            return []
        except Exception as e:
            _logger.error("NDD Digital: falha ao obter token: %s", e)
            raise

        # Nota: campo `municipio` na API é nome da cidade (ex: "Rio de Janeiro"),
        # não código IBGE. Buscamos tudo por data e filtramos por CNPJ do tomador.
        base = f"{NDD_BASE}/nfse-api/api/NFSeRecepcao"
        headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}

        odata_filter = (
            f"dataEmissao ge {data_inicio.isoformat()}T00:00:00 "
            f"and dataEmissao le {data_fim.isoformat()}T23:59:59"
        )

        # Busca nome da cidade pelo IBGE para filtrar na resposta
        city_info = NFSE_CITY_REGISTRY.get(ibge, {})
        city_name_norm = city_info.get("nome", "").upper()

        docs = []
        skip = 0
        page_size = 100

        while True:
            try:
                resp = requests.get(
                    base,
                    headers=headers,
                    params={
                        "$filter": odata_filter,
                        "$top": page_size,
                        "$skip": skip,
                        "$orderby": "dataEmissao asc",
                    },
                    timeout=30,
                )
                resp.raise_for_status()
            except Exception as e:
                _logger.error("NDD Digital IBGE %s skip=%d: %s", ibge, skip, e)
                raise

            data = resp.json()
            items = data if isinstance(data, list) else data.get("items", data.get("value", []))
            if not items:
                break

            for item in items:
                # Filtra pelo município da cidade (nome) se ibge especificado
                if city_name_norm:
                    item_city = (item.get("municipio") or "").upper()
                    item_uf = (item.get("uf") or "").upper()
                    city_uf = city_info.get("uf", "").upper()
                    if city_name_norm not in item_city and item_uf != city_uf:
                        continue

                nfse_id = item.get("id")
                xml_content = None
                if nfse_id:
                    try:
                        xml_resp = requests.get(
                            f"{base}/xml/{nfse_id}",
                            headers=headers,
                            timeout=15,
                        )
                        if xml_resp.ok:
                            xml_data = xml_resp.json()
                            xml_content = xml_data.get("xml") or xml_data.get("xmlNfse")
                    except Exception:
                        pass

                uid = item.get("identificadorUnico") or f"ndd{nfse_id}"
                docs.append({
                    "tipo": "NFSe",
                    "numero": str(item.get("numero") or ""),
                    "serie": item.get("serie") or "",
                    "chave_acesso": uid.ljust(44, "0")[:44],
                    "data_emissao": (item.get("dataEmissao") or "")[:10] or None,
                    "emitente_cnpj": (item.get("cnpjPrestador") or "").replace(".", "").replace("/", "").replace("-", ""),
                    "emitente_nome": item.get("nomePrestador") or "",
                    "destinatario_cnpj": (item.get("cnpjTomador") or "").replace(".", "").replace("/", "").replace("-", ""),
                    "destinatario_nome": item.get("nomeTomador") or "",
                    "valor_total": float(item.get("valorTotalServicos") or 0),
                    "valor_pis": float(item.get("valorPis") or 0),
                    "valor_cofins": float(item.get("valorCofins") or 0),
                    "valor_icms": 0.0,
                    "municipio_ibge": ibge,
                    "status": "pendente",
                    "xml_content": xml_content,
                    "_ndd_id": nfse_id,
                })

            if len(items) < page_size:
                break
            skip += page_size

        _logger.info("NDD Digital IBGE %s: %d notas importadas", ibge, len(docs))
        return docs

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
