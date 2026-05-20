# Tabelas estáticas de validação CFOP e CST para Lucro Real

# Prefixos válidos por direção
CFOP_ENTRADA = {"1", "2", "3"}   # intraestadual, interestadual, exterior
CFOP_SAIDA   = {"5", "6", "7"}   # intraestadual, interestadual, exterior

# CST ICMS válidos (regime normal / Lucro Real)
CST_ICMS_VALIDOS = {
    "00", "10", "20", "30", "40", "41", "50", "51", "60", "70", "90",
}

# CST PIS/COFINS não-cumulativo (Lucro Real) — válidos
CST_PIS_COFINS_NAO_CUMULATIVO = {
    "01", "02", "03", "04", "05", "06", "07", "08", "09",
    "49", "50", "51", "52", "53", "54", "55", "56", "60", "61", "62",
    "63", "64", "65", "66", "67", "70", "71", "72", "73", "74", "75",
    "98", "99",
}

# CST PIS/COFINS cumulativos (Simples Nacional / regime cumulativo)
# Esses são inválidos para empresas Lucro Real
CST_PIS_COFINS_CUMULATIVO = {"03", "04", "05", "06"}

# Alíquotas padrão Lucro Real não-cumulativo
ALIQUOTA_PIS_LUCRO_REAL    = 1.65
ALIQUOTA_COFINS_LUCRO_REAL = 7.6

# Alíquotas do regime cumulativo (Simples / Lucro Presumido) — sinalizam erro
ALIQUOTA_PIS_CUMULATIVO    = 0.65
ALIQUOTA_COFINS_CUMULATIVO = 3.0

# Tolerância para comparação de alíquotas (arredondamento)
ALIQUOTA_TOLERANCE = 0.01


def is_cfop_entrada(cfop: str) -> bool:
    return bool(cfop) and cfop[0] in CFOP_ENTRADA


def is_cfop_saida(cfop: str) -> bool:
    return bool(cfop) and cfop[0] in CFOP_SAIDA


def is_cfop_interestadual_entrada(cfop: str) -> bool:
    return bool(cfop) and cfop[0] == "2"


def is_cst_icms_valido(cst: str) -> bool:
    return (cst or "").zfill(2) in CST_ICMS_VALIDOS


def is_cst_pis_cofins_valido_lucro_real(cst: str) -> bool:
    c = (cst or "").zfill(2)
    return c not in CST_PIS_COFINS_CUMULATIVO


def is_aliquota_pis_cumulativa(aliquota: float) -> bool:
    return abs(aliquota - ALIQUOTA_PIS_CUMULATIVO) < ALIQUOTA_TOLERANCE


def is_aliquota_cofins_cumulativa(aliquota: float) -> bool:
    return abs(aliquota - ALIQUOTA_COFINS_CUMULATIVO) < ALIQUOTA_TOLERANCE


# Vencimentos ICMS por UF (dia do mês seguinte ao período)
ICMS_VENCIMENTO_DIA: dict[str, int] = {
    "AC": 20, "AL": 20, "AM": 20, "AP": 20, "BA": 20,
    "CE": 20, "DF": 20, "ES": 20, "GO": 20, "MA": 20,
    "MG": 20, "MS": 20, "MT": 20, "PA": 20, "PB": 20,
    "PE": 15, "PI": 20, "PR": 20, "RJ": 20, "RN": 20,
    "RO": 20, "RR": 20, "RS": 20, "SC": 20, "SE": 20,
    "SP": 20, "TO": 20,
}
