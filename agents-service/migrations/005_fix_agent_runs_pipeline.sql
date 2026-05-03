-- ============================================================
-- Fix: agent_runs.agent_id deve aceitar NULL para pipeline runs
-- Pipeline runs não têm um agente real na tabela agents.
-- ============================================================

-- Remover NOT NULL constraint (mantém FK para quando agent_id está presente)
ALTER TABLE agent_runs ALTER COLUMN agent_id DROP NOT NULL;

-- Coluna para identificar qual pipeline gerou o run
ALTER TABLE agent_runs ADD COLUMN IF NOT EXISTS pipeline_name TEXT;

-- Coluna para distinguir tipo de run
ALTER TABLE agent_runs ADD COLUMN IF NOT EXISTS run_type TEXT DEFAULT 'agent';
-- run_type: 'agent' | 'pipeline' | 'manual'

-- Índice para buscar pipeline runs rapidamente
CREATE INDEX IF NOT EXISTS idx_agent_runs_pipeline
    ON agent_runs(pipeline_name, started_at DESC)
    WHERE pipeline_name IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_agent_runs_type
    ON agent_runs(run_type, started_at DESC);
