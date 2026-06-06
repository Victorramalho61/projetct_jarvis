-- cards-service — cofre seguro de cartões com auditoria de acesso
-- Execute via Supabase SQL Editor ou psql

-- Clientes donos dos cartões
CREATE TABLE IF NOT EXISTS cards_clientes (
    id         uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    nome       text NOT NULL,
    cnpj       varchar(18),
    ativo      boolean NOT NULL DEFAULT true,
    criado_por uuid,
    created_at timestamptz NOT NULL DEFAULT now()
);

-- Cartões (dados sensíveis todos criptografados via Fernet)
CREATE TABLE IF NOT EXISTS cards_cartoes (
    id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    cliente_id          uuid NOT NULL REFERENCES cards_clientes(id) ON DELETE RESTRICT,
    bandeira            text NOT NULL,        -- VISA | MASTER | ELO | AMEX | HIPERCARD
    numero_final        varchar(4) NOT NULL,  -- últimos 4 dígitos em plaintext (exibição)
    numero_encrypted    text NOT NULL,        -- número completo — Fernet
    cvv_encrypted       text NOT NULL,        -- CVV — Fernet
    expiracao_encrypted text NOT NULL,        -- MM/AA — Fernet
    titular_encrypted   text NOT NULL,        -- nome do titular — Fernet
    ativo               boolean NOT NULL DEFAULT true,
    criado_por          uuid,
    created_at          timestamptz NOT NULL DEFAULT now(),
    updated_at          timestamptz NOT NULL DEFAULT now()
);

-- Permissões do módulo (independente do role JWT global)
CREATE TABLE IF NOT EXISTS cards_permissoes (
    id         uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id    uuid NOT NULL UNIQUE,
    user_login text NOT NULL,
    user_nome  text NOT NULL,
    perfil     text NOT NULL CHECK (perfil IN ('colaborador', 'supervisor')),
    ativo      boolean NOT NULL DEFAULT true,
    created_at timestamptz NOT NULL DEFAULT now()
);

-- Log imutável de cada acesso a dados de cartão
CREATE TABLE IF NOT EXISTS cards_acessos (
    id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    cartao_id        uuid NOT NULL REFERENCES cards_cartoes(id) ON DELETE RESTRICT,
    cliente_id       uuid,                    -- desnormalizado para filtros
    -- dados do colaborador (do JWT)
    user_id          uuid NOT NULL,
    user_login       text NOT NULL,
    user_nome        text NOT NULL,
    data_hora_acesso timestamptz NOT NULL DEFAULT now(),
    ip_origem        text,
    -- campos obrigatórios preenchidos pelo colaborador
    localizador_os   text NOT NULL,
    nome_cliente     text NOT NULL,
    produto          text NOT NULL,           -- aereo | hotel | locacao
    data_reserva     date NOT NULL,
    nome_pax         text NOT NULL,
    fornecedor       text NOT NULL,
    valor_transacao  numeric(15,2) NOT NULL,
    created_at       timestamptz NOT NULL DEFAULT now()
);

-- Solicitações de acesso pendentes de aprovação (antirreuso de localizador)
CREATE TABLE IF NOT EXISTS cards_solicitacoes (
    id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    cartao_id           uuid NOT NULL REFERENCES cards_cartoes(id) ON DELETE RESTRICT,
    cliente_id          uuid,
    -- dados do colaborador
    user_id             uuid NOT NULL,
    user_login          text NOT NULL,
    user_nome           text NOT NULL,
    ip_origem           text,
    -- campos do formulário
    localizador_os      text NOT NULL,
    nome_cliente        text NOT NULL,
    produto             text NOT NULL,
    data_reserva        date NOT NULL,
    nome_pax            text NOT NULL,
    fornecedor          text NOT NULL,
    valor_transacao     numeric(15,2) NOT NULL,
    -- controle de aprovação
    status              text NOT NULL DEFAULT 'pendente'
                            CHECK (status IN ('pendente', 'aprovada', 'rejeitada', 'consumida')),
    aprovado_por        uuid,
    aprovado_por_nome   text,
    aprovado_em         timestamptz,
    aprovacao_expira_em timestamptz,          -- aprovada + 10 min; após isso, precisa nova aprovação
    motivo_rejeicao     text,
    created_at          timestamptz NOT NULL DEFAULT now()
);

-- Trigger de imutabilidade: cards_acessos nunca pode ser alterado ou deletado
CREATE OR REPLACE FUNCTION cards_acessos_immutable()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'cards_acessos é imutável — registros de auditoria não podem ser alterados ou excluídos';
END;
$$;

CREATE TRIGGER trg_cards_acessos_immutable
BEFORE UPDATE OR DELETE ON cards_acessos
FOR EACH ROW EXECUTE FUNCTION cards_acessos_immutable();

-- Índices de performance
CREATE INDEX IF NOT EXISTS idx_cards_cartoes_cliente     ON cards_cartoes(cliente_id);
CREATE INDEX IF NOT EXISTS idx_cards_cartoes_final       ON cards_cartoes(numero_final);
CREATE INDEX IF NOT EXISTS idx_cards_acessos_cartao      ON cards_acessos(cartao_id);
CREATE INDEX IF NOT EXISTS idx_cards_acessos_user        ON cards_acessos(user_id);
CREATE INDEX IF NOT EXISTS idx_cards_acessos_cliente     ON cards_acessos(cliente_id);
CREATE INDEX IF NOT EXISTS idx_cards_acessos_data        ON cards_acessos(data_hora_acesso);
CREATE INDEX IF NOT EXISTS idx_cards_acessos_loc         ON cards_acessos(localizador_os);
CREATE INDEX IF NOT EXISTS idx_cards_solicit_user        ON cards_solicitacoes(user_id);
CREATE INDEX IF NOT EXISTS idx_cards_solicit_status      ON cards_solicitacoes(status);
CREATE INDEX IF NOT EXISTS idx_cards_solicit_cartao      ON cards_solicitacoes(cartao_id);
