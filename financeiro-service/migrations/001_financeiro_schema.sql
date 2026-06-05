-- financeiro-service: migration inicial
-- Tabela de audit de queries (opcional — aplicar se desejado via Supabase SQL Editor)

CREATE TABLE IF NOT EXISTS public.query_logs_financeiro (
    id                   SERIAL PRIMARY KEY,
    user_id              TEXT NOT NULL,
    modulo               VARCHAR(50) NOT NULL,
    periodo_inicio       DATE,
    periodo_fim          DATE,
    registros_retornados INTEGER,
    tempo_resposta_ms    INTEGER,
    cache_hit            BOOLEAN DEFAULT false,
    created_at           TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_qlf_user   ON public.query_logs_financeiro(user_id);
CREATE INDEX IF NOT EXISTS idx_qlf_modulo ON public.query_logs_financeiro(modulo);
CREATE INDEX IF NOT EXISTS idx_qlf_ts     ON public.query_logs_financeiro(created_at DESC);
