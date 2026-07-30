-- Migration 001: Plano de Ação - Feedback
-- Executar no Supabase SQL Editor
--
-- Aditiva: nenhuma tabela existente é removida ou tem coluna alterada/removida.
-- Confirme os nomes de coluna das FKs (performance_cycles, performance_employees,
-- performance_reviews, performance_indicators) contra o banco real antes de rodar,
-- pois schema_performance.sql está parcialmente desatualizado em relação ao runtime.

-- Data-base de início do acompanhamento trimestral, definida pelo RH por ciclo.
ALTER TABLE performance_cycles
  ADD COLUMN IF NOT EXISTS action_plan_start_date date;


-- ------------------------------------------------------------
-- Cabeçalho do plano de ação (1 por colaborador + ciclo)
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS performance_action_plans (
  id                      uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  cycle_id                uuid NOT NULL REFERENCES performance_cycles(id),
  employee_id             uuid NOT NULL REFERENCES performance_employees(id),
  review_id               uuid NOT NULL REFERENCES performance_reviews(id),
  manager_id              uuid NOT NULL REFERENCES performance_employees(id),
  status                  text NOT NULL DEFAULT 'pending_manager_fill'
                            CHECK (status IN ('pending_manager_fill','active','completed','cancelled')),
  phase_base_date         date NOT NULL,
  current_phase           int NOT NULL DEFAULT 0,
  initial_token           uuid UNIQUE NOT NULL DEFAULT gen_random_uuid(),
  initial_token_sent_at   timestamptz,
  initial_token_used_at   timestamptz,
  initial_token_invalidated_at timestamptz,
  generated_by            text NOT NULL,
  generated_at            timestamptz DEFAULT now(),
  initial_form_filled_at  timestamptz,
  created_at              timestamptz DEFAULT now(),
  updated_at              timestamptz DEFAULT now(),
  CONSTRAINT uq_action_plan_employee_cycle UNIQUE (employee_id, cycle_id)
);
CREATE INDEX IF NOT EXISTS idx_perf_ap_cycle    ON performance_action_plans (cycle_id);
CREATE INDEX IF NOT EXISTS idx_perf_ap_employee ON performance_action_plans (employee_id);
CREATE INDEX IF NOT EXISTS idx_perf_ap_manager  ON performance_action_plans (manager_id);
CREATE INDEX IF NOT EXISTS idx_perf_ap_status   ON performance_action_plans (status);
CREATE INDEX IF NOT EXISTS idx_perf_ap_token    ON performance_action_plans (initial_token);


-- ------------------------------------------------------------
-- Itens do plano — 1 por competência (indicador) com nota 1 ou 2
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS performance_action_plan_items (
  id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  action_plan_id  uuid NOT NULL REFERENCES performance_action_plans(id) ON DELETE CASCADE,
  indicator_id    uuid NOT NULL REFERENCES performance_indicators(id),
  original_score  numeric NOT NULL CHECK (original_score IN (1, 2)),
  plan_text       text,
  cumulative_pct  numeric NOT NULL DEFAULT 0 CHECK (cumulative_pct >= 0 AND cumulative_pct <= 100),
  created_at      timestamptz DEFAULT now(),
  updated_at      timestamptz DEFAULT now(),
  CONSTRAINT uq_action_plan_item UNIQUE (action_plan_id, indicator_id)
);
CREATE INDEX IF NOT EXISTS idx_perf_ap_items_plan ON performance_action_plan_items (action_plan_id);


-- ------------------------------------------------------------
-- Fases trimestrais — 4 por plano, calendário fixo por ciclo
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS performance_action_plan_phases (
  id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  action_plan_id  uuid NOT NULL REFERENCES performance_action_plans(id) ON DELETE CASCADE,
  phase_number    int NOT NULL CHECK (phase_number BETWEEN 1 AND 4),
  due_date        date NOT NULL,
  status          text NOT NULL DEFAULT 'scheduled'
                    CHECK (status IN ('scheduled','pending_rh_send','sent','completed')),
  token           uuid UNIQUE NOT NULL DEFAULT gen_random_uuid(),
  became_due_at   timestamptz,
  sent_at         timestamptz,
  completed_at    timestamptz,
  reminder_count  int NOT NULL DEFAULT 0,
  last_reminder_at timestamptz,
  invalidated_at  timestamptz,
  created_at      timestamptz DEFAULT now(),
  CONSTRAINT uq_action_plan_phase UNIQUE (action_plan_id, phase_number)
);
CREATE INDEX IF NOT EXISTS idx_perf_ap_phases_plan   ON performance_action_plan_phases (action_plan_id);
CREATE INDEX IF NOT EXISTS idx_perf_ap_phases_status ON performance_action_plan_phases (status, due_date);
CREATE INDEX IF NOT EXISTS idx_perf_ap_phases_token  ON performance_action_plan_phases (token);


-- ------------------------------------------------------------
-- Respostas de check-in — por competência, por fase
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS performance_action_plan_phase_items (
  id                          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  phase_id                    uuid NOT NULL REFERENCES performance_action_plan_phases(id) ON DELETE CASCADE,
  action_plan_item_id         uuid NOT NULL REFERENCES performance_action_plan_items(id) ON DELETE CASCADE,
  result                      text CHECK (result IN ('total','parcial','nao_atingida')),
  pct_awarded                 numeric,
  justification               text,
  phase4_override_100         boolean,
  phase4_final_justification  text,
  answered_at                 timestamptz,
  created_at                  timestamptz DEFAULT now(),
  CONSTRAINT uq_action_plan_phase_item UNIQUE (phase_id, action_plan_item_id)
);
CREATE INDEX IF NOT EXISTS idx_perf_ap_phase_items_phase ON performance_action_plan_phase_items (phase_id);
