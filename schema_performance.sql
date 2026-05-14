-- =============================================================================
-- performance-service schema
-- Aplicar no Supabase antes do primeiro deploy do performance-service
-- =============================================================================

-- ── Audit log global ─────────────────────────────────────────────────────────
create table if not exists performance_audit_logs (
  id          uuid primary key default gen_random_uuid(),
  entity_type text not null,
  entity_id   uuid not null,
  action      text not null,
  old_data    jsonb,
  new_data    jsonb,
  actor       text not null,
  ip_address  text,
  user_agent  text,
  ts          timestamptz default now()
);
create index if not exists idx_audit_entity   on performance_audit_logs (entity_type, entity_id);
create index if not exists idx_audit_actor    on performance_audit_logs (actor);
create index if not exists idx_audit_ts       on performance_audit_logs (ts);

-- ── Versionamento de avaliações ───────────────────────────────────────────────
create table if not exists performance_review_versions (
  id          uuid primary key default gen_random_uuid(),
  review_id   uuid not null,
  version     int  not null,
  snapshot    jsonb not null,
  changed_by  text not null,
  changed_at  timestamptz default now()
);
create index if not exists idx_review_versions on performance_review_versions (review_id, version);

-- ── Permissões do módulo ─────────────────────────────────────────────────────
create table if not exists performance_permissions (
  code        text primary key,
  description text not null
);

create table if not exists performance_role_permissions (
  role            text not null,
  permission_code text not null references performance_permissions(code),
  primary key (role, permission_code)
);

insert into performance_permissions values
  ('create_goal',          'Criar e propor metas'),
  ('acknowledge_goal',     'Assinar objetivos recebidos'),
  ('fill_self_review',     'Preencher autoavaliação'),
  ('fill_manager_review',  'Preencher avaliação de liderado'),
  ('sign_review',          'Assinar resultado de avaliação (gestor)'),
  ('acknowledge_review',   'Tomar ciência do resultado (colaborador)'),
  ('close_cycle',          'Fechar ciclo de avaliação'),
  ('calibrate',            'Calibrar notas (RH)'),
  ('view_financial_score', 'Visualizar score financeiro de outras áreas'),
  ('manage_kpis',          'Gerenciar KPIs e snapshots'),
  ('manage_pdi',           'Criar e acompanhar PDI')
on conflict (code) do nothing;

insert into performance_role_permissions values
  ('colaborador', 'acknowledge_goal'),
  ('colaborador', 'fill_self_review'),
  ('colaborador', 'acknowledge_review'),
  ('supervisor',  'create_goal'),
  ('supervisor',  'fill_manager_review'),
  ('supervisor',  'sign_review'),
  ('coordenador', 'create_goal'),
  ('coordenador', 'fill_manager_review'),
  ('coordenador', 'sign_review'),
  ('coordenador', 'manage_pdi'),
  ('gestor',      'create_goal'),
  ('gestor',      'fill_manager_review'),
  ('gestor',      'sign_review'),
  ('gestor',      'manage_pdi'),
  ('gestor',      'manage_kpis'),
  ('rh',          'create_goal'),
  ('rh',          'fill_manager_review'),
  ('rh',          'sign_review'),
  ('rh',          'close_cycle'),
  ('rh',          'calibrate'),
  ('rh',          'view_financial_score'),
  ('rh',          'manage_kpis'),
  ('rh',          'manage_pdi')
on conflict (role, permission_code) do nothing;

-- ── Hierarquia organizacional ─────────────────────────────────────────────────
create table if not exists performance_departments (
  id          uuid primary key default gen_random_uuid(),
  name        text not null,
  parent_id   uuid references performance_departments(id),
  director    text,
  cost_center text unique,
  company_id  text,
  synced_at   timestamptz default now()
);

create table if not exists performance_employees (
  id            uuid primary key default gen_random_uuid(),
  benner_id     text unique not null,
  name          text not null,
  email         text,
  role          text,
  department_id uuid references performance_departments(id),
  manager_id    uuid references performance_employees(id),
  active        boolean default true,
  synced_at     timestamptz default now()
);
create index if not exists idx_employees_email on performance_employees (email);
create index if not exists idx_employees_dept  on performance_employees (department_id);

-- ── Metas ─────────────────────────────────────────────────────────────────────
-- status: draft → pending_ack → active → in_review → completed | expired | cancelled
create table if not exists performance_goals (
  id             uuid primary key default gen_random_uuid(),
  title          text not null,
  type           text not null,
  description    text,
  kpi_name       text,
  formula        text,
  target_value   numeric,
  current_value  numeric default 0,
  unit           text,
  weight         numeric default 1.0,
  period_start   date not null,
  period_end     date not null,
  owner_id       uuid references performance_employees(id),
  department_id  uuid references performance_departments(id),
  status         text default 'draft',
  parent_goal_id uuid references performance_goals(id),
  created_by     text,
  created_at     timestamptz default now(),
  updated_at     timestamptz default now()
);
create index if not exists idx_goals_owner  on performance_goals (owner_id);
create index if not exists idx_goals_status on performance_goals (status);

-- Momento 1: assinatura de objetivos
create table if not exists performance_goal_acknowledgments (
  id              uuid primary key default gen_random_uuid(),
  goal_id         uuid not null references performance_goals(id),
  employee_id     uuid not null references performance_employees(id),
  acknowledged_at timestamptz default now(),
  ip_address      text,
  signature_text  text,
  unique (goal_id, employee_id)
);

create table if not exists performance_goal_templates (
  id                uuid primary key default gen_random_uuid(),
  title             text not null,
  type              text not null,
  department_type   text,
  kpi_name          text,
  formula           text,
  default_target    numeric,
  unit              text,
  weight_suggestion numeric,
  description       text
);

-- ── Competências ──────────────────────────────────────────────────────────────
create table if not exists performance_competencies (
  id           uuid primary key default gen_random_uuid(),
  name         text not null,
  description  text,
  category     text not null,
  is_mandatory boolean default false,
  created_at   timestamptz default now()
);

insert into performance_competencies (name, category, is_mandatory) values
  ('Atendimento ao Cliente',      'corporativa', true),
  ('Qualidade e Precisão',        'corporativa', true),
  ('Compliance e Ética',          'corporativa', true),
  ('Comunicação',                 'corporativa', true),
  ('Agilidade',                   'corporativa', true),
  ('Relacionamento Interpessoal', 'corporativa', true),
  ('Gestão de Pessoas',           'lideranca', false),
  ('Tomada de Decisão',           'lideranca', false),
  ('Planejamento',                'lideranca', false),
  ('Desenvolvimento de Equipe',   'lideranca', false)
on conflict do nothing;

-- ── Ciclos e Avaliações ───────────────────────────────────────────────────────
-- status ciclo: draft|open|evaluation|calibration|closed
create table if not exists performance_cycles (
  id           uuid primary key default gen_random_uuid(),
  name         text not null,
  period_start date not null,
  period_end   date not null,
  status       text default 'draft',
  created_by   text,
  created_at   timestamptz default now()
);

-- status review: pending_self|pending_manager|pending_second_manager|pending_hr|
--               pending_ack|completed|disputed|archived
create table if not exists performance_reviews (
  id                 uuid primary key default gen_random_uuid(),
  cycle_id           uuid not null references performance_cycles(id),
  employee_id        uuid not null references performance_employees(id),
  reviewer_id        uuid references performance_employees(id),
  step               text not null default 'self',
  status             text not null default 'pending_self',
  goals_score        numeric,
  competencies_score numeric,
  behavior_score     numeric,
  compliance_score   numeric,
  raw_score          numeric,
  normalized_score   numeric,
  final_score        numeric,
  blocked_by         text,
  comments           text,
  manager_signed_at  timestamptz,
  manager_signature  text,
  submitted_at       timestamptz,
  created_at         timestamptz default now(),
  updated_at         timestamptz default now()
);
create index if not exists idx_reviews_cycle    on performance_reviews (cycle_id);
create index if not exists idx_reviews_employee on performance_reviews (employee_id);
create index if not exists idx_reviews_status   on performance_reviews (status);

create table if not exists performance_competency_scores (
  review_id     uuid not null references performance_reviews(id),
  competency_id uuid not null references performance_competencies(id),
  score         numeric not null,
  justification text,
  primary key (review_id, competency_id)
);

-- Momento 2: ciência ou contestação do colaborador
create table if not exists performance_review_acknowledgments (
  id              uuid primary key default gen_random_uuid(),
  review_id       uuid not null references performance_reviews(id),
  employee_id     uuid not null references performance_employees(id),
  action          text not null,
  acknowledged_at timestamptz default now(),
  comments        text,
  unique (review_id, employee_id)
);

-- ── Calibração ────────────────────────────────────────────────────────────────
create table if not exists performance_calibrations (
  id               uuid primary key default gen_random_uuid(),
  cycle_id         uuid references performance_cycles(id),
  review_id        uuid not null references performance_reviews(id),
  original_score   numeric not null,
  calibrated_score numeric not null,
  justification    text not null,
  calibrated_by    text not null,
  calibrated_at    timestamptz default now()
);

-- ── Evidências ────────────────────────────────────────────────────────────────
create table if not exists performance_evidences (
  id          uuid primary key default gen_random_uuid(),
  goal_id     uuid references performance_goals(id),
  employee_id uuid not null references performance_employees(id),
  type        text not null,
  source      text,
  value       numeric,
  unit        text,
  description text,
  evidence_date date not null,
  created_by  text,
  created_at  timestamptz default now()
);
create index if not exists idx_evidences_goal     on performance_evidences (goal_id);
create index if not exists idx_evidences_employee on performance_evidences (employee_id);

-- ── KPIs ──────────────────────────────────────────────────────────────────────
create table if not exists performance_kpis (
  id              uuid primary key default gen_random_uuid(),
  name            text not null,
  department_type text,
  formula         text,
  source          text,
  unit            text,
  created_at      timestamptz default now()
);

create table if not exists performance_kpi_snapshots (
  id          uuid primary key default gen_random_uuid(),
  kpi_id      uuid not null references performance_kpis(id),
  employee_id uuid references performance_employees(id),
  value       numeric not null,
  period      text not null,
  captured_at timestamptz default now()
);
create index if not exists idx_kpi_snapshots on performance_kpi_snapshots (kpi_id, period);

-- ── PDI (estrutura pronta, funcional na Fase 2) ───────────────────────────────
create table if not exists performance_pdis (
  id          uuid primary key default gen_random_uuid(),
  review_id   uuid references performance_reviews(id),
  employee_id uuid not null references performance_employees(id),
  status      text default 'draft',
  created_by  text,
  created_at  timestamptz default now(),
  updated_at  timestamptz default now()
);

create table if not exists performance_pdi_actions (
  id          uuid primary key default gen_random_uuid(),
  pdi_id      uuid not null references performance_pdis(id),
  action      text not null,
  deadline    date,
  responsible text,
  status      text default 'pending',
  created_at  timestamptz default now()
);
