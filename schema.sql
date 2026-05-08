-- ============================================================
-- Schema Jarvis — aplicar em banco novo com:
--   docker exec -i jarvis-db-1 bash -c \
--     "PGPASSWORD='...' psql -U postgres -d postgres" < schema.sql
-- ============================================================

-- profiles
CREATE TABLE IF NOT EXISTS public.profiles (
    id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    username      text UNIQUE NOT NULL,
    display_name  text NOT NULL,
    email         text UNIQUE NOT NULL,
    role          text NOT NULL DEFAULT 'user' CHECK (role IN ('admin','user')),
    active        boolean NOT NULL DEFAULT false,
    password_hash text,
    whatsapp_phone text DEFAULT '',
    created_at    timestamptz NOT NULL DEFAULT now(),
    updated_at    timestamptz NOT NULL DEFAULT now()
);

-- connected_accounts
CREATE TABLE IF NOT EXISTS public.connected_accounts (
    id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id       uuid NOT NULL REFERENCES public.profiles(id) ON DELETE CASCADE,
    provider      text NOT NULL,
    email         text NOT NULL DEFAULT '',
    access_token  text NOT NULL DEFAULT '',
    refresh_token text NOT NULL DEFAULT '',
    token_expiry  timestamptz NOT NULL DEFAULT now(),
    created_at    timestamptz NOT NULL DEFAULT now(),
    updated_at    timestamptz NOT NULL DEFAULT now(),
    UNIQUE (user_id, provider)
);

-- notification_prefs
CREATE TABLE IF NOT EXISTS public.notification_prefs (
    id                uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id           uuid UNIQUE NOT NULL REFERENCES public.profiles(id) ON DELETE CASCADE,
    active            boolean NOT NULL DEFAULT true,
    send_hour_utc     integer NOT NULL DEFAULT 10 CHECK (send_hour_utc BETWEEN 0 AND 23),
    channels_config   jsonb,
    teams_webhook_url text DEFAULT '',
    whatsapp_phone    text DEFAULT '',
    updated_at        timestamptz NOT NULL DEFAULT now()
);

-- app_logs
CREATE TABLE IF NOT EXISTS public.app_logs (
    id         bigserial PRIMARY KEY,
    created_at timestamptz NOT NULL DEFAULT now(),
    level      text NOT NULL CHECK (level IN ('info','warning','error')),
    module     text NOT NULL,
    message    text NOT NULL,
    detail     text,
    user_id    uuid REFERENCES public.profiles(id) ON DELETE SET NULL,
    trace_id   text
);

-- migration: adiciona trace_id em instâncias existentes sem a coluna
ALTER TABLE public.app_logs ADD COLUMN IF NOT EXISTS trace_id text;

-- monitored_systems
CREATE TABLE IF NOT EXISTS public.monitored_systems (
    id                    uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    name                  text NOT NULL,
    description           text NOT NULL DEFAULT '',
    url                   text NOT NULL DEFAULT '',
    system_type           text NOT NULL CHECK (system_type IN ('http','evolution','metrics','tcp','custom')),
    config                jsonb NOT NULL DEFAULT '{}',
    check_interval_minutes integer NOT NULL DEFAULT 5,
    enabled               boolean NOT NULL DEFAULT true,
    last_alerted_at       timestamptz,
    created_by            uuid REFERENCES public.profiles(id) ON DELETE SET NULL,
    created_at            timestamptz NOT NULL DEFAULT now(),
    updated_at            timestamptz NOT NULL DEFAULT now()
);

-- system_checks
CREATE TABLE IF NOT EXISTS public.system_checks (
    id          bigserial PRIMARY KEY,
    system_id   uuid NOT NULL REFERENCES public.monitored_systems(id) ON DELETE CASCADE,
    status      text NOT NULL CHECK (status IN ('up','down','degraded','unknown')),
    latency_ms  integer,
    http_status integer,
    detail      text,
    metrics     jsonb,
    checked_by  text NOT NULL DEFAULT 'scheduler',
    checked_at  timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_system_checks_system_id_checked_at
    ON public.system_checks (system_id, checked_at DESC);

-- agents
CREATE TABLE IF NOT EXISTS public.agents (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    name            text NOT NULL,
    description     text DEFAULT '',
    agent_type      text NOT NULL DEFAULT 'script'
                    CHECK (agent_type IN ('freshservice_sync', 'script')),
    config          jsonb NOT NULL DEFAULT '{}',
    schedule_type   text NOT NULL DEFAULT 'manual'
                    CHECK (schedule_type IN ('manual','interval','daily','weekly','monthly')),
    schedule_config jsonb NOT NULL DEFAULT '{}',
    enabled         boolean NOT NULL DEFAULT true,
    created_by      uuid REFERENCES public.profiles(id) ON DELETE SET NULL,
    created_at      timestamptz NOT NULL DEFAULT now(),
    updated_at      timestamptz NOT NULL DEFAULT now()
);

-- agent_runs
CREATE TABLE IF NOT EXISTS public.agent_runs (
    id          bigserial PRIMARY KEY,
    agent_id    uuid NOT NULL REFERENCES public.agents(id) ON DELETE CASCADE,
    status      text NOT NULL DEFAULT 'running'
                CHECK (status IN ('running','success','error')),
    started_at  timestamptz NOT NULL DEFAULT now(),
    finished_at timestamptz,
    output      text,
    error       text
);

CREATE INDEX IF NOT EXISTS idx_agent_runs_agent_id ON public.agent_runs (agent_id, started_at DESC);

-- Migração: adicionar colunas novas a tabelas existentes
ALTER TABLE public.agents
    ADD COLUMN IF NOT EXISTS schedule_type   text NOT NULL DEFAULT 'manual',
    ADD COLUMN IF NOT EXISTS schedule_config jsonb NOT NULL DEFAULT '{}';

ALTER TABLE public.profiles
    ADD COLUMN IF NOT EXISTS anthropic_api_key text DEFAULT '';

-- password_reset_tokens
CREATE TABLE IF NOT EXISTS public.password_reset_tokens (
    id         uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id    uuid NOT NULL REFERENCES public.profiles(id) ON DELETE CASCADE,
    token      text UNIQUE NOT NULL,
    expires_at timestamptz NOT NULL,
    used_at    timestamptz,
    created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_prt_token ON public.password_reset_tokens(token);

-- Permissões para PostgREST
GRANT USAGE ON SCHEMA public TO anon, authenticated;
GRANT ALL ON ALL TABLES IN SCHEMA public TO anon, authenticated, service_role;
GRANT ALL ON ALL SEQUENCES IN SCHEMA public TO anon, authenticated, service_role;

-- RLS desabilitado — acesso controlado pelo backend via service_role key
ALTER TABLE public.profiles           DISABLE ROW LEVEL SECURITY;
ALTER TABLE public.connected_accounts DISABLE ROW LEVEL SECURITY;
ALTER TABLE public.notification_prefs DISABLE ROW LEVEL SECURITY;
ALTER TABLE public.app_logs           DISABLE ROW LEVEL SECURITY;
ALTER TABLE public.monitored_systems  DISABLE ROW LEVEL SECURITY;
ALTER TABLE public.system_checks      DISABLE ROW LEVEL SECURITY;
ALTER TABLE public.agents             DISABLE ROW LEVEL SECURITY;
ALTER TABLE public.agent_runs                DISABLE ROW LEVEL SECURITY;
ALTER TABLE public.password_reset_tokens     DISABLE ROW LEVEL SECURITY;

-- ── expenses_cache ────────────────────────────────────────────────────────────
-- Cache de dados pré-computados do módulo Gastos TI.
-- Populado pelo agente expenses_sync (diariamente às 06:00 BRT).
CREATE TABLE IF NOT EXISTS public.expenses_cache (
    id          SERIAL PRIMARY KEY,
    year        INTEGER  NOT NULL,
    cache_key   TEXT     NOT NULL,
    payload     JSONB    NOT NULL,
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    status      TEXT     NOT NULL DEFAULT 'success',
    error_msg   TEXT,
    UNIQUE (year, cache_key)
);

CREATE INDEX IF NOT EXISTS idx_expenses_cache_year ON public.expenses_cache(year);
CREATE INDEX IF NOT EXISTS idx_expenses_cache_updated ON public.expenses_cache(updated_at DESC);

ALTER TABLE public.expenses_cache DISABLE ROW LEVEL SECURITY;

-- ── Performance indexes ────────────────────────────────────────────────────────
-- app_logs: log_monitor faz range scan por created_at a cada 6h
CREATE INDEX IF NOT EXISTS idx_app_logs_created_at
    ON public.app_logs (created_at DESC);

-- app_logs: correlação de logs por trace_id entre serviços
CREATE INDEX IF NOT EXISTS idx_app_logs_trace_id
    ON public.app_logs (trace_id)
    WHERE trace_id IS NOT NULL;

-- app_logs: queries por módulo + level + created_at (log_monitor, growth check)
CREATE INDEX IF NOT EXISTS idx_app_logs_module_level_time
    ON public.app_logs (module, level, created_at DESC);

-- correction_proposals: join com app_logs por source_log_id
CREATE INDEX IF NOT EXISTS idx_correction_proposals_source_log
    ON public.correction_proposals (source_log_id)
    WHERE source_log_id IS NOT NULL;

-- quality_metrics: queries temporais dos agentes DBA e evolution
CREATE INDEX IF NOT EXISTS idx_quality_metrics_time
    ON public.quality_metrics (measured_at DESC);

-- security_alerts: queries temporais do code_security agent
CREATE INDEX IF NOT EXISTS idx_security_alerts_time
    ON public.security_alerts (created_at DESC);

-- system_checks: filtro por status para alertas (exclui 'up' que é maioria)
CREATE INDEX IF NOT EXISTS idx_system_checks_status_time
    ON public.system_checks (status, checked_at DESC)
    WHERE status != 'up';
