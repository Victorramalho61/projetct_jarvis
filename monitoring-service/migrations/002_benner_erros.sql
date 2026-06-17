-- Tabela de acumulação individual de erros Benner (pré-requisito do RPA)
-- Cada erro do BB_LOGINTEGRACOES vira uma linha; benner_handle é idempotente.

CREATE TABLE IF NOT EXISTS benner_erros (
    id               BIGSERIAL PRIMARY KEY,
    benner_handle    BIGINT UNIQUE NOT NULL,       -- BB_LOGINTEGRACOES.HANDLE
    capturado_em     TIMESTAMPTZ NOT NULL DEFAULT now(),
    situacao         INT,                          -- 2=Erro, 20=Erro cliente
    tipo_erro        INT,
    produto          TEXT,
    sistema_origem   TEXT,                         -- derivado por _map_sistema_origem()
    cliente          TEXT,
    codigo_reserva   TEXT,
    data_registro    TIMESTAMPTZ,                  -- DATAREENVIO
    mensagem         TEXT,                         -- completa, sem truncar
    -- campos RPA
    rpa_status       TEXT NOT NULL DEFAULT 'pendente',
    rpa_categoria    TEXT,
    rpa_tentativas   INT  NOT NULL DEFAULT 0,
    rpa_ultima_acao  TIMESTAMPTZ,
    rpa_resultado    TEXT
);

COMMENT ON COLUMN benner_erros.rpa_status IS
    'pendente | processando | resolvido | aguardando_input | ignorado';

CREATE INDEX IF NOT EXISTS idx_benner_erros_rpa_status
    ON benner_erros(rpa_status, capturado_em DESC);

CREATE INDEX IF NOT EXISTS idx_benner_erros_handle
    ON benner_erros(benner_handle);

CREATE INDEX IF NOT EXISTS idx_benner_erros_categoria
    ON benner_erros(rpa_categoria, rpa_status);
