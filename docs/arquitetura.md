# Jarvis — Arquitetura e Documentação

## Visão Geral

Sistema interno da Voetur/VTCLog com autenticação própria e seis módulos:

| Módulo | Serviço | Descrição |
|---|---|---|
| Core | core-service | Autenticação, usuários, administração |
| Monitoramento | monitoring-service | Health checks agendados, dashboard em tempo real |
| Freshservice | freshservice-service | Dashboard e sync de tickets do helpdesk |
| Moneypenny | moneypenny-service | Resumo diário de e-mails e agenda via Microsoft 365 |
| Agentes | agents-service | Jobs agendados + criação de agentes via Claude AI |
| Gastos TI | expenses-service | Dashboard financeiro executivo — despesas de TI via ERP Benner |

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
        │                                     └─ /api/expenses/*
        │                                           └─► expenses-service:8006
        └─ / ──────────────────────────────► SPA React (nginx serve estático)

Inter-serviço (Docker app_net):
  agents-service → freshservice-service:8003 (HTTP interno + JWT gerado em agent_runner.py)
  expenses-service → SQL Server externo 10.141.0.111:1444 (BennerSistemaCorporativo — leitura)

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

Microsserviços (8001–8006): sem portas expostas ao host, apenas rede interna Docker.

---

## Stack

- **Frontend**: React 18 + TypeScript + Vite + Tailwind CSS + Recharts → build com `nginx:alpine`
- **Microsserviços**: FastAPI (Python 3.11) + Supabase SDK + APScheduler + httpx + slowapi + pyodbc
- **Gateway**: Kong 2.8.1 — config declarativa em `volumes/api/kong.yml`
- **Banco**: Supabase self-hosted (PostgreSQL 15, GoTrue, PostgREST, Realtime, Storage)
- **Monitor Agent**: Python 3.12 + psutil — expõe `/metrics` (CPU/RAM/disco)
- **CI/CD**: GitHub Actions (self-hosted runner) → `deploy.sh` → `docker compose up -d --build`

---

## Microsserviços — Estrutura Padrão

Cada serviço tem a mesma estrutura:

```
{service}/
├── Dockerfile
├── requirements.txt
├── main.py          # FastAPI: routers + CORS + lifespan
├── db.py            # Supabase client + Settings (pydantic-settings)
├── auth.py          # JWT decode + require_role dependency
├── limiter.py       # slowapi rate limiter
├── app_logger.py    # log_event → tabela app_logs
├── routes/
│   ├── health.py    # GET /health (liveness) + GET /ready (readiness)
│   └── {module}.py
└── services/
    └── {specific}.py
```

`db.py`, `auth.py`, `limiter.py` e `app_logger.py` são cópias compartilhadas — mudanças devem ser replicadas nos 5 serviços.

### Schedulers

| Serviço | Job | Frequência |
|---|---|---|
| monitoring-service | run_all_checks | a cada 5 min |
| freshservice-service | run_daily_sync | diariamente às 9h UTC |
| moneypenny-service | run_daily_summaries | a cada hora (minuto 0) |
| agents-service | jobs dinâmicos por agente | configurável via CRUD (manual/interval/daily/weekly/monthly) |

---

## Módulo de Agentes (agents-service)

### Tipos de agente

| `agent_type` | Descrição |
|---|---|
| `freshservice_sync` | Dispara sync do Freshservice via HTTP interno. Config: `{"mode": "daily"}` ou `{"mode": "backfill"}` |
| `script` | Executa código Python em subprocess isolado |
| `langgraph` | Agente LangGraph com raciocínio LLM |

### Pipelines LangGraph

O sistema de agentes é orquestrado via LangGraph com 6 pipelines que rodam em scheduler:

| Pipeline | Frequência | Agentes |
|---|---|---|
| `monitoring` | 15 min | uptime, quality, docker_intel, backend_agent, infrastructure, api_agent, log_scanner |
| `security` | 30 min | security, code_security |
| `cicd` | 5 min | cicd_monitor |
| `dba` | 4 h | db_dba_agent |
| `governance` | diário (6h) | opportunity_scout, log_strategic_advisor, change_mgmt, itil_version, quality_validator, docs, quality_code_backend, quality_code_frontend, integration_validator, change_validator, scheduling, automation, log_intelligence, log_improver, fix_validator, **proposal_supervisor**, **llm_manager_agent** |
| `evolution` | diário (7h) | evolution_agent, frontend_agent |

**Roteamento manual de proposals**: além do pipeline diário às 6h, o `proposal_supervisor` pode ser acionado imediatamente via `POST /api/agents/proposals/route-approved` (botão "Rotear N aprovadas" na página Proposals).

**Nota**: `proposal_supervisor` processa até 200 proposals aprovadas por ciclo. Proposals de tipo `index`/`vacuum` são auto-executadas (SQL seguro). Demais tipos são roteadas para o agente responsável e mudam para status `auto_implementing`.

Além dos pipelines, o `agent_health_supervisor` roda a cada 15 min como job separado.

### CTO Agent — Supervisor Central

O **CTO Agent** é o supervisor infalível do sistema. Responsabilidades:
- Recebe todos os reports de todos os agentes via mensagens e eventos
- Avalia SLAs e aciona agentes para auto-resolução
- Cobra agentes silenciosos e em falha (auto-recovery)
- Aciona `evolution_agent` para toda falha, gap ou oportunidade
- Propõe melhorias ao humano em formato organizado (🚨 Crítico / ⚠️ Alertas / 💡 Oportunidades)
- Usa cascata multi-LLM para nunca falhar: Groq → Together → HF → Ollama

### Agentes Especializados

| Agente | Pipeline | Skill | SLA Principal |
|---|---|---|---|
| `cto` | manual | Supervisor central | 100% agentes com qualidade garantida |
| `agent_health_supervisor` | health (15min) | Saúde de todos os agentes + auto-recovery | 100% agentes saudáveis |
| `proposal_supervisor` | governance | Executa proposals aprovadas por humanos | 90% execution rate |
| `llm_manager_agent` | governance | Saúde dos LLMs + routing adaptativo | 80% providers disponíveis |
| `evolution_agent` | evolution | Inovação, novos agentes, SLAs automáticos | ≥2 proposals/ciclo |
| `db_dba_agent` | dba | DBA PostgreSQL: índices, vacuum, backup, locks | 100% backup success |
| `api_agent` | monitoring | Validação de endpoints e contratos de API | 95% endpoint availability |
| `integration_validator` | governance | Validação de integrações externas | 100% integrations checked |
| `opportunity_scout` | governance | Radar de oportunidades e melhorias | ≥3 oportunidades/ciclo |
| `docker_intel` | monitoring | Inteligência de containers e recursos | 100% containers monitored |
| `security` + `code_security` | security | Segurança e vulnerabilidades | 100% scan coverage |

### Sistema de SLAs

Cada agente possui exatamente 3+ SLAs de execução (não de health — esse é do `agent_health_supervisor`):
- Armazenados na tabela `agent_slas` com histórico em `agent_sla_history`
- Gerados automaticamente pelo `evolution_agent` para novos agentes
- Pré-definidos para todos os agentes existentes
- Reportados via `sla_tracker.report_sla()` ao final de cada run
- Endpoint: `GET /api/agents/slas` — visão geral e por agente

### LLMs Multi-Provider (gratuito/open-source)

Cascata automática com fallback:
1. **Groq** (groq.com — free tier, Llama 3.3 70B / 8B, ultrarrápido)
2. **Together AI** (together.ai — free tier, Llama / Qwen)
3. **HuggingFace** (huggingface.co — free inference API)
4. **Ollama** (local — llama3.2:1b, sempre disponível)

Funções: `get_reasoning_llm()`, `get_fast_llm()`, `get_code_llm()`, `invoke_with_fallback()`.

### Todos os Agentes com Capacidade LLM

O `llm_mixin.py` adiciona automaticamente análise LLM a todos os agentes determinísticos:
- Analisa findings e gera proposals de melhoria via LLM
- Reporta problemas e gaps ao CTO e ao `evolution_agent`
- Usa `build_llm_enhanced_agent()` wrapper no `graph.py`

### Code Generator

O `code_generator.py` permite que qualquer agente gere planos de implementação com código real:
- Python, SQL, Dockerfile, TypeScript, shell
- Plano de rollback e verificação
- Auto-execução segura de SQL (ANALYZE, CREATE INDEX CONCURRENTLY, VACUUM)

### Tipos de agendamento (agents manuais)

| `schedule_type` | `schedule_config` |
|---|---|
| `manual` | `{}` |
| `interval` | `{"minutes": 30}` |
| `daily` | `{"hour": 9, "minute": 0}` |
| `weekly` | `{"day_of_week": "mon", "hour": 9, "minute": 0}` |
| `monthly` | `{"day": 1, "hour": 9, "minute": 0}` |

Horários em **BRT (America/Sao_Paulo)**.

### Criação de agentes via Claude AI

Cada usuário pode criar agentes via chat com Claude usando sua própria chave Anthropic (cadastrada em Perfil → Chave Anthropic). O Claude tem acesso à ferramenta `create_agent` que faz INSERT na tabela `agents` — sem acesso a DDL ou a outras operações.

### Segurança do subprocess

Scripts Python executados por agentes do tipo `script` rodam em subprocess com ambiente filtrado:
- ✅ Disponível: `SUPABASE_URL`, `SUPABASE_ANON_KEY` (read-only + RLS)
- ❌ Bloqueado: `SERVICE_ROLE_KEY`, `ANTHROPIC_API_KEY`, `JWT_SECRET`

---

## Autenticação e Segurança

- JWT HS256 assinado com `JWT_SECRET` (compartilhado entre todos os microsserviços)
- Token contém: `id`, `username`, `email`, `role` (`admin` ou `user`), `active`
- Rotas admin: `Depends(require_role("admin"))` — retorna 403 para role `user`
- Rate limits: login 10 req/min, registro 5 req/min (slowapi)
- Senhas: bcrypt, mínimo 8 caracteres
- Domínios permitidos para registro: `@voetur.com.br`, `@vtclog.com.br`
- Primeiro usuário registrado vira admin automaticamente

---

## Kong Gateway

Arquivo: `volumes/api/kong.yml` (config declarativa — restart do Kong aplica mudanças).

Ordem de roteamento (específico antes do genérico):
```
/api/monitoring   → monitoring-service:8002
/api/freshservice → freshservice-service:8003
/api/moneypenny   → moneypenny-service:8004
/api/agents       → agents-service:8005
/api/expenses     → expenses-service:8006
/api/             → core-service:8001
```

CORS gerenciado pelos microsserviços (plugin Kong desabilitado para rotas de app).

---

## Schema do Banco

Arquivos SQL na raiz:
- `schema.sql` — tabelas core
- `schema_freshservice.sql` — tabelas do módulo Freshservice

Aplicar em banco novo:
```bash
docker exec -i jarvis-db-1 bash -c "PGPASSWORD='...' psql -U postgres -d postgres" < schema.sql
docker exec -i jarvis-db-1 bash -c "PGPASSWORD='...' psql -U postgres -d postgres" < schema_freshservice.sql
```

### Tabelas

| Tabela | Serviço | Descrição |
|---|---|---|
| `profiles` | core | Usuários — bcrypt, role admin/user, `anthropic_api_key` |
| `connected_accounts` | moneypenny | OAuth Microsoft 365 — access/refresh token |
| `notification_prefs` | moneypenny | Preferências — channels_config JSONB, horário UTC |
| `app_logs` | todos | Audit trail — login, erros, alertas |
| `monitored_systems` | monitoring | Sistemas — tipo, URL, consecutive_down_count |
| `system_checks` | monitoring | Histórico de checks — status, latência, métricas |
| `agents` | agents | Jobs agendados — schedule_type/config JSONB, agent_type |
| `agent_runs` | agents | Histórico de execuções — status, output, error |
| `agent_events` | agents | Bus de eventos entre agentes |
| `agent_messages` | agents | Mensagens inter-agentes e para humano |
| `improvement_proposals` | agents | Proposals de melhoria com tracking de implementação |
| `change_requests` | agents | Change requests ITIL |
| `deployment_windows` | agents | Janelas de deploy ativas |
| `db_health_snapshots` | agents | Snapshots de saúde do banco (DBA agent) |
| `agent_slas` | agents | SLAs de execução por agente (≥3 por agente) |
| `agent_sla_history` | agents | Histórico de valores de SLAs |
| `llm_health_metrics` | agents | Saúde e latência por LLM provider |
| `llm_routing_preferences` | agents | Preferências aprendidas de routing LLM por agente |
| `quality_metrics` | agents | Métricas de qualidade por serviço |
| `governance_reports` | agents | Relatórios diários/semanais de governança |
| `freshservice_tickets` | freshservice | Tickets sincronizados |
| `freshservice_agents` | freshservice | Agentes do helpdesk |
| `freshservice_groups` | freshservice | Grupos do helpdesk |
| `freshservice_companies` | freshservice | Empresas do helpdesk |
| `freshservice_sync_log` | freshservice | Log de sincronizações + checkpoint para backfill |

---

## Variáveis de Ambiente

Ver `.env.example` na raiz para a lista completa. Variáveis críticas:

| Variável | Descrição |
|---|---|
| `POSTGRES_PASSWORD` | Senha PostgreSQL |
| `SUPABASE_JWT_SECRET` | JWT do Supabase (GoTrue + PostgREST + Kong) |
| `ANON_KEY` / `SERVICE_ROLE_KEY` | JWTs gerados do `SUPABASE_JWT_SECRET` |
| `JWT_SECRET` | JWT da aplicação (compartilhado entre microsserviços) |
| `FRESHSERVICE_API_KEY` | API key do Freshservice |
| `MICROSOFT_CLIENT_ID/TENANT_ID/SECRET` | Azure AD — app Moneypenny |
| `WHATSAPP_API_KEY` / `WHATSAPP_INSTANCE` | Evolution API |
| `MONITOR_AGENT_TOKENS` | Token de autenticação do monitor-agent |
| `VITE_API_URL` | URL da API para build do frontend |
| `SQL_SERVER_HOST/PORT/DB` | ERP Benner — `10.141.0.111:1444 / BennerSistemaCorporativo` |
| `SQL_SERVER_USER/PASSWORD` | Credenciais leitura ERP (`usr_jarvis_read`) |
| `OLLAMA_BASE_URL` / `OLLAMA_MODEL` | LLM local — `http://ollama:11434` / `llama3.2:1b` |
| `GROQ_API_KEY` | Groq free tier — Llama 3.3 70B (opcional, recomendado) |
| `TOGETHER_API_KEY` | Together AI free tier — fallback LLM (opcional) |
| `HUGGINGFACE_API_KEY` | HuggingFace inference API — fallback LLM (opcional) |
| `POSTGRES_DIRECT_URL` | PostgreSQL direto para DBA agent (pg_stat_*, psycopg2) |
| `GITHUB_TOKEN` | Token de acesso ao GitHub (agentes de docs/code) |
| `GITHUB_REPO` | Repositório no formato `owner/repo` (ex: `Victorramalho61/projetct_jarvis`) |

Geração dos JWTs do Supabase:
```python
import jwt
secret = "SEU_SUPABASE_JWT_SECRET"
jwt.encode({"iss":"supabase-local","role":"anon","exp":2051222400}, secret, algorithm="HS256")
jwt.encode({"iss":"supabase-local","role":"service_role","exp":2051222400}, secret, algorithm="HS256")
```

---

## Módulo Gastos de TI (expenses-service)

Dashboard financeiro executivo que lê dados do ERP Benner (SQL Server) via `pyodbc` e os expõe como API REST.

### Fonte de Dados

- **ERP**: Benner Sistema Corporativo — SQL Server em `10.141.0.111:1444`
- **Banco**: `BennerSistemaCorporativo` — acesso leitura (`usr_jarvis_read`)
- **Filtro base**: `PAR.EMPRESA = 1` + `DOC.GRUPOASSINATURAS` do gestor K_GESTOR=23 (TI)
- **Tabelas principais**: `FN_PARCELAS`, `FN_DOCUMENTOS`, `FN_LANCAMENTOS`, `FN_CONTAS`, `GN_PESSOAS`, `FILIAIS`

### Endpoints

| Método | Rota | Descrição |
|---|---|---|
| GET | `/api/expenses/dashboard` | KPIs + agregações por mês/origem/fornecedor/filial + sparkline + YoY |
| GET | `/api/expenses/forecast` | Previsão estatística até dez/2026 + projeção por fornecedor |
| GET | `/api/expenses/empresas` | Lista empresas disponíveis no ERP |
| GET | `/api/expenses/health` | Liveness check |

**Parâmetros do dashboard**: `year` (2025/2026), `filial` (filtro por filial), `tipo` (`todos`/`contrato`/`eventual`)

### Arquivos Principais

```
expenses-service/
├── services/
│   ├── expenses.py   # Query principal + agregações (fetch_dashboard)
│   └── forecast.py   # Regressão linear + média móvel 3m (fetch_forecast)
└── routes/
    └── expenses.py   # Endpoints FastAPI
```

### Frontend — Componentes

```
frontend/src/
├── pages/admin/ExpensesPage.tsx           # Página principal (L0 + sub-abas Gastos/Previsão)
├── types/expenses.ts                      # Interfaces TypeScript
└── components/expenses/
    ├── KPICard.tsx                        # Card executivo com skeleton shimmer
    ├── ForecastChart.tsx                  # ComposedChart real+projetado com banda de confiança
    ├── DonutOrigem.tsx                    # PieChart donut com legenda lateral
    ├── FornecedoresRadial.tsx             # BarChart horizontal top 5 fornecedores
    ├── YearSelector.tsx                   # Toggle de ano (2025/2026)
    ├── Sparkline.tsx                      # Mini LineChart 12 meses nos KPIs
    └── TrafficLight.tsx                   # Badge semáforo verde/amarelo/vermelho

```

### Metodologia de Forecast

- **Janela de treino**: Jul/2025 em diante (dados consistentes pós-implementação)
- **Modelo**: Regressão Linear (60%) + Média Móvel 3 meses (40%) — pure Python, sem dependências externas
- **Intervalo de confiança**: ±15% do valor projetado
- **Por fornecedor**: média mensal executada × meses restantes do ano + badge de tendência (▲→▼)

### Categorias de Gasto

| Campo ORIGEM | Categoria Frontend |
|---|---|
| `Contrato` | Contrato |
| `Ordem de Compra` | Eventual |
| `Financeiro` | Eventual |

Recorrência (`Recorrente` = ≥3 meses histórico; `Eventual` = <3 meses) calculada via `_RECURRENCE_QUERY` nos últimos 16 meses.

---

## Observabilidade

### Logging

Todos os containers usam `json-file` com rotação automática (configurado em `docker-compose.yml`):

```yaml
logging:
  driver: "json-file"
  options:
    max-size: "10m"
    max-file: "3"
```

Consultar logs:
```bash
docker compose logs -f agents-service --tail=100
docker compose logs --since=1h freshservice-service
```

### Healthchecks

| Serviço | Comando | Intervalo |
|---|---|---|
| db | `pg_isready` | 5s |
| rest | — (imagem distroless sem shell) | — |
| realtime | `curl -s localhost:4000` | 30s |
| meta | `node -e "require('http').get(...)"` | 30s |
| kong | `kong health` | 30s |
| studio | `wget --spider localhost:3000` | 30s |
| core/monitoring/freshservice/moneypenny/agents | `urllib.request.urlopen(/health)` | 30s |

```bash
# Ver status dos healthchecks
docker compose ps
```

### Resource Limits (serviços Supabase + Evolution)

| Serviço | mem_limit | cpus |
|---|---|---|
| db | 1500m | 2 |
| auth | 256m | 0.5 |
| rest | 256m | 0.5 |
| realtime | 512m | 1 |
| storage | 256m | 0.5 |
| imgproxy | 256m | 0.5 |
| meta | 256m | 0.5 |
| kong | 1000m | 2 |
| studio | 512m | 1 |
| evolution-api | 512m | 1 |

---

## Backup

Ver `docs/BACKUP.md` para instruções completas.

```bash
# Executar backup manual
bash scripts/backup.sh

# Agendar backup diário às 3h
echo "0 3 * * * cd /opt/jarvis && bash scripts/backup.sh >> /var/log/jarvis-backup.log 2>&1" | crontab -
```

O script salva em `BACKUP_DIR` (padrão `/opt/jarvis/backups`) com rotação automática por `RETENTION_DAYS` dias.

---

## CI/CD

### GitHub Actions (`.github/workflows/deploy.yml`)

1. **security-scan** — Gitleaks (detecção de secrets no código)
2. **test-frontend** — typecheck + npm audit
3. **deploy** — self-hosted runner → `deploy.sh`

### Self-Hosted Runner

Runner em `C:\actions-runner` no servidor Windows.
- Conecta ao GitHub por saída (não abre portas)
- Iniciar após reboot: `Start-Process C:\actions-runner\run.cmd -WindowStyle Hidden`
- Como serviço permanente: `cd C:\actions-runner && .\config.cmd --runasservice`

### deploy.sh

```bash
cd $APP_DIR
git fetch origin main && git checkout origin/main
docker compose up -d --build
```

---

## Microsoft 365 / Azure AD

App: **Moneypenny**
Tenant: `fb902eca-dc08-4dec-9e2c-7ce70ee14cf5`
Scopes: `Calendars.Read Mail.Read Mail.Send User.Read`

Redirect URI (registrado no Azure AD):
```
https://jarvis.voetur.com.br/api/moneypenny/auth/microsoft/callback
```

---

## WhatsApp (Evolution API)

- Servidor: OCI São Paulo (bind 127.0.0.1 no host)
- Instância e credenciais: ver `.env`
- Envio em background — `ReadTimeout` tratado como entregue (OCI free tier lento)

---

## nginx Standalone (nginx/ — preparado, não ativo)

O diretório `nginx/` contém config de proxy reverso alternativa (upstream `frontend:80` + `kong:8000`). Não está ativo no `docker-compose.yml` — o frontend já embute nginx. Use se quiser separar as responsabilidades futuramente.

---

## Comandos Úteis

```bash
# Status de todos os containers + healthchecks
docker compose ps

# Logs de um serviço (últimas 100 linhas)
docker compose logs -f core-service --tail=100
docker compose logs -f freshservice-service

# Rebuild de serviço específico
docker compose up -d --build agents-service
docker compose up -d --build agents-service frontend

# Restart sem rebuild (ex: após mudança no docker-compose.yml)
docker compose up -d kong studio

# Acessar banco
docker exec -it jarvis-db-1 bash -c "PGPASSWORD='...' psql -U postgres -d postgres"

# Aplicar migração SQL
docker exec -i jarvis-db-1 bash -c "PGPASSWORD='...' psql -U postgres -d postgres" < schema.sql

# Métricas do servidor
curl http://localhost:9100/metrics

# Healthcheck da aplicação
curl https://jarvis.voetur.com.br/api/health
curl https://jarvis.voetur.com.br/api/ready

# Backup manual
bash scripts/backup.sh

# Ver uso de disco dos volumes Docker
docker system df -v | grep jarvis
```
