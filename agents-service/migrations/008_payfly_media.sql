-- PayFly — monitoramento de mídia (Google News / RSS)

CREATE TABLE IF NOT EXISTS public.payfly_media_posts (
    id             uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    platform       text        NOT NULL DEFAULT 'google_news',
    title          text        NOT NULL,
    url            text        NOT NULL,
    snippet        text,
    source         text,
    published_at   timestamptz,
    fetched_at     timestamptz NOT NULL DEFAULT now(),
    sentiment      text        NOT NULL DEFAULT 'neutro'
                               CHECK (sentiment IN ('positivo', 'negativo', 'neutro')),
    sentiment_score numeric(4,3)  -- -1.0 a 1.0
);

ALTER TABLE public.payfly_media_posts
    ADD CONSTRAINT payfly_media_posts_url_unique UNIQUE (url);

CREATE INDEX IF NOT EXISTS idx_payfly_posts_pub  ON public.payfly_media_posts (published_at DESC);
CREATE INDEX IF NOT EXISTS idx_payfly_posts_plat ON public.payfly_media_posts (platform);
CREATE INDEX IF NOT EXISTS idx_payfly_posts_sent ON public.payfly_media_posts (sentiment);

CREATE TABLE IF NOT EXISTS public.payfly_media_metrics (
    id              uuid  PRIMARY KEY DEFAULT gen_random_uuid(),
    ref_month       text  NOT NULL,         -- 'YYYY-MM'
    platform        text  NOT NULL,
    posts_count     int   NOT NULL DEFAULT 0,
    positive_count  int   NOT NULL DEFAULT 0,
    negative_count  int   NOT NULL DEFAULT 0,
    neutral_count   int   NOT NULL DEFAULT 0,
    computed_at     timestamptz NOT NULL DEFAULT now(),
    UNIQUE (ref_month, platform)
);

-- RLS
ALTER TABLE public.payfly_media_posts    ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.payfly_media_metrics  ENABLE ROW LEVEL SECURITY;

DO $$ BEGIN
  CREATE POLICY "service_role full access posts"
      ON public.payfly_media_posts FOR ALL TO service_role USING (true) WITH CHECK (true);
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
  CREATE POLICY "authenticated read posts"
      ON public.payfly_media_posts FOR SELECT TO authenticated USING (true);
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
  CREATE POLICY "service_role full access metrics"
      ON public.payfly_media_metrics FOR ALL TO service_role USING (true) WITH CHECK (true);
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
  CREATE POLICY "authenticated read metrics"
      ON public.payfly_media_metrics FOR SELECT TO authenticated USING (true);
EXCEPTION WHEN duplicate_object THEN NULL; END $$;
