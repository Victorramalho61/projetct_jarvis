-- Migration: versiona a função fiscal_nfse_stats (aplicada anteriormente direto no
-- banco, sem migration correspondente — este arquivo só documenta/recria o que já
-- está em produção, para rastreabilidade).
-- Execute no Supabase SQL Editor (Settings → SQL Editor)
-- Data: 2026-07-02

CREATE OR REPLACE FUNCTION public.fiscal_nfse_stats(
    p_company_id uuid DEFAULT NULL,
    p_ano        int  DEFAULT NULL,
    p_mes        int  DEFAULT NULL
)
RETURNS jsonb
LANGUAGE plpgsql STABLE
AS $$
DECLARE
    v_date_from  timestamptz;
    v_date_to    timestamptz;
    v_result     jsonb;
BEGIN
    -- Converte ano/mês em intervalo de datas (permite uso de índice btree em data_emissao)
    IF p_ano IS NOT NULL THEN
        IF p_mes IS NOT NULL THEN
            v_date_from := make_date(p_ano, p_mes, 1)::timestamptz;
            v_date_to   := (make_date(p_ano, p_mes, 1) + interval '1 month')::timestamptz;
        ELSE
            v_date_from := make_date(p_ano, 1, 1)::timestamptz;
            v_date_to   := make_date(p_ano + 1, 1, 1)::timestamptz;
        END IF;
    END IF;

    -- Único CTE sobre fiscal_documents (era 3 passes separados)
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

GRANT EXECUTE ON FUNCTION public.fiscal_nfse_stats(uuid, int, int) TO anon, authenticated, service_role;
