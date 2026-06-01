-- =============================================================
-- SEGURANÇA: Remove policies permissivas para authenticated (qual=true)
-- e adiciona policy RESTRICTIVE de negação explícita para anon
-- Executar: docker exec jarvis-db-1 psql -U postgres -d postgres -f /tmp/03_harden_policies.sql
-- =============================================================

\echo 'Removendo policies qual=true para authenticated...'

DO $$
DECLARE
  r RECORD;
  cnt INTEGER := 0;
BEGIN
  FOR r IN
    SELECT schemaname, tablename, policyname
    FROM pg_policies
    WHERE roles @> ARRAY['authenticated']::name[]
      AND qual = 'true'
  LOOP
    EXECUTE format('DROP POLICY IF EXISTS %I ON %I.%I',
      r.policyname, r.schemaname, r.tablename);
    cnt := cnt + 1;
    RAISE NOTICE 'Removida policy: %.% -> %', r.schemaname, r.tablename, r.policyname;
  END LOOP;
  RAISE NOTICE '% policies permissivas removidas', cnt;
END $$;

\echo 'Adicionando policy RESTRICTIVE de negacao para anon...'

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
    BEGIN
      EXECUTE format(
        'CREATE POLICY anon_no_access ON %I.%I
         AS RESTRICTIVE TO anon
         USING (false)
         WITH CHECK (false)',
        r.schemaname, r.tablename
      );
      cnt := cnt + 1;
    EXCEPTION WHEN duplicate_object THEN
      NULL; -- policy ja existe, ignorar
    END;
  END LOOP;
  RAISE NOTICE 'Policy de negacao criada em % tabelas', cnt;
END $$;

\echo 'Hardening de policies concluido.'
