-- =============================================================
-- VERIFICAÇÃO: Confirma que todas as medidas foram aplicadas
-- Todos os resultados devem retornar 0 linhas
-- =============================================================

\echo '=== 1. Tabelas public SEM RLS (esperado: 0 linhas) ==='
SELECT relname AS tabela
FROM pg_class c
JOIN pg_namespace n ON n.oid = c.relnamespace
WHERE n.nspname = 'public' AND c.relkind = 'r' AND relrowsecurity = false;

\echo '=== 2. Grants restantes para anon/authenticated (esperado: 0 linhas) ==='
SELECT grantee, table_name, privilege_type
FROM information_schema.role_table_grants
WHERE grantee IN ('anon','authenticated') AND table_schema = 'public'
ORDER BY table_name, grantee
LIMIT 20;

\echo '=== 3. Policies permissivas qual=true para authenticated (esperado: 0 linhas) ==='
SELECT tablename, policyname, roles, qual
FROM pg_policies
WHERE roles @> ARRAY['authenticated']::name[]
  AND qual = 'true';

\echo '=== 4. Tabelas com RLS ativo (deve listar todas) ==='
SELECT COUNT(*) AS tabelas_com_rls
FROM pg_class c
JOIN pg_namespace n ON n.oid = c.relnamespace
WHERE n.nspname = 'public' AND c.relkind = 'r' AND relrowsecurity = true;

\echo '=== 5. vault.secrets com RLS ==='
SELECT relname, relrowsecurity, relforcerowsecurity
FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
WHERE n.nspname = 'vault' AND c.relkind = 'r';

\echo '=== VERIFICACAO CONCLUIDA ==='
