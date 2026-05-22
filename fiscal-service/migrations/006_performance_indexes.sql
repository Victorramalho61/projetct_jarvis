-- 006: Índices de performance para tabelas do fiscal-service
-- Aplica via: docker exec jarvis-db-1 psql -U postgres -d postgres -f /tmp/006_performance_indexes.sql

-- Índice composto para o padrão principal de busca em fiscal_documents:
-- company_id + tipo + status + data_emissao (cobre 90% das queries da FiscalPage)
CREATE INDEX IF NOT EXISTS idx_fiscal_docs_company_tipo_status_data
    ON fiscal_documents (company_id, tipo, status, data_emissao DESC);

-- Índice auxiliar para ORDER BY data_emissao sem filtros de tipo/status
CREATE INDEX IF NOT EXISTS idx_fiscal_docs_company_data
    ON fiscal_documents (company_id, data_emissao DESC);

-- Índice para busca por emitente (prestador em NFSe, remetente em NFe)
CREATE INDEX IF NOT EXISTS idx_fiscal_docs_emitente_cnpj
    ON fiscal_documents (emitente_cnpj);

-- Índice para busca por destinatário / tomador
CREATE INDEX IF NOT EXISTS idx_fiscal_docs_destinatario_cnpj
    ON fiscal_documents (destinatario_cnpj);

-- fiscal_sync_logs: histórico recente por empresa + tipo (tab Sync e Certificados)
CREATE INDEX IF NOT EXISTS idx_sync_logs_company_tipo_data
    ON fiscal_sync_logs (company_id, tipo, executado_em DESC);

-- system_checks: índice composto para _bulk_enrich (monitored_systems dashboard)
-- Cobre: .in_(system_id).gte(checked_at).select(status) em uma única varredura de índice
CREATE INDEX IF NOT EXISTS idx_system_checks_sid_at_status
    ON system_checks (system_id, checked_at DESC, status)
    WHERE status IS NOT NULL;
