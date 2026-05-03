-- Migration 002: Agent Versioning
-- Cria tabela de versões de agentes com ciclo de vida completo.
-- Fluxo: draft → testing → approved ↔ canary → deprecated

CREATE TABLE IF NOT EXISTS agent_versions (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    agent_name          TEXT NOT NULL,
    version             TEXT NOT NULL DEFAULT 'v1',

    -- Ciclo de vida
    status              TEXT NOT NULL DEFAULT 'draft'
                        CHECK (status IN ('draft', 'testing', 'approved', 'canary', 'deprecated')),

    -- Definição do agente
    system_prompt       TEXT,
    tools               JSONB DEFAULT '[]',
    model               TEXT DEFAULT 'llama3.2:1b',
    config              JSONB DEFAULT '{}',
    prompt_hash         TEXT,

    -- Linhagem
    parent_version_id   UUID REFERENCES agent_versions(id) ON DELETE SET NULL,

    -- Aprovação
    created_by          TEXT DEFAULT 'system',
    approved_by         TEXT,
    approved_at         TIMESTAMPTZ,

    -- Métricas de uso
    total_runs          INTEGER DEFAULT 0,
    failure_count       INTEGER DEFAULT 0,
    success_rate        FLOAT DEFAULT 0,

    -- Canary
    canary_percentage   INTEGER DEFAULT 0 CHECK (canary_percentage BETWEEN 0 AND 100),

    notes               TEXT,
    created_at          TIMESTAMPTZ DEFAULT NOW(),
    updated_at          TIMESTAMPTZ DEFAULT NOW(),

    UNIQUE (agent_name, version)
);

-- Índices de consulta
CREATE INDEX IF NOT EXISTS idx_agent_versions_name   ON agent_versions (agent_name);
CREATE INDEX IF NOT EXISTS idx_agent_versions_status ON agent_versions (agent_name, status);
CREATE INDEX IF NOT EXISTS idx_agent_versions_active ON agent_versions (agent_name, approved_at DESC)
    WHERE status IN ('approved', 'canary');

-- Auto-update de updated_at
CREATE OR REPLACE FUNCTION update_agent_versions_ts()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
  NEW.updated_at = NOW();
  RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_agent_versions_ts ON agent_versions;
CREATE TRIGGER trg_agent_versions_ts
  BEFORE UPDATE ON agent_versions
  FOR EACH ROW EXECUTE FUNCTION update_agent_versions_ts();
