-- ============================================================
-- Migration 006: quality_metrics e security_alerts
-- Tabelas usadas pelos agentes quality, quality_validator,
-- security e code_security.
-- ============================================================

-- Tabela de métricas de qualidade (série temporal)
CREATE TABLE IF NOT EXISTS quality_metrics (
    id            BIGSERIAL PRIMARY KEY,
    metric_name   TEXT        NOT NULL,
    metric_value  NUMERIC     NOT NULL,
    unit          TEXT,
    service       TEXT,
    metadata      JSONB       DEFAULT '{}',
    measured_at   TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_quality_metrics_name_time
    ON quality_metrics(metric_name, measured_at DESC);

CREATE INDEX IF NOT EXISTS idx_quality_metrics_service
    ON quality_metrics(service, measured_at DESC)
    WHERE service IS NOT NULL;

-- Tabela de alertas de segurança
CREATE TABLE IF NOT EXISTS security_alerts (
    id                BIGSERIAL PRIMARY KEY,
    severity          TEXT        NOT NULL CHECK (severity IN ('low','medium','high','critical')),
    category          TEXT        NOT NULL,
    description       TEXT        NOT NULL,
    affected_resource TEXT,
    status            TEXT        NOT NULL DEFAULT 'open' CHECK (status IN ('open','acknowledged','resolved')),
    resolved_at       TIMESTAMPTZ,
    metadata          JSONB       DEFAULT '{}',
    created_at        TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_security_alerts_status
    ON security_alerts(status, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_security_alerts_severity
    ON security_alerts(severity, created_at DESC);
