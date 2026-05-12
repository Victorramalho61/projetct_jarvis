-- VoeIA Support Service schema
-- Run against the Supabase PostgreSQL instance before starting support-service

CREATE TABLE IF NOT EXISTS support_users (
    id            BIGSERIAL PRIMARY KEY,
    phone         TEXT UNIQUE NOT NULL,
    name          TEXT,
    email         TEXT,
    company       TEXT,
    location      TEXT,
    freshservice_requester_id BIGINT,
    profile_complete BOOLEAN NOT NULL DEFAULT FALSE,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS support_conversations (
    id            BIGSERIAL PRIMARY KEY,
    phone         TEXT NOT NULL UNIQUE,
    state         TEXT NOT NULL DEFAULT 'onboarding_email',
    context       JSONB NOT NULL DEFAULT '{}',
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS support_messages (
    id              BIGSERIAL PRIMARY KEY,
    conversation_id BIGINT REFERENCES support_conversations(id) ON DELETE CASCADE,
    direction       TEXT NOT NULL CHECK (direction IN ('inbound', 'outbound')),
    content         TEXT NOT NULL,
    message_id      TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE UNIQUE INDEX IF NOT EXISTS uniq_support_messages_msg_id
    ON support_messages(message_id) WHERE message_id IS NOT NULL;

CREATE TABLE IF NOT EXISTS support_tickets (
    id                     BIGSERIAL PRIMARY KEY,
    freshservice_ticket_id BIGINT UNIQUE NOT NULL,
    phone                  TEXT NOT NULL,
    status                 INT NOT NULL DEFAULT 2,
    subject                TEXT,
    created_at             TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at             TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS support_notifications (
    id                     BIGSERIAL PRIMARY KEY,
    freshservice_ticket_id BIGINT NOT NULL,
    event_type             TEXT NOT NULL,
    phone                  TEXT,
    sent                   BOOLEAN NOT NULL DEFAULT FALSE,
    payload                JSONB,
    created_at             TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (freshservice_ticket_id, event_type)
);

CREATE INDEX IF NOT EXISTS idx_support_conversations_phone ON support_conversations(phone);
CREATE INDEX IF NOT EXISTS idx_support_tickets_phone       ON support_tickets(phone);
CREATE INDEX IF NOT EXISTS idx_support_notifications_ticket ON support_notifications(freshservice_ticket_id);
