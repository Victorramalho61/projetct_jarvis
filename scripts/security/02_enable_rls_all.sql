-- =============================================================
-- SEGURANÇA: Habilita RLS em todas as tabelas do schema public
-- Com RLS ativo e sem policies para anon/authenticated = default DENY
-- service_role tem bypassrls nativamente — backend não é afetado
-- Executar: docker exec jarvis-db-1 psql -U postgres -d postgres -f /tmp/02_enable_rls_all.sql
-- =============================================================

\echo 'Habilitando RLS em todas as tabelas public...'

DO $$
DECLARE
  r RECORD;
  cnt INTEGER := 0;
BEGIN
  FOR r IN
    SELECT schemaname, tablename
    FROM pg_tables
    WHERE schemaname = 'public'
  LOOP
    EXECUTE format('ALTER TABLE %I.%I ENABLE ROW LEVEL SECURITY',  r.schemaname, r.tablename);
    EXECUTE format('ALTER TABLE %I.%I FORCE ROW LEVEL SECURITY',   r.schemaname, r.tablename);
    cnt := cnt + 1;
  END LOOP;
  RAISE NOTICE 'RLS habilitado em % tabelas', cnt;
END $$;

-- vault.secrets: contém segredos criptografados — blindar também
ALTER TABLE vault.secrets ENABLE ROW LEVEL SECURITY;
ALTER TABLE vault.secrets FORCE ROW LEVEL SECURITY;

\echo 'RLS habilitado com sucesso.'
