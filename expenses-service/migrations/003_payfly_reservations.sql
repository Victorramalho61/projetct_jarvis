-- Migration 003: PayFly Reservations (Vendas API V2)
-- Execute no Supabase SQL Editor

CREATE TABLE IF NOT EXISTS payfly_reservations (
  -- Identificação
  id                          text PRIMARY KEY,
  type                        text,
  status                      text,
  os_number                   text,
  trip_type                   text,
  is_reissue                  boolean,
  original_id                 text,
  order_origin                text,

  -- Datas
  choice_date                 timestamptz,
  emission_date               timestamptz,
  travel_start_date           timestamptz,
  travel_end_date             timestamptz,
  approval_date               timestamptz,
  cancellation_date           timestamptz,
  expiration_date             timestamptz,
  last_update_date            timestamptz,
  request_date                timestamptz,

  -- Empresa
  company_id                  text,
  company_cnpj                text,
  company_name                text,

  -- Passageiro
  passenger_name              text,
  passenger_email             text,
  passenger_document          text,
  passenger_employee_id       text,
  passenger_department_name   text,
  passenger_age_group         text,
  passenger_employee_level    text,

  -- Aprovador / Solicitante
  approver_name               text,
  approver_email              text,
  solicitor_name              text,
  solicitor_email             text,

  -- Financeiro
  currency                    text,
  total_amount                numeric(18,2),
  daily_rate                  numeric(18,2),
  total_nights                int,
  base_fare                   numeric(18,2),
  service_tax                 numeric(18,2),
  boarding_tax                numeric(18,2),
  iss_tax                     numeric(18,2),
  net_amount                  numeric(18,2),
  published_fare              numeric(18,2),
  payment_method              text,

  -- Hotel
  hotel_name                  text,
  hotel_city                  text,
  hotel_address               text,
  checkin_date                timestamptz,
  checkout_date               timestamptz,
  rooms                       int,
  adults                      int,
  children                    int,
  destination                 text,
  record_locator              text,
  source_system               text,
  supplier_code               text,
  room_name                   text,
  cancellation_policy         text,

  -- Voo
  origin                      text,
  airline                     text,
  flight_number               text,
  cabin_class                 text,

  -- Corporativo
  cost_center_name            text,
  project_name                text,
  reason_name                 text,
  travel_justification_name   text,
  sales_channel               text,
  policy_compliance           text,

  -- Meta
  raw_json                    jsonb,
  synced_at                   timestamptz DEFAULT now(),
  created_at                  timestamptz DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_pf_res_status         ON payfly_reservations (status);
CREATE INDEX IF NOT EXISTS idx_pf_res_type           ON payfly_reservations (type);
CREATE INDEX IF NOT EXISTS idx_pf_res_company        ON payfly_reservations (company_name);
CREATE INDEX IF NOT EXISTS idx_pf_res_choice_date    ON payfly_reservations (choice_date);
CREATE INDEX IF NOT EXISTS idx_pf_res_travel_start   ON payfly_reservations (travel_start_date);
CREATE INDEX IF NOT EXISTS idx_pf_res_total_amount   ON payfly_reservations (total_amount);

-- ── RPC: payfly_reservation_stats ────────────────────────────────────────────

CREATE OR REPLACE FUNCTION payfly_reservation_stats(
  p_start_date  date DEFAULT NULL,
  p_end_date    date DEFAULT NULL,
  p_company     text DEFAULT NULL,
  p_status      text DEFAULT NULL,
  p_type        text DEFAULT NULL
)
RETURNS json AS $$
  SELECT json_build_object(
    'total_count',    COUNT(*),
    'total_amount',   COALESCE(SUM(total_amount), 0),
    'amount_flight',  COALESCE(SUM(total_amount) FILTER (WHERE type = 'flight'), 0),
    'amount_hotel',   COALESCE(SUM(total_amount) FILTER (WHERE type = 'hotel'),  0),
    'count_flight',   COUNT(*) FILTER (WHERE type = 'flight'),
    'count_hotel',    COUNT(*) FILTER (WHERE type = 'hotel'),
    'por_status', json_build_object(
      'Emitido',   COUNT(*) FILTER (WHERE status = 'Emitido'),
      'Cancelado', COUNT(*) FILTER (WHERE status = 'Cancelado'),
      'Reservado', COUNT(*) FILTER (WHERE status = 'Reservado'),
      'Expirado',  COUNT(*) FILTER (WHERE status = 'Expirado')
    ),
    'por_empresa', (
      SELECT json_object_agg(company_name, cnt)
      FROM (
        SELECT company_name, COUNT(*) AS cnt
        FROM payfly_reservations
        WHERE
          (p_start_date IS NULL OR choice_date::date >= p_start_date)
          AND (p_end_date   IS NULL OR choice_date::date <= p_end_date)
          AND (p_company    IS NULL OR company_name     = p_company)
          AND (p_status     IS NULL OR status           = p_status)
          AND (p_type       IS NULL OR type             = p_type)
        GROUP BY company_name
        ORDER BY cnt DESC
        LIMIT 20
      ) sub
    )
  )
  FROM payfly_reservations
  WHERE
    (p_start_date IS NULL OR choice_date::date >= p_start_date)
    AND (p_end_date   IS NULL OR choice_date::date <= p_end_date)
    AND (p_company    IS NULL OR company_name     = p_company)
    AND (p_status     IS NULL OR status           = p_status)
    AND (p_type       IS NULL OR type             = p_type);
$$ LANGUAGE sql STABLE;

-- ── RPC: payfly_dashboard ─────────────────────────────────────────────────────

CREATE OR REPLACE FUNCTION payfly_dashboard(
  p_start_date  date DEFAULT NULL,
  p_end_date    date DEFAULT NULL,
  p_company     text DEFAULT NULL
)
RETURNS json AS $$
  SELECT json_build_object(
    'total_amount', COALESCE(SUM(total_amount), 0),
    'total_count',  COUNT(*),
    'top10_by_value', (
      SELECT json_agg(r ORDER BY r.total_amount DESC)
      FROM (
        SELECT solicitor_name,
               SUM(total_amount) AS total_amount,
               COUNT(*)          AS qty
        FROM payfly_reservations
        WHERE status != 'Cancelado'
          AND (p_start_date IS NULL OR choice_date::date >= p_start_date)
          AND (p_end_date   IS NULL OR choice_date::date <= p_end_date)
          AND (p_company    IS NULL OR company_name      = p_company)
          AND solicitor_name IS NOT NULL
        GROUP BY solicitor_name
        ORDER BY total_amount DESC
        LIMIT 10
      ) r
    ),
    'top10_by_qty', (
      SELECT json_agg(r ORDER BY r.qty DESC)
      FROM (
        SELECT solicitor_name,
               COUNT(*)          AS qty,
               SUM(total_amount) AS total_amount
        FROM payfly_reservations
        WHERE status != 'Cancelado'
          AND (p_start_date IS NULL OR choice_date::date >= p_start_date)
          AND (p_end_date   IS NULL OR choice_date::date <= p_end_date)
          AND (p_company    IS NULL OR company_name      = p_company)
          AND solicitor_name IS NOT NULL
        GROUP BY solicitor_name
        ORDER BY qty DESC
        LIMIT 10
      ) r
    )
  )
  FROM payfly_reservations
  WHERE status != 'Cancelado'
    AND (p_start_date IS NULL OR choice_date::date >= p_start_date)
    AND (p_end_date   IS NULL OR choice_date::date <= p_end_date)
    AND (p_company    IS NULL OR company_name      = p_company);
$$ LANGUAGE sql STABLE;
