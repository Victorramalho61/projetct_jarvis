-- Migration 001: Módulo Avaliação de Experiência
-- Executar no Supabase SQL Editor

-- Colaboradores sincronizados do Benner TH
CREATE TABLE IF NOT EXISTS exp_employees (
  id             uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  matricula      text NOT NULL UNIQUE,
  nome           text NOT NULL,
  cargo          text,
  departamento   text,
  empresa        text,
  data_admissao  date NOT NULL,
  gestor_nome    text,
  gestor_email   text,
  ativo          boolean DEFAULT true,
  synced_at      timestamptz DEFAULT now(),
  created_at     timestamptz DEFAULT now()
);

-- Uma avaliação por colaborador por tipo (45 ou 90 dias)
CREATE TABLE IF NOT EXISTS exp_avaliacoes (
  id                   uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  employee_id          uuid NOT NULL REFERENCES exp_employees(id) ON DELETE CASCADE,
  tipo                 text NOT NULL CHECK (tipo IN ('45_dias', '90_dias')),
  data_prevista        date NOT NULL,
  status               text NOT NULL DEFAULT 'pendente'
                         CHECK (status IN ('pendente','enviado','respondido','expirado','sem_gestor')),
  token                text UNIQUE,
  token_expires_at     timestamptz,
  -- Resposta do gestor
  respostas            jsonb,
  gestor_concordou     boolean,
  gestor_assinatura_at timestamptz,
  gestor_ip            text,
  -- Controle de envios
  primeiro_envio_at    timestamptz,
  ultimo_envio_at      timestamptz,
  total_envios         int DEFAULT 0,
  -- Metadados
  created_at           timestamptz DEFAULT now(),
  updated_at           timestamptz DEFAULT now(),
  UNIQUE(employee_id, tipo)
);

-- Log de todos os e-mails enviados
CREATE TABLE IF NOT EXISTS exp_email_log (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  avaliacao_id  uuid NOT NULL REFERENCES exp_avaliacoes(id) ON DELETE CASCADE,
  destinatario  text NOT NULL,
  tipo_email    text NOT NULL CHECK (tipo_email IN ('primeiro_envio','cobranca','confirmacao_rh')),
  enviado_at    timestamptz DEFAULT now(),
  sucesso       boolean NOT NULL
);

-- Índices
CREATE INDEX IF NOT EXISTS idx_exp_av_status     ON exp_avaliacoes(status);
CREATE INDEX IF NOT EXISTS idx_exp_av_tipo        ON exp_avaliacoes(tipo);
CREATE INDEX IF NOT EXISTS idx_exp_av_prevista    ON exp_avaliacoes(data_prevista);
CREATE INDEX IF NOT EXISTS idx_exp_emp_mat        ON exp_employees(matricula);
CREATE INDEX IF NOT EXISTS idx_exp_emp_empresa    ON exp_employees(empresa);
CREATE INDEX IF NOT EXISTS idx_exp_log_avaliacao  ON exp_email_log(avaliacao_id);

-- RLS: habilitar mas permitir acesso via service_role (backend usa chave de serviço)
ALTER TABLE exp_employees   ENABLE ROW LEVEL SECURITY;
ALTER TABLE exp_avaliacoes  ENABLE ROW LEVEL SECURITY;
ALTER TABLE exp_email_log   ENABLE ROW LEVEL SECURITY;

-- Políticas abertas para service_role (o backend autentica via JWT do Supabase)
CREATE POLICY "service_role_all" ON exp_employees  FOR ALL TO service_role USING (true) WITH CHECK (true);
CREATE POLICY "service_role_all" ON exp_avaliacoes FOR ALL TO service_role USING (true) WITH CHECK (true);
CREATE POLICY "service_role_all" ON exp_email_log  FOR ALL TO service_role USING (true) WITH CHECK (true);
