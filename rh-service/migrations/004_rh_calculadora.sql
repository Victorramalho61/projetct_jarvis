-- rh-service -- Fase 3: calculadora de custos de admissao (perfis do DP)
-- Execute apos 001/002/003. Fonte: 'Custas para Admissao.xlsx' (17 abas)

CREATE TABLE IF NOT EXISTS rh_perfis_calculo (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    nome text UNIQUE NOT NULL,
    vale_transporte numeric(12,2) NOT NULL DEFAULT 0,
    vale_alimentacao numeric(12,2) NOT NULL DEFAULT 0,
    seguro_vida numeric(12,2) NOT NULL DEFAULT 0,
    plano_saude numeric(12,2) NOT NULL DEFAULT 0,
    uniforme numeric(12,2) NOT NULL DEFAULT 0,
    cracha_cordao numeric(12,2) NOT NULL DEFAULT 0,
    aso numeric(12,2) NOT NULL DEFAULT 0,
    insalubridade numeric(12,2) NOT NULL DEFAULT 0,
    periculosidade numeric(12,2) NOT NULL DEFAULT 0,
    aparelhos_eletronicos numeric(12,2) NOT NULL DEFAULT 0,
    outros_creditos numeric(12,2) NOT NULL DEFAULT 0,
    taxa_administrativa numeric(12,2) NOT NULL DEFAULT 0,
    pct_inss numeric(6,3) NOT NULL DEFAULT 0,
    pct_fgts numeric(6,3) NOT NULL DEFAULT 0,
    pct_multa_fgts numeric(6,3) NOT NULL DEFAULT 40,
    created_at timestamptz NOT NULL DEFAULT now()
);

ALTER TABLE rh_vagas ADD COLUMN IF NOT EXISTS perfil_calculo_id uuid REFERENCES rh_perfis_calculo(id);
ALTER TABLE rh_vagas ADD COLUMN IF NOT EXISTS custo_total numeric(12,2);
ALTER TABLE rh_vagas ADD COLUMN IF NOT EXISTS calculo_detalhado jsonb;
CREATE INDEX IF NOT EXISTS idx_rh_vagas_perfil_calculo ON rh_vagas(perfil_calculo_id);

INSERT INTO rh_perfis_calculo (nome, vale_transporte, vale_alimentacao, seguro_vida, plano_saude, uniforme, cracha_cordao, aso, taxa_administrativa, pct_inss, pct_fgts, pct_multa_fgts) VALUES
    ('JOVEM APRENDIZ VIAGENS', 231, 150, 0, 205.05, 13.75, 0.5, 0.83, 118, 26.3, 2.0, 40.0),
    ('JOVEM APRENDIZ VTC', 231, 150, 0, 491.53, 13.75, 0.5, 0.83, 118, 27.3, 2.0, 40.0),
    ('Clube de Lazer', 630, 977.76, 0, 491.53, 13.75, 0.5, 0.83, 0, 26.3, 2.0, 40.0),
    ('Vip Cargas BSB', 231, 1488.67, 8.98, 205.05, 13.75, 0.5, 0.83, 0, 26.7, 8.0, 40.0),
    ('Vip Cargas SP', 630, 1488.67, 8.98, 491.53, 13.75, 0.5, 0.83, 0, 28.2, 8.0, 40.0),
    ('Vip Cargas RJ', 336, 1488.67, 8.98, 319.6, 13.75, 0.5, 0.83, 0, 26.7, 8.0, 40.0),
    ('Vip Locadora', 231, 859.11, 4.25, 491.53, 13.75, 0.5, 0.83, 0, 1.0, 8.0, 40.0),
    ('Vip Marina', 231, 588, 0, 491.53, 13.75, 0.5, 0.83, 0, 1.0, 8.0, 40.0),
    ('Promo e Eventos', 231, 777, 0, 147, 13.75, 0.5, 0.83, 0, 26.3, 8.0, 50.0),
    ('Operadora MTZ', 231, 777, 0, 147, 13.75, 0.5, 0.83, 0, 26.3, 8.0, 40.0),
    ('Turismo SP', 630, 977.76, 0, 491.52, 13.75, 0.5, 0.83, 0, 26.3, 2.0, 40.0),
    ('Turismo RJ', 546, 756, 0, 446.23, 13.75, 0.5, 0.83, 0, 26.3, 2.0, 40.0),
    ('Turismo MTZ', 231, 821.1, 0, 205.05, 13.75, 0.5, 0.83, 0, 26.3, 2.0, 40.0),
    ('VTC MTZ', 231, 948.2, 16.27, 491.53, 13.75, 0.5, 0.83, 0, 29.4126, 8.0, 40.0),
    ('VTC Brasil 21', 231, 948.2, 16.27, 491.53, 13.75, 0.5, 0.83, 0, 27.8, 8.0, 40.0),
    ('VTC RJ', 0, 651, 18.74, 544.34, 13.75, 0.5, 0.83, 0, 29.2257, 8.0, 40.0),
    ('VTC GRU', 630, 823.2, 19.55, 491.53, 13.75, 0.5, 0.83, 0, 27.3, 8.0, 40.0)
ON CONFLICT (nome) DO NOTHING;

ALTER TABLE rh_perfis_calculo ENABLE ROW LEVEL SECURITY;
ALTER TABLE rh_perfis_calculo FORCE ROW LEVEL SECURITY;
CREATE POLICY "rh_perfis_calculo_service_role" ON rh_perfis_calculo FOR ALL TO service_role USING (true) WITH CHECK (true);
