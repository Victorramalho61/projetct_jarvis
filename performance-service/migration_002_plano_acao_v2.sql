-- Migration 002: Plano de Ação v2 — competências obrigatórias (2), campos ricos
-- do formulário oficial e ciência do colaborador.
-- Executar no Supabase SQL Editor. Aditiva — nenhuma tabela/coluna existente é removida.

-- Cabeçalho do plano: combinado de acompanhamento (só existe 1 por plano)
ALTER TABLE performance_action_plans
  ADD COLUMN IF NOT EXISTS frequencia_alinhamento text;

-- Itens: campos ricos do formulário oficial (substituem o plan_text livre)
ALTER TABLE performance_action_plan_items
  ADD COLUMN IF NOT EXISTS situacao_observada          text,
  ADD COLUMN IF NOT EXISTS meta_esperada               text,
  ADD COLUMN IF NOT EXISTS acoes                       text,
  ADD COLUMN IF NOT EXISTS responsavel_acompanhamento  text,
  ADD COLUMN IF NOT EXISTS como_sera_verificado         text;

-- Antes só indicadores com nota 1/2 podiam virar item; agora o gestor escolhe
-- livremente entre todo o catálogo, então a restrição de nota não se aplica mais.
ALTER TABLE performance_action_plan_items
  ALTER COLUMN original_score DROP NOT NULL;

ALTER TABLE performance_action_plan_items
  DROP CONSTRAINT IF EXISTS performance_action_plan_items_original_score_check;

-- Ciência do colaborador sobre o próprio plano — mesma forma de
-- performance_acknowledgment_tokens / performance_review_acknowledgments.
CREATE TABLE IF NOT EXISTS performance_action_plan_ack_tokens (
  id             uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  action_plan_id uuid NOT NULL REFERENCES performance_action_plans(id),
  employee_id    uuid NOT NULL REFERENCES performance_employees(id),
  token          uuid UNIQUE NOT NULL DEFAULT gen_random_uuid(),
  sent_at        timestamptz,
  used_at        timestamptz,
  expires_at     timestamptz,
  created_at     timestamptz DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_perf_ap_ack_tokens_token ON performance_action_plan_ack_tokens (token);

CREATE TABLE IF NOT EXISTS performance_action_plan_acknowledgments (
  id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  action_plan_id  uuid NOT NULL REFERENCES performance_action_plans(id),
  employee_id     uuid NOT NULL REFERENCES performance_employees(id),
  acknowledged_via text NOT NULL CHECK (acknowledged_via IN ('email','presencial')),
  acknowledged_at timestamptz DEFAULT now(),
  ip_address      text,
  CONSTRAINT uq_ap_ack_plan_employee UNIQUE (action_plan_id, employee_id)
);
