-- Dados de teste para validação manual do módulo Pesquisa de Satisfação de Clientes.
-- Não faz parte do schema oficial — script utilitário, pode ser reexecutado (idempotente via ON CONFLICT).

-- Clientes de teste
-- Nota: sat_clientes não tem UNIQUE em empresa_nome/e-mail (por design — um cliente pode
-- trocar de contato entre campanhas), então usamos NOT EXISTS em vez de ON CONFLICT
-- (que seria um no-op sem uma constraint pra servir de "arbiter" e duplicaria a cada execução).
INSERT INTO sat_clientes (empresa_nome, contato_nome, contato_cargo, contato_email, contato_telefone)
SELECT v.empresa_nome, v.contato_nome, v.contato_cargo, v.contato_email, v.contato_telefone
FROM (VALUES
  ('Empresa Teste Alfa',    'Ana Souza',   'Gerente de Viagens',        'ana.alfa@teste.voetur.com.br',     '(11) 90000-0001'),
  ('Empresa Teste Beta',    'Bruno Lima',  'Coordenador Financeiro',    'bruno.beta@teste.voetur.com.br',   '(11) 90000-0002'),
  ('Empresa Teste Gamma',   'Carla Dias',  'Analista de Compras',       'carla.gamma@teste.voetur.com.br',  '(11) 90000-0003'),
  ('Empresa Teste Delta',   'Diego Alves', 'Supervisor Administrativo', 'diego.delta@teste.voetur.com.br',  '(11) 90000-0004'),
  ('Empresa Teste Epsilon', 'Elisa Rocha', 'Gestora de Contrato',       'elisa.epsilon@teste.voetur.com.br','(11) 90000-0005')
) AS v(empresa_nome, contato_nome, contato_cargo, contato_email, contato_telefone)
WHERE NOT EXISTS (SELECT 1 FROM sat_clientes WHERE empresa_nome = v.empresa_nome);

-- Campanha de teste (ano 2026), já em andamento
INSERT INTO sat_campanhas (ano, titulo, status, data_inicio, data_prazo, data_prazo_original, ms_forms_url, created_by)
VALUES (2026, 'Pesquisa de Satisfação 2026 (dados de teste)', 'em_andamento', CURRENT_DATE - 5, CURRENT_DATE + 16, CURRENT_DATE + 16, 'https://forms.office.com/r/exemplo-teste', 'seed_teste')
ON CONFLICT (ano) DO NOTHING;

-- Garante o link do Forms mesmo se a campanha já existia de uma rodada anterior do seed
UPDATE sat_campanhas SET ms_forms_url = 'https://forms.office.com/r/exemplo-teste'
WHERE ano = 2026 AND (ms_forms_url IS NULL OR ms_forms_url = '');

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

-- 1 cliente ainda pendente de resposta (convite já "enviado")
INSERT INTO sat_respostas (campanha_id, cliente_id, status, primeiro_envio_at, total_envios)
SELECT c.id, cl.id, 'enviado', now() - interval '2 days', 1
FROM sat_campanhas c, sat_clientes cl
WHERE c.ano = 2026 AND cl.empresa_nome = 'Empresa Teste Epsilon'
ON CONFLICT (campanha_id, cliente_id) DO NOTHING;

-- Simula uma resposta do Microsoft Forms que chegou com e-mail que não bate com nenhum
-- cliente cadastrado — testa a fila de conciliação manual na aba "Log de Envios".
INSERT INTO sat_ms_forms_log (campanha_id, ano_informado, email_informado, empresa_informada, ms_forms_response_id, payload_bruto, matched, status, erro_detalhe)
SELECT c.id, 2026, 'contato@empresa-desconhecida-teste.com.br', 'Empresa Desconhecida Teste',
       'seed-teste-response-id-001',
       '{"itens": [{"ordem":1,"nota":2,"comentario":"Teste de conciliação manual"},{"ordem":2,"nota":4,"comentario":null},{"ordem":3,"nota":5,"comentario":null},{"ordem":4,"nota":4,"comentario":null},{"ordem":5,"nota":3,"comentario":null}]}'::jsonb,
       false, 'recebido', 'Nenhum cliente convidado encontrado com esse e-mail/empresa'
FROM sat_campanhas c
WHERE c.ano = 2026
ON CONFLICT (ms_forms_response_id) WHERE ms_forms_response_id IS NOT NULL DO NOTHING;

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
