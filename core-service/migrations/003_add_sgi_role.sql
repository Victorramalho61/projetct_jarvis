-- Corrige o CHECK de profiles.role (desatualizado — só listava 'admin'/'user',
-- mas roles como 'rh'/'gerente'/'coordenador_supervisor'/'administrativo_operacional'
-- já estão em uso) e adiciona o novo role 'sgi' (módulo Pesquisa de Satisfação de Clientes).

DO $$
DECLARE
  constraint_name text;
BEGIN
  SELECT con.conname INTO constraint_name
  FROM pg_constraint con
  JOIN pg_class rel ON rel.oid = con.conrelid
  JOIN pg_attribute att ON att.attrelid = rel.oid
  WHERE rel.relname = 'profiles'
    AND con.contype = 'c'
    AND con.conkey = ARRAY[att.attnum]
    AND att.attname = 'role';

  IF constraint_name IS NOT NULL THEN
    EXECUTE format('ALTER TABLE profiles DROP CONSTRAINT %I', constraint_name);
  END IF;
END $$;

ALTER TABLE profiles ADD CONSTRAINT profiles_role_check
  CHECK (role IN ('admin', 'user', 'rh', 'gerente', 'coordenador_supervisor', 'administrativo_operacional', 'sgi'));
