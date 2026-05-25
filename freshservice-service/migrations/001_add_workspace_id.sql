-- Migration: Adicionar workspace_id à tabela freshservice_tickets
-- Execute no Supabase SQL Editor (Settings → SQL Editor)
-- Data: 2026-05-25

ALTER TABLE public.freshservice_tickets
  ADD COLUMN IF NOT EXISTS workspace_id integer;

CREATE INDEX IF NOT EXISTS idx_fst_workspace
  ON public.freshservice_tickets (workspace_id);

-- Confirma
SELECT COUNT(*) AS total_tickets,
       COUNT(workspace_id) AS com_workspace
FROM public.freshservice_tickets;
