-- Benner integration log snapshots
-- Snapshot comprimido 1x/dia pelo scheduler (07h BRT)
-- Acumula indefinidamente — sem retenção automática

CREATE TABLE IF NOT EXISTS benner_snapshots (
    id             BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    capturado_em   TIMESTAMPTZ NOT NULL DEFAULT now(),
    total          INT         NOT NULL DEFAULT 0,
    ok             INT         NOT NULL DEFAULT 0,
    erros          INT         NOT NULL DEFAULT 0,
    taxa_erro_pct  NUMERIC(5,2) NOT NULL DEFAULT 0,
    -- {"AirTicket":[122,3], "Pedido":[0,27]}  → [ok, erros]
    por_produto    JSONB       NOT NULL DEFAULT '{}',
    -- [{"i":id,"p":"produto","r":"reserva","s":situacao,"m":"msg150","t":"iso"}]
    erros_recentes JSONB       NOT NULL DEFAULT '[]'
);

CREATE INDEX IF NOT EXISTS idx_benner_snapshots_capturado
    ON benner_snapshots (capturado_em DESC);

ALTER TABLE benner_snapshots ENABLE ROW LEVEL SECURITY;

CREATE POLICY "service_role_full" ON benner_snapshots
    FOR ALL TO service_role USING (true) WITH CHECK (true);

CREATE POLICY "authenticated_read" ON benner_snapshots
    FOR SELECT TO authenticated USING (true);
