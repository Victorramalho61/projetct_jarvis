-- Seed de permissões de teste para o módulo de cartões
--
-- Substitua os UUIDs pelos IDs reais dos usuários em auth.users
-- Para encontrar o UUID: SELECT id, email FROM users WHERE email = 'email@voetur.com.br';
--
-- Execute via Supabase SQL Editor após rodar a migration 001.

-- Exemplo de inserção manual (ajuste os UUIDs e e-mails):
/*
INSERT INTO cards_permissoes (user_id, user_login, user_nome, perfil, ativo)
VALUES
  ('UUID-DO-COLABORADOR', 'colaborador@voetur.com.br', 'Nome Colaborador', 'colaborador', true),
  ('UUID-DO-SUPERVISOR',  'supervisor@voetur.com.br',  'Nome Supervisor',  'supervisor',  true)
ON CONFLICT (user_id) DO UPDATE SET
  perfil = EXCLUDED.perfil,
  ativo  = true;
*/

-- Alternativa: use o script Python scripts/seed_test_users.py
-- que busca os usuários automaticamente pelo e-mail.
