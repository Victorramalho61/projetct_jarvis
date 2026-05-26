-- ============================================================
-- Jarvis — Correção de colunas ausentes
-- Gerado em 2026-05-25 para corrigir erros 42703 nos logs
-- Executar: docker exec -i jarvis-db-1 psql -U postgres jarvis < fix_missing_columns.sql
-- ============================================================

-- 1. monitored_systems.consecutive_down_count
--    Usado por: monitoring-service/services/monitor.py e core-service/routes/notifications.py
ALTER TABLE public.monitored_systems
  ADD COLUMN IF NOT EXISTS consecutive_down_count integer NOT NULL DEFAULT 0;

-- 2. improvement_proposals.validation_status
--    Usado por: core-service/routes/notifications.py e agents-service (desabilitado)
--    A migration 002_improvement_proposals.sql nunca foi aplicada
ALTER TABLE public.improvement_proposals
  ADD COLUMN IF NOT EXISTS validation_status varchar(20) NOT NULL DEFAULT 'pending';

CREATE INDEX IF NOT EXISTS idx_improvement_proposals_status
  ON improvement_proposals(validation_status, created_at DESC);

-- 3. performance_cycle_reopens.created_at
--    Usado por: performance-service/routes/admin.py (order + leitura por created_at)
--    O schema só tem reopened_at; adicionamos created_at como alias definitivo
ALTER TABLE performance_cycle_reopens
  ADD COLUMN IF NOT EXISTS created_at timestamptz DEFAULT now();

-- Para registros existentes que só têm reopened_at, popula created_at
UPDATE performance_cycle_reopens
  SET created_at = reopened_at
  WHERE created_at IS NULL AND reopened_at IS NOT NULL;

-- 4. notification_prefs.teams_chat_id e teams_mode
--    Usado por: moneypenny-service/routes/moneypenny.py e services/summary.py
ALTER TABLE public.notification_prefs
  ADD COLUMN IF NOT EXISTS teams_chat_id text NOT NULL DEFAULT '';

ALTER TABLE public.notification_prefs
  ADD COLUMN IF NOT EXISTS teams_mode text NOT NULL DEFAULT 'webhook';
