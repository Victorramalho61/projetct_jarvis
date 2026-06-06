import csv
import io
import xml.etree.ElementTree as ET

COLUMNS = [
    ("data_hora_acesso", "Data/Hora Acesso"),
    ("user_nome", "Colaborador"),
    ("user_login", "Login"),
    ("ip_origem", "IP Origem"),
    ("localizador_os", "Localizador/OS"),
    ("nome_cliente", "Cliente"),
    ("produto", "Produto"),
    ("data_reserva", "Data Reserva"),
    ("nome_pax", "Nome PAX"),
    ("fornecedor", "Fornecedor"),
    ("valor_transacao", "Valor Transação (R$)"),
]


def _flatten(row: dict) -> dict:
    card = row.get("cards_cartoes") or {}
    cli = (card.get("cards_clientes") or {}) if isinstance(card, dict) else {}
    flat = {k: str(row.get(k) or "") for k, _ in COLUMNS}
    flat["cartao_4dig"] = f"****{card.get('numero_final', '')}" if isinstance(card, dict) else ""
    flat["bandeira"] = card.get("bandeira", "") if isinstance(card, dict) else ""
    flat["cliente_cartao"] = cli.get("nome", "") if isinstance(cli, dict) else ""
    return flat


_EXTRA_COLS = [
    ("cartao_4dig", "Cartão (4 dígitos)"),
    ("bandeira", "Bandeira"),
    ("cliente_cartao", "Cliente do Cartão"),
]


def to_csv(rows: list[dict]) -> str:
    out = io.StringIO()
    all_cols = COLUMNS + _EXTRA_COLS
    fieldnames = [k for k, _ in all_cols]
    headers = {k: h for k, h in all_cols}
    writer = csv.DictWriter(out, fieldnames=fieldnames, extrasaction="ignore")
    writer.writerow(headers)
    for row in rows:
        writer.writerow(_flatten(row))
    return "﻿" + out.getvalue()  # BOM para Excel abrir corretamente


def to_xml(rows: list[dict]) -> str:
    root = ET.Element("acessos_cartoes")
    all_cols = COLUMNS + _EXTRA_COLS
    for row in rows:
        flat = _flatten(row)
        item = ET.SubElement(root, "acesso")
        for col, _ in all_cols:
            el = ET.SubElement(item, col)
            el.text = flat.get(col, "")
    return '<?xml version="1.0" encoding="UTF-8"?>\n' + ET.tostring(root, encoding="unicode")
