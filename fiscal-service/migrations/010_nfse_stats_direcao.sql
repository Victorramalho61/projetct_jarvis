-- Migration 010 — RPCs fiscal_nfse_stats e fiscal_nfse_search: filtro por
-- direcao ('emitida' | 'recebida') e período customizado (data_inicio/data_fim)
-- para a aba "NFSe Emitidas". Execute no Supabase SQL Editor.

-- Remove as assinaturas antigas (parâmetros diferentes = overload distinto no
-- Postgres) para evitar "could not choose a best candidate function" quando o
-- PostgREST chamar com um subconjunto de argumentos nomeados.
DROP FUNCTION IF EXISTS public.fiscal_nfse_stats(uuid, int, int);
DROP FUNCTION IF EXISTS public.fiscal_nfse_search(text, uuid, int, int);

CREATE OR REPLACE FUNCTION public.fiscal_nfse_stats(
    p_company_id  uuid DEFAULT NULL,
    p_ano         int  DEFAULT NULL,
    p_mes         int  DEFAULT NULL,
    p_data_inicio date DEFAULT NULL,
    p_data_fim    date DEFAULT NULL,
    p_direcao     text DEFAULT NULL
)
RETURNS jsonb
LANGUAGE plpgsql STABLE
AS $$
DECLARE
    v_date_from  timestamptz;
    v_date_to    timestamptz;
    v_result     jsonb;
BEGIN
    -- Período customizado tem prioridade sobre ano/mês
    IF p_data_inicio IS NOT NULL OR p_data_fim IS NOT NULL THEN
        v_date_from := p_data_inicio::timestamptz;
        v_date_to   := (p_data_fim + interval '1 day')::timestamptz; -- inclusive
    ELSIF p_ano IS NOT NULL THEN
        IF p_mes IS NOT NULL THEN
            v_date_from := make_date(p_ano, p_mes, 1)::timestamptz;
            v_date_to   := (make_date(p_ano, p_mes, 1) + interval '1 month')::timestamptz;
        ELSE
            v_date_from := make_date(p_ano, 1, 1)::timestamptz;
            v_date_to   := make_date(p_ano + 1, 1, 1)::timestamptz;
        END IF;
    END IF;

    WITH base AS (
        SELECT
            valor_total,
            valor_iss,
            COALESCE(municipio_nome, 'Desconhecido') AS municipio_nome,
            COALESCE(status, 'desconhecido')          AS status
        FROM public.fiscal_documents
        WHERE tipo = 'NFSe'
          AND (p_company_id IS NULL OR company_id = p_company_id)
          AND (v_date_from  IS NULL OR data_emissao >= v_date_from)
          AND (v_date_to    IS NULL OR data_emissao <  v_date_to)
          AND (p_direcao    IS NULL OR direcao = p_direcao)
    ),
    totals AS (
        SELECT COUNT(*)                    AS total_notas,
               COALESCE(SUM(valor_total), 0) AS valor_total,
               COALESCE(SUM(valor_iss),   0) AS valor_iss
        FROM base
    ),
    por_municipio AS (
        SELECT jsonb_object_agg(municipio_nome, cnt) AS j
        FROM (
            SELECT municipio_nome, COUNT(*) AS cnt
            FROM base
            GROUP BY municipio_nome
            ORDER BY cnt DESC
            LIMIT 20
        ) t
    ),
    por_status AS (
        SELECT jsonb_object_agg(status, cnt) AS j
        FROM (
            SELECT status, COUNT(*) AS cnt
            FROM base
            GROUP BY status
        ) t
    )
    SELECT jsonb_build_object(
        'total_notas',   t.total_notas,
        'valor_total',   t.valor_total,
        'valor_iss',     t.valor_iss,
        'por_municipio', COALESCE(m.j, '{}'),
        'por_status',    COALESCE(s.j, '{}')
    )
    INTO v_result
    FROM totals t, por_municipio m, por_status s;

    RETURN v_result;
END;
$$;

GRANT EXECUTE ON FUNCTION public.fiscal_nfse_stats(uuid, int, int, date, date, text) TO anon, authenticated, service_role;

CREATE OR REPLACE FUNCTION fiscal_nfse_search(
    p_query      text,
    p_company_id uuid    DEFAULT NULL,
    p_limit      int     DEFAULT 50,
    p_offset     int     DEFAULT 0,
    p_direcao    text    DEFAULT NULL
)
RETURNS SETOF fiscal_documents AS $$
BEGIN
  RETURN QUERY
  SELECT *
  FROM fiscal_documents
  WHERE tipo = 'NFSe'
    AND search_vector @@ websearch_to_tsquery('portuguese', p_query)
    AND (p_company_id IS NULL OR company_id = p_company_id)
    AND (p_direcao IS NULL OR direcao = p_direcao)
  ORDER BY ts_rank(search_vector, websearch_to_tsquery('portuguese', p_query)) DESC
  LIMIT p_limit OFFSET p_offset;
END;
$$ LANGUAGE plpgsql STABLE;

GRANT EXECUTE ON FUNCTION fiscal_nfse_search(text, uuid, int, int, text) TO anon, authenticated, service_role;
