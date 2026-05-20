-- Migration 002 — NFSe NDD Digital: colunas extras + full-text search + indexes
-- Execute via Supabase SQL editor

-- Colunas adicionais para NFSe NDD
ALTER TABLE fiscal_documents
  ADD COLUMN IF NOT EXISTS valor_iss        numeric(15,2),
  ADD COLUMN IF NOT EXISTS valor_iss_retido numeric(15,2),
  ADD COLUMN IF NOT EXISTS municipio_nome   text,
  ADD COLUMN IF NOT EXISTS ndd_id           bigint,
  ADD COLUMN IF NOT EXISTS ndd_sync_at      timestamptz;

-- Watermark de sync incremental por empresa
ALTER TABLE fiscal_companies
  ADD COLUMN IF NOT EXISTS ndd_last_sync_at timestamptz;

-- Full-text search em português (trigger atualiza search_vector automaticamente)
ALTER TABLE fiscal_documents
  ADD COLUMN IF NOT EXISTS search_vector tsvector;

CREATE OR REPLACE FUNCTION fiscal_documents_search_vector_update()
RETURNS TRIGGER AS $$
BEGIN
  NEW.search_vector :=
    setweight(to_tsvector('portuguese', coalesce(NEW.emitente_nome,       '')), 'A') ||
    setweight(to_tsvector('portuguese', coalesce(NEW.destinatario_nome,   '')), 'A') ||
    setweight(to_tsvector('portuguese', coalesce(NEW.natureza_operacao,   '')), 'B') ||
    setweight(to_tsvector('portuguese', coalesce(NEW.municipio_nome,      '')), 'C') ||
    setweight(to_tsvector('portuguese', coalesce(NEW.numero,              '')), 'D') ||
    setweight(to_tsvector('portuguese', coalesce(NEW.chave_acesso,        '')), 'D');
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS tsvector_update_fiscal_documents ON fiscal_documents;
CREATE TRIGGER tsvector_update_fiscal_documents
  BEFORE INSERT OR UPDATE ON fiscal_documents
  FOR EACH ROW EXECUTE FUNCTION fiscal_documents_search_vector_update();

-- Atualiza search_vector nos registros existentes
UPDATE fiscal_documents SET status = status WHERE search_vector IS NULL;

-- Índice GIN para full-text search
CREATE INDEX IF NOT EXISTS idx_fiscal_docs_search    ON fiscal_documents USING GIN(search_vector);

-- Índices B-tree para filtros simples
CREATE INDEX IF NOT EXISTS idx_fiscal_docs_tipo       ON fiscal_documents(tipo);
CREATE INDEX IF NOT EXISTS idx_fiscal_docs_status     ON fiscal_documents(status);
CREATE INDEX IF NOT EXISTS idx_fiscal_docs_valor      ON fiscal_documents(valor_total);
CREATE INDEX IF NOT EXISTS idx_fiscal_docs_municipio  ON fiscal_documents(municipio_nome);
CREATE INDEX IF NOT EXISTS idx_fiscal_docs_emit_cnpj  ON fiscal_documents(emitente_cnpj);
CREATE INDEX IF NOT EXISTS idx_fiscal_docs_dest_cnpj  ON fiscal_documents(destinatario_cnpj);
CREATE INDEX IF NOT EXISTS idx_fiscal_docs_ndd_id     ON fiscal_documents(ndd_id);

-- pg_trgm para busca parcial (CNPJ parcial, chave incompleta)
CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE INDEX IF NOT EXISTS idx_fiscal_docs_chave_trgm ON fiscal_documents USING GIN(chave_acesso gin_trgm_ops);
CREATE INDEX IF NOT EXISTS idx_fiscal_docs_emit_trgm  ON fiscal_documents USING GIN(emitente_cnpj gin_trgm_ops);
CREATE INDEX IF NOT EXISTS idx_fiscal_docs_dest_trgm  ON fiscal_documents USING GIN(destinatario_cnpj gin_trgm_ops);

-- RPC para full-text com ranking (usado pelo endpoint GET /api/fiscal/nfse?q=...)
CREATE OR REPLACE FUNCTION fiscal_nfse_search(
    p_query      text,
    p_company_id uuid    DEFAULT NULL,
    p_limit      int     DEFAULT 50,
    p_offset     int     DEFAULT 0
)
RETURNS SETOF fiscal_documents AS $$
BEGIN
  RETURN QUERY
  SELECT *
  FROM fiscal_documents
  WHERE tipo = 'NFSe'
    AND search_vector @@ websearch_to_tsquery('portuguese', p_query)
    AND (p_company_id IS NULL OR company_id = p_company_id)
  ORDER BY ts_rank(search_vector, websearch_to_tsquery('portuguese', p_query)) DESC
  LIMIT p_limit OFFSET p_offset;
END;
$$ LANGUAGE plpgsql STABLE;
