-- rh-service -- corrige base de calculo do FGTS por perfil
-- A planilha do DP usa duas bases diferentes pro FGTS:
--   pct_fgts=2%  -> base = salario + provisao_13_ferias + ferias
--   pct_fgts=8%  -> base = salario (padrao legal CLT)
-- Confirmado nas 17 abas: 100% de correlacao com o pct_fgts, mas guardamos
-- como coluna explicita em vez de inferir pelo valor do percentual.

ALTER TABLE rh_perfis_calculo ADD COLUMN IF NOT EXISTS fgts_base_com_provisoes boolean NOT NULL DEFAULT false;

UPDATE rh_perfis_calculo SET fgts_base_com_provisoes = true WHERE pct_fgts = 2;
