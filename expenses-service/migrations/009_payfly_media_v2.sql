-- PayFly Mídia v2 — pgvector + categoria + sentimento expandido + tabelas auxiliares
-- Aplicar via: docker exec -i jarvis-db-1 psql -U postgres -d postgres < migrations/009_payfly_media_v2.sql

-- pgvector já incluso no Supabase por padrão
CREATE EXTENSION IF NOT EXISTS vector;

-- ── payfly_media_posts: novas colunas ─────────────────────────────────────────
ALTER TABLE public.payfly_media_posts
  ADD COLUMN IF NOT EXISTS category        text NOT NULL DEFAULT 'Neutro',
  ADD COLUMN IF NOT EXISTS sentiment_label text NOT NULL DEFAULT 'neutro',
  ADD COLUMN IF NOT EXISTS full_text       text,
  ADD COLUMN IF NOT EXISTS embedding       vector(768);

-- Índice IVFFlat para busca por similaridade coseno
CREATE INDEX IF NOT EXISTS idx_payfly_posts_embedding
  ON public.payfly_media_posts
  USING ivfflat (embedding vector_cosine_ops)
  WITH (lists = 50);

CREATE INDEX IF NOT EXISTS idx_payfly_posts_category
  ON public.payfly_media_posts (category);

-- ── Métricas diárias ──────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS public.payfly_media_daily_metrics (
  id             uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
  ref_date       date        NOT NULL,
  platform       text        NOT NULL,
  posts_count    int         NOT NULL DEFAULT 0,
  positive_count int         NOT NULL DEFAULT 0,
  negative_count int         NOT NULL DEFAULT 0,
  neutral_count  int         NOT NULL DEFAULT 0,
  computed_at    timestamptz NOT NULL DEFAULT now(),
  UNIQUE (ref_date, platform)
);

-- ── Resumos executivos semanais ───────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS public.payfly_executive_summaries (
  id         uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
  ref_week   text        NOT NULL UNIQUE,   -- 'YYYY-WNN'
  summary    text        NOT NULL,
  model_used text,
  created_at timestamptz NOT NULL DEFAULT now()
);

-- ── Log de crises detectadas ──────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS public.payfly_crisis_log (
  id           uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
  detected_at  timestamptz NOT NULL DEFAULT now(),
  severity     text        NOT NULL CHECK (severity IN ('warning', 'critical')),
  neg_count    int         NOT NULL,
  avg_baseline numeric(8,2),
  alert_sent   boolean     NOT NULL DEFAULT false,
  summary      text
);

-- ── RLS ───────────────────────────────────────────────────────────────────────
ALTER TABLE public.payfly_media_daily_metrics  ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.payfly_executive_summaries  ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.payfly_crisis_log           ENABLE ROW LEVEL SECURITY;

DO $$ BEGIN
  CREATE POLICY "service_role full access daily_metrics"
    ON public.payfly_media_daily_metrics FOR ALL TO service_role USING (true) WITH CHECK (true);
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
  CREATE POLICY "authenticated read daily_metrics"
    ON public.payfly_media_daily_metrics FOR SELECT TO authenticated USING (true);
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
  CREATE POLICY "service_role full access exec_summaries"
    ON public.payfly_executive_summaries FOR ALL TO service_role USING (true) WITH CHECK (true);
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
  CREATE POLICY "authenticated read exec_summaries"
    ON public.payfly_executive_summaries FOR SELECT TO authenticated USING (true);
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
  CREATE POLICY "service_role full access crisis_log"
    ON public.payfly_crisis_log FOR ALL TO service_role USING (true) WITH CHECK (true);
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
  CREATE POLICY "authenticated read crisis_log"
    ON public.payfly_crisis_log FOR SELECT TO authenticated USING (true);
EXCEPTION WHEN duplicate_object THEN NULL; END $$;
