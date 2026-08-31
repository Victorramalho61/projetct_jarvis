-- Migration 002: Seed dos Pontos de Avaliação (taxonomia de causa-raiz para notas 1-2)
-- Fonte: "Questões da Pesquisa e Notas Ruins.xlsx", aba "Notas Ruins de 1 a 2"
-- Executar após migration_001_satisfacao.sql

-- Questão 1 — Comercial
INSERT INTO sat_pontos_avaliacao (pergunta_id, titulo, descricao, ordem)
SELECT p.id, v.titulo, v.descricao, v.ordem
FROM sat_perguntas p
JOIN (VALUES
  ('Entendimento da necessidade', 'O Comercial não compreendeu corretamente o perfil, política de viagens e nossas necessidades', 1),
  ('Clareza das informações', 'As condições comerciais, tarifas, regras, taxas e restrições não foram explicadas corretamente', 2),
  ('Proposta comercial', 'A proposta não estava adequada ao solicitado, incompleta e com informações divergentes', 3),
  ('Prazo de retorno', 'A proposta/orçamento não foi recebida dentro do prazo esperado', 4),
  ('Cumprimento do prometido', 'O que foi prometido na negociação não foi efetivamente entregue', 5),
  ('Comunicação', 'Não houve clareza, transparência e objetividade durante a negociação', 6),
  ('Conhecimento do produto', 'O profissional não demonstrou conhecimento suficiente sobre os serviços oferecidos', 7),
  ('Gestão de expectativas', 'Foram criadas expectativas que posteriormente não puderam ser atendidas', 8),
  ('Implantação/integração', 'Houve problemas na implantação ou na transição para a operação', 9),
  ('Relacionamento', 'Não percebemos disponibilidade e interesse na resolução de nossas necessidades', 10)
) AS v(titulo, descricao, ordem) ON true
WHERE p.categoria = 'comercial';

-- Questão 2 — Atendimento
INSERT INTO sat_pontos_avaliacao (pergunta_id, titulo, descricao, ordem)
SELECT p.id, v.titulo, v.descricao, v.ordem
FROM sat_perguntas p
JOIN (VALUES
  ('Tempo de resposta', 'Tempo de espera da resposta além do prazo acordado', 1),
  ('Disponibilidade', 'Não conseguimos contato quando precisamos', 2),
  ('Agilidade', 'A solicitação não foi resolvida rapidamente', 3),
  ('Assertividade', 'A primeira resposta não trouxe uma solução adequada', 4),
  ('Conhecimento técnico', 'O atendente não demonstrou domínio das regras e dos produtos oferecidos', 5),
  ('Cordialidade', 'O atendimento foi desrespeitoso e foi percebida a falta de profissionalismo', 6),
  ('Clareza', 'As informações não foram apresentadas de maneira compreensível', 7),
  ('Resolução de problemas', 'O problema não foi efetivamente solucionado', 8),
  ('Follow-up', 'Falta de acompanhamento até a conclusão da solicitação', 9),
  ('Atendimento emergencial', 'Não houve suporte adequado, quando em situações críticas', 10),
  ('Transferências/repasses', 'O cliente precisou repetir informações para diferentes atendentes', 11),
  ('Comunicação de alterações', 'Mudanças de voo, cancelamentos, atrasos etc. não foram comunicados adequadamente', 12)
) AS v(titulo, descricao, ordem) ON true
WHERE p.categoria = 'atendimento';

-- Questão 3 — Financeiro
INSERT INTO sat_pontos_avaliacao (pergunta_id, titulo, descricao, ordem)
SELECT p.id, v.titulo, v.descricao, v.ordem
FROM sat_perguntas p
JOIN (VALUES
  ('Faturamento', 'A cobrança não corresponde ao serviço efetivamente contratado', 1),
  ('Conferência', 'Existem divergências de valores, passageiros, centros de custo ou serviços', 2),
  ('Prazo de envio', 'O faturamento/documentação não chegou no prazo acordado', 3),
  ('Clareza da cobrança', 'Não conseguimos entender os valores cobrados', 4),
  ('Taxas', 'As taxas e encargos foram apresentados incorretamente', 5),
  ('Notas fiscais', 'Houve erro, atraso ou inconsistência na documentação fiscal', 6),
  ('Reembolsos', 'O processo de reembolso não foi conduzido adequadamente', 7),
  ('Estornos/cancelamentos', 'Os valores não foram tratados corretamente, fora do prazo', 8),
  ('Conciliação', 'Existem diferenças entre o faturamento e nossos controles', 9),
  ('Retorno às dúvidas', 'As dúvidas financeiras não foram respondidas com clareza e rapidez', 10),
  ('Acordos comerciais', 'Os valores cobrados não estão de acordo com as condições negociadas', 11)
) AS v(titulo, descricao, ordem) ON true
WHERE p.categoria = 'financeiro';

-- Questão 4 — Avaliação dos Produtos e Serviços
INSERT INTO sat_pontos_avaliacao (pergunta_id, titulo, descricao, ordem)
SELECT p.id, v.titulo, v.descricao, v.ordem
FROM sat_perguntas p
JOIN (VALUES
  ('Qualidade do serviço', 'O serviço entregue não correspondeu ao esperado', 1),
  ('Adequação às necessidades', 'A solução não atende ao nosso perfil', 2),
  ('Disponibilidade', 'Não houve disponibilidade adequada de voos, hotéis e demais serviços', 3),
  ('Variedade de opções', 'Não foram apresentadas alternativas suficientes', 4),
  ('Condições tarifárias', 'As opções apresentadas não foram competitivas e adequadas à política de viagens', 5),
  ('Qualidade dos fornecedores', 'Houve problemas recorrentes com companhias aéreas, hotéis ou outros fornecedores', 6),
  ('Confiabilidade', 'Não confiamos nas informações e soluções oferecidas', 7),
  ('Tecnologia/sistemas', 'As ferramentas, portais, plataformas ou integrações não funcionaram adequadamente', 8),
  ('Relatórios/indicadores', 'As informações gerenciais não atendem nossas necessidades', 9),
  ('Política de viagens', 'Os serviços não estão aderentes às regras estabelecidas por nós', 10),
  ('Experiência do viajante', 'O serviço não facilita a experiência do colaborador que viaja', 11),
  ('Custo-benefício', 'O valor não é compatível com o que é recebido em termos de qualidade', 12)
) AS v(titulo, descricao, ordem) ON true
WHERE p.categoria = 'produtos_servicos';

-- Questão 5 — Probabilidade de Indicação dos Serviços Voetur
INSERT INTO sat_pontos_avaliacao (pergunta_id, titulo, descricao, ordem)
SELECT p.id, v.titulo, v.descricao, v.ordem
FROM sat_perguntas p
JOIN (VALUES
  ('Comercial', 'Promessas não cumpridas, proposta inadequada, falta de entendimento da necessidade, condições comerciais etc.', 1),
  ('Atendimento', 'Demora, falta de retorno, dificuldade de contato, solução inadequada, falta de acompanhamento etc.', 2),
  ('Financeiro', 'Erros de cobrança, divergências, reembolso, taxas, faturamento etc.', 3),
  ('Produtos e Serviços', 'Qualidade, disponibilidade, adequação, custo-benefício, fornecedores etc.', 4),
  ('Comunicação', 'Informações incompletas, divergentes ou transmitidas fora do prazo', 5),
  ('Tecnologia/Sistemas', 'Instabilidade, dificuldades de utilização, integrações ou informações incorretas', 6),
  ('Experiência geral', 'Insatisfação que não se limita a um departamento específico', 7),
  ('Outro', 'Campo aberto', 8)
) AS v(titulo, descricao, ordem) ON true
WHERE p.categoria = 'indicacao';
