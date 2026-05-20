-- Migration 003 — Campos de agrupamento + seed inicial de empresas

ALTER TABLE fiscal_companies
  ADD COLUMN IF NOT EXISTS grupo  text,   -- vtclog | voetur | payfly
  ADD COLUMN IF NOT EXISTS tipo   text,   -- matriz | filial
  ADD COLUMN IF NOT EXISTS cidade text;

-- VTC Operadora Logística Ltda (7 CNPJs)
INSERT INTO fiscal_companies
  (cnpj, nome, regime, uf_sede, cidade, grupo, tipo,
   sync_nfe_ativo, sync_cte_ativo, sync_nfse_ativo)
VALUES
  ('24893687000108', 'VTC Operadora Logística Ltda', 'lucro_real', 'DF', 'Brasília',       'vtclog', 'matriz', true,  true,  false),
  ('24893687000280', 'VTC Operadora Logística Ltda', 'lucro_real', 'RJ', 'Rio de Janeiro',  'vtclog', 'filial', true,  true,  false),
  ('24893687000361', 'VTC Operadora Logística Ltda', 'lucro_real', 'PE', 'Recife',          'vtclog', 'filial', true,  true,  false),
  ('24893687001171', 'VTC Operadora Logística Ltda', 'lucro_real', 'SP', 'Guarulhos',       'vtclog', 'filial', true,  true,  false),
  ('24893687001414', 'VTC Operadora Logística Ltda', 'lucro_real', 'MG', 'Contagem',        'vtclog', 'filial', true,  true,  false),
  ('24893687001503', 'VTC Operadora Logística Ltda', 'lucro_real', 'DF', 'Brasília (fil.)', 'vtclog', 'filial', true,  true,  false),
  ('24893687001767', 'VTC Operadora Logística Ltda', 'lucro_real', 'SP', 'Campinas',        'vtclog', 'filial', true,  true,  false),
-- Voetur
  ('01017250000105', 'Voetur Turismo e Representações Ltda', 'lucro_real', 'DF', 'Brasília', 'voetur', 'matriz', true, false, true),
-- Payfly (sem certificado A1 por enquanto — sync desativado)
  ('66649752000196', 'Payfly Soluções Integradas em Turismo e Tecnologia Ltda', 'lucro_real', 'SP', 'São Paulo', 'payfly', 'matriz', false, false, false)
ON CONFLICT (cnpj) DO NOTHING;
