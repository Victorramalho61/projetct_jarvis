-- SLA configurável por ciclo e fase
CREATE TABLE IF NOT EXISTS performance_sla_configs (
  id          uuid DEFAULT gen_random_uuid() PRIMARY KEY,
  cycle_id    uuid REFERENCES performance_cycles(id) ON DELETE CASCADE,
  phase       text NOT NULL CHECK (phase IN ('goal_signing','self_assessment','manager_review','acknowledgment')),
  max_days    integer NOT NULL DEFAULT 7,
  created_by  text NOT NULL,
  created_at  timestamptz DEFAULT now(),
  UNIQUE(cycle_id, phase)
);

-- Log de lembretes enviados (evita duplicatas no mesmo dia)
CREATE TABLE IF NOT EXISTS performance_sla_reminder_log (
  id          uuid DEFAULT gen_random_uuid() PRIMARY KEY,
  cycle_id    uuid,
  employee_id uuid REFERENCES performance_employees(id),
  phase       text NOT NULL,
  sent_at     timestamptz DEFAULT now(),
  sent_by     text   -- NULL = automático
);
