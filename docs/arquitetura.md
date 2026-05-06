# Jarvis — Arquitetura e Documentação

## Visão Geral

Sistema interno da Voetur/VTCLog com autenticação própria e sete módulos:

| Módulo | Serviço | Descrição |
|---|---|---|
| Core | core-service | Autenticação, usuários, administração |
| Monitoramento | monitoring-service | Health checks agendados, dashboard em tempo real |
| Freshservice | freshservice-service | Dashboard e sync de tickets do helpdesk |
| Moneypenny | moneypenny-service | Resumo diário de e-mails e agenda via Microsoft 365 |
| Agentes | agents-service | Jobs agendados + criação de agentes via Claude AI |
| Gastos TI | expenses-service | Dashboard financeiro executivo — despesas de TI via ERP Benner |
| Governança | governance-service | Cruzamento Jarvis×Benner, análise de aderência contratual, totais financeiros, verificação de conformidade e dashboard de oportunidades |

---

## Arquitetura

```
Browser
  └─► nginx:443 (HTTPS — frontend container)
        ├─ /api/* ─────────────────────────► Kong:8000 (interno Docker)
        │                                     ├─ /api/auth, /api/users, /api/admin, /api/health
        │                                     │     └─► core-service:8001
        │                                     ├─ /api/monitoring/*
        │                                     │     └─► monitoring-service:8002
        │                                     ├─ /api/freshservice/*
        │                                     │     └─► freshservice-service:8003
        │                                     ├─ /api/moneypenny/*
        │                                     │     └─► moneypenny-service:8004
        │                                     ├─ /api/agents/*
        │                                     │     └─► agents-service:8005
        │                                     ├─ /api/expenses/*
        │                                     │     └─► expenses-service:8006
        │                                     └─ /api/governance/*
        │                                           └─► governance-service:8007
        └─ / ──────────────────────────────► SPA React (nginx serve estático)

Inter-serviço (Docker app_net):
  agents-service → freshservice-service:8003 (HTTP interno + JWT gerado em agent_runner.py)
  expenses-service → SQL Server externo 10.141.0.111:1444 (BennerSistemaCorporativo — leitura)
  governance-service → SQL Server externo 10.141.0.111:1444 (BennerSistemaCorporativo — leitura)

Supabase Self-Hosted (Docker app_net):
  Kong:8000 → postgrest, gotrue, realtime, storage
  postgres:5432  (127.0.0.1 — nunca exposto)
  studio:54323   (127.0.0.1 — admin local)
```

---

## Portas

| Porta | Serviço | Bind | Acesso externo |
|---|---|---|---|
| 443 | nginx (HTTPS) | 0.0.0.0 | sim |
| 80 | nginx (redirect) | 0.0.0.0 | sim |
| 5432 | PostgreSQL | 127.0.0.1 | bloqueado |
| 9100 | Monitor Agent | 127.0.0.1 | bloqueado |
| 8080 | Evolution API | 127.0.0.1 | bloqueado |
| 54321 | Supabase Kong | 127.0.0.1 | bloqueado |
| 54323 | Supabase Studio | 127.0.0.1 | bloqueado |

Microsserviços (8001–8007): sem portas expostas ao host, apenas rede interna Docker.

> **Atualizações recentes**: Intervalos de health checks reduzidos para 5 minutos, polling de agentes ajustado para 60 segundos, polling SSE alterado de 2s para 5s, validação de priorização (priority/effort/risk) e limitação a 3 propostas por ciclo no módulo de agentes.

---

## Stack

- **Frontend**: React 18 + TypeScript + Vite + Tailwind CSS + Recharts → build com `nginx:alpine`
- **Microsserviços**: FastAPI (Python 3.11) + Supabase SDK + APScheduler + httpx + slowapi + pyodbc
- **Gateway**: Kong 2.8.1 — config declarativa em `volumes/api/kong.yml`
- **Banco**: Supabase self-hosted (PostgreSQL 15, GoTrue, PostgREST, Realtime, Storage)
- **Monitor Agent**: Python 3.12 + psutil — expõe `/metrics` (CPU/RAM/disco)
- **CI/CD**: GitHub Actions (self-hosted runner) → `deploy.sh` → `docker compose up -d --build`

> **Melhorias recentes**: Governança com cruzamento Jarvis×Benner e verificação de aderência contratual aprimorada, resiliência em proposals, priorização com base em impacto (priority/effort/risk), limitação a 3 propostas por ciclo e card de taxa de falhas.