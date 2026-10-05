-- rh-service -- planilha de controle de vagas como fonte da verdade (pedido do R&S, 2026-10-01).
-- Backup antes da migration: E:\claudecode\backups\rh_*_2026-10-05.csv (fora do repositório).

-- 1. Histórico: vaga fora da última planilha importada não aparece em telas/indicadores.
--    O import marca historico=true em tudo que não veio na planilha (reversível, nada é apagado).
ALTER TABLE rh_vagas ADD COLUMN IF NOT EXISTS historico boolean NOT NULL DEFAULT false;
ALTER TABLE rh_vagas ADD COLUMN IF NOT EXISTS ultimo_upload_id uuid REFERENCES rh_uploads(id) ON DELETE SET NULL;
CREATE INDEX IF NOT EXISTS idx_rh_vagas_historico ON rh_vagas (historico);

-- 2. Recrutadores ativos/inativos: o filtro Analista mostra só os ativos.
--    O import sincroniza com a coluna RECRUTADORES RESPONSÁVEIS da aba LISTAS SUSPENSAS.
ALTER TABLE rh_analistas ADD COLUMN IF NOT EXISTS ativo boolean NOT NULL DEFAULT true;

-- Grafia duplicada / placeholder, sem nenhuma vaga
DELETE FROM rh_analistas a
WHERE a.nome IN ('MONICA NOBRE', 'NÃO INFORMADO')
  AND NOT EXISTS (SELECT 1 FROM rh_vagas v WHERE v.responsavel_id = a.id);

UPDATE rh_analistas SET ativo = nome IN (
    'MARLIZE GOMES', 'KAIRO MOTA', 'LILIAN CARDOSO', 'CONSULTORIA/RACHEL', 'DEISE FERNANDES'
);

-- 3. Status com os mesmos nomes da planilha (aba LISTAS SUSPENSAS, "STATUS DA VAGA"):
--    ABERTA · PREENCHIDA/FECHADA · CANCELADA · EM STANDBY. Mesmo id: rh_vagas não muda.
DELETE FROM rh_status_vaga s
WHERE s.nome IN ('EM STANDBY', 'REABERTO')
  AND NOT EXISTS (SELECT 1 FROM rh_vagas v WHERE v.status_id = s.id);
UPDATE rh_status_vaga SET nome = 'PREENCHIDA/FECHADA' WHERE nome = 'CONCLUÍDO';
UPDATE rh_status_vaga SET nome = 'CANCELADA' WHERE nome = 'CANCELADO';
UPDATE rh_status_vaga SET nome = 'EM STANDBY' WHERE nome = 'CONGELADO';

-- 4. Nº de requisição digitado com ponto -> barra, igual ao import
UPDATE rh_vagas SET numero_requisicao = 'TUR.ADM.290/26'
WHERE numero_requisicao = 'TUR.ADM.290.26'
  AND NOT EXISTS (SELECT 1 FROM rh_vagas WHERE numero_requisicao = 'TUR.ADM.290/26');
