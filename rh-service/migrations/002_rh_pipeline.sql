-- rh-service -- pipeline ordenado de etapas do processo de admissao
-- Execute apos 001_rh_schema.sql

CREATE TABLE IF NOT EXISTS rh_etapas_processo (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    ordem int NOT NULL UNIQUE,
    nome text NOT NULL UNIQUE,
    secao_responsavel_id uuid REFERENCES rh_secoes(id),
    created_at timestamptz NOT NULL DEFAULT now()
);

ALTER TABLE rh_vagas ADD CONSTRAINT fk_rh_vagas_etapa_atual
    FOREIGN KEY (etapa_atual_id) REFERENCES rh_etapas_processo(id);

-- Seed -- 16 etapas oficiais (ordem/descricao/secao da aba LISTA da planilha real)
INSERT INTO rh_etapas_processo (ordem, nome, secao_responsavel_id)
SELECT v.ordem, v.nome, rs.id
FROM (VALUES
    (1, 'DIVULGAÇÃO DA VAGA', 'RH'),
    (2, 'HUNTING', 'RH'),
    (3, 'TRIAGEM', 'RH'),
    (4, 'ENTREVISTA COM O RH', 'RH'),
    (5, 'APLICAÇÃO DE TESTES', 'RH'),
    (6, 'ENTREVISTA COM O LÍDER', 'RH'),
    (7, 'RETORNO DO LÍDER', 'RH'),
    (8, 'CONSULTAS BUONNY', 'RH'),
    (9, 'SOLICITAÇÃO DE DOCUMENTOS PARA ADMISSÃO', 'RH'),
    (10, 'AGENDAMENTO EXAMES', 'RH'),
    (11, 'ENCAMINHAMENTO EXAMES', 'SESMT'),
    (12, 'RECEPÇÃO DE DOCUMENTOS', 'RH/DP'),
    (13, 'INCLUSÃO NO BENNER', 'DP'),
    (14, 'INTEGRAÇÃO', 'RH/DP/AREAS AFINS'),
    (15, 'CONCLUÍDO', 'RH'),
    (16, 'CANCELADO', 'RH')
) AS v(ordem, nome, secao_nome)
JOIN rh_secoes rs ON rs.nome = v.secao_nome
ON CONFLICT (ordem) DO NOTHING;

CREATE INDEX IF NOT EXISTS idx_rh_vagas_etapa ON rh_vagas(etapa_atual_id);

ALTER TABLE rh_etapas_processo ENABLE ROW LEVEL SECURITY;
ALTER TABLE rh_etapas_processo FORCE ROW LEVEL SECURITY;
CREATE POLICY "rh_etapas_processo_service_role" ON rh_etapas_processo FOR ALL TO service_role USING (true) WITH CHECK (true);
