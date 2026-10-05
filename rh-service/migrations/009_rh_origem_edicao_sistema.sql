-- rh-service -- preserva o trabalho feito direto no Jarvis no import da planilha (pedido do RH, 2026-10-05).
-- origem: 'planilha' (veio de um import) | 'sistema' (criada pelo RH no Jarvis).
--   Só vaga de origem 'planilha' que saiu da planilha vai para o histórico.
-- editado_sistema_em: última edição feita na tela do Jarvis (PATCH). Edição posterior ao
--   upload anterior não é sobrescrita pelo import seguinte.
ALTER TABLE rh_vagas ADD COLUMN IF NOT EXISTS origem text NOT NULL DEFAULT 'sistema'
    CHECK (origem IN ('sistema', 'planilha'));
ALTER TABLE rh_vagas ADD COLUMN IF NOT EXISTS editado_sistema_em timestamptz;

-- Backfill origem: criadas dentro da janela de algum import (created_at usa now() do banco)
UPDATE rh_vagas v SET origem = 'planilha'
WHERE EXISTS (
    SELECT 1 FROM rh_uploads u
    WHERE v.created_at BETWEEN u.criado_em - interval '15 minutes' AND u.criado_em
);

-- Backfill edições no Jarvis depois do último import (24/09 16:39). updated_at era gravado com
-- datetime.utcnow() sem fuso e o banco interpretou como -03 => valores 3h adiantados.
UPDATE rh_vagas SET editado_sistema_em = updated_at - interval '3 hours'
WHERE updated_at > '2026-09-24 19:39:03.5-03';
