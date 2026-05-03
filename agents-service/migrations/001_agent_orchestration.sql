-- ============================================================
-- Jarvis Agent Core v2.0 — Orquestração LangGraph + Supabase
-- Fase 1: Schema para CTO Agent, Event Bus e Pipelines
-- ============================================================

-- 1. Event Bus — fila reativa entre agentes
CREATE TABLE IF NOT EXISTS agent_events (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    event_type  VARCHAR(50) NOT NULL,   -- error_detected, security_alert, deploy_start, proposal_ready, etc.
    source      VARCHAR(50) NOT NULL,
    payload     JSONB        DEFAULT '{}',
    priority    VARCHAR(20)  DEFAULT 'medium', -- critical / high / medium / low
    processed   BOOLEAN      DEFAULT FALSE,
    created_at  TIMESTAMPTZ  DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_agent_events_processed ON agent_events(processed, priority, created_at);
-- Habilita Realtime para triggers reativos
ALTER TABLE agent_events REPLICA IDENTITY FULL;

-- 2. Fila de tarefas despachadas pelo CTO Agent
CREATE TABLE IF NOT EXISTS agent_tasks (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    dispatched_by    VARCHAR(50)  NOT NULL DEFAULT 'cto',
    assigned_to      VARCHAR(50)  NOT NULL,
    task_description TEXT         NOT NULL,
    priority         VARCHAR(20)  DEFAULT 'medium',
    status           VARCHAR(20)  DEFAULT 'pending', -- pending / running / completed / failed
    context          JSONB        DEFAULT '{}',
    result           JSONB,
    created_at       TIMESTAMPTZ  DEFAULT NOW(),
    started_at       TIMESTAMPTZ,
    completed_at     TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS idx_agent_tasks_status    ON agent_tasks(status, priority, created_at);
CREATE INDEX IF NOT EXISTS idx_agent_tasks_assigned  ON agent_tasks(assigned_to, status);

-- 3. Janelas de deploy — suspende automações durante deploys
CREATE TABLE IF NOT EXISTS deployment_windows (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    active       BOOLEAN     DEFAULT TRUE,
    reason       TEXT,
    started_by   VARCHAR(100),
    started_at   TIMESTAMPTZ DEFAULT NOW(),
    expected_end TIMESTAMPTZ,
    ended_at     TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS idx_deployment_windows_active ON deployment_windows(active, started_at);

-- 4. Propostas de correção do pipeline auto-fix
CREATE TABLE IF NOT EXISTS correction_proposals (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_log_id     UUID,           -- referência ao app_log que originou o pipeline
    pipeline_run_id   UUID,
    source_agent      VARCHAR(50)  DEFAULT 'auto_fix_pipeline',
    description       TEXT,
    proposed_fix      TEXT,           -- código ou script proposto
    root_cause        TEXT,
    effort_estimate   VARCHAR(20),    -- low / medium / high
    validation_status VARCHAR(20)  DEFAULT 'pending', -- pending / approved / rejected
    applied           BOOLEAN      DEFAULT FALSE,
    applied_at        TIMESTAMPTZ,
    rejected_reason   TEXT,
    created_at        TIMESTAMPTZ  DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_correction_proposals_status ON correction_proposals(validation_status, created_at);

-- 5. Relatórios de governança gerados pelo CTO Agent
CREATE TABLE IF NOT EXISTS governance_reports (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    period           VARCHAR(20)  NOT NULL,  -- daily / weekly
    report_date      DATE         NOT NULL,
    metrics          JSONB        DEFAULT '{}',
    findings_summary TEXT,
    recommendations  TEXT,
    agents_health    JSONB        DEFAULT '{}',
    generated_by     VARCHAR(50)  DEFAULT 'cto_agent',
    created_at       TIMESTAMPTZ  DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_governance_reports_date ON governance_reports(report_date DESC);

-- ============================================================
-- RLS: apenas service_role acessa (agentes rodam com service key)
-- ============================================================
ALTER TABLE agent_events         ENABLE ROW LEVEL SECURITY;
ALTER TABLE agent_tasks          ENABLE ROW LEVEL SECURITY;
ALTER TABLE deployment_windows   ENABLE ROW LEVEL SECURITY;
ALTER TABLE correction_proposals ENABLE ROW LEVEL SECURITY;
ALTER TABLE governance_reports   ENABLE ROW LEVEL SECURITY;

-- Política permissiva para service_role (agentes internos)
CREATE POLICY "service_role_all" ON agent_events         FOR ALL TO service_role USING (true) WITH CHECK (true);
CREATE POLICY "service_role_all" ON agent_tasks          FOR ALL TO service_role USING (true) WITH CHECK (true);
CREATE POLICY "service_role_all" ON deployment_windows   FOR ALL TO service_role USING (true) WITH CHECK (true);
CREATE POLICY "service_role_all" ON correction_proposals FOR ALL TO service_role USING (true) WITH CHECK (true);
CREATE POLICY "service_role_all" ON governance_reports   FOR ALL TO service_role USING (true) WITH CHECK (true);

-- Leitura autenticada para o frontend
CREATE POLICY "authenticated_read" ON agent_events         FOR SELECT TO authenticated USING (true);
CREATE POLICY "authenticated_read" ON agent_tasks          FOR SELECT TO authenticated USING (true);
CREATE POLICY "authenticated_read" ON deployment_windows   FOR SELECT TO authenticated USING (true);
CREATE POLICY "authenticated_read" ON correction_proposals FOR SELECT TO authenticated USING (true);
CREATE POLICY "authenticated_read" ON governance_reports   FOR SELECT TO authenticated USING (true);

-- ============================================================
-- Realtime: habilita publicação para as tabelas de orquestração
-- ============================================================
-- Execute no Supabase Dashboard > Database > Replication se preferir UI:
-- ALTER PUBLICATION supabase_realtime ADD TABLE agent_events;
-- ALTER PUBLICATION supabase_realtime ADD TABLE agent_tasks;
-- ALTER PUBLICATION supabase_realtime ADD TABLE deployment_windows;
