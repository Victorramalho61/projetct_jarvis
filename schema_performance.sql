-- schema_performance.sql v2 — Refatoração AVD 2026-05-23

-- ============================================================
-- PARTE 1: REMOÇÃO DE TABELAS ANTIGAS (permite re-execução)
-- ============================================================

DROP TABLE IF EXISTS performance_pdi_actions CASCADE;
DROP TABLE IF EXISTS performance_pdis CASCADE;
DROP TABLE IF EXISTS performance_kpi_snapshots CASCADE;
DROP TABLE IF EXISTS performance_kpis CASCADE;
DROP TABLE IF EXISTS performance_evidences CASCADE;
DROP TABLE IF EXISTS performance_competency_scores CASCADE;
DROP TABLE IF EXISTS performance_competencies CASCADE;
DROP TABLE IF EXISTS performance_goal_templates CASCADE;
DROP TABLE IF EXISTS performance_goal_acknowledgments CASCADE;
DROP TABLE IF EXISTS performance_goals CASCADE;
DROP TABLE IF EXISTS performance_role_permissions CASCADE;
DROP TABLE IF EXISTS performance_permissions CASCADE;
DROP TABLE IF EXISTS performance_sla_reminder_log CASCADE;
DROP TABLE IF EXISTS performance_sla_configs CASCADE;
DROP TABLE IF EXISTS performance_calibrations CASCADE;
DROP TABLE IF EXISTS performance_review_acknowledgments CASCADE;
DROP TABLE IF EXISTS performance_review_versions CASCADE;
DROP TABLE IF EXISTS performance_reviews CASCADE;
DROP TABLE IF EXISTS performance_cycles CASCADE;
DROP TABLE IF EXISTS performance_employees CASCADE;
DROP TABLE IF EXISTS performance_departments CASCADE;
DROP TABLE IF EXISTS performance_audit_logs CASCADE;
-- novas tabelas também (para permitir re-execução)
DROP TABLE IF EXISTS performance_ciencia_attempts CASCADE;
DROP TABLE IF EXISTS performance_acknowledgment_tokens CASCADE;
DROP TABLE IF EXISTS performance_evaluation_tokens CASCADE;
DROP TABLE IF EXISTS performance_indicator_scores CASCADE;
DROP TABLE IF EXISTS performance_indicators CASCADE;
DROP TABLE IF EXISTS performance_cycle_reopens CASCADE;
DROP TABLE IF EXISTS performance_managements CASCADE;
DROP TABLE IF EXISTS performance_branches CASCADE;
DROP TABLE IF EXISTS performance_companies CASCADE;


-- ============================================================
-- PARTE 2: CRIAÇÃO DAS NOVAS TABELAS
-- ============================================================

-- ------------------------------------------------------------
-- Audit log
-- ------------------------------------------------------------
CREATE TABLE performance_audit_logs (
  id          uuid primary key default gen_random_uuid(),
  entity_type text not null,
  entity_id   text not null,
  action      text not null,
  old_data    jsonb,
  new_data    jsonb,
  actor       text not null,
  ip_address  text,
  user_agent  text,
  ts          timestamptz default now()
);
CREATE INDEX idx_perf_audit_entity ON performance_audit_logs (entity_type, entity_id);
CREATE INDEX idx_perf_audit_actor  ON performance_audit_logs (actor);
CREATE INDEX idx_perf_audit_ts     ON performance_audit_logs (ts);


-- ------------------------------------------------------------
-- Review versions
-- ------------------------------------------------------------
CREATE TABLE performance_review_versions (
  id         uuid primary key default gen_random_uuid(),
  review_id  uuid not null,
  version    int  not null,
  snapshot   jsonb not null,
  changed_by text not null,
  changed_at timestamptz default now()
);
CREATE INDEX idx_perf_review_vers ON performance_review_versions (review_id, version);


-- ------------------------------------------------------------
-- Empresas (seed fixo)
-- ------------------------------------------------------------
CREATE TABLE performance_companies (
  id     uuid primary key default gen_random_uuid(),
  name   text not null,
  code   text not null unique,
  active boolean default true
);

INSERT INTO performance_companies (name, code) VALUES
  ('VTC Operadora Logística', 'VTCLOG'),
  ('Voetur Viagens',          'VOETUR');


-- ------------------------------------------------------------
-- Filiais (seed fixo)
-- ------------------------------------------------------------
CREATE TABLE performance_branches (
  id         uuid primary key default gen_random_uuid(),
  company_id uuid not null references performance_companies(id),
  name       text not null,
  active     boolean default true
);

-- VTCLOG branches
INSERT INTO performance_branches (company_id, name)
SELECT id, unnest(ARRAY[
  'Brasil 21',
  'Guarulhos',
  'Contagem',
  'BSB Log',
  'Recife',
  'Galeão - Rio de Janeiro'
])
FROM performance_companies WHERE code = 'VTCLOG';

-- Voetur branches
INSERT INTO performance_branches (company_id, name)
SELECT id, unnest(ARRAY[
  'Brasília Shopping',
  'Liberty Mall',
  'Rio de Janeiro',
  'São Paulo'
])
FROM performance_companies WHERE code = 'VOETUR';


-- ------------------------------------------------------------
-- Gerências (cadastradas pelo RH)
-- ------------------------------------------------------------
CREATE TABLE performance_managements (
  id         uuid primary key default gen_random_uuid(),
  branch_id  uuid not null references performance_branches(id),
  name       text not null,
  active     boolean default true,
  created_at timestamptz default now()
);


-- ------------------------------------------------------------
-- Colaboradores (novo, sem Benner)
-- ------------------------------------------------------------
CREATE TABLE performance_employees (
  id                  uuid primary key default gen_random_uuid(),
  name                text not null,
  matricula           text not null,
  email               text,
  cargo               text,
  has_corporate_email boolean not null default true,
  whatsapp_phone      text default '',
  perfil              text default 'administrativo_operacional',
  hierarchy_level     int not null check (hierarchy_level in (1, 2, 3)),
  manager_id          uuid references performance_employees(id),
  management_id       uuid references performance_managements(id),
  branch_id           uuid not null references performance_branches(id),
  company_id          uuid not null references performance_companies(id),
  jarvis_username     text,
  jarvis_role         text,
  active              boolean default true,
  created_at          timestamptz default now(),
  updated_at          timestamptz default now(),
  CONSTRAINT uq_matricula_company UNIQUE (matricula, company_id)
);
CREATE INDEX idx_perf_emp_branch    ON performance_employees (branch_id);
CREATE INDEX idx_perf_emp_company   ON performance_employees (company_id);
CREATE INDEX idx_perf_emp_manager   ON performance_employees (manager_id);
CREATE INDEX idx_perf_emp_matricula ON performance_employees (matricula);


-- ------------------------------------------------------------
-- Indicadores de avaliação
-- ------------------------------------------------------------
CREATE TABLE performance_indicators (
  id          uuid primary key default gen_random_uuid(),
  name        text not null,
  description text,
  active      boolean default true,
  created_by  text,
  created_at  timestamptz default now(),
  updated_at  timestamptz default now()
);


-- ------------------------------------------------------------
-- Ciclos (simplificado)
-- ------------------------------------------------------------
CREATE TABLE performance_cycles (
  id           uuid primary key default gen_random_uuid(),
  name         text not null,
  period_start date not null,
  period_end   date not null,
  status       text not null default 'draft' check (status in ('draft','open','closed')),
  company_id   uuid references performance_companies(id),  -- null = todas as empresas
  created_by   text,
  created_at   timestamptz default now(),
  updated_at   timestamptz default now()
);
CREATE INDEX idx_perf_cycles_status ON performance_cycles (status);


-- ------------------------------------------------------------
-- Histórico de reaberturas
-- ------------------------------------------------------------
CREATE TABLE performance_cycle_reopens (
  id            uuid primary key default gen_random_uuid(),
  cycle_id      uuid not null references performance_cycles(id),
  reopened_by   text not null,
  justification text not null,
  company_id    uuid references performance_companies(id),  -- null = todas
  period_start  date,
  period_end    date,
  reopened_at   timestamptz default now()
);


-- ------------------------------------------------------------
-- Avaliações (simplificadas)
-- ------------------------------------------------------------
CREATE TABLE performance_reviews (
  id           uuid primary key default gen_random_uuid(),
  cycle_id     uuid not null references performance_cycles(id),
  employee_id  uuid not null references performance_employees(id),
  evaluator_id uuid references performance_employees(id),
  status       text not null default 'pending' check (status in ('pending','completed')),
  final_score  numeric,
  comments     text,
  submitted_at timestamptz,
  created_at   timestamptz default now(),
  updated_at   timestamptz default now(),
  CONSTRAINT uq_review_cycle_employee UNIQUE (cycle_id, employee_id)
);
CREATE INDEX idx_perf_reviews_cycle    ON performance_reviews (cycle_id);
CREATE INDEX idx_perf_reviews_employee ON performance_reviews (employee_id);
CREATE INDEX idx_perf_reviews_status   ON performance_reviews (status);


-- ------------------------------------------------------------
-- Notas por indicador (chave primária composta)
-- ------------------------------------------------------------
CREATE TABLE performance_indicator_scores (
  review_id    uuid not null references performance_reviews(id) ON DELETE CASCADE,
  indicator_id uuid not null references performance_indicators(id),
  score        numeric not null check (score >= 1 and score <= 5),
  PRIMARY KEY (review_id, indicator_id)
);


-- ------------------------------------------------------------
-- Calibrações
-- ------------------------------------------------------------
CREATE TABLE performance_calibrations (
  id               uuid primary key default gen_random_uuid(),
  cycle_id         uuid references performance_cycles(id),
  review_id        uuid not null references performance_reviews(id),
  original_score   numeric not null,
  calibrated_score numeric not null,
  justification    text not null,
  calibrated_by    text not null,
  calibrated_at    timestamptz default now()
);


-- ------------------------------------------------------------
-- Tokens de avaliação (para avaliadores L1/L2)
-- ------------------------------------------------------------
CREATE TABLE performance_evaluation_tokens (
  id             uuid primary key default gen_random_uuid(),
  evaluator_id   uuid not null references performance_employees(id),
  cycle_id       uuid not null references performance_cycles(id),
  company_id     uuid references performance_companies(id),
  token          uuid unique not null default gen_random_uuid(),
  sent_at        timestamptz,
  sent_to_email  text,
  is_used        boolean default false,
  used_at        timestamptz,
  resend_count   int default 0,
  invalidated_at timestamptz,
  created_at     timestamptz default now()
);
CREATE INDEX idx_perf_eval_tokens_token ON performance_evaluation_tokens (token);
CREATE INDEX idx_perf_eval_tokens_eval  ON performance_evaluation_tokens (evaluator_id, cycle_id);


-- ------------------------------------------------------------
-- Tokens de ciência (para colaboradores L3 com e-mail)
-- ------------------------------------------------------------
CREATE TABLE performance_acknowledgment_tokens (
  id          uuid primary key default gen_random_uuid(),
  review_id   uuid not null references performance_reviews(id),
  employee_id uuid not null references performance_employees(id),
  token       uuid unique not null default gen_random_uuid(),
  sent_at     timestamptz,
  used_at     timestamptz,
  expires_at  timestamptz,  -- now() + interval '30 days' ao criar
  created_at  timestamptz default now()
);
CREATE INDEX idx_perf_ack_tokens_token ON performance_acknowledgment_tokens (token);


-- ------------------------------------------------------------
-- Ciência registrada
-- ------------------------------------------------------------
CREATE TABLE performance_review_acknowledgments (
  id                uuid primary key default gen_random_uuid(),
  review_id         uuid not null references performance_reviews(id),
  employee_id       uuid not null references performance_employees(id),
  feedback_received boolean not null,
  acknowledged_via  text not null check (acknowledged_via in ('email','presencial')),
  acknowledged_at   timestamptz default now(),
  ip_address        text,
  CONSTRAINT uq_ack_review_employee UNIQUE (review_id, employee_id)
);


-- ------------------------------------------------------------
-- Anti-brute-force para ciência presencial
-- ------------------------------------------------------------
CREATE TABLE performance_ciencia_attempts (
  id           uuid primary key default gen_random_uuid(),
  matricula    text not null,
  ip_address   text,
  attempted_at timestamptz default now()
);
CREATE INDEX idx_perf_ciencia_attempts ON performance_ciencia_attempts (ip_address, attempted_at);
