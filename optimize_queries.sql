-- ============================================================
-- Jarvis — Otimização de Queries e Índices
-- Gerado em 2026-05-25
-- Executar: docker exec -i jarvis-db-1 psql -U postgres postgres < optimize_queries.sql
-- ============================================================

-- ============================================================
-- 1. ÍNDICES AUSENTES — freshservice_sync_log
--    Problema: 188 seq_scans, só tem PK
--    Queries: .order("started_at", desc=True).limit(1)
--             .eq("sync_type","daily").order("started_at", desc=True)
-- ============================================================
CREATE INDEX IF NOT EXISTS idx_fsl_started_at
  ON public.freshservice_sync_log (started_at DESC);

CREATE INDEX IF NOT EXISTS idx_fsl_sync_type_started_at
  ON public.freshservice_sync_log (sync_type, started_at DESC);


-- ============================================================
-- 2. ÍNDICES AUSENTES — monitored_systems
--    Problema: 100% seq_scan em todas as consultas
--    Queries: .select("...").eq("enabled", True)
--             .update({...}).eq("id", ...)  ← usa PK, ok
-- ============================================================
CREATE INDEX IF NOT EXISTS idx_monitored_systems_enabled
  ON public.monitored_systems (enabled)
  WHERE enabled = TRUE;


-- ============================================================
-- 3. ÍNDICE COMPOSTO — payfly_reservations
--    Problema: 24.472 tuplas lidas via seq_scan
--    choice_date é timestamptz, mas o dashboard faz choice_date::date — cast impede uso do índice btree
--    Fix: índice funcional + índice composto para ORDER BY
-- ============================================================
-- Índice funcional em (choice_date::date) para o cast da função payfly_dashboard
CREATE INDEX IF NOT EXISTS idx_pf_res_choice_date_cast
  ON public.payfly_reservations ((choice_date::date) DESC);

-- Índice composto coberto para a query de listagem (choice_date DESC + filtros comuns)
CREATE INDEX IF NOT EXISTS idx_pf_res_status_choice_date
  ON public.payfly_reservations (status, choice_date DESC);

CREATE INDEX IF NOT EXISTS idx_pf_res_company_choice_date
  ON public.payfly_reservations (company_name, choice_date DESC);


-- ============================================================
-- 4. ÍNDICES AUSENTES — freshservice_tickets
--    idx_fst_created_at e idx_fst_updated_at existem mas com idx_scan=0
--    O sync faz .order("updated_at", desc=True) e .gte("updated_at", ...)
--    Verificar se existem; recriar se necessário
-- ============================================================
CREATE INDEX IF NOT EXISTS idx_fst_updated_at
  ON public.freshservice_tickets (updated_at DESC);

CREATE INDEX IF NOT EXISTS idx_fst_workspace_updated
  ON public.freshservice_tickets (workspace_id, updated_at DESC);


-- ============================================================
-- 5. REMOVER ÍNDICES DUPLICADOS — fiscal_documents
--    Cada par abaixo é btree idêntico: o UNIQUE já serve como índice de leitura
--    Duplicatas = escrita 2x mais lenta (INSERT/UPDATE/DELETE) sem nenhum ganho
-- ============================================================

-- chave_acesso: o UNIQUE (fiscal_documents_chave_acesso_key) já cobre leituras
DROP INDEX IF EXISTS public.idx_fiscal_docs_chave;

-- emitente_cnpj: manter apenas idx_fiscal_docs_emitente_cnpj (nome mais descritivo)
DROP INDEX IF EXISTS public.idx_fiscal_docs_emit_cnpj;

-- destinatario_cnpj: manter apenas idx_fiscal_docs_destinatario_cnpj
DROP INDEX IF EXISTS public.idx_fiscal_docs_dest_cnpj;


-- ============================================================
-- 6. REESCREVER fiscal_nfse_stats — de seq_scan para index_scan
--    Problema: EXTRACT(YEAR/MONTH FROM data_emissao) impede uso de qualquer índice btree
--    O índice idx_fiscal_docs_company_tipo_status_data existe mas nunca é usado (idx_scan=0)
--    Fix: converter p_ano/p_mes em range de datas → planner usa o índice btree normalmente
--    Bônus: 3 passes separados → 1 único CTE (3x menos I/O)
-- ============================================================
CREATE OR REPLACE FUNCTION public.fiscal_nfse_stats(
    p_company_id uuid    DEFAULT NULL,
    p_ano        integer DEFAULT NULL,
    p_mes        integer DEFAULT NULL
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


-- ============================================================
-- 7. REESCREVER payfly_dashboard — remover cast que impede índice
--    Problema: choice_date::date nas comparações força conversão linha a linha
--    choice_date é timestamptz → comparar diretamente com timestamptz evita o cast
-- ============================================================
CREATE OR REPLACE FUNCTION public.payfly_dashboard(
    p_start_date date DEFAULT NULL,
    p_end_date   date DEFAULT NULL,
    p_company    text DEFAULT NULL
)
RETURNS json
LANGUAGE sql STABLE
AS $$
  WITH base AS (
    SELECT solicitor_name, total_amount
    FROM payfly_reservations
    WHERE status != 'Cancelado'
      AND (p_start_date IS NULL OR choice_date >= p_start_date::timestamptz)
      AND (p_end_date   IS NULL OR choice_date <  (p_end_date  + 1)::timestamptz)
      AND (p_company    IS NULL OR company_name = p_company)
      AND solicitor_name IS NOT NULL
  )
  SELECT json_build_object(
    'total_amount',  COALESCE(SUM(total_amount), 0),
    'total_count',   COUNT(*),
    'top10_by_value', (
      SELECT json_agg(r ORDER BY r.total_amount DESC)
      FROM (
        SELECT solicitor_name, SUM(total_amount) AS total_amount, COUNT(*) AS qty
        FROM base GROUP BY solicitor_name ORDER BY total_amount DESC LIMIT 10
      ) r
    ),
    'top10_by_qty', (
      SELECT json_agg(r ORDER BY r.qty DESC)
      FROM (
        SELECT solicitor_name, COUNT(*) AS qty, SUM(total_amount) AS total_amount
        FROM base GROUP BY solicitor_name ORDER BY qty DESC LIMIT 10
      ) r
    )
  )
  FROM base;
$$;


-- ============================================================
-- 8. ANALYZE — forçar atualização das estatísticas do planner
--    (n_live_tup zerado em várias tabelas = planner com dados velhos)
-- ============================================================
ANALYZE public.fiscal_documents;
ANALYZE public.freshservice_sync_log;
ANALYZE public.freshservice_tickets;
ANALYZE public.payfly_reservations;
ANALYZE public.monitored_systems;
ANALYZE public.profiles;
ANALYZE public.performance_cycles;
ANALYZE public.performance_indicator_scores;
ANALYZE public.performance_managements;
