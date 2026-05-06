-- Módulo Governança de Contratos — Jarvis
-- Executar: docker exec -i jarvis-db-1 psql -U postgres jarvis < schema_governance.sql

-- Tabela principal de contratos
CREATE TABLE IF NOT EXISTS public.contracts (
  id                       UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  benner_documento_match   TEXT,
  numero                   TEXT,
  titulo                   TEXT NOT NULL,
  fornecedor_nome          TEXT NOT NULL,
  fornecedor_benner_handle BIGINT,
  valor_total              NUMERIC(15,2) NOT NULL,
  valor_mensal             NUMERIC(15,2),
  qtd_parcelas             INTEGER,
  data_inicio              DATE NOT NULL,
  data_fim                 DATE NOT NULL,
  modalidade               TEXT NOT NULL DEFAULT 'servico'
                             CHECK (modalidade IN ('servico','fornecimento','manutencao','licenca','outro')),
  status                   TEXT NOT NULL DEFAULT 'vigente'
                             CHECK (status IN ('vigente','vencendo','vencido','rescindido','suspenso')),
  objeto                   TEXT,
  sla_config               JSONB DEFAULT '[]'::jsonb,
  observacoes              TEXT,
  arquivo_url              TEXT,
  created_by               UUID REFERENCES public.profiles(id) ON DELETE SET NULL,
  created_at               TIMESTAMPTZ DEFAULT now(),
  updated_at               TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_contracts_status
  ON public.contracts(status, data_fim);
CREATE INDEX IF NOT EXISTS idx_contracts_fornecedor
  ON public.contracts(fornecedor_benner_handle);

-- Itens/serviços do contrato
CREATE TABLE IF NOT EXISTS public.contract_items (
  id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  contract_id    UUID NOT NULL REFERENCES public.contracts(id) ON DELETE CASCADE,
  descricao      TEXT NOT NULL,
  quantidade     NUMERIC(10,2) DEFAULT 1,
  valor_unitario NUMERIC(15,2) NOT NULL,
  valor_total    NUMERIC(15,2) NOT NULL,
  unidade        TEXT DEFAULT 'un',
  periodicidade  TEXT DEFAULT 'mensal'
                   CHECK (periodicidade IN ('mensal','anual','unico')),
  conta_contabil TEXT,
  created_at     TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_ci_contract
  ON public.contract_items(contract_id);

-- Ocorrências: glosas, multas, descontos, acréscimos, notificações
CREATE TABLE IF NOT EXISTS public.contract_occurrences (
  id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  contract_id         UUID NOT NULL REFERENCES public.contracts(id) ON DELETE CASCADE,
  tipo                TEXT NOT NULL
                        CHECK (tipo IN ('glosa','multa','desconto','acrescimo','reajuste','notificacao')),
  valor               NUMERIC(15,2),
  descricao           TEXT NOT NULL,
  data_ocorrencia     DATE NOT NULL,
  competencia         TEXT,
  status              TEXT DEFAULT 'pendente'
                        CHECK (status IN ('pendente','aplicado','contestado','cancelado')),
  email_enviado       BOOLEAN DEFAULT false,
  email_destinatarios TEXT[],
  email_assunto       TEXT,
  email_corpo         TEXT,
  email_enviado_at    TIMESTAMPTZ,
  created_by          UUID REFERENCES public.profiles(id) ON DELETE SET NULL,
  created_at          TIMESTAMPTZ DEFAULT now(),
  updated_at          TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_co_contract
  ON public.contract_occurrences(contract_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_co_status
  ON public.contract_occurrences(status, tipo);

-- Documentos vinculados (contratos PDF, aditivos, NFs, e-mails)
CREATE TABLE IF NOT EXISTS public.contract_documents (
  id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  contract_id   UUID NOT NULL REFERENCES public.contracts(id) ON DELETE CASCADE,
  occurrence_id UUID REFERENCES public.contract_occurrences(id) ON DELETE SET NULL,
  tipo          TEXT NOT NULL
                  CHECK (tipo IN ('contrato_original','aditivo','email','nota_fiscal','outro')),
  nome_arquivo  TEXT NOT NULL,
  url           TEXT NOT NULL,
  tamanho_bytes BIGINT,
  uploaded_by   UUID REFERENCES public.profiles(id) ON DELETE SET NULL,
  created_at    TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_cd_contract
  ON public.contract_documents(contract_id);

-- Violações de SLA
CREATE TABLE IF NOT EXISTS public.contract_sla_violations (
  id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  contract_id      UUID NOT NULL REFERENCES public.contracts(id) ON DELETE CASCADE,
  sla_metrica      TEXT NOT NULL,
  valor_contratado NUMERIC(10,4) NOT NULL,
  valor_medido     NUMERIC(10,4) NOT NULL,
  periodo          TEXT NOT NULL,
  impacto          TEXT,
  penalidade_valor NUMERIC(15,2),
  status           TEXT DEFAULT 'registrado'
                     CHECK (status IN ('registrado','notificado','aplicado','contestado','resolvido')),
  created_by       UUID REFERENCES public.profiles(id) ON DELETE SET NULL,
  created_at       TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_csv_contract
  ON public.contract_sla_violations(contract_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_csv_status
  ON public.contract_sla_violations(status);
