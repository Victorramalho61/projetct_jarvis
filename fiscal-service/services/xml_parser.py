import hashlib
import logging
from typing import Optional
import xml.etree.ElementTree as ET

_logger = logging.getLogger(__name__)

NS_NFE  = "http://www.portalfiscal.inf.br/nfe"
NS_CTE  = "http://www.portalfiscal.inf.br/cte"
NS_NFSE = "http://www.sped.fazenda.gov.br/nfse"


def parse_xml_auto(xml_str: str) -> Optional[dict]:
    if not xml_str or not xml_str.strip().startswith("<"):
        return None
    try:
        # Strip UTF-8 BOM if present
        clean = xml_str.lstrip("﻿")
        root = ET.fromstring(clean)
        tag = root.tag.lower()
        if f"{{{NS_NFSE}}}" in root.tag or "nfse" in tag:
            return parse_nfse_portal(clean)
        if "nfe" in tag or f"{{{NS_NFE}}}" in root.tag:
            return parse_nfe(clean)
        if "cte" in tag or f"{{{NS_CTE}}}" in root.tag:
            return parse_cte(clean)
        return None
    except ET.ParseError as e:
        _logger.warning("XML parse error: %s", e)
        return None


def _compute_hash(xml_str: str) -> str:
    """SHA-256 do XML original (UTF-8 sem BOM) — requisito compliance fiscal 5+ anos."""
    return hashlib.sha256(xml_str.encode("utf-8")).hexdigest()


def parse_nfse_portal(xml_str: str) -> Optional[dict]:
    """Parse NFS-e do Portal Nacional ADN. Namespace: http://www.sped.fazenda.gov.br/nfse"""
    try:
        clean = xml_str.lstrip("﻿")
        root = ET.fromstring(clean)

        inf = root.find(f".//{{{NS_NFSE}}}InfNFSe") or root.find(".//InfNFSe")
        if inf is None:
            return None

        def txt(path):
            el = inf.find(path)
            return el.text.strip() if el is not None and el.text else ""

        def ptxt(el, tag):
            if el is None:
                return ""
            child = el.find(f".//{{{NS_NFSE}}}{tag}")
            if child is None:
                child = el.find(f".//{tag}")
            return child.text.strip() if child is not None and child.text else ""

        prest = inf.find(f"{{{NS_NFSE}}}Prestador") or inf.find("Prestador")
        tomad = inf.find(f"{{{NS_NFSE}}}Tomador")   or inf.find("Tomador")
        vals  = inf.find(f".//{{{NS_NFSE}}}Valores") or inf.find(".//Valores")

        data_raw = txt(f"{{{NS_NFSE}}}DataEmissao") or txt(f"{{{NS_NFSE}}}DhEmi")

        return {
            "tipo":              "NFSe",
            "chave_acesso":      inf.get("Id") or txt(f"{{{NS_NFSE}}}ChaveAcesso"),
            "numero":            txt(f"{{{NS_NFSE}}}Numero") or txt(f"{{{NS_NFSE}}}NumeroNFSe"),
            "serie":             txt(f"{{{NS_NFSE}}}Serie") or None,
            "data_emissao":      data_raw[:10] if data_raw else None,
            "emitente_cnpj":     ptxt(prest, "Cnpj"),
            "emitente_nome":     ptxt(prest, "RazaoSocial") or ptxt(prest, "NomePrestador"),
            "destinatario_cnpj": ptxt(tomad, "Cnpj"),
            "destinatario_nome": ptxt(tomad, "RazaoSocial") or ptxt(tomad, "NomeTomador"),
            "valor_total":       _decimal(ptxt(vals, "ValorServicos")),
            "valor_iss":         _decimal(ptxt(vals, "ValorIss")),
            "valor_pis":         _decimal(ptxt(vals, "ValorPis")),
            "valor_cofins":      _decimal(ptxt(vals, "ValorCofins")),
            "valor_icms":        0.0,
            "valor_produtos":    _decimal(ptxt(vals, "ValorServicos")),
            "municipio_ibge":    txt(f"{{{NS_NFSE}}}CodigoMunicipio") or None,
            "status":            "pendente",
            "fonte":             "portal_nacional",
            "_items":            [],
        }
    except Exception as e:
        _logger.warning("parse_nfse_portal erro: %s", e)
        return None


def parse_nfe(xml_str: str) -> Optional[dict]:
    try:
        root = ET.fromstring(xml_str)
        ns = {"n": NS_NFE}

        inf = root.find(f".//{{{NS_NFE}}}infNFe") or root.find(".//infNFe")
        if inf is None:
            return None

        def t(path, default=""):
            el = inf.find(path, ns) if ns else inf.find(path)
            return el.text if el is not None and el.text else default

        ide = inf.find("n:ide", ns) or inf.find("ide")
        emit = inf.find("n:emit", ns) or inf.find("emit")
        dest = inf.find("n:dest", ns) or inf.find("dest")
        total = inf.find(".//n:ICMSTot", ns) or inf.find(".//ICMSTot")

        def txt(el, path, default=""):
            if el is None:
                return default
            child = el.find(f"n:{path}", ns) or el.find(path)
            return child.text if child is not None and child.text else default

        chave = inf.get("Id", "").replace("NFe", "") or None
        if not chave:
            chave = txt(ide, "cNF") or None

        doc: dict = {
            "tipo": "NFe",
            "chave_acesso": chave,
            "numero": txt(ide, "nNF"),
            "serie": txt(ide, "serie"),
            "natureza_operacao": txt(ide, "natOp"),
            "data_emissao": txt(ide, "dhEmi")[:10] if txt(ide, "dhEmi") else txt(ide, "dEmi"),
            "emitente_cnpj": txt(emit, "CNPJ"),
            "emitente_nome": txt(emit, "xNome"),
            "destinatario_cnpj": txt(dest, "CNPJ") or txt(dest, "CPF"),
            "destinatario_nome": txt(dest, "xNome"),
            "valor_total": _decimal(txt(total, "vNF")),
            "valor_produtos": _decimal(txt(total, "vProd")),
            "valor_icms": _decimal(txt(total, "vICMS")),
            "valor_pis": _decimal(txt(total, "vPIS")),
            "valor_cofins": _decimal(txt(total, "vCOFINS")),
            "status": "pendente",
        }

        items = _parse_nfe_items(inf, ns)
        doc["_items"] = items

        return doc
    except Exception as e:
        _logger.warning("parse_nfe erro: %s", e)
        return None


def _parse_nfe_items(inf, ns: dict) -> list[dict]:
    items = []
    dets = inf.findall("n:det", ns) or inf.findall("det")
    for det in dets:
        prod = det.find("n:prod", ns) or det.find("prod")
        imp = det.find("n:imposto", ns) or det.find("imposto")

        def pt(el, path, default=""):
            if el is None:
                return default
            child = el.find(f"n:{path}", ns) or el.find(path)
            return child.text if child is not None and child.text else default

        item: dict = {
            "numero_item": int(det.get("nItem", 0)),
            "descricao": pt(prod, "xProd"),
            "ncm": pt(prod, "NCM"),
            "cfop": pt(prod, "CFOP"),
            "quantidade": _decimal(pt(prod, "qCom")),
            "valor_unitario": _decimal(pt(prod, "vUnCom")),
            "valor_produto": _decimal(pt(prod, "vProd")),
        }

        if imp is not None:
            icms_group = imp.find(".//") if False else None
            # Find any ICMS sub-element
            for icms_tag in ["ICMS00", "ICMS10", "ICMS20", "ICMS30", "ICMS40",
                             "ICMS41", "ICMS50", "ICMS51", "ICMS60", "ICMS70", "ICMS90"]:
                icms_el = imp.find(f".//n:{icms_tag}", ns) or imp.find(f".//{icms_tag}")
                if icms_el is not None:
                    icms_group = icms_el
                    break

            if icms_group is not None:
                item["cst_icms"] = pt(icms_group, "CST") or pt(icms_group, "CSOSN")
                item["base_icms"] = _decimal(pt(icms_group, "vBC"))
                item["aliquota_icms"] = _decimal(pt(icms_group, "pICMS"))
                item["valor_icms"] = _decimal(pt(icms_group, "vICMS"))

            # DIFAL (EC 87/2015)
            icms_uf = imp.find(".//n:ICMSUFDest", ns) or imp.find(".//ICMSUFDest")
            if icms_uf is not None:
                item["valor_icms_uf_dest"] = _decimal(pt(icms_uf, "vICMSUFDest"))
                item["valor_icms_uf_remi"] = _decimal(pt(icms_uf, "vICMSUFRemi"))
                item["valor_fcp_uf_dest"] = _decimal(pt(icms_uf, "vFCPUFDest"))

            # PIS
            pis_el = imp.find(".//n:PISAliq", ns) or imp.find(".//PISAliq") or \
                     imp.find(".//n:PISQtde", ns) or imp.find(".//PISQtde") or \
                     imp.find(".//n:PISNT", ns) or imp.find(".//PISNT")
            if pis_el is not None:
                item["cst_pis"] = pt(pis_el, "CST")
                item["base_pis"] = _decimal(pt(pis_el, "vBC"))
                item["aliquota_pis"] = _decimal(pt(pis_el, "pPIS"))
                item["valor_pis"] = _decimal(pt(pis_el, "vPIS"))

            # COFINS
            cof_el = imp.find(".//n:COFINSAliq", ns) or imp.find(".//COFINSAliq") or \
                     imp.find(".//n:COFINSNT", ns) or imp.find(".//COFINSNT")
            if cof_el is not None:
                item["cst_cofins"] = pt(cof_el, "CST")
                item["base_cofins"] = _decimal(pt(cof_el, "vBC"))
                item["aliquota_cofins"] = _decimal(pt(cof_el, "pCOFINS"))
                item["valor_cofins"] = _decimal(pt(cof_el, "vCOFINS"))

        items.append(item)
    return items


def parse_cte(xml_str: str) -> Optional[dict]:
    try:
        root = ET.fromstring(xml_str)
        ns = {"c": NS_CTE}

        inf = root.find(f".//{{{NS_CTE}}}infCte") or root.find(".//infCte")
        if inf is None:
            return None

        def txt(el, path, default=""):
            if el is None:
                return default
            child = el.find(f"c:{path}", ns) or el.find(path)
            return child.text if child is not None and child.text else default

        ide = inf.find("c:ide", ns) or inf.find("ide")
        emit = inf.find("c:emit", ns) or inf.find("emit")
        dest = inf.find("c:dest", ns) or inf.find("dest")
        vPrest = inf.find(".//c:vTPrest", ns) or inf.find(".//vTPrest")

        chave = inf.get("Id", "").replace("CTe", "") or None

        return {
            "tipo": "CTe",
            "chave_acesso": chave,
            "numero": txt(ide, "nCT"),
            "serie": txt(ide, "serie"),
            "natureza_operacao": txt(ide, "natOp") or "Prestação de Serviço de Transporte",
            "data_emissao": txt(ide, "dhEmi")[:10] if txt(ide, "dhEmi") else txt(ide, "dEmi"),
            "emitente_cnpj": txt(emit, "CNPJ"),
            "emitente_nome": txt(emit, "xNome"),
            "destinatario_cnpj": txt(dest, "CNPJ") or txt(dest, "CPF"),
            "destinatario_nome": txt(dest, "xNome") or txt(dest, "xRem"),
            "valor_total": _decimal(vPrest.text if vPrest is not None else "0"),
            "valor_produtos": _decimal(vPrest.text if vPrest is not None else "0"),
            "valor_icms": 0,
            "valor_pis": 0,
            "valor_cofins": 0,
            "status": "pendente",
            "_items": [],
        }
    except Exception as e:
        _logger.warning("parse_cte erro: %s", e)
        return None


def _decimal(value: str) -> float:
    try:
        return float(value) if value else 0.0
    except (ValueError, TypeError):
        return 0.0
