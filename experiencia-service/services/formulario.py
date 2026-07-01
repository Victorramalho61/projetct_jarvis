"""Definição dos formulários de Avaliação de Experiência (VPA.RH.PGP.09 v04)."""

ESCALA = [
    {"valor": 1, "label": "Não atende"},
    {"valor": 2, "label": "Atende Parcialmente"},
    {"valor": 3, "label": "Atende"},
    {"valor": 4, "label": "Supera"},
]

INDICADORES = [
    {"id": "apresentacao_pessoal",       "label": "Apresentação Pessoal"},
    {"id": "produtividade",              "label": "Produtividade"},
    {"id": "conhecimento_trabalho",      "label": "Conhecimento do Trabalho"},
    {"id": "cooperacao",                 "label": "Cooperação"},
    {"id": "iniciativa_proatividade",    "label": "Iniciativa e Proatividade"},
    {"id": "relacionamento_interpessoal","label": "Relacionamento Interpessoal"},
    {"id": "aprendizagem",               "label": "Aprendizagem"},
    {"id": "hierarquia_disciplina",      "label": "Hierarquia e Disciplina"},
    {"id": "assiduidade_pontualidade",   "label": "Assiduidade e Pontualidade"},
]

CAMPOS_TEXTO = [
    {"id": "pontos_destaque",  "label": "Pontos de destaque"},
    {"id": "pontos_melhoria",  "label": "Pontos de melhoria"},
    {"id": "acoes_planejadas", "label": "Ações planejadas para desenvolvimento"},
]

PARECER_45_DIAS = [
    {"id": "seguir",      "label": "Seguir contrato por mais 45 dias"},
    {"id": "interromper", "label": "Interromper o contrato nos 45 dias"},
]

PARECER_90_DIAS = [
    {"id": "efetivar",  "label": "Efetivação do colaborador"},
    {"id": "encerrar",  "label": "Encerrar contrato nos 90 dias"},
]

AVISO_IMPARCIALIDADE = (
    "Certifique-se de que sua avaliação esteja sendo justa e imparcial."
)

DECLARACAO_ASSINATURA = (
    "Declaro que as informações preenchidas são verdadeiras e assumo a "
    "responsabilidade pelo parecer emitido nesta avaliação de experiência."
)


def get_formulario(tipo: str) -> dict:
    """Retorna a estrutura completa do formulário para o tipo '45_dias' ou '90_dias'."""
    if tipo == "45_dias":
        titulo = "Avaliação de Experiência — 45 Dias de Contrato"
        subtitulo = "45 DIAS DE CONTRATO"
        parecer = PARECER_45_DIAS
        acao_texto = "Ações planejadas para desenvolvimento nos próximos 45 dias"
    else:
        titulo = "Avaliação de Experiência — 90 Dias de Contrato"
        subtitulo = "90 DIAS DE CONTRATO"
        parecer = PARECER_90_DIAS
        acao_texto = "Ações planejadas para desenvolvimento"

    campos_texto = [
        {"id": "pontos_destaque",  "label": "Pontos de destaque"},
        {"id": "pontos_melhoria",  "label": "Pontos de melhoria"},
        {"id": "acoes_planejadas", "label": acao_texto},
    ]

    return {
        "titulo": titulo,
        "subtitulo": subtitulo,
        "aviso": AVISO_IMPARCIALIDADE,
        "escala": ESCALA,
        "indicadores": INDICADORES,
        "campos_texto": campos_texto,
        "parecer": parecer,
        "declaracao_assinatura": DECLARACAO_ASSINATURA,
    }


def validate_respostas(respostas: dict, tipo: str) -> list[str]:
    """Retorna lista de erros de validação. Lista vazia = OK."""
    erros = []
    indicador_ids = {i["id"] for i in INDICADORES}
    parecer_ids = {p["id"] for p in (PARECER_45_DIAS if tipo == "45_dias" else PARECER_90_DIAS)}

    indicadores_resp = respostas.get("indicadores", {})
    for ind in INDICADORES:
        val = indicadores_resp.get(ind["id"])
        if val is None:
            erros.append(f"Indicador '{ind['label']}' não avaliado")
        elif val not in (1, 2, 3, 4):
            erros.append(f"Indicador '{ind['label']}' com valor inválido: {val}")

    if not respostas.get("pontos_destaque", "").strip():
        erros.append("Pontos de destaque é obrigatório")
    if not respostas.get("pontos_melhoria", "").strip():
        erros.append("Pontos de melhoria é obrigatório")
    if not respostas.get("acoes_planejadas", "").strip():
        erros.append("Ações planejadas é obrigatório")

    parecer = respostas.get("parecer")
    if parecer not in parecer_ids:
        erros.append(f"Parecer inválido ou não selecionado: {parecer}")

    return erros
