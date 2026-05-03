-- ============================================================
-- Jarvis Agent Core v2.1 — Tabela improvement_proposals
-- Separada de correction_proposals: cobre melhorias sistêmicas,
-- refatorações, novas features e propostas dos agentes LLM.
-- ============================================================

CREATE TABLE IF NOT EXISTS improvement_proposals (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_agent        VARCHAR(50)  NOT NULL,
    proposal_type       VARCHAR(50)  NOT NULL,  -- refactoring|new_feature|infrastructure|config|monitoring|new_agent|automation|modernization|process|index|vacuum|rewrite
    title               TEXT         NOT NULL,
    description         TEXT,
    evidence            TEXT,                   -- dados que embasam a proposta (logs, métricas)
    proposed_fix        TEXT,                   -- código ou SQL proposto
    proposed_action     TEXT,                   -- ação descritiva quando não é código
    affected_files      TEXT[],
    sql_proposal        TEXT,                   -- SQL específico (db_dba_agent)
    expected_gain       TEXT,                   -- ganho esperado quantificado
    business_value      TEXT,                   -- valor de negócio (evolution_agent)
    motivational_note   TEXT,                   -- nota motivacional (evolution_agent)
    priority            VARCHAR(20)  DEFAULT 'medium',  -- critical|high|medium|low
    risk                VARCHAR(20)  DEFAULT 'low',     -- low|medium|high
    estimated_effort    VARCHAR(50),                    -- horas|dias|semanas|meses
    auto_implementable  BOOLEAN      DEFAULT FALSE,
    validation_status   VARCHAR(20)  DEFAULT 'pending', -- pending|approved|rejected|applied
    applied             BOOLEAN      DEFAULT FALSE,
    applied_at          TIMESTAMPTZ,
    rejection_reason    TEXT,
    created_at          TIMESTAMPTZ  DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_improvement_proposals_status
    ON improvement_proposals(validation_status, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_improvement_proposals_agent
    ON improvement_proposals(source_agent, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_improvement_proposals_type
    ON improvement_proposals(proposal_type, priority);

ALTER TABLE improvement_proposals ENABLE ROW LEVEL SECURITY;

CREATE POLICY "service_role_all" ON improvement_proposals
    FOR ALL TO service_role USING (true) WITH CHECK (true);

CREATE POLICY "authenticated_read" ON improvement_proposals
    FOR SELECT TO authenticated USING (true);

-- Realtime para o frontend ver proposals em tempo real
ALTER TABLE improvement_proposals REPLICA IDENTITY FULL;
