# Mapa IBGE → sistema NFSe + endpoint
# Tipos: nacional | abrasf | paulistana | carioca | df | nddigital
#
# nddigital: ND Digital / NDD Space Portal — portal centralizador REST (OData)
# Uma única chamada retorna NFSe de todos os municípios; IBGE é passado como filtro.
# Auth: OIDC password grant → Bearer JWT
# Base: https://spaceportalprod.e-datacenter.nddigital.com.br/nfse-api
# Swagger: /nfse-api/swagger/v1/swagger.json

NDD_BASE = "https://spaceportalprod.e-datacenter.nddigital.com.br"
NDD_IDENTITY = "https://spacenddidentityprod.e-datacenter.nddigital.com.br"

# Voetur Viagens — 30 hotéis, todos gerenciados via portal ND Digital
NFSE_CITY_REGISTRY: dict[str, dict] = {
    # RJ
    "3304557": {"nome": "Rio de Janeiro",          "uf": "RJ", "tipo": "nddigital", "url": NDD_BASE},
    "3303203": {"nome": "Macaé",                   "uf": "RJ", "tipo": "nddigital", "url": NDD_BASE},
    "3300001": {"nome": "Angra dos Reis",           "uf": "RJ", "tipo": "nddigital", "url": NDD_BASE},
    "3302007": {"nome": "Itaboraí",                "uf": "RJ", "tipo": "nddigital", "url": NDD_BASE},
    "3301009": {"nome": "Campos dos Goytacazes",   "uf": "RJ", "tipo": "nddigital", "url": NDD_BASE},

    # DF
    "5300108": {"nome": "Brasília",                "uf": "DF", "tipo": "nddigital", "url": NDD_BASE},

    # SP
    "3550308": {"nome": "São Paulo",               "uf": "SP", "tipo": "nddigital", "url": NDD_BASE},
    "3548807": {"nome": "Santos",                  "uf": "SP", "tipo": "nddigital", "url": NDD_BASE},
    "3509502": {"nome": "Campinas",                "uf": "SP", "tipo": "nddigital", "url": NDD_BASE},
    "3543402": {"nome": "Ribeirão Preto",          "uf": "SP", "tipo": "nddigital", "url": NDD_BASE},
    "3549904": {"nome": "São José dos Campos",     "uf": "SP", "tipo": "nddigital", "url": NDD_BASE},
    "3548708": {"nome": "São Sebastião",           "uf": "SP", "tipo": "nddigital", "url": NDD_BASE},

    # PA
    "1501402": {"nome": "Belém",                   "uf": "PA", "tipo": "nddigital", "url": NDD_BASE},

    # PR
    "4106902": {"nome": "Curitiba",                "uf": "PR", "tipo": "nddigital", "url": NDD_BASE},
    "4108304": {"nome": "Foz do Iguaçu",           "uf": "PR", "tipo": "nddigital", "url": NDD_BASE},
    "4104808": {"nome": "Cascavel",                "uf": "PR", "tipo": "nddigital", "url": NDD_BASE},

    # MG
    "3106200": {"nome": "Belo Horizonte",          "uf": "MG", "tipo": "nddigital", "url": NDD_BASE},
    "3127701": {"nome": "Sete Lagoas",             "uf": "MG", "tipo": "nddigital", "url": NDD_BASE},
    "3170206": {"nome": "Uberlândia",              "uf": "MG", "tipo": "nddigital", "url": NDD_BASE},

    # PE
    "2611606": {"nome": "Recife",                  "uf": "PE", "tipo": "nddigital", "url": NDD_BASE},

    # BA
    "2927408": {"nome": "Salvador",                "uf": "BA", "tipo": "nddigital", "url": NDD_BASE},

    # ES
    "3205309": {"nome": "Vitória",                 "uf": "ES", "tipo": "nddigital", "url": NDD_BASE},

    # RS
    "4314902": {"nome": "Porto Alegre",            "uf": "RS", "tipo": "nddigital", "url": NDD_BASE},

    # CE
    "2304400": {"nome": "Fortaleza",               "uf": "CE", "tipo": "nddigital", "url": NDD_BASE},

    # AM
    "1302603": {"nome": "Manaus",                  "uf": "AM", "tipo": "nddigital", "url": NDD_BASE},

    # MA
    "2111300": {"nome": "São Luís",                "uf": "MA", "tipo": "nddigital", "url": NDD_BASE},

    # SE
    "2800308": {"nome": "Aracaju",                 "uf": "SE", "tipo": "nddigital", "url": NDD_BASE},

    # SC
    "4205407": {"nome": "Florianópolis",           "uf": "SC", "tipo": "nddigital", "url": NDD_BASE},

    # GO
    "5208707": {"nome": "Goiânia",                 "uf": "GO", "tipo": "nddigital", "url": NDD_BASE},
    "5218805": {"nome": "Rio Verde",               "uf": "GO", "tipo": "nddigital", "url": NDD_BASE},
}
