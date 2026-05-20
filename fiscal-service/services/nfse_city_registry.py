# Mapa IBGE → sistema NFSe + endpoint
# Tipos: nacional | abrasf | paulistana | carioca | df

NFSE_CITY_REGISTRY: dict[str, dict] = {
    # ── Sistemas proprietários ─────────────────────────────────────────
    "3550308": {
        "nome": "São Paulo", "uf": "SP", "tipo": "paulistana",
        "url": "https://nfe.prefeitura.sp.gov.br/ws/lotenfe.asmx",
    },
    "3304557": {
        "nome": "Rio de Janeiro", "uf": "RJ", "tipo": "carioca",
        "url": "https://notacarioca.rio.gov.br/WSCertificado/Server.groovy",
    },
    "5300108": {
        "nome": "Brasília", "uf": "DF", "tipo": "df",
        "url": "https://www.nfse.df.gov.br/nfse-ws/NfseWS",
    },

    # ── Portal Nacional NFS-e (SEFAZ) ──────────────────────────────────
    "3509502": {
        "nome": "Campinas", "uf": "SP", "tipo": "nacional",
        "url": "https://www.nfse.gov.br/EmissorNacional/api/v1",
    },
    "3543402": {
        "nome": "Ribeirão Preto", "uf": "SP", "tipo": "nacional",
        "url": "https://www.nfse.gov.br/EmissorNacional/api/v1",
    },
    "3549904": {
        "nome": "São José dos Campos", "uf": "SP", "tipo": "nacional",
        "url": "https://www.nfse.gov.br/EmissorNacional/api/v1",
    },
    "2800308": {
        "nome": "Aracaju", "uf": "SE", "tipo": "nacional",
        "url": "https://www.nfse.gov.br/EmissorNacional/api/v1",
    },
    "1501402": {
        "nome": "Belém", "uf": "PA", "tipo": "nacional",
        "url": "https://www.nfse.gov.br/EmissorNacional/api/v1",
    },

    # ── ABRASF local (mesmo WSDL/método, URL varia por cidade) ─────────
    "3303203": {
        "nome": "Macaé", "uf": "RJ", "tipo": "abrasf",
        "url": "https://nfse.macae.rj.gov.br/webservice/nfse.asmx",
    },
    "3548807": {
        "nome": "Santos", "uf": "SP", "tipo": "abrasf",
        "url": "https://www.issdigital.santos.sp.gov.br/webservice/nfseservice.asmx",
    },
    "4106902": {
        "nome": "Curitiba", "uf": "PR", "tipo": "abrasf",
        "url": "https://tributacao.curitiba.pr.gov.br/index.php/webservice",
    },
    "3106200": {
        "nome": "Belo Horizonte", "uf": "MG", "tipo": "abrasf",
        "url": "https://bhissdigital.pbh.gov.br/bhiss-ws/nfse",
    },
    "2611606": {
        "nome": "Recife", "uf": "PE", "tipo": "abrasf",
        "url": "https://nfse.recife.pe.gov.br/nfse.asmx",
    },
    "2927408": {
        "nome": "Salvador", "uf": "BA", "tipo": "abrasf",
        "url": "https://nfse.salvador.ba.gov.br/webservice/nfse.asmx",
    },
    "3205309": {
        "nome": "Vitória", "uf": "ES", "tipo": "abrasf",
        "url": "https://sistemas.vitoria.es.gov.br/nfse-ws/nfse",
    },
    "4314902": {
        "nome": "Porto Alegre", "uf": "RS", "tipo": "abrasf",
        "url": "https://www.issdigital.portoalegre.rs.gov.br/webservice/nfseservice.asmx",
    },
    "2304400": {
        "nome": "Fortaleza", "uf": "CE", "tipo": "abrasf",
        "url": "https://nfse.fortaleza.ce.gov.br/Nfse/nfse.asmx",
    },
    "3127701": {
        "nome": "Sete Lagoas", "uf": "MG", "tipo": "abrasf",
        "url": "https://nfse.setelagoas.mg.gov.br/webservice/nfse.asmx",
    },
    "3300001": {
        "nome": "Angra dos Reis", "uf": "RJ", "tipo": "abrasf",
        "url": "https://nfse.angra.rj.gov.br/webservice/nfse.asmx",
    },
    "1302603": {
        "nome": "Manaus", "uf": "AM", "tipo": "abrasf",
        "url": "https://notamanaus.manaus.am.gov.br/webservice/nfse.asmx",
    },
    "4108304": {
        "nome": "Foz do Iguaçu", "uf": "PR", "tipo": "abrasf",
        "url": "https://nfse.pmfi.pr.gov.br/webservice/nfse.asmx",
    },
    "2111300": {
        "nome": "São Luís", "uf": "MA", "tipo": "abrasf",
        "url": "https://nfse.saoluis.ma.gov.br/webservice/nfse.asmx",
    },
    "4205407": {
        "nome": "Florianópolis", "uf": "SC", "tipo": "abrasf",
        "url": "https://nfse.pmf.sc.gov.br/webservice/nfse.asmx",
    },
    "3302007": {
        "nome": "Itaboraí", "uf": "RJ", "tipo": "abrasf",
        "url": "https://nfse.itaborai.rj.gov.br/webservice/nfse.asmx",
    },
    "3301009": {
        "nome": "Campos dos Goytacazes", "uf": "RJ", "tipo": "abrasf",
        "url": "https://nfse.campos.rj.gov.br/webservice/nfse.asmx",
    },
    "3170206": {
        "nome": "Uberlândia", "uf": "MG", "tipo": "abrasf",
        "url": "https://nfse.uberlandia.mg.gov.br/webservice/nfse.asmx",
    },
    "4104808": {
        "nome": "Cascavel", "uf": "PR", "tipo": "abrasf",
        "url": "https://nfse.cascavel.pr.gov.br/webservice/nfse.asmx",
    },
    "5208707": {
        "nome": "Goiânia", "uf": "GO", "tipo": "abrasf",
        "url": "https://nfse.goiania.go.gov.br/webservice/nfse.asmx",
    },
    "5218805": {
        "nome": "Rio Verde", "uf": "GO", "tipo": "abrasf",
        "url": "https://nfse.rioverde.go.gov.br/webservice/nfse.asmx",
    },
    "3548708": {
        "nome": "São Sebastião", "uf": "SP", "tipo": "abrasf",
        "url": "https://nfse.saosebastiao.sp.gov.br/webservice/nfse.asmx",
    },
}
