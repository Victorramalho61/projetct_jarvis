-- Migration 004 — Portal Nacional NFS-e + SEFAZ guards + compliance
-- Execute via Supabase SQL editor

-- fiscal_companies: controles Portal Nacional NFS-e e SEFAZ
ALTER TABLE fiscal_companies
  ADD COLUMN IF NOT EXISTS ultimo_nsu_nfse_nacional     bigint      DEFAULT 0,
  ADD COLUMN IF NOT EXISTS sync_portal_nfse_ativo       boolean     DEFAULT false,
  ADD COLUMN IF NOT EXISTS portal_nfse_last_sync_at     timestamptz,
  ADD COLUMN IF NOT EXISTS sefaz_usar_svc_an            boolean     DEFAULT false,
  ADD COLUMN IF NOT EXISTS sefaz_nfe_bloqueado_ate      timestamptz,
  ADD COLUMN IF NOT EXISTS sefaz_nfe_ultima_consulta_hb timestamptz;

-- fiscal_documents: rastreabilidade e compliance fiscal
ALTER TABLE fiscal_documents
  ADD COLUMN IF NOT EXISTS fonte        text,       -- 'ndd' | 'portal_nacional' | 'sefaz'
  ADD COLUMN IF NOT EXISTS nsu_nacional bigint,     -- NSU do ADN (Portal Nacional NFS-e)
  ADD COLUMN IF NOT EXISTS tipo_schema  text,       -- 'resumo' | 'completo' (resNFe/resNFse = resumo)
  ADD COLUMN IF NOT EXISTS xml_hash     char(64);   -- SHA-256 do xml_content (compliance 5-6 anos)

CREATE INDEX IF NOT EXISTS idx_fiscal_docs_nsu_nacional
  ON fiscal_documents(nsu_nacional)
  WHERE nsu_nacional IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_fiscal_docs_fonte
  ON fiscal_documents(fonte);

CREATE INDEX IF NOT EXISTS idx_fiscal_docs_tipo_schema
  ON fiscal_documents(tipo_schema)
  WHERE tipo_schema IS NOT NULL;

-- Backfill hash nos XMLs já existentes (execução única, pode demorar)
-- UPDATE fiscal_documents
--   SET xml_hash = encode(digest(xml_content::bytea, 'sha256'), 'hex')
-- WHERE xml_content IS NOT NULL AND xml_hash IS NULL;
-- (Descomente se quiser backfill imediato — requer extensão pgcrypto)
