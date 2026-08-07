"""Calculadora de custo total de admissao — mesma formula usada pelo
Departamento Pessoal na planilha 'Custas para Admissao.xlsx'.

Os 4 campos informativos (insalubridade, periculosidade, aparelhos
eletronicos, outros_creditos) aparecem no detalhamento mas NAO entram no
custo_total — replica o comportamento da planilha original do DP
(SUM(B7:B15,F7:F15) nao inclui esses campos).
"""
from decimal import ROUND_HALF_UP, Decimal


def _d(v) -> Decimal:
    return Decimal(str(v or 0))


def _money(v: Decimal) -> float:
    return float(v.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def calcular_custo(perfil: dict, salario) -> dict:
    s = _d(salario)
    pct_inss = _d(perfil.get("pct_inss")) / _d(100)
    pct_fgts = _d(perfil.get("pct_fgts")) / _d(100)
    pct_multa = _d(perfil.get("pct_multa_fgts")) / _d(100)

    provisao_13_ferias = (s / 12) + (s / 12 / 3)
    ferias = s / 12
    inss = s * pct_inss
    # Base do FGTS varia por perfil: alguns usam so o salario (padrao legal
    # CLT, 8%), outros incluem as provisoes de 13o/ferias na base (2%) —
    # confirmado nas 17 abas da planilha do DP, nao e so o percentual.
    base_fgts = (s + provisao_13_ferias + ferias) if perfil.get("fgts_base_com_provisoes") else s
    fgts = base_fgts * pct_fgts
    fgts_multa = fgts * pct_multa
    inss_13_ferias = (s / 12) * Decimal("2.333") * pct_inss

    vale_transporte = _d(perfil.get("vale_transporte"))
    vale_alimentacao = _d(perfil.get("vale_alimentacao"))
    seguro_vida = _d(perfil.get("seguro_vida"))
    plano_saude = _d(perfil.get("plano_saude"))
    uniforme = _d(perfil.get("uniforme"))
    cracha_cordao = _d(perfil.get("cracha_cordao"))
    aso = _d(perfil.get("aso"))
    taxa_administrativa = _d(perfil.get("taxa_administrativa"))

    # informativos — nao entram no total, replicando a planilha do DP
    insalubridade = _d(perfil.get("insalubridade"))
    periculosidade = _d(perfil.get("periculosidade"))
    aparelhos_eletronicos = _d(perfil.get("aparelhos_eletronicos"))
    outros_creditos = _d(perfil.get("outros_creditos"))

    custo_total = (
        s + vale_transporte + vale_alimentacao + provisao_13_ferias + ferias
        + inss + fgts + fgts_multa + inss_13_ferias + seguro_vida
        + plano_saude + uniforme + cracha_cordao + aso + taxa_administrativa
    )

    return {
        "salario": _money(s),
        "vale_transporte": _money(vale_transporte),
        "vale_alimentacao": _money(vale_alimentacao),
        "provisao_13_ferias": _money(provisao_13_ferias),
        "ferias": _money(ferias),
        "inss": _money(inss),
        "fgts": _money(fgts),
        "fgts_multa": _money(fgts_multa),
        "inss_13_ferias": _money(inss_13_ferias),
        "seguro_vida": _money(seguro_vida),
        "plano_saude": _money(plano_saude),
        "uniforme": _money(uniforme),
        "cracha_cordao": _money(cracha_cordao),
        "aso": _money(aso),
        "taxa_administrativa": _money(taxa_administrativa),
        "insalubridade_informativo": _money(insalubridade),
        "periculosidade_informativo": _money(periculosidade),
        "aparelhos_eletronicos_informativo": _money(aparelhos_eletronicos),
        "outros_creditos_informativo": _money(outros_creditos),
        "custo_total": _money(custo_total),
    }


_PALAVRAS_IGNORADAS = {"DE", "DA", "DO", "E", "-"}


def sugerir_perfil(perfis: list[dict], empresa: str, alocacao: str, tipo_contrato: str) -> str | None:
    """Heuristica simples de auto-sugestao por nome — sempre editavel pelo RH."""
    if tipo_contrato and "APRENDIZ" in tipo_contrato.upper():
        grupo = "VTC" if empresa and "VTC" in empresa.upper() else "VIAGENS"
        for p in perfis:
            if "JOVEM APRENDIZ" in p["nome"].upper() and grupo in p["nome"].upper():
                return p["id"]

    texto_busca = f"{empresa or ''} {alocacao or ''}".upper()
    palavras = {w for w in texto_busca.replace("-", " ").split() if w not in _PALAVRAS_IGNORADAS and len(w) > 1}

    melhor, melhor_score = None, 0
    for p in perfis:
        nome_palavras = {w for w in p["nome"].upper().replace("-", " ").split() if w not in _PALAVRAS_IGNORADAS}
        score = len(palavras & nome_palavras)
        if score > melhor_score:
            melhor, melhor_score = p["id"], score
    return melhor if melhor_score > 0 else None
