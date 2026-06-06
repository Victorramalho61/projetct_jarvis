-- ============================================================
-- cards-service — Row Level Security para todas as 5 tabelas
-- Execute no Supabase SQL Editor DEPOIS de 001_cards_schema.sql
-- ============================================================
-- O serviço FastAPI usa SERVICE_ROLE_KEY que bypassa RLS.
-- RLS garante que anon / authenticated não acessem dados mesmo
-- via PostgREST direto (ex: vazamento de credencial, misconfiguration).
-- ============================================================

-- cards_clientes
ALTER TABLE cards_clientes ENABLE ROW LEVEL SECURITY;
ALTER TABLE cards_clientes FORCE ROW LEVEL SECURITY;
CREATE POLICY "cards_clientes_service_role" ON cards_clientes
    FOR ALL TO service_role USING (true) WITH CHECK (true);

-- cards_cartoes
ALTER TABLE cards_cartoes ENABLE ROW LEVEL SECURITY;
ALTER TABLE cards_cartoes FORCE ROW LEVEL SECURITY;
CREATE POLICY "cards_cartoes_service_role" ON cards_cartoes
    FOR ALL TO service_role USING (true) WITH CHECK (true);

-- cards_acessos (log imutável)
ALTER TABLE cards_acessos ENABLE ROW LEVEL SECURITY;
ALTER TABLE cards_acessos FORCE ROW LEVEL SECURITY;
CREATE POLICY "cards_acessos_service_role" ON cards_acessos
    FOR ALL TO service_role USING (true) WITH CHECK (true);

-- cards_solicitacoes
ALTER TABLE cards_solicitacoes ENABLE ROW LEVEL SECURITY;
ALTER TABLE cards_solicitacoes FORCE ROW LEVEL SECURITY;
CREATE POLICY "cards_solicitacoes_service_role" ON cards_solicitacoes
    FOR ALL TO service_role USING (true) WITH CHECK (true);

-- cards_permissoes
ALTER TABLE cards_permissoes ENABLE ROW LEVEL SECURITY;
ALTER TABLE cards_permissoes FORCE ROW LEVEL SECURITY;
CREATE POLICY "cards_permissoes_service_role" ON cards_permissoes
    FOR ALL TO service_role USING (true) WITH CHECK (true);

-- ============================================================
-- Verificação (execute após aplicar)
-- ============================================================
SELECT
    tablename,
    rowsecurity      AS rls_enabled,
    forcerowsecurity AS rls_forced
FROM pg_tables
WHERE tablename IN (
    'cards_clientes',
    'cards_cartoes',
    'cards_acessos',
    'cards_solicitacoes',
    'cards_permissoes'
)
ORDER BY tablename;
