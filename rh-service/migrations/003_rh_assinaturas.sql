-- rh-service -- Fase 2: assinatura eletronica via D4Sign
-- Execute via Supabase SQL Editor, apos 001_rh_schema.sql e 002_rh_pipeline.sql

CREATE TABLE IF NOT EXISTS rh_assinaturas (
    id                     uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    vaga_id                uuid NOT NULL REFERENCES rh_vagas(id) ON DELETE CASCADE,
    d4sign_document_uuid   text,
    status                 text NOT NULL DEFAULT 'PRE_ENVIO'
                               CHECK (status IN ('PRE_ENVIO', 'ENVIADO', 'PARCIAL', 'EM_ALTERACAO', 'CONCLUIDO')),
    signatarios            jsonb NOT NULL DEFAULT '[]'::jsonb,
    documento_assinado     text,   -- PDF final em base64, mesmo padrao do certificado A1 no fiscal-service
    historico_documentos   jsonb NOT NULL DEFAULT '[]'::jsonb,  -- document_uuid cancelados (alterar/cancelar), com timestamp
    -- aditivo: so preenchido quando esta linha representa um aditivo/distrato de outra
    aditivo_de_id          uuid REFERENCES rh_assinaturas(id),
    tipo_aditivo           text CHECK (tipo_aditivo IN ('CANCELAMENTO', 'ALTERACAO')),
    justificativa_aditivo  text,
    created_at             timestamptz NOT NULL DEFAULT now(),
    updated_at             timestamptz NOT NULL DEFAULT now(),
    created_by             uuid REFERENCES profiles(id)
);

CREATE INDEX IF NOT EXISTS idx_rh_assinaturas_vaga       ON rh_assinaturas(vaga_id);
CREATE INDEX IF NOT EXISTS idx_rh_assinaturas_status     ON rh_assinaturas(status);
CREATE INDEX IF NOT EXISTS idx_rh_assinaturas_document   ON rh_assinaturas(d4sign_document_uuid);
CREATE INDEX IF NOT EXISTS idx_rh_assinaturas_aditivo_de ON rh_assinaturas(aditivo_de_id);

ALTER TABLE rh_assinaturas ENABLE ROW LEVEL SECURITY;
ALTER TABLE rh_assinaturas FORCE ROW LEVEL SECURITY;
CREATE POLICY "rh_assinaturas_service_role" ON rh_assinaturas
    FOR ALL TO service_role USING (true) WITH CHECK (true);
