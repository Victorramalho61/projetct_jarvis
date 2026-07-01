-- Migration: Adicionar tabelas de Projects (Freshservice PM / Freshrelease)
-- Execute no Supabase SQL Editor (Settings → SQL Editor)
-- Data: 2026-06-30

CREATE TABLE IF NOT EXISTS public.freshservice_projects (
    id          bigint PRIMARY KEY,
    name        text NOT NULL,
    key         text,
    description text,
    status_id   bigint,
    priority_id bigint,
    start_date  date,
    end_date    date,
    archived    boolean DEFAULT false,
    manager_id  bigint,
    raw         jsonb NOT NULL,
    synced_at   timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.freshservice_project_tasks (
    id                 bigint PRIMARY KEY,
    project_id         bigint NOT NULL REFERENCES public.freshservice_projects(id) ON DELETE CASCADE,
    title              text NOT NULL,
    display_key        text,
    status_id          bigint,
    priority_id        bigint,
    assignee_id        bigint,
    reporter_id        bigint,
    parent_id          bigint,
    planned_start_date date,
    planned_end_date   date,
    raw                jsonb NOT NULL,
    synced_at          timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_fspt_project  ON public.freshservice_project_tasks (project_id);
CREATE INDEX IF NOT EXISTS idx_fspt_assignee ON public.freshservice_project_tasks (assignee_id);
CREATE INDEX IF NOT EXISTS idx_fspt_status   ON public.freshservice_project_tasks (status_id);

-- A API do Freshservice Projects não expõe nome/categoria dos status (status_id são IDs
-- numéricos custom da conta). O sync auto-cadastra cada status_id visto com label=NULL;
-- o admin completa label e is_done na tela de Projetos para habilitar o cálculo de % conclusão.
CREATE TABLE IF NOT EXISTS public.freshservice_project_statuses (
    status_id  bigint PRIMARY KEY,
    kind       text NOT NULL CHECK (kind IN ('project', 'task')),
    label      text,
    is_done    boolean NOT NULL DEFAULT false,
    updated_at timestamptz NOT NULL DEFAULT now()
);

GRANT ALL ON public.freshservice_projects        TO anon, authenticated, service_role;
GRANT ALL ON public.freshservice_project_tasks   TO anon, authenticated, service_role;
GRANT ALL ON public.freshservice_project_statuses TO anon, authenticated, service_role;

ALTER TABLE public.freshservice_projects         DISABLE ROW LEVEL SECURITY;
ALTER TABLE public.freshservice_project_tasks    DISABLE ROW LEVEL SECURITY;
ALTER TABLE public.freshservice_project_statuses DISABLE ROW LEVEL SECURITY;

-- Confirma
SELECT COUNT(*) AS total_projects FROM public.freshservice_projects;
