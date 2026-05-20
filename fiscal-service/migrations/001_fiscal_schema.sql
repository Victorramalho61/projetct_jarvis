-- fiscal-service schema — Jarvis
-- Execute via Supabase SQL editor ou psql

CREATE TABLE IF NOT EXISTS fiscal_companies (
    id                    uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    cnpj                  varchar(14) UNIQUE NOT NULL,
    nome                  text NOT NULL,
    regime                text NOT NULL DEFAULT 'lucro_real',
    uf_sede               varchar(2),
    inscricao_municipal   text,
    cert_pfx_encrypted    text,
    cert_password_encrypted text,
    cert_expiry           date,
    ultimo_nsu_nfe        bigint DEFAULT 0,
    ultimo_nsu_cte        bigint DEFAULT 0,
    sync_nfe_ativo        boolean DEFAULT false,
    sync_cte_ativo        boolean DEFAULT false,
    sync_nfse_ativo       boolean DEFAULT false,
    ultima_sync           timestamptz,
    -- ND Digital portal (NFSe recebidas via portal centralizador)
    ndd_access_token      text,
    ndd_refresh_token     text,
    ndd_token_expires_at  timestamptz,
    created_at            timestamptz DEFAULT now()
);

CREATE TABLE IF NOT EXISTS fiscal_nfse_municipalities (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id      uuid REFERENCES fiscal_companies(id) ON DELETE CASCADE,
    municipio_ibge  varchar(7) NOT NULL,
    municipio_nome  text NOT NULL,
    uf              varchar(2) NOT NULL,
    sistema_tipo    text NOT NULL,
    -- nacional | abrasf | paulistana | carioca | df
    status          text NOT NULL DEFAULT 'pendente',
    -- pendente = não cadastrado na prefeitura
    -- cadastrado = sync ativo
    -- erro = falha na última tentativa
    obs             text,
    ativo           boolean DEFAULT false,
    ultima_sync     timestamptz,
    UNIQUE(company_id, municipio_ibge)
);

CREATE TABLE IF NOT EXISTS fiscal_periods (
    id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id  uuid REFERENCES fiscal_companies(id) ON DELETE CASCADE,
    ano         int NOT NULL,
    mes         int NOT NULL,
    status      text NOT NULL DEFAULT 'aberto',
    -- aberto | fechado
    fechado_em  timestamptz,
    created_at  timestamptz DEFAULT now(),
    UNIQUE(company_id, ano, mes)
);

CREATE TABLE IF NOT EXISTS fiscal_documents (
    id                   uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id           uuid REFERENCES fiscal_companies(id) ON DELETE CASCADE,
    period_id            uuid REFERENCES fiscal_periods(id),
    tipo                 text NOT NULL,
    -- NFe | CTe | NFSe
    municipio_ibge       varchar(7),
    chave_acesso         varchar(44) UNIQUE,
    numero               varchar(20),
    serie                varchar(3),
    emitente_cnpj        varchar(14),
    emitente_nome        text,
    destinatario_cnpj    varchar(14),
    destinatario_nome    text,
    natureza_operacao    text,
    data_emissao         date,
    data_entrada         date,
    valor_total          numeric(15,2),
    valor_produtos       numeric(15,2),
    valor_icms           numeric(15,2),
    valor_pis            numeric(15,2),
    valor_cofins         numeric(15,2),
    xml_content          text,
    status               text NOT NULL DEFAULT 'pendente',
    -- pendente | conferido | divergencia | cancelado
    created_at           timestamptz DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_fiscal_docs_company_period
    ON fiscal_documents(company_id, period_id);
CREATE INDEX IF NOT EXISTS idx_fiscal_docs_emissao
    ON fiscal_documents(data_emissao);
CREATE INDEX IF NOT EXISTS idx_fiscal_docs_chave
    ON fiscal_documents(chave_acesso);

CREATE TABLE IF NOT EXISTS fiscal_items (
    id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id      uuid REFERENCES fiscal_documents(id) ON DELETE CASCADE,
    numero_item      int,
    descricao        text,
    ncm              varchar(8),
    cfop             varchar(4),
    cst_icms         varchar(3),
    cst_pis          varchar(2),
    cst_cofins       varchar(2),
    quantidade       numeric(15,4),
    valor_unitario   numeric(15,4),
    valor_produto    numeric(15,2),
    base_icms        numeric(15,2),
    aliquota_icms    numeric(5,2),
    valor_icms       numeric(15,2),
    base_pis         numeric(15,2),
    aliquota_pis     numeric(5,4),
    valor_pis        numeric(15,2),
    base_cofins      numeric(15,2),
    aliquota_cofins  numeric(5,4),
    valor_cofins     numeric(15,2),
    valor_icms_uf_dest  numeric(15,2),
    valor_icms_uf_remi  numeric(15,2),
    valor_fcp_uf_dest   numeric(15,2),
    cfop_valido      boolean,
    cst_valido       boolean,
    divergencias     jsonb DEFAULT '[]'
);

CREATE INDEX IF NOT EXISTS idx_fiscal_items_document
    ON fiscal_items(document_id);

CREATE TABLE IF NOT EXISTS fiscal_sync_logs (
    id                    uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id            uuid REFERENCES fiscal_companies(id) ON DELETE CASCADE,
    tipo                  text NOT NULL,
    -- NFe | CTe | NFSe
    municipio_ibge        varchar(7),
    nsu_inicial           bigint,
    nsu_final             bigint,
    documentos_novos      int DEFAULT 0,
    documentos_cancelados int DEFAULT 0,
    status                text NOT NULL,
    -- ok | erro
    erro_msg              text,
    janela                text,
    -- principal (02:00) | retry (04:00) | manual
    executado_em          timestamptz DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_sync_logs_company_date
    ON fiscal_sync_logs(company_id, executado_em DESC);

CREATE TABLE IF NOT EXISTS fiscal_conference_reports (
    id                     uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    period_id              uuid REFERENCES fiscal_periods(id) ON DELETE CASCADE,
    total_documentos       int DEFAULT 0,
    documentos_ok          int DEFAULT 0,
    documentos_divergencia int DEFAULT 0,
    divergencias_resumo    jsonb DEFAULT '{}',
    claude_analysis        text,
    created_at             timestamptz DEFAULT now()
);

CREATE TABLE IF NOT EXISTS fiscal_apurations (
    id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    period_id        uuid REFERENCES fiscal_periods(id) ON DELETE CASCADE,
    tipo_tributo     text NOT NULL,
    -- PIS | COFINS | ICMS | DIFAL | FCP | ISS | IRPJ | CSLL
    debitos          numeric(15,2) DEFAULT 0,
    creditos         numeric(15,2) DEFAULT 0,
    saldo_anterior   numeric(15,2) DEFAULT 0,
    valor_apurado    numeric(15,2),
    valor_a_pagar    numeric(15,2),
    codigo_receita   varchar(6),
    data_vencimento  date,
    status           text NOT NULL DEFAULT 'apurado',
    detalhamento     jsonb DEFAULT '{}',
    created_at       timestamptz DEFAULT now(),
    UNIQUE(period_id, tipo_tributo)
);
