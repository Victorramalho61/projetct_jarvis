# Jarvis — Documentação do Projeto

## Visão Geral

Sistema interno da Voetur/VTCLog com autenticação própria e três módulos principais:
- **Moneypenny** — resumo diário de e-mails e agenda via Microsoft 365 (e-mail, Teams, WhatsApp)
- **Monitoramento** — health check agendado de sistemas com alertas WhatsApp e dashboard em tempo real
- **Gestão de Acesso** — aprovação/recusa de solicitações, controle de roles e perfis

## Arquitetura

```
┌────────────────────────────────────────────────────────────────┐
│  Servidor Windows Server 2022 — 10.61.10.100                   │
│                                                                 │
│  ┌──────────────┐    ┌──────────────┐   ┌──────────────────┐  │
│  │  Frontend    │    │  Backend     │   │  Monitor Agent   │  │
│  │  React+Vite  │───▶│  FastAPI     │   │  Python/psutil   │  │
│  │  nginx :3000 │    │  Python :8000│   │  :9100 (interno) │  │
│  └──────────────┘    └──────┬───────┘   └──────────────────┘  │
│                             │ http://kong:8000                  │
│  ┌──────────────────────────▼──────────────────────────────┐   │
│  │  Supabase Self-Hosted (Docker Compose)                  │   │
│  │                                                         │   │
│  │  kong :54321  ──▶  postgrest (REST API)                 │   │
│  │                ──▶  gotrue   (auth)                     │   │
│  │                ──▶  realtime                           │   │
│  │                ──▶  storage                            │   │
│  │                                                         │   │
│  │  postgres :5432 (127.0.0.1 only)                        │   │
│  │  studio   :54323 (127.0.0.1 only — admin local)         │   │
│  └─────────────────────────────────────────────────────────┘   │
│                             │                                   │
│                 WhatsApp alertas                                │
│                             ▼                                   │
│              Evolution API — OCI São Paulo                      │
│              http://168.138.129.157:8080                        │
└────────────────────────────────────────────────────────────────┘
```

## Portas dos Serviços

| Porta  | Serviço              | Bind          | Acesso externo |
|--------|----------------------|---------------|----------------|
| 3000   | Frontend (nginx)     | 0.0.0.0       | firewall fecha |
| 8000   | Backend (FastAPI)    | 0.0.0.0       | firewall fecha |
| 5432   | PostgreSQL           | **127.0.0.1** | bloqueado      |
| 9100   | Monitor Agent        | **127.0.0.1** | bloqueado      |
| 54321  | Supabase API (Kong)  | 0.0.0.0       | firewall fecha |
| 54322  | Supabase API (HTTPS) | 0.0.0.0       | firewall fecha |
| 54323  | Supabase Studio      | **127.0.0.1** | bloqueado      |

> Firewall Windows: nenhuma porta liberada externamente. Abertura manual pelo administrador.

## Stack

- **Frontend**: React 18 + TypeScript + Vite + Tailwind CSS → build Docker com `nginx:alpine`
- **Backend**: FastAPI (Python 3.11) + Supabase Python SDK + APScheduler + httpx + slowapi
- **Banco**: Supabase self-hosted (PostgreSQL 15, GoTrue, PostgREST, Realtime, Storage, Kong)
- **Monitor Agent**: Python 3.12 + psutil — expõe `/metrics` com CPU/RAM/disco em JSON
- **CI/CD**: GitHub Actions → SSH → `deploy.sh` → `docker compose up -d --build`

## Módulos

### Moneypenny
Resumo diário via Microsoft Graph API. Busca e-mails não lidos e agenda do dia, envia via canal configurado pelo usuário.
- Canais: e-mail (HTML), Teams (Adaptive Card), WhatsApp (texto)
- `channels_config` JSONB define quais canais e conteúdo por canal
- Tokens OAuth Microsoft renovados automaticamente via refresh_token
- WhatsApp enviado sempre em background (Evolution API OCI free tier é lenta)

### Monitoramento
Health checks agendados via APScheduler (a cada 5 min por padrão).
- Tipos: `http` (status code), `evolution` (connectionState), `metrics` (monitor-agent), `custom`
- Alertas WhatsApp para admins com **cooldown de 30 min** (deduplicação)
- Alerta de recuperação quando sistema volta de DOWN → UP
- Dashboard em tempo real com auto-refresh a cada 30s
- Histórico paginado de checks por sistema

### Gestão de Acesso
- Solicitação de acesso com domínios permitidos: `@voetur.com.br`, `@vtclog.com.br`
- Primeiro usuário cadastrado vira admin automaticamente
- Admins aprovam ou recusam solicitações (recusar deleta o perfil pendente)
- Roles: `admin` | `user`

## Segurança

| Camada | Proteção |
|---|---|
| Login | Rate limit: 10 req/min por IP (slowapi) |
| Solicitação de acesso | Rate limit: 5 req/min por IP |
| Agent push | Rate limit: 60 req/min por IP |
| Senhas | bcrypt + mínimo 8 caracteres |
| Audit trail | Login (sucesso/falha) registrado em `app_logs` |
| PostgreSQL | Bind em 127.0.0.1 (inacessível externamente) |
| Supabase Studio | Bind em 127.0.0.1 (admin local apenas) |
| Tokens JWT | HS256, expiração configurável (`JWT_EXPIRE_MINUTES`) |

## Configuração (`docker-compose.yml` + `.env`)

O arquivo `.env` na raiz configura todos os serviços. **Nunca commitar o `.env`.**

### Variáveis Críticas

| Variável                    | Descrição                                                  |
|-----------------------------|------------------------------------------------------------|
| `POSTGRES_PASSWORD`         | Senha do PostgreSQL (todos os usuários internos)           |
| `SUPABASE_JWT_SECRET`       | Secret JWT do Supabase (GoTrue + PostgREST + Kong)         |
| `ANON_KEY`                 | JWT role `anon` — gerado do `SUPABASE_JWT_SECRET`          |
| `SERVICE_ROLE_KEY`         | JWT role `service_role` — gerado do `SUPABASE_JWT_SECRET`  |
| `JWT_SECRET`                | Secret JWT da aplicação (diferente do Supabase)            |
| `API_EXTERNAL_URL`          | URL externa da API Supabase (ex: `http://IP:54321`)        |
| `SITE_URL`                  | URL do frontend (ex: `http://IP:3000`)                     |
| `MICROSOFT_CLIENT_ID`       | Azure AD app "Moneypenny" — ID do cliente                  |
| `MICROSOFT_TENANT_ID`       | Azure AD tenant ID                                         |
| `MICROSOFT_CLIENT_SECRET`   | Azure AD client secret                                     |
| `MICROSOFT_REDIRECT_URI`    | `http://IP:8000/api/moneypenny/auth/microsoft/callback`    |
| `WHATSAPP_API_URL`          | URL da Evolution API (ex: `http://168.138.129.157:8080`)   |
| `WHATSAPP_API_KEY`          | API key da Evolution API                                   |
| `WHATSAPP_INSTANCE`         | Nome da instância WhatsApp (ex: `voetur`)                  |
| `MONITOR_AGENT_URL`         | `http://monitor-agent:9100` (interno Docker)               |
| `MONITOR_AGENT_TOKENS`      | Token(s) para autenticar o agente (separados por vírgula)  |
| `REALTIME_SECRET_KEY_BASE`  | Secret base do Supabase Realtime                           |
| `REALTIME_DB_ENC_KEY`       | Chave de criptografia do Realtime                          |

### Geração dos JWTs do Supabase

```python
import jwt
secret = "SEU_SUPABASE_JWT_SECRET"
jwt.encode({"iss":"supabase-local","role":"anon","exp":2051222400}, secret, algorithm="HS256")
jwt.encode({"iss":"supabase-local","role":"service_role","exp":2051222400}, secret, algorithm="HS256")
```

## Schema do Banco

Arquivo: `schema.sql` — aplicar em banco novo:
```bash
docker exec -i jarvis-db-1 bash -c \
  "PGPASSWORD='...' psql -U postgres -d postgres" < schema.sql
```

### Tabelas

| Tabela | Descrição |
|---|---|
| `profiles` | Usuários — bcrypt, role admin/user, primeiro cadastro vira admin |
| `connected_accounts` | OAuth Microsoft 365 — access/refresh token, renovação automática |
| `notification_prefs` | Preferências Moneypenny — channels_config JSONB, horário UTC |
| `app_logs` | Audit trail do sistema — login, erros, alertas (paginado 100/req) |
| `monitored_systems` | Sistemas monitorados — tipo, URL, config, last_alerted_at |
| `system_checks` | Histórico de checks — status, latência, métricas, deduplicado |

## CI/CD

### GitHub Actions (`.github/workflows/deploy.yml`)

1. **security-scan** — Gitleaks (detecção de secrets no código)
2. **test-backend** — pytest + pip-audit
3. **test-frontend** — typecheck + npm audit
4. **deploy** — SSH → `bash ~/app/backend/deploy.sh`

### Secrets do GitHub

| Secret            | Valor                                      |
|-------------------|--------------------------------------------|
| `SSH_HOST`        | IP do servidor (10.61.10.100)              |
| `SSH_USER`        | Usuário SSH                                |
| `SSH_PRIVATE_KEY` | Chave privada SSH (PEM)                    |
| `SUPABASE_URL`    | `http://localhost:54321` (para testes CI)  |
| `SUPABASE_KEY`    | Service role key (para testes CI)          |
| `JWT_SECRET`      | Secret JWT da app (para testes CI)         |

### `deploy.sh`

1. Verifica `.env` existe
2. `git fetch` + `git checkout origin/main`
3. `docker compose up -d --build`

## Microsoft 365 / Azure AD

App: **Moneypenny** (`e1084655-9bfe-41fc-bc59-3f76bd172b17`)  
Tenant: `fb902eca-dc08-4dec-9e2c-7ce70ee14cf5`  
Scopes: `Calendars.Read Mail.Read Mail.Send User.Read`

Redirect URI registrado no Azure AD:
```
http://10.61.10.100:8000/api/moneypenny/auth/microsoft/callback
```

## WhatsApp (Evolution API)

- Instância: `voetur` | API Key: `voetur_evolution_2026`
- Servidor: OCI São Paulo — `http://168.138.129.157:8080`
- Envio em background — `ReadTimeout` tratado como entregue (OCI free tier lento)
- Alertas de monitoramento com cooldown 30 min para evitar spam

## Comandos Úteis

```bash
# Status de todos os containers
docker compose ps

# Logs em tempo real
docker compose logs -f backend
docker compose logs -f monitor-agent

# Rebuild de serviço específico
docker compose up -d --build backend

# Acessar banco diretamente
docker exec -it jarvis-db-1 bash -c \
  "PGPASSWORD='...' psql -U postgres -d postgres"

# Métricas do servidor (CPU/RAM/disco)
curl http://localhost:9100/metrics

# Reiniciar tudo
docker compose restart
```
