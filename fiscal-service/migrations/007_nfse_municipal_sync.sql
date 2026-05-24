-- Migration 007 — NFSe Municipal Sync: colunas de estado + watermark NDD
-- Execute via Supabase SQL editor ou:
-- docker exec jarvis-db-1 psql -U postgres -d postgres -f /migrations/007_nfse_municipal_sync.sql

-- fiscal_companies: watermark incremental do ND Digital
ALTER TABLE fiscal_companies
  ADD COLUMN IF NOT EXISTS ndd_last_sync_at timestamptz;

-- fiscal_nfse_municipalities: estado de sync por município
ALTER TABLE fiscal_nfse_municipalities
  ADD COLUMN IF NOT EXISTS last_sync_at  timestamptz,
  ADD COLUMN IF NOT EXISTS ultimo_erro   text,
  ADD COLUMN IF NOT EXISTS docs_total    int DEFAULT 0;
