-- Migration 009 — direção do documento NFSe: 'emitida' (empresa é prestadora)
-- vs 'recebida' (empresa é tomadora). Necessário para diferenciar "NFSe
-- emitidas pela empresa" de "NFSe emitidas contra a empresa" nos filtros/UI.
-- Execute no Supabase SQL Editor (Settings → SQL Editor)

ALTER TABLE fiscal_documents
  ADD COLUMN IF NOT EXISTS direcao text; -- 'emitida' | 'recebida'

CREATE INDEX IF NOT EXISTS idx_fiscal_docs_direcao ON fiscal_documents(direcao) WHERE direcao IS NOT NULL;

-- Backfill dos dados já sincronizados
UPDATE fiscal_documents SET direcao = 'recebida' WHERE tipo = 'NFSe' AND fonte = 'ndd' AND direcao IS NULL;
UPDATE fiscal_documents SET direcao = 'emitida'  WHERE tipo = 'NFSe' AND fonte = 'municipal_direto' AND direcao IS NULL;

-- Portal Nacional: compara CNPJ (só dígitos) do emitente/destinatário com o CNPJ da empresa dona do company_id
UPDATE fiscal_documents d
SET direcao = 'emitida'
FROM fiscal_companies c
WHERE d.company_id = c.id
  AND d.tipo = 'NFSe' AND d.fonte = 'portal_nacional' AND d.direcao IS NULL
  AND regexp_replace(d.emitente_cnpj, '\D', '', 'g') = regexp_replace(c.cnpj, '\D', '', 'g');

UPDATE fiscal_documents d
SET direcao = 'recebida'
FROM fiscal_companies c
WHERE d.company_id = c.id
  AND d.tipo = 'NFSe' AND d.fonte = 'portal_nacional' AND d.direcao IS NULL
  AND regexp_replace(d.destinatario_cnpj, '\D', '', 'g') = regexp_replace(c.cnpj, '\D', '', 'g');
