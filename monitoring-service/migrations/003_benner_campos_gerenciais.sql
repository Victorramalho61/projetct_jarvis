-- Snapshot diário de vendas sem centro de custo (campo gerencial do cadastro
-- do cliente) entre clientes que cadastram centro de custo válido no Benner.
-- Contratos Benner (BB_CLIENTECONTRATOS.OBRIGA*) não são usados na prática —
-- o sinal real de "cliente usa a feature" é BB_CLIENTECC.VALIDO='S'.

CREATE TABLE IF NOT EXISTS benner_campos_gerenciais_snapshots (
    id             BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    capturado_em   TIMESTAMPTZ NOT NULL DEFAULT now(),
    periodo_dias   INT         NOT NULL DEFAULT 90,
    -- {"total": n, "sem_cc": n, "pct": n}
    aereo          JSONB       NOT NULL DEFAULT '{}',
    vendas_gerais  JSONB       NOT NULL DEFAULT '{}',
    -- [{"cliente":"...", "aereo_sem_cc":n, "vendas_sem_cc":n, "total_sem_cc":n}]
    por_cliente    JSONB       NOT NULL DEFAULT '[]'
);

CREATE INDEX IF NOT EXISTS idx_benner_campos_gerenciais_capturado
    ON benner_campos_gerenciais_snapshots (capturado_em DESC);

ALTER TABLE benner_campos_gerenciais_snapshots ENABLE ROW LEVEL SECURITY;

CREATE POLICY "service_role_full" ON benner_campos_gerenciais_snapshots
    FOR ALL TO service_role USING (true) WITH CHECK (true);

CREATE POLICY "authenticated_read" ON benner_campos_gerenciais_snapshots
    FOR SELECT TO authenticated USING (true);
