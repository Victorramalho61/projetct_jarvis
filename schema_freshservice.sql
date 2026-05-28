-- ─────────────────────────────────────────────────────────────────────────────
-- FRESHSERVICE ANALYTICS — Schema
-- Aplicar com: docker exec -i jarvis-db-1 bash -c \
--   "PGPASSWORD='...' psql -U postgres -d postgres" < schema_freshservice.sql
-- ─────────────────────────────────────────────────────────────────────────────

-- ── Tabelas ──────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS public.freshservice_tickets (
    id                  integer PRIMARY KEY,
    workspace_id        integer,                    -- ID do workspace Freshservice (multi-workspace)
    subject             text NOT NULL,
    status              smallint NOT NULL,          -- 4=resolved, 5=closed
    priority            smallint,                   -- 1=low 2=medium 3=high 4=urgent
    type                text,
    group_id            bigint,
    responder_id        bigint,
    requester_id        bigint,
    company_id          bigint,
    created_at          timestamptz NOT NULL,
    updated_at          timestamptz NOT NULL,
    resolved_at         timestamptz,
    closed_at           timestamptz,
    due_by              timestamptz,
    fr_due_by           timestamptz,
    fr_responded_at     timestamptz,
    is_escalated        boolean DEFAULT false,
    csat_rating         smallint,                   -- 1=unhappy 2=neutral 3=happy
    csat_comment        text,
    resolution_time_min integer GENERATED ALWAYS AS (
        CASE WHEN resolved_at IS NOT NULL
             THEN EXTRACT(EPOCH FROM (resolved_at - created_at))::integer / 60
        END
    ) STORED,
    fr_time_min         integer GENERATED ALWAYS AS (
        CASE WHEN fr_responded_at IS NOT NULL
             THEN EXTRACT(EPOCH FROM (fr_responded_at - created_at))::integer / 60
        END
    ) STORED,
    sla_breached        boolean GENERATED ALWAYS AS (
        resolved_at IS NOT NULL AND due_by IS NOT NULL AND resolved_at > due_by
    ) STORED,
    raw                 jsonb NOT NULL,
    ingested_at         timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_fst_workspace   ON public.freshservice_tickets (workspace_id);
CREATE INDEX IF NOT EXISTS idx_fst_status      ON public.freshservice_tickets (status);
CREATE INDEX IF NOT EXISTS idx_fst_group       ON public.freshservice_tickets (group_id);
CREATE INDEX IF NOT EXISTS idx_fst_responder   ON public.freshservice_tickets (responder_id);
CREATE INDEX IF NOT EXISTS idx_fst_company     ON public.freshservice_tickets (company_id);
CREATE INDEX IF NOT EXISTS idx_fst_created_at  ON public.freshservice_tickets (created_at DESC);
CREATE INDEX IF NOT EXISTS idx_fst_resolved_at ON public.freshservice_tickets (resolved_at DESC);
CREATE INDEX IF NOT EXISTS idx_fst_updated_at  ON public.freshservice_tickets (updated_at DESC);

CREATE TABLE IF NOT EXISTS public.freshservice_agents (
    id          bigint PRIMARY KEY,
    name        text NOT NULL,
    email       text,
    synced_at   timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.freshservice_groups (
    id          bigint PRIMARY KEY,
    name        text NOT NULL,
    synced_at   timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.freshservice_companies (
    id          bigint PRIMARY KEY,
    name        text NOT NULL,
    synced_at   timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.freshservice_sync_log (
    id               bigserial PRIMARY KEY,
    sync_type        text NOT NULL,         -- 'backfill' | 'daily'
    started_at       timestamptz NOT NULL DEFAULT now(),
    completed_at     timestamptz,
    checkpoint       jsonb DEFAULT '{}',    -- {phase, page}
    tickets_upserted integer DEFAULT 0,
    status           text NOT NULL DEFAULT 'running',  -- running|completed|failed
    error            text,
    summary_json     jsonb                  -- resultado do Claude após sync diário
);

-- ── Permissões ───────────────────────────────────────────────────────────────

GRANT ALL ON public.freshservice_tickets   TO anon, authenticated, service_role;
GRANT ALL ON public.freshservice_agents    TO anon, authenticated, service_role;
GRANT ALL ON public.freshservice_groups    TO anon, authenticated, service_role;
GRANT ALL ON public.freshservice_companies TO anon, authenticated, service_role;
GRANT ALL ON public.freshservice_sync_log  TO anon, authenticated, service_role;
GRANT ALL ON SEQUENCE public.freshservice_sync_log_id_seq TO anon, authenticated, service_role;

ALTER TABLE public.freshservice_tickets    DISABLE ROW LEVEL SECURITY;
ALTER TABLE public.freshservice_agents     DISABLE ROW LEVEL SECURITY;
ALTER TABLE public.freshservice_groups     DISABLE ROW LEVEL SECURITY;
ALTER TABLE public.freshservice_companies  DISABLE ROW LEVEL SECURITY;
ALTER TABLE public.freshservice_sync_log   DISABLE ROW LEVEL SECURITY;

-- ── Funções SQL para analytics (chamadas via db.rpc()) ──────────────────────

-- Helper: data efetiva de fechamento
-- COALESCE(resolved_at, closed_at, updated_at)

CREATE OR REPLACE FUNCTION public.freshservice_summary(p_from timestamptz, p_to timestamptz)
RETURNS json
LANGUAGE sql STABLE SECURITY DEFINER
AS $$
  SELECT json_build_object(
    'total_closed',       COALESCE(COUNT(*), 0),
    'csat_avg',           ROUND(AVG(csat_rating::numeric), 2),
    'sla_breach_pct',     ROUND(
                            100.0 * SUM(CASE WHEN sla_breached THEN 1 ELSE 0 END)::numeric
                            / NULLIF(COUNT(*)::numeric, 0), 1),
    'avg_resolution_min', ROUND(AVG(resolution_time_min::numeric), 0),
    'avg_fr_min',         ROUND(AVG(fr_time_min::numeric), 0),
    'by_priority', (
      SELECT COALESCE(json_agg(r ORDER BY r.priority NULLS LAST), '[]'::json)
      FROM (
        SELECT
          priority,
          COUNT(*) AS count,
          ROUND(
            100.0 * SUM(CASE WHEN sla_breached THEN 1 ELSE 0 END)::numeric
            / NULLIF(COUNT(*)::numeric, 0), 1
          ) AS breach_pct
        FROM public.freshservice_tickets
        WHERE COALESCE(resolved_at, closed_at, updated_at) >= p_from
          AND COALESCE(resolved_at, closed_at, updated_at) < p_to
          AND status IN (4, 5)
        GROUP BY priority
      ) r
    )
  )
  FROM public.freshservice_tickets
  WHERE COALESCE(resolved_at, closed_at, updated_at) >= p_from
    AND COALESCE(resolved_at, closed_at, updated_at) < p_to
    AND status IN (4, 5)
$$;

CREATE OR REPLACE FUNCTION public.freshservice_sla_by_group(p_from timestamptz, p_to timestamptz)
RETURNS json
LANGUAGE sql STABLE SECURITY DEFINER
AS $$
  SELECT COALESCE(json_agg(r ORDER BY r.count DESC), '[]'::json)
  FROM (
    SELECT
      t.group_id,
      COALESCE(g.name, 'Sem grupo') AS group_name,
      COUNT(*) AS count,
      ROUND(AVG(t.resolution_time_min::numeric), 0) AS avg_resolution_min,
      ROUND(
        100.0 * SUM(CASE WHEN t.sla_breached THEN 1 ELSE 0 END)::numeric
        / NULLIF(COUNT(*)::numeric, 0), 1
      ) AS breach_pct
    FROM public.freshservice_tickets t
    LEFT JOIN public.freshservice_groups g ON g.id = t.group_id
    WHERE COALESCE(t.resolved_at, t.closed_at, t.updated_at) >= p_from
      AND COALESCE(t.resolved_at, t.closed_at, t.updated_at) < p_to
      AND t.status IN (4, 5)
    GROUP BY t.group_id, g.name
  ) r
$$;

CREATE OR REPLACE FUNCTION public.freshservice_agents_monthly(p_year int, p_month int)
RETURNS json
LANGUAGE sql STABLE SECURITY DEFINER
AS $$
  SELECT COALESCE(json_agg(r ORDER BY r.closed_count DESC), '[]'::json)
  FROM (
    SELECT
      t.responder_id AS agent_id,
      COALESCE(a.name, 'Não atribuído') AS agent_name,
      COUNT(*) AS closed_count,
      ROUND(AVG(t.resolution_time_min::numeric), 0) AS avg_resolution_min
    FROM public.freshservice_tickets t
    LEFT JOIN public.freshservice_agents a ON a.id = t.responder_id
    WHERE EXTRACT(YEAR FROM COALESCE(t.resolved_at, t.closed_at, t.updated_at)) = p_year
      AND EXTRACT(MONTH FROM COALESCE(t.resolved_at, t.closed_at, t.updated_at)) = p_month
      AND t.status IN (4, 5)
    GROUP BY t.responder_id, a.name
  ) r
$$;

CREATE OR REPLACE FUNCTION public.freshservice_top_requesters(
  p_from timestamptz,
  p_to timestamptz,
  p_limit int DEFAULT 5
)
RETURNS json
LANGUAGE sql STABLE SECURITY DEFINER
AS $$
  SELECT COALESCE(json_agg(r ORDER BY r.count DESC), '[]'::json)
  FROM (
    SELECT
      t.company_id,
      COALESCE(c.name, 'Sem empresa') AS company_name,
      COUNT(*) AS count
    FROM public.freshservice_tickets t
    LEFT JOIN public.freshservice_companies c ON c.id = t.company_id
    WHERE COALESCE(t.resolved_at, t.closed_at, t.updated_at) >= p_from
      AND COALESCE(t.resolved_at, t.closed_at, t.updated_at) < p_to
      AND t.status IN (4, 5)
    GROUP BY t.company_id, c.name
    ORDER BY count DESC
    LIMIT p_limit
  ) r
$$;

CREATE OR REPLACE FUNCTION public.freshservice_csat_summary(p_from timestamptz, p_to timestamptz)
RETURNS json
LANGUAGE sql STABLE SECURITY DEFINER
AS $$
  -- CTE lê a tabela UMA vez; subqueries reutilizam o resultado em memória
  WITH base AS (
    SELECT
      t.id,
      t.subject,
      t.csat_rating,
      t.csat_comment,
      t.group_id,
      COALESCE(t.resolved_at, t.closed_at, t.updated_at) AS eff_date
    FROM public.freshservice_tickets t
    WHERE COALESCE(t.resolved_at, t.closed_at, t.updated_at) >= p_from
      AND COALESCE(t.resolved_at, t.closed_at, t.updated_at) < p_to
      AND t.status IN (4, 5)
  )
  SELECT json_build_object(
    'total_rated',   SUM(CASE WHEN csat_rating IS NOT NULL THEN 1 ELSE 0 END),
    'avg_rating',    ROUND(AVG(csat_rating::numeric), 2),
    'happy_pct',     ROUND(
                       100.0 * SUM(CASE WHEN csat_rating = 3 THEN 1 ELSE 0 END)::numeric
                       / NULLIF(SUM(CASE WHEN csat_rating IS NOT NULL THEN 1 ELSE 0 END)::numeric, 0), 1),
    'neutral_pct',   ROUND(
                       100.0 * SUM(CASE WHEN csat_rating = 2 THEN 1 ELSE 0 END)::numeric
                       / NULLIF(SUM(CASE WHEN csat_rating IS NOT NULL THEN 1 ELSE 0 END)::numeric, 0), 1),
    'unhappy_pct',   ROUND(
                       100.0 * SUM(CASE WHEN csat_rating = 1 THEN 1 ELSE 0 END)::numeric
                       / NULLIF(SUM(CASE WHEN csat_rating IS NOT NULL THEN 1 ELSE 0 END)::numeric, 0), 1),
    'by_group', (
      SELECT COALESCE(json_agg(r ORDER BY r.count DESC), '[]'::json)
      FROM (
        SELECT
          b.group_id,
          COALESCE(g.name, 'Sem grupo') AS group_name,
          COUNT(*) FILTER (WHERE b.csat_rating IS NOT NULL) AS count,
          ROUND(AVG(b.csat_rating::numeric) FILTER (WHERE b.csat_rating IS NOT NULL), 2) AS avg_rating,
          ROUND(
            100.0 * COUNT(*) FILTER (WHERE b.csat_rating = 3)::numeric
            / NULLIF(COUNT(*) FILTER (WHERE b.csat_rating IS NOT NULL)::numeric, 0), 1
          ) AS happy_pct,
          ROUND(
            100.0 * COUNT(*) FILTER (WHERE b.csat_rating = 1)::numeric
            / NULLIF(COUNT(*) FILTER (WHERE b.csat_rating IS NOT NULL)::numeric, 0), 1
          ) AS unhappy_pct
        FROM base b
        LEFT JOIN public.freshservice_groups g ON g.id = b.group_id
        WHERE b.csat_rating IS NOT NULL
        GROUP BY b.group_id, g.name
      ) r
    ),
    'recent_comments', (
      SELECT COALESCE(json_agg(r ORDER BY r.eff_date DESC), '[]'::json)
      FROM (
        SELECT id, subject, csat_rating, csat_comment, eff_date
        FROM base
        WHERE csat_rating IN (1, 2)
          AND csat_comment IS NOT NULL
          AND csat_comment <> ''
        ORDER BY eff_date DESC
        LIMIT 5
      ) r
    )
  )
  FROM base
$$;

-- Índice funcional para acelerar o filtro por data efetiva (COALESCE)
CREATE INDEX IF NOT EXISTS idx_freshservice_tickets_eff_date
  ON public.freshservice_tickets (COALESCE(resolved_at, closed_at, updated_at))
  WHERE status IN (4, 5);

-- Batch update de CSAT ratings (evita N queries individuais)
CREATE OR REPLACE FUNCTION public.upsert_csat_ratings(p_ratings jsonb)
RETURNS integer
LANGUAGE plpgsql VOLATILE SECURITY DEFINER
AS $$
DECLARE
  v_item  jsonb;
  v_total integer := 0;
BEGIN
  FOR v_item IN SELECT * FROM jsonb_array_elements(p_ratings)
  LOOP
    UPDATE public.freshservice_tickets
    SET
      csat_rating  = (v_item->>'csat_rating')::smallint,
      csat_comment = v_item->>'csat_comment'
    WHERE id = (v_item->>'ticket_id')::integer;
    v_total := v_total + 1;
  END LOOP;
  RETURN v_total;
END;
$$;

GRANT EXECUTE ON FUNCTION public.freshservice_summary(timestamptz, timestamptz)           TO anon, authenticated, service_role;
GRANT EXECUTE ON FUNCTION public.freshservice_sla_by_group(timestamptz, timestamptz)      TO anon, authenticated, service_role;
GRANT EXECUTE ON FUNCTION public.freshservice_agents_monthly(int, int)                    TO anon, authenticated, service_role;
GRANT EXECUTE ON FUNCTION public.freshservice_top_requesters(timestamptz, timestamptz, int) TO anon, authenticated, service_role;
GRANT EXECUTE ON FUNCTION public.freshservice_csat_summary(timestamptz, timestamptz)      TO anon, authenticated, service_role;
GRANT EXECUTE ON FUNCTION public.upsert_csat_ratings(jsonb)                               TO anon, authenticated, service_role;
