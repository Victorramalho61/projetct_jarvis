-- ============================================================
-- Jarvis LangGraph — Schema de Orquestração de Agentes
-- Aplicar: docker exec -i jarvis-db-1 bash -c "PGPASSWORD='...' psql -U postgres -d postgres" < schema_langgraph.sql
-- ============================================================

-- ── LangGraph: threads de execução ────────────────────────────────────────
CREATE TABLE IF NOT EXISTS langgraph_threads (
  id           UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
  agent_id     UUID        REFERENCES agents(id) ON DELETE CASCADE,
  thread_id    TEXT        NOT NULL UNIQUE,
  status       TEXT        NOT NULL DEFAULT 'running'
                           CHECK (status IN ('running','completed','error','paused')),
  created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_lg_threads_agent ON langgraph_threads (agent_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_lg_threads_status ON langgraph_threads (status);

-- ── LangGraph: checkpoints de estado ──────────────────────────────────────
CREATE TABLE IF NOT EXISTS langgraph_checkpoints (
  id            BIGSERIAL   PRIMARY KEY,
  thread_id     TEXT        NOT NULL,
  checkpoint_id TEXT        NOT NULL,
  parent_id     TEXT,
  state         JSONB       NOT NULL,
  metadata      JSONB       NOT NULL DEFAULT '{}',
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (thread_id, checkpoint_id)
);
CREATE INDEX IF NOT EXISTS idx_lg_ckpt_thread ON langgraph_checkpoints (thread_id, created_at DESC);

-- ── Mensagens inter-agente ─────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS agent_messages (
  id          BIGSERIAL   PRIMARY KEY,
  thread_id   TEXT,
  from_agent  TEXT        NOT NULL,
  to_agent    TEXT        NOT NULL,
  content     JSONB       NOT NULL,
  status      TEXT        NOT NULL DEFAULT 'pending'
                          CHECK (status IN ('pending','delivered','processed')),
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_agent_msg_to ON agent_messages (to_agent, status, created_at DESC);

-- ── Alertas de Segurança ───────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS security_alerts (
  id                BIGSERIAL   PRIMARY KEY,
  severity          TEXT        NOT NULL CHECK (severity IN ('low','medium','high','critical')),
  category          TEXT        NOT NULL,
  description       TEXT        NOT NULL,
  affected_resource TEXT,
  status            TEXT        NOT NULL DEFAULT 'open'
                                CHECK (status IN ('open','investigating','resolved','false_positive')),
  resolved_at       TIMESTAMPTZ,
  created_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_sec_alerts_status ON security_alerts (status, severity, created_at DESC);

-- ── Métricas de Qualidade ──────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS quality_metrics (
  id            BIGSERIAL   PRIMARY KEY,
  metric_name   TEXT        NOT NULL,
  metric_value  NUMERIC     NOT NULL,
  unit          TEXT,
  service       TEXT,
  measured_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
  metadata      JSONB       NOT NULL DEFAULT '{}'
);
CREATE INDEX IF NOT EXISTS idx_qm_measured ON quality_metrics (metric_name, measured_at DESC);
CREATE INDEX IF NOT EXISTS idx_qm_service ON quality_metrics (service, measured_at DESC);

-- ── ITIL: Change Requests (RFC) ────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS change_requests (
  id               UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
  title            TEXT        NOT NULL,
  description      TEXT        NOT NULL,
  change_type      TEXT        NOT NULL CHECK (change_type IN ('standard','normal','emergency')),
  priority         TEXT        NOT NULL DEFAULT 'normal'
                               CHECK (priority IN ('low','normal','high','critical')),
  status           TEXT        NOT NULL DEFAULT 'pending'
                               CHECK (status IN (
                                 'pending','approved','rejected',
                                 'implementing','completed','validated'
                               )),
  requested_by     TEXT        NOT NULL,
  approved_by      TEXT,
  rollback_plan    TEXT,
  implemented_at   TIMESTAMPTZ,
  validated_at     TIMESTAMPTZ,
  created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_cr_status ON change_requests (status, priority, created_at DESC);

-- ── Atualizações de Documentação ───────────────────────────────────────────
CREATE TABLE IF NOT EXISTS documentation_updates (
  id             BIGSERIAL   PRIMARY KEY,
  trigger_event  TEXT        NOT NULL,
  file_path      TEXT        NOT NULL,
  summary        TEXT        NOT NULL,
  diff_content   TEXT,
  status         TEXT        NOT NULL DEFAULT 'pending'
                             CHECK (status IN ('pending','applied','failed')),
  created_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
  applied_at     TIMESTAMPTZ
);

-- ── Propostas de Melhoria (Log Improver → CTO) ────────────────────────────
CREATE TABLE IF NOT EXISTS improvement_proposals (
  id                 UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
  source_agent       TEXT        NOT NULL DEFAULT 'log_improver',
  proposal_type      TEXT        NOT NULL
                                 CHECK (proposal_type IN (
                                   'code_fix','config_change','new_agent',
                                   'infrastructure','monitoring'
                                 )),
  title              TEXT        NOT NULL,
  description        TEXT        NOT NULL,
  proposed_action    TEXT        NOT NULL,
  affected_files     JSONB       NOT NULL DEFAULT '[]',
  priority           TEXT        NOT NULL DEFAULT 'medium'
                                 CHECK (priority IN ('low','medium','high','critical')),
  estimated_effort   TEXT        NOT NULL DEFAULT 'hours'
                                 CHECK (estimated_effort IN ('minutes','hours','days')),
  risk               TEXT        NOT NULL DEFAULT 'medium'
                                 CHECK (risk IN ('low','medium','high')),
  auto_implementable BOOLEAN     NOT NULL DEFAULT false,
  source_findings    JSONB       NOT NULL DEFAULT '[]',
  status             TEXT        NOT NULL DEFAULT 'pending_cto'
                                 CHECK (status IN (
                                   'pending_cto',
                                   'approved_auto',
                                   'approved_manual',
                                   'rejected',
                                   'implementing',
                                   'completed',
                                   'failed'
                                 )),
  cto_reasoning      TEXT,
  created_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
  decided_at         TIMESTAMPTZ,
  completed_at       TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS idx_ip_status ON improvement_proposals (status, priority, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_ip_auto ON improvement_proposals (auto_implementable, status);

-- ── Estende CHECK do agent_type para incluir tipos LangGraph ──────────────
ALTER TABLE agents DROP CONSTRAINT IF EXISTS agents_agent_type_check;
ALTER TABLE agents ADD CONSTRAINT agents_agent_type_check
  CHECK (agent_type IN (
    'freshservice_sync','script','expenses_sync',
    'langgraph_cto',
    'langgraph_log_scanner',
    'langgraph_log_improver',
    'langgraph_fix_validator',
    'langgraph_security',
    'langgraph_code_security',
    'langgraph_quality',
    'langgraph_quality_validator',
    'langgraph_uptime',
    'langgraph_docs',
    'langgraph_docker',
    'langgraph_frontend',
    'langgraph_backend',
    'langgraph_infrastructure',
    'langgraph_api',
    'langgraph_automation',
    'langgraph_itil_version',
    'langgraph_change_mgmt',
    'langgraph_change_validator',
    'langgraph_integration_validator',
    'langgraph_scheduling'
  ));
