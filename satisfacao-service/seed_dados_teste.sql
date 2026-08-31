-- Dados de teste para validação manual do módulo Pesquisa de Satisfação de Clientes.
-- Não faz parte do schema oficial — script utilitário, pode ser reexecutado (idempotente via ON CONFLICT).

-- Clientes de teste
INSERT INTO sat_clientes (empresa_nome, contato_nome, contato_cargo, contato_email, contato_telefone) VALUES
  ('Empresa Teste Alfa',    'Ana Souza',   'Gerente de Viagens',        'ana.alfa@teste.voetur.com.br',     '(11) 90000-0001'),
  ('Empresa Teste Beta',    'Bruno Lima',  'Coordenador Financeiro',    'bruno.beta@teste.voetur.com.br',   '(11) 90000-0002'),
  ('Empresa Teste Gamma',   'Carla Dias',  'Analista de Compras',       'carla.gamma@teste.voetur.com.br',  '(11) 90000-0003'),
  ('Empresa Teste Delta',   'Diego Alves', 'Supervisor Administrativo', 'diego.delta@teste.voetur.com.br',  '(11) 90000-0004'),
  ('Empresa Teste Epsilon', 'Elisa Rocha', 'Gestora de Contrato',       'elisa.epsilon@teste.voetur.com.br','(11) 90000-0005')
ON CONFLICT DO NOTHING;

-- Campanha de teste (ano 2026), já em andamento
INSERT INTO sat_campanhas (ano, titulo, status, data_inicio, data_prazo, data_prazo_original, created_by)
VALUES (2026, 'Pesquisa de Satisfação 2026 (dados de teste)', 'em_andamento', CURRENT_DATE - 5, CURRENT_DATE + 16, CURRENT_DATE + 16, 'seed_teste')
ON CONFLICT (ano) DO NOTHING;

-- Snapshot das 5 perguntas ativas nesta campanha
INSERT INTO sat_campanha_perguntas (campanha_id, pergunta_id, ordem, texto_snapshot)
SELECT c.id, p.id, p.ordem, p.texto
FROM sat_campanhas c
CROSS JOIN sat_perguntas p
WHERE c.ano = 2026 AND p.ativa = true
ON CONFLICT (campanha_id, pergunta_id) DO NOTHING;

-- 4 clientes já responderam (canal manual, para simplificar o seed)
INSERT INTO sat_respostas (campanha_id, cliente_id, status, canal_resposta, respondido_at, lancado_por)
SELECT c.id, cl.id, 'respondido', 'manual_sgi', now() - (random() * interval '3 days'), 'seed_teste'
FROM sat_campanhas c, sat_clientes cl
WHERE c.ano = 2026
  AND cl.empresa_nome IN ('Empresa Teste Alfa','Empresa Teste Beta','Empresa Teste Gamma','Empresa Teste Delta')
ON CONFLICT (campanha_id, cliente_id) DO NOTHING;

-- 1 cliente ainda pendente, com link válido de verdade (dá pra testar o formulário público)
INSERT INTO sat_respostas (campanha_id, cliente_id, status, token, token_expires_at, primeiro_envio_at, total_envios)
SELECT c.id, cl.id, 'enviado', 'sKrA7lkDtQigVAaIfnbUChEQGqvXH2TetQDcic_H-WE', now() + interval '60 days', now() - interval '2 days', 1
FROM sat_campanhas c, sat_clientes cl
WHERE c.ano = 2026 AND cl.empresa_nome = 'Empresa Teste Epsilon'
ON CONFLICT (campanha_id, cliente_id) DO NOTHING;

-- Notas por pergunta — inclui notas ruins propositalmente em "Comercial" (2 de 4 = 50%) e "Atendimento" (1 de 4 = 25%)
-- para exercitar o alerta de >30%, a fila de triagem e o cálculo de aderência (4 de 5 = 80%).
WITH dados(empresa_nome, categoria, nota, comentario) AS (
  VALUES
    ('Empresa Teste Alfa',  'comercial',         2, 'Demora no retorno da proposta comercial.'),
    ('Empresa Teste Alfa',  'atendimento',       4, NULL),
    ('Empresa Teste Alfa',  'financeiro',        5, NULL),
    ('Empresa Teste Alfa',  'produtos_servicos', 3, NULL),
    ('Empresa Teste Alfa',  'indicacao',         4, NULL),

    ('Empresa Teste Beta',  'comercial',         1, 'Proposta comercial incompleta e divergente do solicitado.'),
    ('Empresa Teste Beta',  'atendimento',       3, NULL),
    ('Empresa Teste Beta',  'financeiro',        4, NULL),
    ('Empresa Teste Beta',  'produtos_servicos', 4, NULL),
    ('Empresa Teste Beta',  'indicacao',         5, NULL),

    ('Empresa Teste Gamma', 'comercial',         5, NULL),
    ('Empresa Teste Gamma', 'atendimento',       5, NULL),
    ('Empresa Teste Gamma', 'financeiro',        5, NULL),
    ('Empresa Teste Gamma', 'produtos_servicos', 5, NULL),
    ('Empresa Teste Gamma', 'indicacao',         5, NULL),

    ('Empresa Teste Delta', 'comercial',         4, NULL),
    ('Empresa Teste Delta', 'atendimento',       2, 'Atendimento demorado, precisei repetir informações para diferentes pessoas.'),
    ('Empresa Teste Delta', 'financeiro',        3, NULL),
    ('Empresa Teste Delta', 'produtos_servicos', 4, NULL),
    ('Empresa Teste Delta', 'indicacao',         3, NULL)
)
INSERT INTO sat_respostas_itens (resposta_id, campanha_pergunta_id, nota, comentario, triagem_status)
SELECT r.id, cp.id, d.nota, d.comentario,
       CASE WHEN d.nota <= 2 THEN 'pendente' ELSE 'nao_aplicavel' END
FROM dados d
JOIN sat_clientes cl  ON cl.empresa_nome = d.empresa_nome
JOIN sat_campanhas c  ON c.ano = 2026
JOIN sat_respostas r  ON r.campanha_id = c.id AND r.cliente_id = cl.id
JOIN sat_perguntas p  ON p.categoria = d.categoria
JOIN sat_campanha_perguntas cp ON cp.campanha_id = c.id AND cp.pergunta_id = p.id
ON CONFLICT (resposta_id, campanha_pergunta_id) DO NOTHING;
