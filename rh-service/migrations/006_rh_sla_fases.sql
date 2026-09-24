-- rh-service -- SLA separado por fase (R&S e Admissão) + funil novo de 14 etapas
-- Modelo da planilha "Controle de Vagas Voetur Nova" (2026-09). Execute após 005.

-- ── Campos novos da vaga ─────────────────────────────────────────────────────
ALTER TABLE rh_vagas ADD COLUMN IF NOT EXISTS nome_substituido text;
ALTER TABLE rh_vagas ADD COLUMN IF NOT EXISTS observacoes text;
ALTER TABLE rh_vagas ADD COLUMN IF NOT EXISTS data_fechamento_rs date;
ALTER TABLE rh_vagas ADD COLUMN IF NOT EXISTS data_confirmacao_contratacao date;
ALTER TABLE rh_vagas ADD COLUMN IF NOT EXISTS sla_rs_dias int;
ALTER TABLE rh_vagas ADD COLUMN IF NOT EXISTS sla_admissao_dias int;
ALTER TABLE rh_vagas ADD COLUMN IF NOT EXISTS data_inicio_etapa date;
ALTER TABLE rh_vagas ADD COLUMN IF NOT EXISTS sla_etapa_externa_dias int;

-- ── Tabela de SLA por cargo (aba "SLA" da planilha) ──────────────────────────
CREATE TABLE IF NOT EXISTS rh_sla_cargos (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    cargo_nome text UNIQUE NOT NULL,   -- normalizado: upper + trim
    nivel text,
    rs int,                            -- dias de R&S
    link int,                          -- S LINK ADMISSIONAL
    exames int,
    documentos int,                    -- ENTREGA DE DOCUMENTOS AO DP
    empresa text,
    updated_at timestamptz NOT NULL DEFAULT now()
);

-- ── Funil: fase/externa/ativo por etapa ──────────────────────────────────────
ALTER TABLE rh_etapas_processo ADD COLUMN IF NOT EXISTS ativo boolean NOT NULL DEFAULT true;
ALTER TABLE rh_etapas_processo ADD COLUMN IF NOT EXISTS fase text;
ALTER TABLE rh_etapas_processo ADD COLUMN IF NOT EXISTS externa boolean NOT NULL DEFAULT false;
DO $$ BEGIN
    ALTER TABLE rh_etapas_processo ADD CONSTRAINT rh_etapas_fase_chk CHECK (fase IN ('RS', 'ADMISSAO', 'FIM'));
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

INSERT INTO rh_secoes (nome) VALUES ('LIDER') ON CONFLICT (nome) DO NOTHING;

-- Tira as etapas atuais da faixa 1..16 (ordem é UNIQUE) antes de gravar o funil novo
UPDATE rh_etapas_processo SET ordem = ordem + 1000 WHERE ordem < 1000;

INSERT INTO rh_etapas_processo (ordem, nome, secao_responsavel_id, fase, externa, ativo)
SELECT v.ordem, v.nome, rs.id, v.fase, v.secao <> 'RH', true
FROM (VALUES
    (1,  'DIVULGAÇÃO DA VAGA',                'RH',    'RS'),
    (2,  'TRIAGEM',                           'RH',    'RS'),
    (3,  'ENTREVISTA COM O RH',               'RH',    'RS'),
    (4,  'APLICAÇÃO DE TESTES',               'RH',    'RS'),
    (5,  'CONSULTAS GR',                      'RH',    'RS'),
    (6,  'ENTREVISTA COM O LÍDER',            'LIDER', 'RS'),
    (7,  'RETORNO DO LÍDER',                  'LIDER', 'RS'),
    (8,  'SOLICITAÇÃO LINK ADMISSIONAL',      'RH',    'ADMISSAO'),
    (9,  'ENVIO DO LINK ADMISSIONAL',         'DP',    'ADMISSAO'),
    (10, 'SOLICITAÇÃO DE AGENDAMENTO DE ASO', 'RH',    'ADMISSAO'),
    (11, 'ENVIO DO ASO',                      'SESMT', 'ADMISSAO'),
    (12, 'RECEPÇÃO DE DOCUMENTOS',            'DP',    'ADMISSAO'),
    (13, 'ACOMPANHAMENTO DA DOCUMENTAÇÃO',    'RH',    'ADMISSAO'),
    (14, 'APROVAÇÃO DO LÍDER',                'LIDER', 'ADMISSAO'),
    (15, 'CONCLUÍDO',                         'RH',    'FIM'),
    (16, 'CANCELADO',                         'RH',    'FIM')
) AS v(ordem, nome, secao, fase)
JOIN rh_secoes rs ON rs.nome = v.secao
ON CONFLICT (nome) DO UPDATE SET
    ordem = EXCLUDED.ordem,
    secao_responsavel_id = EXCLUDED.secao_responsavel_id,
    fase = EXCLUDED.fase,
    externa = EXCLUDED.externa,
    ativo = true;

-- Etapas do funil antigo (HUNTING, CONSULTAS BUONNY, INCLUSÃO NO BENNER...) ficam
-- inativas: vagas históricas continuam apontando pra elas, mas não aparecem mais.
UPDATE rh_etapas_processo SET ativo = false WHERE ordem >= 1000;

-- ── Histórico de etapas (prazo por etapa daqui pra frente) ───────────────────
CREATE TABLE IF NOT EXISTS rh_vagas_etapas_hist (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    vaga_id uuid NOT NULL REFERENCES rh_vagas(id) ON DELETE CASCADE,
    etapa_id uuid NOT NULL REFERENCES rh_etapas_processo(id),
    inicio date NOT NULL,
    fim date,
    created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_rh_etapas_hist_vaga ON rh_vagas_etapas_hist(vaga_id);
CREATE INDEX IF NOT EXISTS idx_rh_etapas_hist_etapa ON rh_vagas_etapas_hist(etapa_id);

-- ── Empresas: nomes oficiais da lista "EMPRESAS DO GRUPO" ────────────────────
-- VOETUR TURISMO passou a se chamar VOETUR VIAGENS (mesmo prefixo TUR).
UPDATE rh_empresas SET nome = 'VOETUR VIAGENS'
WHERE nome = 'VOETUR TURISMO' AND NOT EXISTS (SELECT 1 FROM rh_empresas WHERE nome = 'VOETUR VIAGENS');
INSERT INTO rh_empresas (nome, prefixo_requisicao) VALUES
    ('VTCLOG BRASIL 21', 'VTC'),
    ('VTCLOG AEROPORTO', 'VTC'),
    ('VIP SERVICE RECEPTIVOS', 'LOC'),
    ('BRASÍLIA EMPREENDIMENTOS IMOBILIÁRIOS', 'RES')
ON CONFLICT (nome) DO NOTHING;

ALTER TABLE rh_sla_cargos ENABLE ROW LEVEL SECURITY;
ALTER TABLE rh_vagas_etapas_hist ENABLE ROW LEVEL SECURITY;
DO $$ BEGIN
    CREATE POLICY "service_role_all" ON rh_sla_cargos FOR ALL TO service_role USING (true) WITH CHECK (true);
EXCEPTION WHEN duplicate_object THEN NULL; END $$;
DO $$ BEGIN
    CREATE POLICY "service_role_all" ON rh_vagas_etapas_hist FOR ALL TO service_role USING (true) WITH CHECK (true);
EXCEPTION WHEN duplicate_object THEN NULL; END $$;
NOTIFY pgrst, 'reload schema';
