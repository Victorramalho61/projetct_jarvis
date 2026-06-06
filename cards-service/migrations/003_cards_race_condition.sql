-- ============================================================
-- cards-service — Registro de primeira revelação por par (cartao_id, localizador_os)
-- Mitiga race condition no caminho de reveal direto.
-- Execute no Supabase SQL Editor DEPOIS de 001_cards_schema.sql
-- ============================================================
-- CONTEXTO DO PROBLEMA:
--   Dois requests simultâneos para o mesmo (cartao_id, localizador_os)
--   inédito podem ambos passar pelo check "par não existe em cards_acessos"
--   antes que qualquer insert seja commitado, revelando o cartão duas vezes
--   sem acionar o fluxo de aprovação.
--
-- POR QUE NÃO USAR UNIQUE (cartao_id, localizador_os) EM cards_acessos:
--   Acessos pós-aprovação também inserem nessa tabela com o MESMO par
--   (é exatamente o log do segundo uso do localizador via aprovação).
--   Um UNIQUE constraint quebraria o segundo insert legítimo.
--
-- MITIGAÇÃO IMPLEMENTADA — tabela de locks de primeiro acesso:
--   Uma tabela separada com UNIQUE (cartao_id, localizador_os) garante
--   atomicidade apenas para o "primeiro reveal direto". Acessos subsequentes
--   (via cards_solicitacoes → aprovação) não tocam nesta tabela.
-- ============================================================

CREATE TABLE IF NOT EXISTS cards_reveal_grants (
    id         uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    cartao_id  uuid NOT NULL REFERENCES cards_cartoes(id) ON DELETE RESTRICT,
    localizador_os text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (cartao_id, localizador_os)
);

-- RLS: mesma política das outras tabelas
ALTER TABLE cards_reveal_grants ENABLE ROW LEVEL SECURITY;
ALTER TABLE cards_reveal_grants FORCE ROW LEVEL SECURITY;
CREATE POLICY "cards_reveal_grants_service_role" ON cards_reveal_grants
    FOR ALL TO service_role USING (true) WITH CHECK (true);

-- Índice para o check de antirreuso existente (já coberto pelo UNIQUE, mas explícito)
CREATE INDEX IF NOT EXISTS idx_cards_reveal_grants_par
    ON cards_reveal_grants (cartao_id, localizador_os);

-- ============================================================
-- ATUALIZAÇÃO NECESSÁRIA NO CÓDIGO (routes/cards.py):
-- 1. Ao verificar par inédito, checar cards_reveal_grants, não cards_acessos
-- 2. INSERT em cards_reveal_grants com ON CONFLICT DO NOTHING
--    Se affected_rows == 0 → par já existe → criar solicitação (antirreuso)
--    Se affected_rows == 1 → par inédito → prosseguir com reveal + log em cards_acessos
-- Isso garante que o "primeiro reveal" seja atômico no nível de banco.
-- ============================================================
