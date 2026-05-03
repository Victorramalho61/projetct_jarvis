-- ============================================================
-- Jarvis Agent Core v2.2 — Tabela db_health_snapshots
-- Snapshots periódicos do DBA Agent para análise de tendências.
-- ============================================================

CREATE TABLE IF NOT EXISTS db_health_snapshots (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    captured_at     TIMESTAMPTZ  DEFAULT NOW(),
    table_sizes     JSONB        DEFAULT '{}',  -- {table_name: size_bytes}
    index_usage     JSONB        DEFAULT '{}',  -- {index_name: {scans, size}}
    slow_queries    JSONB        DEFAULT '[]',  -- top slow queries do pg_stat_statements
    table_bloat     JSONB        DEFAULT '{}',  -- {table_name: {dead_ratio, live_tup, dead_tup}}
    connection_stats JSONB       DEFAULT '{}',  -- {state: count}
    vacuum_status   JSONB        DEFAULT '{}',  -- {table_name: {last_vacuum, last_autovacuum}}
    missing_indexes JSONB        DEFAULT '[]',  -- tabelas candidatas a novos índices
    summary         TEXT                        -- resumo textual do snapshot
);

CREATE INDEX IF NOT EXISTS idx_db_health_snapshots_time
    ON db_health_snapshots(captured_at DESC);

ALTER TABLE db_health_snapshots ENABLE ROW LEVEL SECURITY;

CREATE POLICY "service_role_all" ON db_health_snapshots
    FOR ALL TO service_role USING (true) WITH CHECK (true);

CREATE POLICY "authenticated_read" ON db_health_snapshots
    FOR SELECT TO authenticated USING (true);

-- Tabela de change_requests (ITIL) — referenciada pelo change_mgmt e change_validator
CREATE TABLE IF NOT EXISTS change_requests (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    title           TEXT         NOT NULL,
    description     TEXT,
    change_type     VARCHAR(30)  DEFAULT 'normal',  -- emergency|normal|standard
    priority        VARCHAR(20)  DEFAULT 'medium',
    requested_by    VARCHAR(100) NOT NULL,
    status          VARCHAR(30)  DEFAULT 'pending', -- pending|approved|rejected|implemented|cancelled
    sla_deadline    TIMESTAMPTZ,
    approved_by     VARCHAR(100),
    rejection_reason TEXT,
    context         JSONB        DEFAULT '{}',
    created_at      TIMESTAMPTZ  DEFAULT NOW(),
    updated_at      TIMESTAMPTZ  DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_change_requests_status
    ON change_requests(status, priority, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_change_requests_deadline
    ON change_requests(sla_deadline) WHERE status = 'pending';

ALTER TABLE change_requests ENABLE ROW LEVEL SECURITY;

CREATE POLICY "service_role_all" ON change_requests
    FOR ALL TO service_role USING (true) WITH CHECK (true);

CREATE POLICY "authenticated_read" ON change_requests
    FOR SELECT TO authenticated USING (true);

ALTER TABLE change_requests REPLICA IDENTITY FULL;
