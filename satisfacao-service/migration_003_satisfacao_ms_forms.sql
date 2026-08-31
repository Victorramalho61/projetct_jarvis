-- Migration 003: Integração Microsoft Forms (substitui o formulário público próprio,
-- inacessível para clientes externos à rede da Voetur)

ALTER TABLE sat_campanhas ADD COLUMN IF NOT EXISTS ms_forms_url text;

-- token/token_expires_at de sat_respostas ficam órfãos (formulário próprio removido) —
-- sem migration destrutiva agora, não vale o risco.

CREATE TABLE IF NOT EXISTS sat_ms_forms_log (
  id                    uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  campanha_id           uuid REFERENCES sat_campanhas(id),
  resposta_id           uuid REFERENCES sat_respostas(id),
  cliente_id            uuid REFERENCES sat_clientes(id),
  ano_informado         int,
  email_informado       text,
  empresa_informada     text,
  ms_forms_response_id  text,
  payload_bruto         jsonb NOT NULL,
  matched               boolean NOT NULL DEFAULT false,
  status                text NOT NULL DEFAULT 'recebido'
                          CHECK (status IN ('recebido','conciliado','erro','ignorado')),
  erro_detalhe          text,
  conciliado_por        text,
  conciliado_em         timestamptz,
  recebido_em           timestamptz NOT NULL DEFAULT now()
);

-- Evita conciliar a mesma resposta do Forms duas vezes (reprocessamento do Power Automate)
CREATE UNIQUE INDEX IF NOT EXISTS idx_sat_ms_forms_log_response_id
  ON sat_ms_forms_log(ms_forms_response_id) WHERE ms_forms_response_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_sat_ms_forms_log_campanha ON sat_ms_forms_log(campanha_id);
CREATE INDEX IF NOT EXISTS idx_sat_ms_forms_log_status   ON sat_ms_forms_log(status);

ALTER TABLE sat_ms_forms_log ENABLE ROW LEVEL SECURITY;
CREATE POLICY "service_role_all" ON sat_ms_forms_log FOR ALL TO service_role USING (true) WITH CHECK (true);

-- Corrige o CHECK de canal_resposta pra aceitar 'ms_forms'.
-- Inspecionar o nome real da constraint antes de rodar em produção:
--   SELECT conname FROM pg_constraint WHERE conrelid = 'sat_respostas'::regclass AND contype = 'c';
DO $$
DECLARE
  constraint_name text;
BEGIN
  SELECT con.conname INTO constraint_name
  FROM pg_constraint con
  JOIN pg_class rel ON rel.oid = con.conrelid
  JOIN pg_attribute att ON att.attrelid = rel.oid
  WHERE rel.relname = 'sat_respostas'
    AND con.contype = 'c'
    AND con.conkey = ARRAY[att.attnum]
    AND att.attname = 'canal_resposta';

  IF constraint_name IS NOT NULL THEN
    EXECUTE format('ALTER TABLE sat_respostas DROP CONSTRAINT %I', constraint_name);
  END IF;
END $$;

ALTER TABLE sat_respostas ADD CONSTRAINT sat_respostas_canal_resposta_check
  CHECK (canal_resposta IN ('formulario_link', 'manual_sgi', 'ms_forms'));
