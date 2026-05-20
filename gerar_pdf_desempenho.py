"""Gera PDF do Modulo de Gestao de Desempenho - Jarvis / Voetur"""

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_JUSTIFY
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    HRFlowable, PageBreak, KeepTogether
)

PAGE_W, PAGE_H = A4
MARGIN = 2 * cm

GREEN       = colors.HexColor("#1B6B44")
GREEN_DARK  = colors.HexColor("#134d31")
GREEN_LIGHT = colors.HexColor("#e8f5ee")
GRAY_DARK   = colors.HexColor("#1f2937")
GRAY_MED    = colors.HexColor("#6b7280")
GRAY_LIGHT  = colors.HexColor("#f3f4f6")
WHITE       = colors.white
AMBER       = colors.HexColor("#d97706")
BLUE        = colors.HexColor("#1d4ed8")

usable = PAGE_W - 2 * MARGIN

styles = getSampleStyleSheet()

def S(name, **kw):
    return ParagraphStyle(name, parent=styles["Normal"], **kw)

h1 = S("H1", fontSize=16, textColor=GREEN_DARK, fontName="Helvetica-Bold",
        leading=20, spaceBefore=18, spaceAfter=6)
h2 = S("H2", fontSize=13, textColor=GREEN_DARK, fontName="Helvetica-Bold",
        leading=16, spaceBefore=12, spaceAfter=5)
h3 = S("H3", fontSize=11, textColor=GRAY_DARK, fontName="Helvetica-Bold",
        leading=14, spaceBefore=8, spaceAfter=4)
body = S("Body", fontSize=10, textColor=GRAY_DARK, fontName="Helvetica",
         leading=15, spaceAfter=6, alignment=TA_JUSTIFY)
small = S("Sm", fontSize=9, textColor=GRAY_MED, fontName="Helvetica",
          leading=13, spaceAfter=4)
note = S("Note", fontSize=9, textColor=AMBER, fontName="Helvetica-Oblique",
         leading=13, spaceAfter=4, leftIndent=10)
code = S("Code", fontSize=9, textColor=GRAY_DARK, fontName="Courier",
         leading=13, spaceAfter=2, backColor=GRAY_LIGHT, leftIndent=10, rightIndent=10)
bullet_s = S("Bul", fontSize=10, textColor=GRAY_DARK, fontName="Helvetica",
             leading=15, leftIndent=16, firstLineIndent=-12, spaceAfter=3)
footer_s = S("Foot", fontSize=8, fontName="Helvetica", textColor=GRAY_MED,
             alignment=TA_CENTER, leading=12)

def H1(t): return Paragraph(t, h1)
def H2(t): return Paragraph(t, h2)
def H3(t): return Paragraph(t, h3)
def P(t):  return Paragraph(t, body)
def Sm(t): return Paragraph(t, small)
def Note(t): return Paragraph("Atencao: " + t, note)
def SP(h=0.3): return Spacer(1, h * cm)
def HR(): return HRFlowable(width="100%", thickness=1, color=GREEN_LIGHT, spaceAfter=6)
def PB(): return PageBreak()

def bul(items):
    return [Paragraph("- " + i, bullet_s) for i in items]

def tbl(data, headers=None, cw=None):
    if cw is None:
        cw = [usable / max(len(data[0]), 1)] * len(data[0])
    rows = []
    if headers:
        rows.append([Paragraph(h, S("th" + h[:4], fontSize=9, fontName="Helvetica-Bold",
                                     textColor=WHITE, leading=13)) for h in headers])
    for row in data:
        rows.append([Paragraph(str(c).replace("\n", "<br/>"),
                               S("td", fontSize=9, fontName="Helvetica",
                                 textColor=GRAY_DARK, leading=13)) for c in row])
    st = [
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e5e7eb")),
        ("ROWBACKGROUNDS", (0, 1 if headers else 0), (-1, -1), [WHITE, GRAY_LIGHT]),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING", (0, 0), (-1, -1), 7),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]
    if headers:
        st += [("BACKGROUND", (0, 0), (-1, 0), GREEN),
               ("TOPPADDING", (0, 0), (-1, 0), 7),
               ("BOTTOMPADDING", (0, 0), (-1, 0), 7)]
    t = Table(rows, colWidths=cw)
    t.setStyle(TableStyle(st))
    return t

def box(title, items, bg=GREEN_LIGHT, border=GREEN):
    rows = [[Paragraph(title, S("bt", fontSize=10, fontName="Helvetica-Bold",
                                 textColor=border, leading=14))]]
    for i in items:
        rows.append([Paragraph("- " + i, S("bi", fontSize=9, fontName="Helvetica",
                                            textColor=GRAY_DARK, leading=13, leftIndent=6))])
    t = Table(rows, colWidths=[usable])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), bg),
        ("BACKGROUND", (0, 1), (-1, -1), WHITE),
        ("BOX", (0, 0), (-1, -1), 1.2, border),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [WHITE, colors.HexColor("#f9fafb")]),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING", (0, 0), (-1, -1), 10),
    ]))
    return t

def screen(title, lines):
    rows = [[Paragraph("[ " + title + " ]",
                       S("stitle", fontSize=9, fontName="Courier-Bold",
                         textColor=GREEN_DARK, leading=14))]]
    for ln in lines:
        rows.append([Paragraph(ln, S("sl", fontSize=8.5, fontName="Courier",
                                      textColor=GRAY_DARK, leading=12))])
    t = Table(rows, colWidths=[usable - 2])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), GRAY_LIGHT),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e5e7eb")),
        ("BOX", (0, 0), (-1, -1), 1, colors.HexColor("#d1d5db")),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("LEFTPADDING", (0, 0), (-1, -1), 10),
        ("RIGHTPADDING", (0, 0), (-1, -1), 10),
    ]))
    return t

def step(num, label, detail=""):
    txt = f'<font color="#1B6B44"><b>{num}.</b></font> <b>{label}</b>'
    if detail:
        txt += f'<br/><font size="9" color="#6b7280">    {detail}</font>'
    return Paragraph(txt, S("step", fontSize=10, fontName="Helvetica",
                             textColor=GRAY_DARK, leading=16, spaceAfter=7,
                             leftIndent=4))

# ─── Callbacks de pagina ─────────────────────────────────────────────────────

def on_cover(canvas, doc):
    """Desenha capa na primeira pagina - sem numero."""
    canvas.saveState()
    canvas.setFillColor(GREEN)
    canvas.rect(0, 0, PAGE_W, PAGE_H, fill=1, stroke=0)
    canvas.setFillColor(GREEN_DARK)
    canvas.rect(0, 0, PAGE_W, 3 * cm, fill=1, stroke=0)
    canvas.setFillColor(WHITE)
    canvas.setFont("Helvetica-Bold", 32)
    canvas.drawCentredString(PAGE_W / 2, PAGE_H - 7 * cm, "Gestao de Desempenho")
    canvas.setFont("Helvetica", 16)
    canvas.setFillColor(GREEN_LIGHT)
    canvas.drawCentredString(PAGE_W / 2, PAGE_H - 8.2 * cm, "Manual do Modulo")
    canvas.setStrokeColor(GREEN_LIGHT)
    canvas.setLineWidth(1)
    canvas.line(3 * cm, PAGE_H - 9 * cm, PAGE_W - 3 * cm, PAGE_H - 9 * cm)
    canvas.setFont("Helvetica", 11)
    canvas.drawCentredString(PAGE_W / 2, PAGE_H - 10 * cm, "Jarvis  |  Sistema Interno Voetur/VTCLog")
    canvas.setFont("Helvetica", 9)
    canvas.drawCentredString(PAGE_W / 2, PAGE_H - 11 * cm, "Versao 1.0  |  Maio 2026")
    canvas.setFont("Helvetica", 8)
    canvas.drawCentredString(PAGE_W / 2, 1.5 * cm, "Confidencial - Uso interno Voetur")
    canvas.restoreState()


def on_page(canvas, doc):
    """Numeracao nas demais paginas."""
    canvas.saveState()
    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(GRAY_MED)
    pnum = doc.page - 1
    canvas.drawRightString(PAGE_W - MARGIN, MARGIN / 2,
                           f"Jarvis - Gestao de Desempenho  |  Pag. {pnum}")
    canvas.setFillColor(GREEN)
    canvas.rect(MARGIN, MARGIN / 2 - 2, 1 * cm, 3, fill=1, stroke=0)
    canvas.restoreState()


# ─── Story ───────────────────────────────────────────────────────────────────

def build():
    story = []

    # A capa e desenhada pelo on_cover callback na pg 1.
    # Comecamos o story com um PageBreak para pular para pg 2.
    story.append(PB())

    # ── Sumario ───────────────────────────────────────────────────────────────
    story.append(H1("Sumario"))
    items_toc = [
        ("1", "Visao Geral do Modulo"),
        ("2", "Perfis e Permissoes"),
        ("3", "Conceitos Fundamentais"),
        ("4", "Passo a Passo - RH"),
        ("5", "Passo a Passo - Gestor / Supervisor / Coordenador"),
        ("6", "Passo a Passo - Colaborador"),
        ("7", "Telas do Sistema"),
        ("8", "Motor de Score"),
        ("9", "Fluxo Completo do Ciclo"),
        ("10", "Perguntas Frequentes"),
    ]
    toc_data = [[Paragraph(f"<b>{n}.</b>  {lbl}",
                            S("toc", fontSize=10, fontName="Helvetica",
                              textColor=GRAY_DARK, leading=16))] for n, lbl in items_toc]
    toc_tbl = Table(toc_data, colWidths=[usable])
    toc_tbl.setStyle(TableStyle([
        ("ROWBACKGROUNDS", (0, 0), (-1, -1), [WHITE, GRAY_LIGHT]),
        ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING", (0, 0), (-1, -1), 10),
        ("LINEBELOW", (0, 0), (-1, -1), 0.3, colors.HexColor("#e5e7eb")),
    ]))
    story.append(toc_tbl)
    story.append(PB())

    # ══ 1. VISAO GERAL ════════════════════════════════════════════════════════
    story.append(H1("1. Visao Geral do Modulo"))
    story.append(HR())
    story.append(P(
        "O modulo de <b>Gestao de Desempenho</b> do Jarvis permite a Voetur conduzir ciclos "
        "completos de avaliacao de desempenho - desde a definicao de metas ate a calibracao "
        "final e registro de PDI. O sistema integra-se automaticamente com o ERP Benner para "
        "sincronizar departamentos e colaboradores."
    ))
    story.append(SP())
    story.append(box("O modulo cobre:", [
        "Criacao e gestao de ciclos de avaliacao (semestral, anual ou personalizado)",
        "Definicao de metas individuais e departamentais com KPIs",
        "Processo de assinatura em dois momentos (Momento 1: metas / Momento 2: resultado)",
        "Autoavaliacao pelo colaborador + avaliacao pelo gestor",
        "Avaliacao de 10 competencias corporativas e de lideranca",
        "Motor de score ponderado com protecao de compliance",
        "Calibracao de notas pelo RH",
        "Registro de evidencias e snapshots de KPI",
        "Trilha de auditoria completa de todas as acoes",
        "Base para PDI - Plano de Desenvolvimento Individual (previsto para Fase 2)",
    ]))
    story.append(SP())
    story.append(P(
        "O acesso e feito pelo menu lateral do Jarvis, no item <b>Desempenho</b>. "
        "A interface exibe apenas as abas e acoes compativeis com o perfil do usuario logado."
    ))
    story.append(PB())

    # ══ 2. PERFIS E PERMISSOES ════════════════════════════════════════════════
    story.append(H1("2. Perfis e Permissoes"))
    story.append(HR())
    story.append(P("Cada usuario recebe um perfil no Jarvis. Os perfis do modulo de desempenho:"))
    story.append(SP())

    perfis = [
        ["Perfil", "Quem recebe", "Abas visiveis", "Principais acoes"],
        ["colaborador", "Funcionarios em geral",
         "Meus Objetivos\nMinha Avaliacao",
         "Assinar metas\nAutoavaliacao\nCiencia do resultado"],
        ["supervisor", "Lideres operacionais",
         "+ Avaliar Liderados",
         "Criar metas\nAvaliar equipe\nAssinar avaliacoes"],
        ["coordenador", "Coordenadores",
         "+ Avaliar Liderados",
         "Criar metas\nAvaliar\nAssinar\nGerenciar PDI"],
        ["gestor", "Gestores de departamento",
         "+ Avaliar Liderados",
         "Criar metas\nAvaliar\nAssinar\nKPIs e PDI"],
        ["rh", "Recursos Humanos",
         "Todas + Ciclos + Dashboard",
         "Criar/abrir/fechar ciclos\nCalibrar notas\nVisao consolidada"],
        ["admin", "TI / Administrador",
         "Todas",
         "Acesso total ao modulo"],
    ]
    cw_p = [usable * x for x in [0.14, 0.20, 0.28, 0.38]]
    p_rows = []
    p_rows.append([Paragraph(h, S("ph", fontSize=9, fontName="Helvetica-Bold",
                                   textColor=WHITE, leading=13)) for h in perfis[0]])
    for row in perfis[1:]:
        p_rows.append([Paragraph(c.replace("\n", "<br/>"),
                                  S("pd", fontSize=9, fontName="Helvetica",
                                    textColor=GRAY_DARK, leading=13)) for c in row])
    pt = Table(p_rows, colWidths=cw_p)
    pt.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), GREEN),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [WHITE, GRAY_LIGHT]),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e5e7eb")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
    ]))
    story.append(pt)
    story.append(SP())
    story.append(Sm("* Perfil configurado pelo administrador em Gerenciamento de Acesso."))
    story.append(PB())

    # ══ 3. CONCEITOS FUNDAMENTAIS ═════════════════════════════════════════════
    story.append(H1("3. Conceitos Fundamentais"))
    story.append(HR())

    story.append(H2("3.1 Ciclo de Avaliacao"))
    story.append(P(
        "Um <b>ciclo</b> e o periodo durante o qual as avaliacoes acontecem. "
        "Pode ser semestral, anual ou qualquer duracao definida pelo RH."
    ))
    story.append(SP(0.2))
    estados = [
        ["Status", "Descricao"],
        ["Rascunho", "RH configura o ciclo. Nenhum colaborador ve ainda."],
        ["Aberto", "Ciclo ativo. Colaboradores recebem metas e podem assinar."],
        ["Avaliacao", "Fase de preenchimento: autoavaliacao + avaliacao do gestor."],
        ["Calibracao", "RH revisa e pode ajustar notas antes do encerramento."],
        ["Fechado", "Encerrado. Resultados definitivos e historico preservado."],
    ]
    story.append(tbl(estados[1:], headers=estados[0], cw=[usable * 0.22, usable * 0.78]))

    story.append(H2("3.2 Meta"))
    story.append(P(
        "Uma <b>meta</b> e um objetivo atribuido a um colaborador ou departamento com KPI, "
        "valor-alvo, periodo e peso no score. Ciclo de vida:"
    ))
    story.append(P(
        "<i>Rascunho -> Aguard. Assinatura -> Ativa -> Em Revisao -> Concluida "
        "(ou Expirada / Cancelada)</i>"
    ))

    story.append(H2("3.3 Momento 1 - Assinatura de Metas"))
    story.append(P(
        "Apos o RH abrir o ciclo, o colaborador recebe as metas definidas pelo gestor. "
        "<b>Momento 1</b> e o ato de ler e assinar cada meta, confirmando ciencia dos objetivos."
    ))

    story.append(H2("3.4 Momento 2 - Ciencia do Resultado"))
    story.append(P(
        "Apos o gestor avaliar e assinar o resultado, o colaborador precisa "
        "<b>tomar ciencia</b>. Pode aceitar ou contestar - neste caso o RH analisa."
    ))

    story.append(H2("3.5 Competencias Avaliadas"))
    story.append(SP(0.2))
    comp = [
        ["Competencia", "Categoria", "Obrigatoria"],
        ["Atendimento ao Cliente",      "Corporativa", "Sim"],
        ["Qualidade e Precisao",        "Corporativa", "Sim"],
        ["Compliance e Etica",          "Corporativa", "Sim"],
        ["Comunicacao",                 "Corporativa", "Sim"],
        ["Agilidade",                   "Corporativa", "Sim"],
        ["Relacionamento Interpessoal", "Corporativa", "Sim"],
        ["Gestao de Pessoas",           "Lideranca",   "Nao"],
        ["Tomada de Decisao",           "Lideranca",   "Nao"],
        ["Planejamento",                "Lideranca",   "Nao"],
        ["Desenvolvimento de Equipe",   "Lideranca",   "Nao"],
    ]
    story.append(tbl(comp[1:], headers=comp[0],
                     cw=[usable * 0.50, usable * 0.30, usable * 0.20]))
    story.append(PB())

    # ══ 4. RH ═════════════════════════════════════════════════════════════════
    story.append(H1("4. Passo a Passo - RH"))
    story.append(HR())
    rh = [
        ("1", "Criar o Ciclo",
         "Acesse a aba Ciclos -> Novo Ciclo. Informe nome (ex: '1 Semestre 2026') "
         "e periodo (datas). Status inicial: Rascunho."),
        ("2", "Criar as Metas",
         "Para cada colaborador ou departamento, clique em Criar Meta. Defina: titulo, "
         "tipo (KPI / Tarefa / Projeto), indicador, valor-alvo, unidade, peso e periodo."),
        ("3", "Abrir o Ciclo",
         "Na lista de ciclos, clique em Abrir Ciclo. O sistema cria automaticamente "
         "uma avaliacao para cada colaborador ativo. Ciclo muda para status Aberto."),
        ("4", "Acompanhar no Dashboard",
         "Acesse a aba Dashboard para ver o percentual de completude, colaboradores "
         "pendentes e distribuicao de scores. Atualizacao em tempo real."),
        ("5", "Calibrar Notas (opcional)",
         "Apos os gestores avaliarem, o RH pode ajustar scores individualmente: "
         "informe o colaborador, o score calibrado (1,0-5,0) e a justificativa."),
        ("6", "Fechar o Ciclo",
         "Quando todos concluirem ou apos o prazo, clique em Fechar Ciclo. "
         "Status muda para Fechado. Resultados preservados no historico."),
    ]
    for num, titulo, det in rh:
        story.append(KeepTogether([step(num, titulo, det), SP(0.1)]))
    story.append(SP())
    story.append(Note(
        "Sincronizacao com Benner RH ocorre diariamente as 02:00. Se um colaborador "
        "nao aparecer, aguarde ou acesse Admin -> Sincronizar Benner."
    ))
    story.append(PB())

    # ══ 5. GESTOR ═════════════════════════════════════════════════════════════
    story.append(H1("5. Passo a Passo - Gestor / Supervisor / Coordenador"))
    story.append(HR())

    story.append(H2("5.1 Criar Metas para a Equipe"))
    for num, t, d in [
        ("1", "Acesse Avaliar Liderados",
         "Clique na aba Avaliar Liderados no menu do modulo."),
        ("2", "Clique em Criar Meta",
         "Preencha: titulo, tipo, KPI, valor-alvo, unidade (%, R$, qtd...), "
         "peso e periodo. Selecione o colaborador (dono da meta)."),
        ("3", "Salve a meta",
         "Status: Rascunho. Apos o RH abrir o ciclo, o colaborador vera a meta."),
    ]:
        story.append(step(num, t, d))

    story.append(H2("5.2 Avaliar um Liderado"))
    for num, t, d in [
        ("1", "Aguarde a autoavaliacao",
         "Status aparece como 'Autoaval. feita' quando o colaborador concluir."),
        ("2", "Clique em Avaliar",
         "Voce vera os scores que o proprio colaborador atribuiu a si mesmo."),
        ("3", "Preencha as notas do gestor",
         "Atribua notas de 1 a 5 para: Metas, Competencias, Comportamento e Compliance. "
         "O sistema calcula o score final automaticamente."),
        ("4", "Adicione comentarios",
         "Escreva feedback construtivo - este texto sera visto pelo colaborador."),
        ("5", "Assine a avaliacao",
         "Informe sua assinatura e clique em Assinar e Enviar. "
         "O colaborador recebe notificacao para tomar ciencia (Momento 2)."),
    ]:
        story.append(step(num, t, d))

    story.append(SP())
    story.append(Note(
        "Se a nota de Compliance for abaixo de 2,0, o score final sera "
        "limitado automaticamente a 2,5, independente das demais notas."
    ))
    story.append(PB())

    # ══ 6. COLABORADOR ════════════════════════════════════════════════════════
    story.append(H1("6. Passo a Passo - Colaborador"))
    story.append(HR())

    story.append(H2("6.1 Assinar as Metas - Momento 1"))
    for num, t, d in [
        ("1", "Acesse Meus Objetivos",
         "No modulo de Desempenho, clique na aba Meus Objetivos."),
        ("2", "Leia cada meta",
         "Verifique titulo, KPI, valor-alvo, periodo e peso de cada meta."),
        ("3", "Clique em Assinar e Aceitar",
         "Confirma que voce leu e aceita os objetivos. Meta muda para Ativa."),
        ("4", "Repita para todas as metas",
         "Todas as metas com 'Aguardando assinatura' precisam ser assinadas."),
    ]:
        story.append(step(num, t, d))

    story.append(H2("6.2 Preencher a Autoavaliacao"))
    for num, t, d in [
        ("1", "Acesse Minha Avaliacao",
         "Habilitada quando o RH iniciar a fase de avaliacao."),
        ("2", "Atribua notas de 1 a 5",
         "Para cada dimensao: Metas, Competencias, Comportamento e Compliance. "
         "1=Abaixo do esperado, 3=Dentro do esperado, 5=Excede expectativas."),
        ("3", "Escreva seu comentario (opcional)",
         "Registre conquistas, dificuldades ou contexto relevante."),
        ("4", "Envie a autoavaliacao",
         "Clique em Enviar. Seu gestor preenchera a avaliacao dele em seguida."),
    ]:
        story.append(step(num, t, d))

    story.append(H2("6.3 Tomar Ciencia do Resultado - Momento 2"))
    for num, t, d in [
        ("1", "Receba a notificacao",
         "Quando o gestor assinar, voce sera notificado."),
        ("2", "Leia o resultado",
         "Acesse Minha Avaliacao para ver score final, notas e comentarios do gestor."),
        ("3", "Aceite ou conteste",
         "Clique em Confirmar Ciencia para aceitar, ou Contestar e informe o motivo. "
         "Em caso de contestacao, o RH ira analisar."),
    ]:
        story.append(step(num, t, d))
    story.append(PB())

    # ══ 7. TELAS ══════════════════════════════════════════════════════════════
    story.append(H1("7. Telas do Sistema"))
    story.append(HR())

    story.append(H2("7.1 Meus Objetivos"))
    story.append(screen("Meus Objetivos", [
        "------------------------------------------------------------",
        " Meta: Reduzir tempo de resposta de chamados               ",
        " Tipo: KPI  |  Periodo: Jan-Jun 2026  |  [Rascunho]       ",
        " Meta-alvo: <= 4h  |  Atual: 4h 35min  |  Peso: 2         ",
        "                                    [Assinar e Aceitar]    ",
        "------------------------------------------------------------",
        " Meta: Concluir treinamento ITIL v4                       ",
        " Tipo: Tarefa  |  Periodo: Mar 2026  |  [Aguard. assina.]  ",
        "                                    [Assinar e Aceitar]    ",
        "------------------------------------------------------------",
    ]))
    story.append(SP(0.5))

    story.append(H2("7.2 Minha Avaliacao - Preenchimento"))
    story.append(screen("Minha Avaliacao - 1 Semestre 2026", [
        " Status: Autoavaliacao em andamento                        ",
        "------------------------------------------------------------",
        " Metas:          [4 - Acima do esperado       v]          ",
        " Competencias:   [3 - Dentro do esperado      v]          ",
        " Comportamento:  [4 - Acima do esperado       v]          ",
        " Compliance:     [3 - Dentro do esperado      v]          ",
        "                                                           ",
        " Score calculado:    3,65 / 5,00                          ",
        "                                                           ",
        " Comentarios: ____________________________________________ ",
        "                                                           ",
        "              [Salvar rascunho]        [Enviar]            ",
    ]))
    story.append(SP(0.5))

    story.append(H2("7.3 Avaliar Liderados (Gestor)"))
    story.append(screen("Avaliar Liderados - 1 Semestre 2026", [
        " Colaborador            Status                Acao         ",
        "------------------------------------------------------------",
        " Ana Souza              Ok Autoaval. feita    [Avaliar]    ",
        " Carlos Lima            .. Aguard. autoaval.  [Ver]        ",
        " Paula Mendes           Ok Autoaval. feita    [Avaliar]    ",
        "------------------------------------------------------------",
        "                                          [+ Criar Meta]   ",
    ]))
    story.append(SP(0.5))

    story.append(H2("7.4 Ciclos de Avaliacao (RH)"))
    story.append(screen("Ciclos de Avaliacao", [
        " Novo Ciclo:                                               ",
        " Nome:  [____________________]                             ",
        " Inicio:[__/__/____]  Fim:[__/__/____]   [Criar Ciclo]    ",
        "------------------------------------------------------------",
        " Ciclo                  Periodo          Status    Acao   ",
        " 1 Semestre 2026        Jan-Jun 2026      Rascunho [Abrir] ",
        " 2 Semestre 2025        Jul-Dez 2025      Fechado  [Ver]   ",
    ]))
    story.append(SP(0.5))

    story.append(H2("7.5 Dashboard RH"))
    story.append(screen("Dashboard de Desempenho - 1 Semestre 2026", [
        " Total: 120  |  Concluidas: 45  |  Bloqueadas: 3          ",
        " Completude: 37,5%                                         ",
        "------------------------------------------------------------",
        " Distribuicao de scores:                                   ",
        "   1 (Abaixo)    ==             5%                        ",
        "   2             ====          12%                        ",
        "   3 (Esperado)  ==========   48%                        ",
        "   4             =======      30%                        ",
        "   5 (Excede)    =             5%                        ",
        "------------------------------------------------------------",
        " Calibracao: Colaborador [___v]  Score: [___]             ",
        " Justificativa: [_________________________________]        ",
        "                                  [Aplicar calibracao]    ",
    ]))
    story.append(PB())

    # ══ 8. SCORE ══════════════════════════════════════════════════════════════
    story.append(H1("8. Motor de Score"))
    story.append(HR())
    story.append(P(
        "O score final e calculado automaticamente com base nas notas atribuidas "
        "nas quatro dimensoes, cada uma com peso diferente."
    ))
    story.append(SP())

    sc = [
        ["Dimensao", "Peso", "Contribuicao maxima"],
        ["Metas",        "50%", "2,50 pontos"],
        ["Competencias", "25%", "1,25 pontos"],
        ["Comportamento","15%", "0,75 pontos"],
        ["Compliance",   "10%", "0,50 pontos"],
        ["TOTAL",       "100%", "5,00 pontos"],
    ]
    sc_rows = []
    sc_rows.append([Paragraph(h, S("sch", fontSize=9, fontName="Helvetica-Bold",
                                    textColor=WHITE, leading=13)) for h in sc[0]])
    for i, row in enumerate(sc[1:]):
        bold = (i == 4)
        sc_rows.append([
            Paragraph(c, S(f"scd{i}", fontSize=9,
                            fontName="Helvetica-Bold" if bold else "Helvetica",
                            textColor=GREEN_DARK if bold else GRAY_DARK, leading=13))
            for c in row
        ])
    sc_tbl = Table(sc_rows, colWidths=[usable * 0.40, usable * 0.20, usable * 0.40])
    sc_tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), GREEN),
        ("BACKGROUND", (0, 5), (-1, 5), GREEN_LIGHT),
        ("ROWBACKGROUNDS", (0, 1), (-1, 4), [WHITE, GRAY_LIGHT]),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e5e7eb")),
        ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("LINEABOVE", (0, 5), (-1, 5), 1.5, GREEN),
    ]))
    story.append(sc_tbl)
    story.append(SP())

    story.append(H2("8.1 Exemplo de Calculo"))
    story.append(screen("Calculo de Score - Exemplo Normal", [
        " Nota Metas:         4,0  x  0,50  =  2,00",
        " Nota Competencias:  3,0  x  0,25  =  0,75",
        " Nota Comportamento: 3,5  x  0,15  =  0,53",
        " Nota Compliance:    3,0  x  0,10  =  0,30",
        "                                    -------",
        " Score Final:                         3,58  (Compliance OK)",
    ]))
    story.append(SP())

    story.append(H2("8.2 Regra de Bloqueio por Compliance"))
    story.append(P(
        "Se o colaborador receber nota <b>menor que 2,0</b> em Compliance e Etica, "
        "o score final sera <b>limitado a 2,5</b>, independente das outras notas. "
        "Essa regra existe para garantir que questoes de conduta e etica sejam priorizadas."
    ))
    story.append(SP(0.2))
    story.append(screen("Calculo de Score - Com Bloqueio de Compliance", [
        " Nota Metas:         5,0  x  0,50  =  2,50",
        " Nota Competencias:  5,0  x  0,25  =  1,25",
        " Nota Comportamento: 5,0  x  0,15  =  0,75",
        " Nota Compliance:    1,5  x  0,10  =  0,15  << ABAIXO DE 2,0",
        "                                    -------",
        " Score Bruto:                         4,65",
        " ATENCAO: Compliance < 2,0 -> Score bloqueado!",
        " Score Final:                         2,50  (limitado)",
    ]))
    story.append(SP())

    story.append(H2("8.3 Escala de Notas"))
    notas = [
        ["Nota", "Classificacao", "O que significa"],
        ["1", "Muito abaixo", "Nao atingiu o esperado de forma significativa"],
        ["2", "Abaixo",       "Atingiu parcialmente; precisa de melhoria"],
        ["3", "No esperado",  "Atendeu plenamente o que foi definido"],
        ["4", "Acima",        "Superou os objetivos de forma consistente"],
        ["5", "Excede",       "Desempenho excepcional; referencia para a equipe"],
    ]
    story.append(tbl(notas[1:], headers=notas[0],
                     cw=[usable * 0.10, usable * 0.28, usable * 0.62]))
    story.append(PB())

    # ══ 9. FLUXO COMPLETO ════════════════════════════════════════════════════
    story.append(H1("9. Fluxo Completo do Ciclo"))
    story.append(HR())
    story.append(P("Sequencia de acoes do inicio ao fim de um ciclo de avaliacao:"))
    story.append(SP())

    fluxo = [
        ("RH",          "Cria o ciclo",
         "Aba Ciclos -> Novo Ciclo. Define nome e periodo."),
        ("RH / Gestor", "Cria as metas",
         "Define metas individuais com KPI, valor-alvo e peso."),
        ("RH",          "Abre o ciclo",
         "Botao Abrir Ciclo. Sistema gera uma avaliacao por colaborador ativo."),
        ("Colaborador", "Assina as metas - Momento 1",
         "Aba Meus Objetivos -> Assinar e Aceitar em cada meta."),
        ("Colaborador", "Preenche autoavaliacao",
         "Aba Minha Avaliacao -> notas 1-5 nas 4 dimensoes e envia."),
        ("Gestor",      "Avalia o liderado",
         "Aba Avaliar Liderados -> Avaliar -> preenche notas e comentarios."),
        ("Gestor",      "Assina a avaliacao",
         "Assina e envia. Colaborador e notificado para ciencia."),
        ("Colaborador", "Toma ciencia - Momento 2",
         "Le resultado -> Confirmar Ciencia ou Contestar."),
        ("RH",          "Calibra notas (opcional)",
         "Dashboard -> ajusta score individualmente com justificativa."),
        ("RH",          "Fecha o ciclo",
         "Ciclo -> Fechado. Historico preservado."),
    ]

    f_rows = []
    f_rows.append([
        Paragraph(h, S("fh", fontSize=9, fontName="Helvetica-Bold", textColor=WHITE, leading=13))
        for h in ["#", "Responsavel", "Acao", "Como fazer"]
    ])
    cores_resp = {
        "RH": GREEN_LIGHT,
        "RH / Gestor": colors.HexColor("#d1fae5"),
        "Gestor": colors.HexColor("#eff6ff"),
        "Colaborador": colors.HexColor("#fef9ee"),
    }
    for i, (resp, acao, como) in enumerate(fluxo):
        f_rows.append([
            Paragraph(str(i + 1), S(f"fn{i}", fontSize=9, fontName="Helvetica-Bold",
                                     textColor=GREEN_DARK, leading=13)),
            Paragraph(resp, S(f"fr{i}", fontSize=9, fontName="Helvetica",
                               textColor=GRAY_DARK, leading=13)),
            Paragraph(acao, S(f"fa{i}", fontSize=9, fontName="Helvetica-Bold",
                               textColor=GREEN_DARK, leading=13)),
            Paragraph(como, S(f"fc{i}", fontSize=9, fontName="Helvetica",
                               textColor=GRAY_DARK, leading=13)),
        ])
    cw_f = [usable * x for x in [0.05, 0.16, 0.27, 0.52]]
    ft = Table(f_rows, colWidths=cw_f)
    f_style = [
        ("BACKGROUND", (0, 0), (-1, 0), GREEN),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e5e7eb")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
    ]
    for i, (resp, _, _2) in enumerate(fluxo):
        bg = cores_resp.get(resp, WHITE)
        f_style.append(("BACKGROUND", (0, i + 1), (-1, i + 1), bg))
    ft.setStyle(TableStyle(f_style))
    story.append(ft)
    story.append(SP(0.5))
    story.append(Sm(
        "Verde claro = RH   |   Azul claro = Gestor/Supervisor/Coordenador   "
        "|   Amarelo claro = Colaborador"
    ))
    story.append(PB())

    # ══ 10. PERGUNTAS FREQUENTES ══════════════════════════════════════════════
    story.append(H1("10. Perguntas Frequentes"))
    story.append(HR())

    faqs = [
        ("Nao consigo ver o modulo de Desempenho no menu.",
         "Verifique com o administrador se seu perfil foi configurado como colaborador, "
         "supervisor, coordenador, gestor ou rh. Perfis 'user' padrao nao tem acesso."),
        ("Assinei uma meta por engano. Posso desfazer?",
         "Nao. A assinatura e um ato formal com registro em trilha de auditoria. "
         "Em caso de erro, entre em contato com o RH."),
        ("O colaborador nao aparece na lista.",
         "O sistema sincroniza com o Benner RH diariamente as 02h. Se for novo, "
         "aguarde ate o dia seguinte ou solicite sincronizacao manual em Admin -> Sincronizar Benner."),
        ("O score foi limitado a 2,5.",
         "Isso ocorre quando a nota de Compliance e Etica e menor que 2,0. "
         "Para alterar, o gestor deve revisar a nota ou o RH pode usar a calibracao."),
        ("Como contestar uma avaliacao?",
         "Na aba Minha Avaliacao, apos o gestor assinar, clique em Contestar, "
         "informe o motivo e envie. O RH recebera a contestacao para analise."),
        ("Quando o ciclo fecha automaticamente?",
         "O ciclo nao fecha automaticamente. O RH precisa clicar em Fechar Ciclo "
         "para garantir revisao de todas as avaliacoes antes do encerramento."),
        ("Posso editar minha autoavaliacao apos enviar?",
         "Nao. Apos enviar, fica bloqueada. Entre em contato com o RH se precisar corrigir."),
        ("Onde vejo historico de ciclos anteriores?",
         "Na aba Ciclos, ciclos encerrados aparecem com status Fechado. "
         "Clique em Ver para acessar os dados. O RH tem visao completa no Dashboard."),
    ]

    for i, (perg, resp) in enumerate(faqs):
        story.append(KeepTogether([
            Paragraph(f"<b>P: {perg}</b>",
                      S(f"fp{i}", fontSize=10, fontName="Helvetica-Bold",
                        textColor=GREEN_DARK, leading=14, spaceBefore=8)),
            Paragraph(f"R: {resp}",
                      S(f"fr{i}", fontSize=10, fontName="Helvetica",
                        textColor=GRAY_DARK, leading=15, leftIndent=10, spaceAfter=4)),
            HRFlowable(width="100%", thickness=0.5, color=GRAY_LIGHT, spaceAfter=2),
        ]))

    story.append(SP(1))
    story.append(HRFlowable(width="100%", thickness=1.5, color=GREEN))
    story.append(SP(0.3))
    story.append(Paragraph(
        "Jarvis - Sistema Interno Voetur/VTCLog  |  Gestao de Desempenho  |  "
        "Versao 1.0  |  Maio 2026  |  Uso Confidencial",
        footer_s
    ))

    return story


# ─── Main ────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    output = "/tmp/desempenho_manual.pdf"
    doc = SimpleDocTemplate(
        output,
        pagesize=A4,
        leftMargin=MARGIN, rightMargin=MARGIN,
        topMargin=MARGIN, bottomMargin=MARGIN + 0.5 * cm,
        title="Gestao de Desempenho - Manual do Modulo",
        author="Jarvis / Voetur",
    )
    story = build()
    doc.build(story, onFirstPage=on_cover, onLaterPages=on_page)
    print(f"PDF gerado: {output}")
