-- rh-service -- "EM ANDAMENTO" passa a se chamar "ABERTA" (termo da planilha nova).
-- Mesmo id: as vagas mudam de nome de status sem UPDATE em rh_vagas.
UPDATE rh_status_vaga SET nome = 'ABERTA'
WHERE nome = 'EM ANDAMENTO' AND NOT EXISTS (SELECT 1 FROM rh_status_vaga WHERE nome = 'ABERTA');

-- Vagas com abertura até 31/12/2025 foram removidas em 2026-09-24 a pedido do RH
-- (backup CSV fora do repositório: E:\claudecode\backups\rh_vagas_ate_2025_2026-09-24.csv).
