# DER — Resumo de Entidades Centrais

> Diagrama de Entidade-Relacionamento (ERD) mostrando as 60 entidades mais referenciadas por chaves estrangeiras.
> Gerado automaticamente a partir do schema dos bancos BennerSistemaCorporativo e BennerRh.
> Data: 2026-05-15 07:21

## Tabela: Entidades Mais Referenciadas

| # | Tabela | FKs Apontando |
|---|--------|---------------|
| 1 | Z_GRUPOUSUARIOS | 1418 |
| 2 | EMPRESAS | 1383 |
| 3 | FILIAIS | 901 |
| 4 | GN_PESSOAS | 884 |
| 5 | ADM_EMPRESAS | 554 |
| 6 | FN_CONTAS | 519 |
| 7 | DO_FUNCIONARIOS | 495 |
| 8 | GN_OPERACOES | 459 |
| 9 | R_RELATORIOS | 383 |
| 10 | CT_CC | 361 |
| 11 | ADM_UNIDADES | 358 |
| 12 | CT_CONTAS | 334 |
| 13 | FN_DOCUMENTOS | 329 |
| 14 | PD_PRODUTOS | 273 |
| 15 | GN_PROJETOS | 260 |
| 16 | FP_VERBAS | 256 |
| 17 | Z_TABELAS | 238 |
| 18 | PD_PRODUTOVARIACOESMESTRE | 208 |
| 19 | CM_UNIDADESMEDIDA | 197 |
| 20 | Z_CAMPOS | 182 |
| 21 | GN_MOEDAS | 172 |
| 22 | PD_ALMOXARIFADOS | 171 |
| 23 | CS_CARGOS | 158 |
| 24 | TR_IMPOSTOS | 154 |
| 25 | FN_TIPOSDOCUMENTOS | 149 |
| 26 | ADM_HIERARQUIAS | 129 |
| 27 | PD_FAMILIASPRODUTOS | 128 |
| 28 | FP_LISTASVERBAS | 126 |
| 29 | TR_CLASSIFICACOESTRIBUTARIAS | 126 |
| 30 | TA_ESTADOS | 124 |
| 31 | CP_GRUPOALCADAS | 122 |
| 32 | PO_SITUACOES | 121 |
| 33 | FP_COMPETENCIAS | 117 |
| 34 | Z_CONTADORES | 115 |
| 35 | CM_OPERACOESFATURAMENTO | 109 |
| 36 | TA_MUNICIPIOS | 98 |
| 37 | FN_FORMASPAGAMENTO | 96 |
| 38 | CP_CONDICOESPAGAMENTO | 91 |
| 39 | IN_TABELAS | 89 |
| 40 | Z_GRUPOS | 88 |
| 41 | ADM_ESTABELECIMENTOS | 88 |
| 42 | GN_NATUREZASFISCAIS | 85 |
| 43 | FN_CONTASTESOURARIA | 83 |
| 44 | SEI_PERIODOS | 83 |
| 45 | FP_CENTROSCUSTOS | 83 |
| 46 | TA_PAISES | 82 |
| 47 | CS_ATIVIDADES | 75 |
| 48 | CS_CLASSES | 72 |
| 49 | MUNICIPIOS | 72 |
| 50 | EDCF_PERIODOS | 70 |
| 51 | FP_BASES | 68 |
| 52 | Z_WFPROCESSOS | 64 |
| 53 | CT_CONTASGERENCIAIS | 64 |
| 54 | CN_CONTRATOS | 63 |
| 55 | BB_GRUPOSCONTABEIS | 62 |
| 56 | FP_FUNCIONARIOPAGAMENTO | 62 |
| 57 | Z_ARVORES | 62 |
| 58 | FN_PARCELAS | 62 |
| 59 | BB_MAQUINAS | 62 |
| 60 | ED_PERIODOS | 59 |

## Diagrama ERD (Mermaid)

```mermaid
erDiagram
    Z_GRUPOUSUARIOS {
        int HANDLE PK
        int Z_GRUPO
        char Z_EXCLUIDO
        int GRUPO
        varchar APELIDO
        varchar NOME
        varchar SENHA
        char PROTEGERREGISTRO
    }
    EMPRESAS {
        int HANDLE PK
        int Z_GRUPO
        varchar NOME
        varchar NOMEFANTASIA
        varchar CGC
        varchar BAIRRO
        int PAIS
        int ESTADO
    }
    FILIAIS {
        int HANDLE PK
        int Z_GRUPO
        int EMPRESA
        varchar NOME
        int FILIALCONTABIL
        int CONTACONTABIL
        varchar CGC
        varchar LOGRADOURO
    }
    GN_PESSOAS {
        int HANDLE PK
        int Z_GRUPO
        varchar NOME
        int TIPO
        varchar CGCCPF
        varchar LOGRADOURO
        varchar BAIRRO
        varchar CAIXAPOSTAL
    }
    ADM_EMPRESAS {
        int HANDLE PK
        int Z_GRUPO
        varchar ABREVIATURAMOEDACORPORATIVO
        char ANALITICOCONTAS
        char TERCEIROS
        varchar TIPOESTRUTURASALARIAL
        char TOTALIZADORASUNIDADE
        int UNIDADEHIERARQUIA
    }
    FN_CONTAS {
        int HANDLE PK
        int Z_GRUPO
        int EMPRESA
        int CODIGOREDUZIDO
        varchar NOME
        int NIVELSUPERIOR
        varchar ESTRUTURA
        varchar APELIDO
    }
    DO_FUNCIONARIOS {
        int HANDLE PK
        int Z_GRUPO
        int UNIDADE
        datetime UNIDADEDATA
        varchar NOME
        int ESTADOCIVIL
        datetime DATANASCIMENTO
        int NIVELESCOLARIDADE
    }
    GN_OPERACOES {
        int HANDLE PK
        int Z_GRUPO
        varchar NOME
        int TIPODOCUMENTO
        int EMPRESA
        int OPERACAOCONTABIL
        char EHCONTASPAGAR
        char EHCONTASRECEBER
    }
    R_RELATORIOS {
        int HANDLE PK
        int Z_GRUPO
        varchar NOME
        int DETALHE
        int CABECALHO
        int RODAPE
        varchar FONTE
        char CABECALHOPRIMEIRA
    }
    CT_CC {
        int HANDLE PK
        int Z_GRUPO
        int CODIGO
        varchar NOME
        char ULTIMONIVEL
        int NIVELSUPERIOR
        varchar ESTRUTURA
        int EMPRESA
    }
    ADM_UNIDADES {
        int HANDLE PK
        int Z_GRUPO
        char ATIVA
        char AUTORIZAREXTRAS
        int CODIGO
        varchar CODIGOCONT
        int CODIGOFP
        char DEDUCAOISS
    }
    CT_CONTAS {
        int HANDLE PK
        int Z_GRUPO
        int EMPRESA
        int CODIGOREDUZIDO
        int INDICEFINANCEIRO
        datetime DATAINCLUSAO
        text COMPLEMENTO
        char ULTIMONIVEL
    }
    FN_DOCUMENTOS {
        int HANDLE PK
        int Z_GRUPO
        int EMPRESA
        int FILIAL
        int PESSOA
        varchar DOCUMENTODIGITADO
        datetime DATAENTRADA
        datetime DATAEMISSAO
    }
    PD_PRODUTOS {
        int HANDLE PK
        int Z_GRUPO
        text DESCRICAO
        varchar NOME
        int CODIGO
        char RECUPERAIPI
        int CLASSIFICACAOTRIBUTARIA
        int CLASSIFICACAOTIPI
    }
    GN_PROJETOS {
        int HANDLE PK
        int Z_GRUPO
        varchar ESTRUTURA
        int EMPRESA
        int NIVELSUPERIOR
        varchar NOME
        char ULTIMONIVEL
        int CODIGOREDUZIDO
    }
    FP_VERBAS {
        int HANDLE PK
        int Z_GRUPO
        char ACRESCIMOSALBASE
        char ACUMULARUNIDADE
        varchar CARACTERISTICASARM
        varchar CARACTERISTICASDESCONTO
        varchar CARACTERISTICASPROVENTO
        int CODIGO
    }
    Z_TABELAS {
        int HANDLE PK
        varchar NOME
        varchar APELIDO
        varchar LEGENDA
        char LOCAL
        char TIPO
        char GENERICA
        char DESENVOLVIMENTO
    }
    PD_PRODUTOVARIACOESMESTRE {
        int HANDLE PK
        int Z_GRUPO
        varchar CONJUNTOVARIACOES
        varchar CODIGOBARRAS
        text DESCRICAO
        int USUARIOINCLUIU
        datetime DATAINCLUSAO
        int USUARIOALTEROU
    }
    CM_UNIDADESMEDIDA {
        int HANDLE PK
        int Z_GRUPO
        varchar NOME
        varchar ABREVIATURA
        int CODIGOIN68
        datetime DATAINCLUSAO
        datetime DATAALTERACAO
        varchar ABREVIATURAFCI
    }
    Z_CAMPOS {
        int HANDLE PK
        int TABELA
        varchar NOME
        varchar LEGENDAFORMULARIO
        varchar LEGENDAGRADE
        varchar ORDEM
        varchar DICA
        int PAGINA
    }
    GN_MOEDAS {
        int HANDLE PK
        int Z_GRUPO
        varchar NOME
        varchar ABREVIATURA
        varchar VARIACAO
        char TIPO
        char INDICE
        char PERIODICIDADE
    }
    PD_ALMOXARIFADOS {
        int HANDLE PK
        int Z_GRUPO
        varchar NOME
        int EMPRESA
        int FILIAL
        int ALMOXARIFADO
        int PAIS
        int TIPO
    }
    CS_CARGOS {
        int HANDLE PK
        int CLASSE
        varchar TITULO
        varchar CBO
        int ESCOLARIDADE
        text DESCRICAO
        varchar REPORTA
        float CARGAHORARIADIARIA
    }
    TR_IMPOSTOS {
        int HANDLE PK
        int Z_GRUPO
        int CODIGO
        varchar SIGLA
        varchar COMPETENCIA
        char CALCULADO
        varchar NOME
        varchar CODIGORECEITA
    }
    FN_TIPOSDOCUMENTOS {
        int HANDLE PK
        int Z_GRUPO
        varchar NOME
        char NATUREZA
        char EXIGENUMERACAO
        varchar SIGLA
        char TIPOPROVISAO
        char EHCHEQUEPREDATADO
    }
    ADM_HIERARQUIAS {
        int HANDLE PK
        int EMPRESA
        int UNIDADE
        int NIVELSUPERIOR
        varchar ESTRUTURA
        varchar NOME
        varchar APELIDO
        varchar ULTIMONIVEL
    }
    PD_FAMILIASPRODUTOS {
        int HANDLE PK
        int Z_GRUPO
        int NIVELSUPERIOR
        char ULTIMONIVEL
        varchar FAMILIA
        varchar NOME
        int EMPRESA
        varchar CODIGO
    }
    FP_LISTASVERBAS {
        int HANDLE PK
        int Z_GRUPO
        int CODIGO
        varchar NOME
        varchar ABREVIATURA
        char CONFIRMARINCIDENCIAS
    }
    TR_CLASSIFICACOESTRIBUTARIAS {
        int HANDLE PK
        int Z_GRUPO
        varchar NOME
        int CODIGO
        char NORMAL
        char SERVICO
        int IMPOSTO
        int DESCRICAOPADRAO
    }
    TA_ESTADOS {
        int HANDLE PK
        int PAIS
        varchar NOME
        varchar GENTILICO
        varchar SIGLA
        int Z_GRUPO
        char OUTROS
    }
    CP_GRUPOALCADAS {
        int HANDLE PK
        int Z_GRUPO
        varchar NOMEDOGRUPO
        int EMPRESA
        int FILIAL
        int TIPO
        char EHHIERARQUIA
        char AVISARTODOSREJEICAO
    }
    PO_SITUACOES {
        int HANDLE PK
        int CODIGO
        varchar NOME
        varchar ABREVIACAO
        int OCOFOL
        int SITUACAOCOMP
        int TIPOSITUACAO
        varchar PERDEDIAHORISTA
    }
    FP_COMPETENCIAS {
        int HANDLE PK
        datetime COMPETENCIA
        int SITUACAOMES
        datetime DATACONTABIL
        int Z_GRUPO
        text LOGABERTURACOMP
        text LOGFECHAMENTOCOMP
    }
    Z_CONTADORES {
        int HANDLE PK
        int Z_GRUPO
        varchar NOME
        char UNIVERSAL
        int VALOR
        int PERIODO
        datetime DATA
        int VALORINICIAL
    }
    CM_OPERACOESFATURAMENTO {
        int HANDLE PK
        int Z_GRUPO
        int EMPRESA
        varchar NOME
        int CODIGO
        char DOCUMENTO
        varchar ISENTOICMS
        char ICMSSOBREIPI
    }
    TA_MUNICIPIOS {
        int HANDLE PK
        int PAIS
        int ESTADO
        int CODIGOIBGE
        varchar NOME
        varchar CEP
        int DDD
        int Z_GRUPO
    }
    FN_FORMASPAGAMENTO {
        int HANDLE PK
        int Z_GRUPO
        varchar NOME
        varchar CODIGO
        char K_EHCONTACORRENTE
        varchar NUMERODARF
        varchar TIPOCONTA
        int TIPOOPERACAO
    }
    CP_CONDICOESPAGAMENTO {
        int HANDLE PK
        int Z_GRUPO
        varchar DESCRICAO
        text OBSERVACAO
        int PARCELADIGITADA
        int DIAVENCIMENTO
        char DIAUTIL
        int DIAFIXO
    }
    IN_TABELAS {
        int HANDLE PK
        int Z_GRUPO
        int EMPRESA
        int NUMEROTABELA
        varchar CODIGO
        varchar DESCRICAO
        int HANDLEORIGEM
        datetime DATAATUALIZACAO
    }
    Z_GRUPOS {
        int HANDLE PK
        int Z_GRUPO
        varchar NOME
        char LER
        char ALTERAR
        char INCLUIR
        char EXCLUIR
        char DESENVOLVER
    }
    ADM_ESTABELECIMENTOS {
        int HANDLE PK
        int EMPRESA
        int INSCRICAO
        varchar CGC
        varchar CEI
        varchar CGCCEI
        varchar NOME
        varchar CEP
    }
    GN_NATUREZASFISCAIS {
        int HANDLE PK
        int Z_GRUPO
        varchar NOME
        char SOMARFATURAMENTO
        char DIFERENCAALIQUOTA
        char IRRFAPLICAVEL
        char ULTIMONIVEL
        int NIVELSUPERIOR
    }
    FN_CONTASTESOURARIA {
        int HANDLE PK
        int Z_GRUPO
        int EMPRESA
        int FILIAL
        varchar NOME
        varchar NUMEROCONTA
        int TIPOCONTA
        varchar IDENTIFICACAO
    }
    SEI_PERIODOS {
        int HANDLE PK
        int Z_GRUPO
        int EMPRESA
        float ULTIMONUMEROGASTO
        datetime DATAFINAL
        int SITUACAO
        float ULTIMONUMERODETALHEGASTO
        varchar RECIBOFECHAMENTO
    }
    FP_CENTROSCUSTOS {
        int HANDLE PK
        int EMPRESA
        int CODIGO
        varchar NOME
        int RATEIO
        int Z_GRUPO
        int SITUACAO
        int PROJETO
    }
    TA_PAISES {
        int HANDLE PK
        varchar NOME
        varchar GENTILICO
        varchar SIGLA
        int DDI
        int CODIGORAIS
        int Z_GRUPO
        int ESOCIAL
    }
    CS_ATIVIDADES {
        int HANDLE PK
        int EMPRESA
        varchar NOME
        int Z_GRUPO
        int CODIGO
        text DESCRICAO
        int VERBAGRATIFICACAO
        int VERBAVALORINTEGRAL
    }
    CS_CLASSES {
        int HANDLE PK
        int EMPRESA
        int CODIGO
        varchar NOME
        int Z_GRUPO
        int NUMEROMAXIMO
        float PONTUACAOMAXIMA
        varchar SIGLA
    }
    MUNICIPIOS {
        int HANDLE PK
        int Z_GRUPO
        int PAIS
        int ESTADO
        varchar NOME
        int CODIGOIBGE
        varchar CEP
        int DDD
    }
    EDCF_PERIODOS {
        int HANDLE PK
        int Z_GRUPO
        int EMPRESA
        int ESTABELECIMENTOMATRIZ
        datetime DATAINICIAL
        datetime DATAFINAL
        varchar CNPJ
        varchar NOMEEMPRESARIAL
    }
    FP_BASES {
        int HANDLE PK
        int CODIGO
        varchar NOME
        varchar ABREVIATURA
        int MACRO
        int ACUMULACAO
        int CAMPOACUMULAR
        int TIPOSFOLHA
    }
    Z_WFPROCESSOS {
        int HANDLE PK
        int Z_GRUPO
        varchar IDENTIFICACAO
        varchar Z_IDENTIFICACAO
        varchar TITULO
        int TAREFA
    }
    CT_CONTASGERENCIAIS {
        int HANDLE PK
        int Z_GRUPO
        varchar NOME
        int NIVELSUPERIOR
        char ULTIMONIVEL
        int EMPRESA
        int DIA
        text FORMULA
    }
    CN_CONTRATOS {
        int HANDLE PK
        int Z_GRUPO
        int EMPRESA
        int TIPOCONTRATO
        datetime DATAINICIO
        datetime DATAASSINATURA
        int ORIGINAL
        int SITUACAO
    }
    BB_GRUPOSCONTABEIS {
        int HANDLE PK
        int Z_GRUPO
        varchar NOME
        int OPERACAO
        int OPCOMISSAOKANDIR
        int EMPRESA
    }
    FP_FUNCIONARIOPAGAMENTO {
        int HANDLE PK
        int FUNCIONARIO
        int EMPRESA
        int FOLHAS
        int UNIDADE
        int CONTSINDICAL
        int NAVOS
        float INSALUBRIDADE
    }
    Z_ARVORES {
        int HANDLE PK
        int Z_GRUPO
        varchar NOME
        char TIPO
        varchar ORDEM
        varchar LEGENDA
        char SISTEMA
        char CLIDEF
    }
    FN_PARCELAS {
        int HANDLE PK
        int Z_GRUPO
        int FORMALIQUIDACAO
        char PAGAMENTOELETRONICO
        datetime DATAVENCIMENTO
        int BANCO
        int AGENCIA
        varchar CHAVEASBACE
    }
    BB_MAQUINAS {
        int HANDLE PK
        int Z_GRUPO
        int EMPRESA
        int FILIAL
        varchar PCC
        varchar LOCAL
        varchar LOGRADOURO
        varchar COMPLEMENTO
    }
    ED_PERIODOS {
        int HANDLE PK
        int Z_GRUPO
        int FILIAL
        datetime DATAINICIAL
        datetime DATAFINAL
        varchar LOCALARQUIVO
        int TIPOESCRITURACAO
        int FINALIDADEARQUIVO
    }
    Z_GRUPOUSUARIOS }o--|| Z_GRUPOS : "FK"
    Z_GRUPOUSUARIOS }o--|| CT_CC : "FK"
    Z_GRUPOUSUARIOS }o--|| PD_ALMOXARIFADOS : "FK"
    Z_GRUPOUSUARIOS }o--|| GN_PESSOAS : "FK"
    Z_GRUPOUSUARIOS }o--|| FILIAIS : "FK"
    Z_GRUPOUSUARIOS }o--|| BB_MAQUINAS : "FK"
    EMPRESAS }o--|| GN_PESSOAS : "FK"
    EMPRESAS }o--|| Z_GRUPOUSUARIOS : "FK"
    EMPRESAS }o--|| FN_FORMASPAGAMENTO : "FK"
    EMPRESAS }o--|| PD_FAMILIASPRODUTOS : "FK"
    EMPRESAS }o--|| CM_UNIDADESMEDIDA : "FK"
    EMPRESAS }o--|| GN_OPERACOES : "FK"
    EMPRESAS }o--|| CT_CONTAS : "FK"
    EMPRESAS }o--|| CM_OPERACOESFATURAMENTO : "FK"
    EMPRESAS }o--|| CP_GRUPOALCADAS : "FK"
    FILIAIS }o--|| GN_OPERACOES : "FK"
    FILIAIS }o--|| PD_PRODUTOS : "FK"
    FILIAIS }o--|| CT_CONTAS : "FK"
    FILIAIS }o--|| Z_GRUPOUSUARIOS : "FK"
    FILIAIS }o--|| EMPRESAS : "FK"
    FILIAIS }o--|| R_RELATORIOS : "FK"
    FILIAIS }o--|| CT_CC : "FK"
    FILIAIS }o--|| MUNICIPIOS : "FK"
    GN_PESSOAS }o--|| FILIAIS : "FK"
    GN_PESSOAS }o--|| Z_GRUPOUSUARIOS : "FK"
    GN_PESSOAS }o--|| FN_CONTASTESOURARIA : "FK"
    GN_PESSOAS }o--|| CT_CONTAS : "FK"
    GN_PESSOAS }o--|| CP_CONDICOESPAGAMENTO : "FK"
    GN_PESSOAS }o--|| CP_GRUPOALCADAS : "FK"
    GN_PESSOAS }o--|| FN_FORMASPAGAMENTO : "FK"
    GN_PESSOAS }o--|| FN_CONTAS : "FK"
    GN_PESSOAS }o--|| BB_MAQUINAS : "FK"
    GN_PESSOAS }o--|| R_RELATORIOS : "FK"
    FN_CONTAS }o--|| GN_PESSOAS : "FK"
    GN_OPERACOES }o--|| IN_TABELAS : "FK"
    GN_OPERACOES }o--|| CT_CC : "FK"
    GN_OPERACOES }o--|| TR_CLASSIFICACOESTRIBUTARIAS : "FK"
    GN_OPERACOES }o--|| Z_GRUPOUSUARIOS : "FK"
    GN_OPERACOES }o--|| FN_TIPOSDOCUMENTOS : "FK"
    GN_OPERACOES }o--|| CT_CONTAS : "FK"
    R_RELATORIOS }o--|| Z_ARVORES : "FK"
    R_RELATORIOS }o--|| Z_TABELAS : "FK"
    CT_CC }o--|| Z_GRUPOUSUARIOS : "FK"
    CT_CC }o--|| GN_PESSOAS : "FK"
    CT_CC }o--|| EMPRESAS : "FK"
    CT_CC }o--|| CT_CONTAS : "FK"
    CT_CONTAS }o--|| GN_MOEDAS : "FK"
    CT_CONTAS }o--|| FILIAIS : "FK"
    CT_CONTAS }o--|| Z_GRUPOUSUARIOS : "FK"
    FN_DOCUMENTOS }o--|| GN_PESSOAS : "FK"
    FN_DOCUMENTOS }o--|| CT_CONTAS : "FK"
    FN_DOCUMENTOS }o--|| CM_OPERACOESFATURAMENTO : "FK"
    FN_DOCUMENTOS }o--|| CP_CONDICOESPAGAMENTO : "FK"
    FN_DOCUMENTOS }o--|| Z_GRUPOUSUARIOS : "FK"
    FN_DOCUMENTOS }o--|| PD_ALMOXARIFADOS : "FK"
    FN_DOCUMENTOS }o--|| CP_GRUPOALCADAS : "FK"
    FN_DOCUMENTOS }o--|| TR_IMPOSTOS : "FK"
    FN_DOCUMENTOS }o--|| CT_CC : "FK"
    FN_DOCUMENTOS }o--|| FILIAIS : "FK"
    FN_DOCUMENTOS }o--|| GN_MOEDAS : "FK"
    FN_DOCUMENTOS }o--|| GN_OPERACOES : "FK"
    FN_DOCUMENTOS }o--|| FN_TIPOSDOCUMENTOS : "FK"
    PD_PRODUTOS }o--|| CM_UNIDADESMEDIDA : "FK"
    PD_PRODUTOS }o--|| PD_ALMOXARIFADOS : "FK"
    PD_PRODUTOS }o--|| FN_CONTAS : "FK"
    PD_PRODUTOS }o--|| CT_CC : "FK"
    PD_PRODUTOS }o--|| TR_IMPOSTOS : "FK"
    PD_PRODUTOS }o--|| CT_CONTAS : "FK"
    PD_PRODUTOS }o--|| CM_OPERACOESFATURAMENTO : "FK"
    PD_PRODUTOS }o--|| Z_GRUPOUSUARIOS : "FK"
    PD_PRODUTOS }o--|| CT_CONTASGERENCIAIS : "FK"
    PD_PRODUTOS }o--|| CN_CONTRATOS : "FK"
    PD_PRODUTOS }o--|| GN_NATUREZASFISCAIS : "FK"
    PD_PRODUTOS }o--|| TR_CLASSIFICACOESTRIBUTARIAS : "FK"
    PD_PRODUTOS }o--|| FILIAIS : "FK"
    PD_PRODUTOS }o--|| PD_FAMILIASPRODUTOS : "FK"
    PD_PRODUTOS }o--|| GN_PESSOAS : "FK"
    GN_PROJETOS }o--|| EMPRESAS : "FK"
    GN_PROJETOS }o--|| GN_PESSOAS : "FK"
    Z_TABELAS }o--|| Z_CAMPOS : "FK"
    PD_PRODUTOVARIACOESMESTRE }o--|| Z_GRUPOUSUARIOS : "FK"
    PD_PRODUTOVARIACOESMESTRE }o--|| PD_ALMOXARIFADOS : "FK"
    PD_PRODUTOVARIACOESMESTRE }o--|| PD_PRODUTOS : "FK"
    PD_PRODUTOVARIACOESMESTRE }o--|| PD_FAMILIASPRODUTOS : "FK"
    PD_PRODUTOVARIACOESMESTRE }o--|| CN_CONTRATOS : "FK"
    PD_PRODUTOVARIACOESMESTRE }o--|| CM_UNIDADESMEDIDA : "FK"
    CM_UNIDADESMEDIDA }o--|| IN_TABELAS : "FK"
    Z_CAMPOS }o--|| Z_TABELAS : "FK"
    PD_ALMOXARIFADOS }o--|| FILIAIS : "FK"
    PD_ALMOXARIFADOS }o--|| Z_GRUPOUSUARIOS : "FK"
    PD_ALMOXARIFADOS }o--|| CT_CC : "FK"
    TR_IMPOSTOS }o--|| FN_FORMASPAGAMENTO : "FK"
    TR_IMPOSTOS }o--|| R_RELATORIOS : "FK"
    TR_IMPOSTOS }o--|| CT_CONTAS : "FK"
    TR_IMPOSTOS }o--|| CT_CC : "FK"
    TR_IMPOSTOS }o--|| GN_PESSOAS : "FK"
    TR_IMPOSTOS }o--|| GN_OPERACOES : "FK"
    TR_IMPOSTOS }o--|| FN_TIPOSDOCUMENTOS : "FK"
    TR_IMPOSTOS }o--|| FN_CONTAS : "FK"
    TR_IMPOSTOS }o--|| GN_PROJETOS : "FK"
    TR_IMPOSTOS }o--|| GN_MOEDAS : "FK"
    TR_IMPOSTOS }o--|| CT_CONTASGERENCIAIS : "FK"
    FN_TIPOSDOCUMENTOS }o--|| IN_TABELAS : "FK"
    FN_TIPOSDOCUMENTOS }o--|| CM_OPERACOESFATURAMENTO : "FK"
    PD_FAMILIASPRODUTOS }o--|| Z_GRUPOUSUARIOS : "FK"
    PD_FAMILIASPRODUTOS }o--|| CT_CC : "FK"
    PD_FAMILIASPRODUTOS }o--|| CT_CONTAS : "FK"
    PD_FAMILIASPRODUTOS }o--|| TR_CLASSIFICACOESTRIBUTARIAS : "FK"
    PD_FAMILIASPRODUTOS }o--|| TR_IMPOSTOS : "FK"
    PD_FAMILIASPRODUTOS }o--|| GN_NATUREZASFISCAIS : "FK"
    PD_FAMILIASPRODUTOS }o--|| GN_PESSOAS : "FK"
    PD_FAMILIASPRODUTOS }o--|| CM_OPERACOESFATURAMENTO : "FK"
    CP_GRUPOALCADAS }o--|| FILIAIS : "FK"
    CP_GRUPOALCADAS }o--|| Z_TABELAS : "FK"
    CM_OPERACOESFATURAMENTO }o--|| GN_PESSOAS : "FK"
    CM_OPERACOESFATURAMENTO }o--|| EMPRESAS : "FK"
    CM_OPERACOESFATURAMENTO }o--|| TR_CLASSIFICACOESTRIBUTARIAS : "FK"
    CM_OPERACOESFATURAMENTO }o--|| CT_CC : "FK"
    CM_OPERACOESFATURAMENTO }o--|| FN_CONTAS : "FK"
    CM_OPERACOESFATURAMENTO }o--|| R_RELATORIOS : "FK"
    CM_OPERACOESFATURAMENTO }o--|| Z_CONTADORES : "FK"
    CM_OPERACOESFATURAMENTO }o--|| GN_NATUREZASFISCAIS : "FK"
    CP_CONDICOESPAGAMENTO }o--|| EMPRESAS : "FK"
    CP_CONDICOESPAGAMENTO }o--|| FN_FORMASPAGAMENTO : "FK"
    CP_CONDICOESPAGAMENTO }o--|| GN_PESSOAS : "FK"
    CP_CONDICOESPAGAMENTO }o--|| FN_CONTAS : "FK"
    CP_CONDICOESPAGAMENTO }o--|| CT_CC : "FK"
    CP_CONDICOESPAGAMENTO }o--|| GN_PROJETOS : "FK"
    CP_CONDICOESPAGAMENTO }o--|| GN_OPERACOES : "FK"
    GN_NATUREZASFISCAIS }o--|| TR_IMPOSTOS : "FK"
    GN_NATUREZASFISCAIS }o--|| TR_CLASSIFICACOESTRIBUTARIAS : "FK"
    GN_NATUREZASFISCAIS }o--|| CM_OPERACOESFATURAMENTO : "FK"
    FN_CONTASTESOURARIA }o--|| GN_MOEDAS : "FK"
    FN_CONTASTESOURARIA }o--|| GN_PESSOAS : "FK"
    FN_CONTASTESOURARIA }o--|| FN_CONTAS : "FK"
    FN_CONTASTESOURARIA }o--|| CT_CC : "FK"
    FN_CONTASTESOURARIA }o--|| FILIAIS : "FK"
    FN_CONTASTESOURARIA }o--|| CT_CONTAS : "FK"
    FN_CONTASTESOURARIA }o--|| Z_GRUPOUSUARIOS : "FK"
    SEI_PERIODOS }o--|| EMPRESAS : "FK"
    EDCF_PERIODOS }o--|| EMPRESAS : "FK"
    CT_CONTASGERENCIAIS }o--|| CT_CONTAS : "FK"
    CN_CONTRATOS }o--|| GN_OPERACOES : "FK"
    CN_CONTRATOS }o--|| Z_GRUPOUSUARIOS : "FK"
    CN_CONTRATOS }o--|| CP_GRUPOALCADAS : "FK"
    CN_CONTRATOS }o--|| GN_PESSOAS : "FK"
    CN_CONTRATOS }o--|| FILIAIS : "FK"
    CN_CONTRATOS }o--|| CP_CONDICOESPAGAMENTO : "FK"
    CN_CONTRATOS }o--|| GN_MOEDAS : "FK"
    CN_CONTRATOS }o--|| CT_CC : "FK"
    CN_CONTRATOS }o--|| FN_FORMASPAGAMENTO : "FK"
    BB_GRUPOSCONTABEIS }o--|| GN_OPERACOES : "FK"
    BB_GRUPOSCONTABEIS }o--|| EMPRESAS : "FK"
    Z_ARVORES }o--|| Z_TABELAS : "FK"
    FN_PARCELAS }o--|| FN_CONTASTESOURARIA : "FK"
    FN_PARCELAS }o--|| GN_MOEDAS : "FK"
    FN_PARCELAS }o--|| CN_CONTRATOS : "FK"
    FN_PARCELAS }o--|| FN_DOCUMENTOS : "FK"
    FN_PARCELAS }o--|| GN_OPERACOES : "FK"
    FN_PARCELAS }o--|| FN_FORMASPAGAMENTO : "FK"
    FN_PARCELAS }o--|| Z_GRUPOUSUARIOS : "FK"
    FN_PARCELAS }o--|| FILIAIS : "FK"
    FN_PARCELAS }o--|| CP_GRUPOALCADAS : "FK"
    FN_PARCELAS }o--|| GN_PESSOAS : "FK"
    BB_MAQUINAS }o--|| GN_PESSOAS : "FK"
    BB_MAQUINAS }o--|| EMPRESAS : "FK"
    BB_MAQUINAS }o--|| FILIAIS : "FK"
    BB_MAQUINAS }o--|| MUNICIPIOS : "FK"
    ED_PERIODOS }o--|| FILIAIS : "FK"
    ED_PERIODOS }o--|| R_RELATORIOS : "FK"
    ED_PERIODOS }o--|| EMPRESAS : "FK"
    Z_GRUPOUSUARIOS }o--|| DO_FUNCIONARIOS : "FK"
    ADM_EMPRESAS }o--|| ADM_UNIDADES : "FK"
    ADM_EMPRESAS }o--|| R_RELATORIOS : "FK"
    ADM_EMPRESAS }o--|| ADM_ESTABELECIMENTOS : "FK"
    DO_FUNCIONARIOS }o--|| TA_ESTADOS : "FK"
    DO_FUNCIONARIOS }o--|| CS_CARGOS : "FK"
    DO_FUNCIONARIOS }o--|| ADM_UNIDADES : "FK"
    DO_FUNCIONARIOS }o--|| ADM_HIERARQUIAS : "FK"
    DO_FUNCIONARIOS }o--|| CS_CLASSES : "FK"
    DO_FUNCIONARIOS }o--|| FP_CENTROSCUSTOS : "FK"
    DO_FUNCIONARIOS }o--|| TA_MUNICIPIOS : "FK"
    DO_FUNCIONARIOS }o--|| TA_PAISES : "FK"
    DO_FUNCIONARIOS }o--|| ADM_EMPRESAS : "FK"
    ADM_UNIDADES }o--|| ADM_ESTABELECIMENTOS : "FK"
    ADM_UNIDADES }o--|| ADM_EMPRESAS : "FK"
    FP_VERBAS }o--|| FP_LISTASVERBAS : "FK"
    CS_CARGOS }o--|| CS_CLASSES : "FK"
    ADM_HIERARQUIAS }o--|| Z_GRUPOS : "FK"
    ADM_HIERARQUIAS }o--|| Z_GRUPOUSUARIOS : "FK"
    ADM_HIERARQUIAS }o--|| ADM_ESTABELECIMENTOS : "FK"
    ADM_HIERARQUIAS }o--|| ADM_EMPRESAS : "FK"
    ADM_HIERARQUIAS }o--|| ADM_UNIDADES : "FK"
    TA_ESTADOS }o--|| TA_PAISES : "FK"
    TA_MUNICIPIOS }o--|| TA_ESTADOS : "FK"
    TA_MUNICIPIOS }o--|| TA_PAISES : "FK"
    ADM_ESTABELECIMENTOS }o--|| TA_ESTADOS : "FK"
    ADM_ESTABELECIMENTOS }o--|| TA_MUNICIPIOS : "FK"
    ADM_ESTABELECIMENTOS }o--|| ADM_EMPRESAS : "FK"
    ADM_ESTABELECIMENTOS }o--|| TA_PAISES : "FK"
    FP_CENTROSCUSTOS }o--|| ADM_EMPRESAS : "FK"
    CS_ATIVIDADES }o--|| FP_VERBAS : "FK"
    CS_ATIVIDADES }o--|| ADM_EMPRESAS : "FK"
    CS_CLASSES }o--|| ADM_EMPRESAS : "FK"
    FP_FUNCIONARIOPAGAMENTO }o--|| DO_FUNCIONARIOS : "FK"
    FP_FUNCIONARIOPAGAMENTO }o--|| FP_CENTROSCUSTOS : "FK"
    FP_FUNCIONARIOPAGAMENTO }o--|| ADM_EMPRESAS : "FK"
    FP_FUNCIONARIOPAGAMENTO }o--|| ADM_UNIDADES : "FK"
```

