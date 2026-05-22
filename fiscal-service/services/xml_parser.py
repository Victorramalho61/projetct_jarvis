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
    """Parse NFS-e do Portal Nacional ADN (gov.br/nfse).
    Estrutura real: <NFSe><infNFSe Id="NFS..."><emit>...<DPS><infDPS><toma>...
    """
    try:
        clean = xml_str.lstrip("﻿")
        root = ET.fromstring(clean)
        ns = NS_NFSE

        # Elemento raiz da nota: infNFSe (i minúsculo)
        inf = (root.find(f"{{{ns}}}infNFSe")
               or root.find(f".//{{{ns}}}infNFSe")
               or root.find("infNFSe")
               or root.find(".//infNFSe"))
        if inf is None:
            # <evento> é documento de cancelamento — silencioso, tratado pelo scheduler
            tag_local = root.tag.split("}")[-1] if "}" in root.tag else root.tag
            if tag_local != "evento":
                _logger.warning("parse_nfse_portal: infNFSe não encontrado. root.tag=%r", root.tag)
            return None

        def _t(el, *tags):
            for tag in tags:
                child = el.find(f"{{{ns}}}{tag}")
                if child is None:
                    child = el.find(tag)
                if child is not None and child.text:
                    return child.text.strip()
            return ""

        # Emitente: <emit><CNPJ>...</CNPJ><xNome>...</xNome></emit>
        emit = inf.find(f"{{{ns}}}emit") or inf.find("emit")

        # Tomador e data de emissão ficam dentro de DPS/infDPS
        inf_dps = inf.find(f".//{{{ns}}}infDPS") or inf.find(".//infDPS")
        toma, data_raw, serie = None, "", None
        if inf_dps is not None:
            toma = inf_dps.find(f"{{{ns}}}toma") or inf_dps.find("toma")
            data_raw = _t(inf_dps, "dhEmi", "dEmi")
            serie_val = _t(inf_dps, "serie")
            serie = serie_val or None

        # Valores: <valores><vLiq>|<vBC> e <vISSQN>
        vals = inf.find(f"{{{ns}}}valores") or inf.find("valores")

        # chave_acesso = Id do infNFSe sem o prefixo "NFS"
        inf_id = inf.get("Id") or ""
        chave = inf_id[3:] if inf_id.startswith("NFS") else inf_id or None

        return {
            "tipo":              "NFSe",
            "chave_acesso":      chave,
            "numero":            _t(inf, "nNFSe", "nDFSe", "nDPS"),
            "serie":             serie,
            "data_emissao":      data_raw[:10] if data_raw else None,
            "emitente_cnpj":     _t(emit, "CNPJ") if emit is not None else "",
            "emitente_nome":     _t(emit, "xNome") if emit is not None else "",
            "destinatario_cnpj": _t(toma, "CNPJ") if toma is not None else "",
            "destinatario_nome": _t(toma, "xNome") if toma is not None else "",
            "valor_total":       _decimal(_t(vals, "vLiq", "vBC") if vals is not None else ""),
            "valor_iss":         _decimal(_t(vals, "vISSQN") if vals is not None else ""),
            "valor_pis":         0.0,
            "valor_cofins":      0.0,
            "valor_icms":        0.0,
            "valor_produtos":    _decimal(_t(vals, "vLiq", "vBC") if vals is not None else ""),
            "municipio_ibge":    _t(inf, "cLocIncid") or None,
            "municipio_nome":    _t(inf, "xLocIncid") or None,
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
