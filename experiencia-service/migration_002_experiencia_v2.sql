-- Migration 002: Avaliação de Experiência v2 (2026-09-24)
-- Gestor pela estrutura de supervisão do Benner, chave benner_handle, nota/alertas, envio automático.

-- ── Colaborador ──────────────────────────────────────────────────────────────
-- A matrícula se repete entre empresas no Benner (ex.: 55 = 4 pessoas) — a chave passa a ser
-- DO_FUNCIONARIOS.HANDLE. matricula vira índice comum.
ALTER TABLE exp_employees ADD COLUMN IF NOT EXISTS benner_handle int;
DO $$ BEGIN
  ALTER TABLE exp_employees ADD CONSTRAINT exp_employees_benner_handle_key UNIQUE (benner_handle);  -- NULLs permitidos
EXCEPTION WHEN duplicate_object OR duplicate_table THEN NULL; END $$;
ALTER TABLE exp_employees DROP CONSTRAINT IF EXISTS exp_employees_matricula_key;
CREATE INDEX IF NOT EXISTS idx_exp_emp_matricula ON exp_employees(matricula);

ALTER TABLE exp_employees ADD COLUMN IF NOT EXISTS gestor_direto_nome text;   -- chefe direto na estrutura
ALTER TABLE exp_employees ADD COLUMN IF NOT EXISTS gestor_email_origem text;  -- direto | superior | manual | fallback_supervisor
ALTER TABLE exp_employees ADD COLUMN IF NOT EXISTS gestor_manual boolean NOT NULL DEFAULT false;  -- RH corrigiu: sync não sobrescreve
ALTER TABLE exp_employees ADD COLUMN IF NOT EXISTS estrutura text;            -- SUP_SUPERVISORES.ESTRUTURA do colaborador
ALTER TABLE exp_employees ADD COLUMN IF NOT EXISTS empresa_handle int;

-- ── Avaliação: nota e controle de envio automático ───────────────────────────
ALTER TABLE exp_avaliacoes ADD COLUMN IF NOT EXISTS nota_total int;
ALTER TABLE exp_avaliacoes ADD COLUMN IF NOT EXISTS nota_percentual numeric(5,2);
ALTER TABLE exp_avaliacoes ADD COLUMN IF NOT EXISTS nota_insuficiente boolean;
ALTER TABLE exp_avaliacoes ADD COLUMN IF NOT EXISTS alerta_rh_enviado_at timestamptz;
ALTER TABLE exp_avaliacoes ADD COLUMN IF NOT EXISTS envio_automatico_at timestamptz;

ALTER TABLE exp_email_log DROP CONSTRAINT IF EXISTS exp_email_log_tipo_email_check;
ALTER TABLE exp_email_log ADD CONSTRAINT exp_email_log_tipo_email_check CHECK (tipo_email IN (
  'primeiro_envio', 'cobranca', 'confirmacao_rh', 'envio_automatico', 'alerta_nota_insuficiente'
));

CREATE INDEX IF NOT EXISTS idx_exp_av_nota_insuf ON exp_avaliacoes(nota_insuficiente) WHERE nota_insuficiente;

NOTIFY pgrst, 'reload schema';
