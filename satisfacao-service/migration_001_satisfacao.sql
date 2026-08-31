-- Migration 001: Módulo Pesquisa de Satisfação de Clientes (VTG.CM.PGP.01)
-- Executar no Supabase SQL Editor

-- Cadastro de clientes/contatos
CREATE TABLE IF NOT EXISTS sat_clientes (
  id                uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  empresa_nome      text NOT NULL,
  contato_nome      text NOT NULL,
  contato_cargo     text,
  contato_email     text NOT NULL,
  contato_telefone  text,
  ativo             boolean NOT NULL DEFAULT true,
  observacoes       text,
  created_at        timestamptz NOT NULL DEFAULT now(),
  updated_at        timestamptz NOT NULL DEFAULT now()
);

-- Template de perguntas (nunca apagar fisicamente — usar `ativa=false`)
CREATE TABLE IF NOT EXISTS sat_perguntas (
  id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  ordem        int NOT NULL,
  texto        text NOT NULL,
  categoria    text,
  ativa        boolean NOT NULL DEFAULT true,
  created_at   timestamptz NOT NULL DEFAULT now(),
  updated_at   timestamptz NOT NULL DEFAULT now()
);

-- Taxonomia de causa-raiz para notas ruins (1-2) — uso interno do SGI na triagem
CREATE TABLE IF NOT EXISTS sat_pontos_avaliacao (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  pergunta_id   uuid NOT NULL REFERENCES sat_perguntas(id) ON DELETE CASCADE,
  titulo        text NOT NULL,
  descricao     text NOT NULL,
  ordem         int NOT NULL,
  ativo         boolean NOT NULL DEFAULT true,
  created_at    timestamptz NOT NULL DEFAULT now()
);

-- Ciclo anual da pesquisa
CREATE TABLE IF NOT EXISTS sat_campanhas (
  id                    uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  ano                   int NOT NULL,
  titulo                text NOT NULL,
  status                text NOT NULL DEFAULT 'rascunho'
                          CHECK (status IN ('rascunho','em_andamento','postergada','encerrada','cancelada')),
  data_inicio           date,
  data_prazo            date,
  data_prazo_original   date,
  postergada_em         timestamptz,
  motivo_postergacao    text,
  qtd_postergacoes      int NOT NULL DEFAULT 0,
  encerrada_em          timestamptz,
  created_by            text,
  created_at            timestamptz NOT NULL DEFAULT now(),
  updated_at            timestamptz NOT NULL DEFAULT now(),
  UNIQUE(ano)
);

-- Snapshot das perguntas ativas no momento da criação da campanha
CREATE TABLE IF NOT EXISTS sat_campanha_perguntas (
  id             uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  campanha_id    uuid NOT NULL REFERENCES sat_campanhas(id) ON DELETE CASCADE,
  pergunta_id    uuid NOT NULL REFERENCES sat_perguntas(id),
  ordem          int NOT NULL,
  texto_snapshot text NOT NULL,
  UNIQUE(campanha_id, pergunta_id)
);

-- Uma linha por cliente x campanha — carrega o token de acesso público
CREATE TABLE IF NOT EXISTS sat_respostas (
  id                 uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  campanha_id        uuid NOT NULL REFERENCES sat_campanhas(id) ON DELETE CASCADE,
  cliente_id         uuid NOT NULL REFERENCES sat_clientes(id),
  status             text NOT NULL DEFAULT 'pendente'
                       CHECK (status IN ('pendente','enviado','respondido','expirado')),
  canal_resposta     text CHECK (canal_resposta IN ('formulario_link','manual_sgi')),
  token              text UNIQUE,
  token_expires_at   timestamptz,
  primeiro_envio_at  timestamptz,
  ultimo_envio_at    timestamptz,
  total_envios       int NOT NULL DEFAULT 0,
  respondido_at      timestamptz,
  respondente_ip     text,
  lancado_por        text,
  created_at         timestamptz NOT NULL DEFAULT now(),
  updated_at         timestamptz NOT NULL DEFAULT now(),
  UNIQUE(campanha_id, cliente_id)
);

-- Nota + comentário por pergunta, com triagem de causa-raiz quando nota ruim
CREATE TABLE IF NOT EXISTS sat_respostas_itens (
  id                    uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  resposta_id           uuid NOT NULL REFERENCES sat_respostas(id) ON DELETE CASCADE,
  campanha_pergunta_id  uuid NOT NULL REFERENCES sat_campanha_perguntas(id),
  nota                  int NOT NULL CHECK (nota BETWEEN 1 AND 5),
  comentario            text,
  triagem_status        text NOT NULL DEFAULT 'nao_aplicavel'
                          CHECK (triagem_status IN ('nao_aplicavel','pendente','classificado')),
  triagem_ponto_id      uuid REFERENCES sat_pontos_avaliacao(id),
  triagem_observacao    text,
  triagem_por           text,
  triagem_em            timestamptz,
  created_at            timestamptz NOT NULL DEFAULT now(),
  UNIQUE(resposta_id, campanha_pergunta_id)
);

-- Log de e-mails enviados
CREATE TABLE IF NOT EXISTS sat_email_log (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  resposta_id   uuid NOT NULL REFERENCES sat_respostas(id) ON DELETE CASCADE,
  destinatario  text NOT NULL,
  tipo_email    text NOT NULL CHECK (tipo_email IN ('primeiro_envio','cobranca','reforco_adesao','confirmacao_sgi')),
  enviado_at    timestamptz NOT NULL DEFAULT now(),
  sucesso       boolean NOT NULL,
  erro_detalhe  text
);

-- Plano de ação autocontido (por pergunta x campanha, sem depender de módulo de NC)
CREATE TABLE IF NOT EXISTS sat_planos_acao (
  id                      uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  campanha_id             uuid NOT NULL REFERENCES sat_campanhas(id) ON DELETE CASCADE,
  pergunta_id             uuid NOT NULL REFERENCES sat_perguntas(id),
  percentual_notas_ruins  numeric(5,2) NOT NULL,
  descricao               text NOT NULL,
  responsavel             text NOT NULL,
  prazo                   date NOT NULL,
  status                  text NOT NULL DEFAULT 'aberto'
                            CHECK (status IN ('aberto','em_andamento','concluido')),
  concluido_em            timestamptz,
  observacao_conclusao    text,
  criado_por              text,
  created_at              timestamptz NOT NULL DEFAULT now(),
  updated_at              timestamptz NOT NULL DEFAULT now()
);

-- Índices
CREATE INDEX IF NOT EXISTS idx_sat_clientes_ativo        ON sat_clientes(ativo);
CREATE INDEX IF NOT EXISTS idx_sat_clientes_email        ON sat_clientes(contato_email);
CREATE INDEX IF NOT EXISTS idx_sat_pontos_pergunta       ON sat_pontos_avaliacao(pergunta_id);
CREATE INDEX IF NOT EXISTS idx_sat_campanhas_status      ON sat_campanhas(status);
CREATE INDEX IF NOT EXISTS idx_sat_resp_campanha         ON sat_respostas(campanha_id);
CREATE INDEX IF NOT EXISTS idx_sat_resp_status           ON sat_respostas(status);
CREATE INDEX IF NOT EXISTS idx_sat_resp_token            ON sat_respostas(token);
CREATE INDEX IF NOT EXISTS idx_sat_itens_resposta        ON sat_respostas_itens(resposta_id);
CREATE INDEX IF NOT EXISTS idx_sat_itens_nota             ON sat_respostas_itens(nota);
CREATE INDEX IF NOT EXISTS idx_sat_itens_triagem_status   ON sat_respostas_itens(triagem_status);
CREATE INDEX IF NOT EXISTS idx_sat_itens_pergunta         ON sat_respostas_itens(campanha_pergunta_id);
CREATE INDEX IF NOT EXISTS idx_sat_email_log_resposta     ON sat_email_log(resposta_id);
CREATE INDEX IF NOT EXISTS idx_sat_planos_campanha        ON sat_planos_acao(campanha_id);
CREATE INDEX IF NOT EXISTS idx_sat_planos_status          ON sat_planos_acao(status);

-- RLS: habilitar mas permitir acesso via service_role (backend usa chave de serviço)
ALTER TABLE sat_clientes            ENABLE ROW LEVEL SECURITY;
ALTER TABLE sat_perguntas           ENABLE ROW LEVEL SECURITY;
ALTER TABLE sat_pontos_avaliacao    ENABLE ROW LEVEL SECURITY;
ALTER TABLE sat_campanhas           ENABLE ROW LEVEL SECURITY;
ALTER TABLE sat_campanha_perguntas  ENABLE ROW LEVEL SECURITY;
ALTER TABLE sat_respostas           ENABLE ROW LEVEL SECURITY;
ALTER TABLE sat_respostas_itens     ENABLE ROW LEVEL SECURITY;
ALTER TABLE sat_email_log           ENABLE ROW LEVEL SECURITY;
ALTER TABLE sat_planos_acao         ENABLE ROW LEVEL SECURITY;

CREATE POLICY "service_role_all" ON sat_clientes           FOR ALL TO service_role USING (true) WITH CHECK (true);
CREATE POLICY "service_role_all" ON sat_perguntas          FOR ALL TO service_role USING (true) WITH CHECK (true);
CREATE POLICY "service_role_all" ON sat_pontos_avaliacao   FOR ALL TO service_role USING (true) WITH CHECK (true);
CREATE POLICY "service_role_all" ON sat_campanhas          FOR ALL TO service_role USING (true) WITH CHECK (true);
CREATE POLICY "service_role_all" ON sat_campanha_perguntas FOR ALL TO service_role USING (true) WITH CHECK (true);
CREATE POLICY "service_role_all" ON sat_respostas          FOR ALL TO service_role USING (true) WITH CHECK (true);
CREATE POLICY "service_role_all" ON sat_respostas_itens    FOR ALL TO service_role USING (true) WITH CHECK (true);
CREATE POLICY "service_role_all" ON sat_email_log          FOR ALL TO service_role USING (true) WITH CHECK (true);
CREATE POLICY "service_role_all" ON sat_planos_acao        FOR ALL TO service_role USING (true) WITH CHECK (true);

-- Seed: as 5 perguntas oficiais do VTG.CM.PGP.01
INSERT INTO sat_perguntas (ordem, texto, categoria) VALUES
  (1, 'Em uma escala de 1 a 5, como você avalia o relacionamento com o departamento comercial?', 'comercial'),
  (2, 'Em uma escala de 1 a 5, como você avalia o relacionamento com o departamento de atendimento?', 'atendimento'),
  (3, 'Em uma escala de 1 a 5, como você avalia o relacionamento com o departamento financeiro?', 'financeiro'),
  (4, 'Em uma escala de 1 a 5, como você avalia os nossos produtos e serviços?', 'produtos_servicos'),
  (5, 'Em uma escala de 1 a 5, qual é a probabilidade de você indicar os serviços da Voetur Viagens?', 'indicacao')
ON CONFLICT DO NOTHING;
