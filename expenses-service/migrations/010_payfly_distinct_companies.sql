-- PayFly — RPC para listar clientes/empresas distintos (filtro em Dashboard e Vendas)
-- Aplicar via: docker exec -i jarvis-db-1 psql -U postgres -d postgres < migrations/010_payfly_distinct_companies.sql

CREATE OR REPLACE FUNCTION payfly_distinct_companies()
RETURNS TABLE(company_name text) AS $$
  SELECT DISTINCT company_name
  FROM payfly_reservations
  WHERE company_name IS NOT NULL AND company_name != ''
  ORDER BY company_name;
$$ LANGUAGE sql STABLE;
