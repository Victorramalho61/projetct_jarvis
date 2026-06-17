-- =============================================================
-- Freshdesk → SQL Server BI  |  Migration
-- Database: BI
-- =============================================================

-- ── 1. Tabela de tickets ──────────────────────────────────────
IF OBJECT_ID('dbo.freshdesk_tickets', 'U') IS NULL
CREATE TABLE dbo.freshdesk_tickets (
    id                   BIGINT         NOT NULL,
    empresa              NVARCHAR(255)  NULL,
    subject              NVARCHAR(1000) NULL,
    status               INT            NULL,
    created_at           DATETIME2(7)   NULL,
    resolved_at          DATETIME2(7)   NULL,
    closed_at            DATETIME2(7)   NULL,
    first_responded_at   DATETIME2(7)   NULL,
    tipo_servico_raw     NVARCHAR(255)  NULL,   -- cf_ipo_de_servio (valor original)
    tipo_servico         NVARCHAR(255)  NULL,   -- lowercase + trim, usado no JOIN SLA
    tipo_servico2        NVARCHAR(255)  NULL,   -- cf_tipo_de_servio763654
    tipo_demanda         NVARCHAR(255)  NULL,
    mercado              NVARCHAR(255)  NULL,
    produtos             NVARCHAR(500)  NULL,
    localizador          NVARCHAR(255)  NULL,
    nome_passageiro      NVARCHAR(500)  NULL,
    nome_solicitante     NVARCHAR(500)  NULL,
    cotacao_especial     BIT            NOT NULL DEFAULT 0,
    synced_at            DATETIME2(7)   NOT NULL DEFAULT GETUTCDATE(),
    CONSTRAINT PK_freshdesk_tickets PRIMARY KEY (id)
);

CREATE INDEX IF NOT EXISTS IDX_fd_empresa  ON dbo.freshdesk_tickets (empresa);
CREATE INDEX IF NOT EXISTS IDX_fd_created  ON dbo.freshdesk_tickets (created_at DESC);
CREATE INDEX IF NOT EXISTS IDX_fd_resolved ON dbo.freshdesk_tickets (resolved_at DESC);

-- ── 2. Tabela de regras SLA ───────────────────────────────────
IF OBJECT_ID('dbo.freshdesk_sla_rules', 'U') IS NULL
CREATE TABLE dbo.freshdesk_sla_rules (
    tipo_servico  NVARCHAR(255) NOT NULL,
    sla_horas     DECIMAL(5,1)  NOT NULL,
    sla_minutos   INT           NOT NULL,
    CONSTRAINT PK_freshdesk_sla_rules PRIMARY KEY (tipo_servico)
);

-- Inserir regras (não duplica se já existir)
MERGE dbo.freshdesk_sla_rules AS tgt
USING (VALUES
    (N'cotação',              4.0,  240),
    (N'cotação especial',     8.0,  480),
    (N'emissão',              4.0,  240),
    (N'reemissão/alteração',  4.0,  240),
    (N'cancelamento',         2.0,  120),
    (N'voucher',              3.0,  180),
    (N'apólice de seguro',    3.0,  180),
    (N'cotação de seguro',    8.0,  480)
) AS src (tipo_servico, sla_horas, sla_minutos)
ON tgt.tipo_servico = src.tipo_servico
WHEN NOT MATCHED THEN
    INSERT (tipo_servico, sla_horas, sla_minutos)
    VALUES (src.tipo_servico, src.sla_horas, src.sla_minutos);

-- ── 3. View de SLA ────────────────────────────────────────────
CREATE OR ALTER VIEW dbo.vw_freshdesk_sla AS
SELECT
    t.id,
    t.empresa,
    t.created_at,
    t.resolved_at,
    t.tipo_servico_raw,
    CASE
        WHEN t.cotacao_especial = 1 THEN N'cotação especial'
        ELSE t.tipo_servico
    END                                                           AS tipo_sla,
    r.sla_horas,
    r.sla_minutos                                                 AS sla_target_min,
    DATEDIFF(MINUTE, t.created_at, t.resolved_at)                AS resolution_min,
    CAST(DATEDIFF(MINUTE, t.created_at, t.resolved_at) AS DECIMAL(10,1)) / 60
                                                                  AS resolution_horas,
    CASE
        WHEN r.sla_minutos IS NULL THEN NULL   -- tipo sem regra cadastrada
        WHEN DATEDIFF(MINUTE, t.created_at, t.resolved_at) <= r.sla_minutos THEN 1
        ELSE 0
    END                                                           AS sla_ok
FROM dbo.freshdesk_tickets t
LEFT JOIN dbo.freshdesk_sla_rules r
    ON r.tipo_servico = CASE
        WHEN t.cotacao_especial = 1 THEN N'cotação especial'
        ELSE t.tipo_servico
    END
WHERE t.resolved_at IS NOT NULL;   -- abertos excluídos do cálculo de SLA
GO

-- =============================================================
-- Query pronta — Relatório SLA por empresa e período
-- Troque os parâmetros nas linhas marcadas com <<
-- =============================================================
/*
SELECT
    empresa,
    tipo_sla,
    sla_horas,
    COUNT(*)                                                              AS total,
    SUM(sla_ok)                                                          AS cumprido,
    SUM(CASE WHEN sla_ok = 0 THEN 1 ELSE 0 END)                        AS descumprido,
    CAST(100.0 * SUM(sla_ok) / NULLIF(COUNT(*), 0) AS DECIMAL(5,1))   AS percentual_sla,
    CAST(AVG(resolution_horas) AS DECIMAL(5,1))                         AS tempo_medio_horas
FROM dbo.vw_freshdesk_sla
WHERE empresa    = N'Voetur'        -- << empresa
  AND created_at >= '2026-01-01'    -- << data início
  AND created_at <  '2026-07-01'    -- << data fim (exclusive)
GROUP BY empresa, tipo_sla, sla_horas
ORDER BY total DESC;
*/
