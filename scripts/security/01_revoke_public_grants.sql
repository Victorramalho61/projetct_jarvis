-- =============================================================
-- SEGURANÇA: Revoga acesso direto de anon e authenticated
-- O backend usa service_role (bypassa RLS) — não é afetado
-- Executar: docker exec jarvis-db-1 psql -U postgres -d postgres -f /tmp/01_revoke_public_grants.sql
-- =============================================================

\echo 'Revogando grants de anon e authenticated...'

REVOKE ALL PRIVILEGES ON ALL TABLES    IN SCHEMA public FROM anon;
REVOKE ALL PRIVILEGES ON ALL TABLES    IN SCHEMA public FROM authenticated;
REVOKE ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public FROM anon;
REVOKE ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public FROM authenticated;
REVOKE ALL PRIVILEGES ON ALL FUNCTIONS IN SCHEMA public FROM anon;
REVOKE ALL PRIVILEGES ON ALL FUNCTIONS IN SCHEMA public FROM authenticated;

-- Impede herança automática em tabelas futuras
ALTER DEFAULT PRIVILEGES IN SCHEMA public REVOKE ALL ON TABLES    FROM anon;
ALTER DEFAULT PRIVILEGES IN SCHEMA public REVOKE ALL ON TABLES    FROM authenticated;
ALTER DEFAULT PRIVILEGES IN SCHEMA public REVOKE ALL ON SEQUENCES FROM anon;
ALTER DEFAULT PRIVILEGES IN SCHEMA public REVOKE ALL ON SEQUENCES FROM authenticated;
ALTER DEFAULT PRIVILEGES IN SCHEMA public REVOKE ALL ON FUNCTIONS FROM anon;
ALTER DEFAULT PRIVILEGES IN SCHEMA public REVOKE ALL ON FUNCTIONS FROM authenticated;

\echo 'Grants revogados com sucesso.'
