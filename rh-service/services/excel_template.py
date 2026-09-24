"""Gera o .xlsx modelo (formato "Controle de Vagas Voetur Nova") para a equipe preencher e reenviar.

Mesmos nomes de aba/coluna que services/excel_import.py::_importar_modelo_novo lê. As colunas
calculadas da planilha original (data limite, dias, status do prazo) ficam de fora — o Jarvis
recalcula tudo em services/sla.py.
"""
import io

from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill
from openpyxl.worksheet.datavalidation import DataValidation

from services.paginacao import buscar_todos

_COLUNAS = [
    "Nº REQUISIÇÃO", "EMPRESA", "UF", "ALOCAÇÃO REAL", "CARGO / VAGA", "NÍVEL", "CENTRO DE CUSTO",
    "HIERARQUIA", "TIPO DE CONTRATO", "TIPO DA VAGA", "NOME DO SUBSTITUIDO", "REQUISITANTE / GESTOR",
    "RECRUTADOR RESPONSÁVEL", "STATUS POR VAGA", "FUNIL DE VAGAS", "SEÇÃO RESPONSÁVEL",
    "DATA DE ABERTURA", "SLA R&S (DIAS)", "DATA DE FECHAMENTO DO R&S", "CONFIRMAÇÃO DE CONTRATAÇÃO",
    "DATA DE ADMISSÃO", "SLA ADMISSÃO (DIAS)", "OBSERVAÇÕES", "DATA INÍCIO ETAPA ATUAL",
    "SLA ETAPA EXTERNA (DIAS)",
]

_STATUS_PLANILHA = ["ABERTA", "PREENCHIDA/FECHADA", "CANCELADA", "EM STANDBY"]

# coluna da aba LISTAS SUSPENSAS -> (coluna de dados validada, tabela, campo)
_LISTAS = [
    ("EMPRESAS DO GRUPO", "EMPRESA", "rh_empresas", "nome"),
    ("UF", "UF", "rh_ufs", "sigla"),
    ("ALOCAÇÃO REAL", "ALOCAÇÃO REAL", "rh_alocacoes", "nome"),
    ("CARGO", "CARGO / VAGA", "rh_cargos", "nome"),
    ("HIERARQUIA", "HIERARQUIA", "rh_hierarquias", "nome"),
    ("TIPO DO CONTRATO", "TIPO DE CONTRATO", "rh_tipos_contrato", "nome"),
    ("TIPO DA VAGA", "TIPO DA VAGA", "rh_tipos_vaga", "nome"),
    ("RECRUTADORES RESPONSÁVEIS", "RECRUTADOR RESPONSÁVEL", "rh_analistas", "nome"),
    ("REQUISITANTES", "REQUISITANTE / GESTOR", "rh_requisitantes", "nome"),
]


def _header(ws, valores):
    ws.append(valores)
    for c in ws[1]:
        c.font = Font(bold=True, color="FFFFFF")
        c.fill = PatternFill("solid", fgColor="00694E")
        ws.column_dimensions[c.column_letter].width = max(14, len(str(c.value)) + 2)
    ws.freeze_panes = "A2"


def gerar_template(sb) -> io.BytesIO:
    wb = Workbook()
    ws = wb.active
    ws.title = "CONTROLE DE VAGAS"
    _header(ws, _COLUNAS)

    listas = wb.create_sheet("LISTAS SUSPENSAS")

    def _col_dados(nome):
        return ws.cell(row=1, column=_COLUNAS.index(nome) + 1).column_letter

    col = 1
    extras = [
        ("STATUS DA VAGA", "STATUS POR VAGA", _STATUS_PLANILHA),
        ("FUNIL DE VAGAS", "FUNIL DE VAGAS", [
            e["nome"] for e in sb.table("rh_etapas_processo").select("nome,ordem").eq("ativo", True).order("ordem").execute().data
        ]),
    ]
    blocos = [
        (h, dados, sorted(r[campo] for r in buscar_todos(lambda t=t, campo=campo: sb.table(t).select(f"id,{campo}")) if r.get(campo)))
        for h, dados, t, campo in _LISTAS
    ] + extras
    for header, coluna_dados, valores in blocos:
        listas.cell(row=1, column=col, value=header)
        for i, v in enumerate(valores, start=2):
            listas.cell(row=i, column=col, value=v)
        if valores:
            letra = listas.cell(row=1, column=col).column_letter
            dv = DataValidation(
                type="list", formula1=f"'LISTAS SUSPENSAS'!${letra}$2:${letra}${len(valores) + 1}", allow_blank=True
            )
            ws.add_data_validation(dv)
            dv.add(f"{_col_dados(coluna_dados)}2:{_col_dados(coluna_dados)}1000")
        col += 1

    sla_ws = wb.create_sheet("SLA")
    _header(sla_ws, ["CARGO", "TIPO", "R&S", "S LINK ADMISSIONAL", "EXAMES", "ENTREGA DE DOCUMENTOS AO DP", "EMPRESA"])
    for r in buscar_todos(lambda: sb.table("rh_sla_cargos").select("*").order("cargo_nome")):
        sla_ws.append([r["cargo_nome"], r.get("nivel"), r.get("rs"), r.get("link"), r.get("exames"), r.get("documentos"), r.get("empresa")])

    buffer = io.BytesIO()
    wb.save(buffer)
    buffer.seek(0)
    return buffer
