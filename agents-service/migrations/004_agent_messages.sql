-- ============================================================
-- Jarvis Agent Core v2.3 — Tabela agent_messages
-- Canal de mensagens entre agentes e para o humano (to_agent="human").
-- ============================================================

CREATE TABLE IF NOT EXISTS agent_messages (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    from_agent  VARCHAR(50)  NOT NULL,
    to_agent    VARCHAR(50)  NOT NULL,   -- nome do agente ou "human"
    message     TEXT,                    -- conteúdo textual da mensagem
    context     JSONB        DEFAULT '{}',
    thread_id   UUID,
    status      VARCHAR(20)  DEFAULT 'pending',  -- pending | read | processed
    read_at     TIMESTAMPTZ,
    created_at  TIMESTAMPTZ  DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_agent_messages_to_status
    ON agent_messages(to_agent, status, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_agent_messages_human
    ON agent_messages(status, created_at DESC)
    WHERE to_agent = 'human';

ALTER TABLE agent_messages ENABLE ROW LEVEL SECURITY;

CREATE POLICY "service_role_all" ON agent_messages
    FOR ALL TO service_role USING (true) WITH CHECK (true);

CREATE POLICY "authenticated_read" ON agent_messages
    FOR SELECT TO authenticated USING (true);

-- Realtime para notificações em tempo real no frontend
ALTER TABLE agent_messages REPLICA IDENTITY FULL;
