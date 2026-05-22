-- Migration 005 — Portal Nacional NFS-e: agendamento por empresa
-- Execute via Supabase SQL editor ou psql

ALTER TABLE fiscal_companies
  ADD COLUMN IF NOT EXISTS portal_nfse_hora_sync integer DEFAULT 6;
  -- hora (0-23) em que o sync automático roda para esta empresa (horário de Brasília)
