# Jarvis — Claude Code Instructions

## Arquitetura

7 microsserviços FastAPI (Python 3.11) + React frontend + Supabase self-hosted, orquestrados via Docker Compose. Kong roteia `/api/*` para cada serviço.

```
nginx:443 → Kong:8000 → core-service:8001        (/api/auth, /api/users, /api/admin, /api/health)
                      → monitoring-service:8002   (/api/monitoring/*)
                      → freshservice-service:8003 (/api/freshservice/*)
                      → moneypenny-service:8004   (/api/moneypenny/*)
                      → agents-service:8005       (/api/agents/*)
                      → expenses-service:8006     (/api/expenses/*, /api/expenses/governance/*)
                      → support-service:8007      (/api/support/*)
```

Inter-serviço: `agents-service` chama `freshservice-service` e `expenses-service` via HTTP interno com JWT (com `exp` de 5 min) gerado em `agent_runner.py`. Header `X-Trace-ID` é propagado em todas as chamadas.

## Regras importantes

- **Código compartilhado** (`db.py`, `auth.py`, `limiter.py`, `app_logger.py`) existe em cópia em cada serviço — mudanças devem ser replicadas nos 7.
- **app_logger.py** aceita `trace_id` opcional — sempre passar quando disponível via `current_trace_id.get()` do `main.py`.
- **Autenticação**: rotas admin usam `Depends(require_role("admin"))`, nunca `get_current_user` diretamente em rotas protegidas.
- **Deploy**: `deploy.sh` na raiz → `docker compose up -d --build`. CI/CD via GitHub Actions (self-hosted runner no servidor).
- **Kong config**: `volumes/api/kong.yml` — declarativo, restart do Kong aplica mudanças.
- **Portas expostas ao host**: apenas 80/443 (nginx) e 127.0.0.1 para Supabase/Evolution/monitor-agent. Microsserviços 8001–8007 são internos.
- **Health checks e polling**: intervalos reduzidos para 5 minutos (health check) e 60 segundos (polling interno); SSE ajustado de 2s para 5s para maior estabilidade.
- **Resiliência e priorização**: implementada priorização de proposals com base em `priority`, `effort` e `risk`; limitação de até 3 proposals por execução no `docker_intel` agent.
- **Rate-limiting**: removido rate-limiting global do Kong, que estava causando erros 429 no tráfego interno entre microsserviços.

## Resiliência (expenses-service + Benner)

- `expenses-service/services/resilience.py` — `CircuitBreaker("benner")` + `@sql_retry` (3 tentativas, 2s→10s backoff)
- `get_sql_connection()` em `db.py` usa o circuit breaker automaticamente
- `TTLCache(ttl=300)` nos serviços `governance.py` e `payfly.py` para queries Benner pesadas
- Cache Supabase (`expenses_cache`) cobre dashboard/forecast via `POST /api/expenses/sync`

## Observabilidade

- `app_logs.trace_id` — coluna adicionada ao schema; permite correlacionar logs entre serviços pelo mesmo `X-Trace-ID`
- `run_error_growth_check()` em `monitoring-service/services/log_monitor.py` — roda a cada 6h, detecta módulos com crescimento ≥ 80% de erros e envia alerta interno + abre GitHub issue
- **Alerta WhatsApp automático desabilitado temporariamente** — estava gerando ruído excessivo; substituído por alertas internos até reavaliação
- `/ready` padronizado em todos os 7 serviços: `{status, service, uptime_seconds, components: {...}}`
- **Performance**: otimizações em todo o sistema para reduzir uso de recursos e corrigir bugs de bloqueio assíncrono.
- **Indexação**: adicionado índice em `agent_messages(to_agent, status, created_at)` para melhorar performance de consultas.

## VoeIA — Central de Demandas WhatsApp (support-service:8007)

Bot de suporte via WhatsApp que gerencia onboarding de usuários e abertura/acompanhamento de chamados no Freshservice.

- **FSM**: 13 estados em `services/conversation.py`; estado + contexto persistidos em `support_conversations.state` + `.context` (JSONB)
- **Onboarding**: busca e-mail em `/requesters` e fallback `/agents` (com resolução de `location_id`/`department_ids`); coleta `empresa` obrigatória antes do catálogo
- **Catálogo**: 5 departamentos (TI→ws2, Financeiro→ws5, RH→ws6, Operações→ws13, Suprimentos→ws18) com subcategorias
- **Tickets**: cria via `POST /api/v2/tickets`; usa `requester_id` para agents (email é ignorado silenciosamente pela API); `custom_fields.empresa` obrigatório neste Freshservice; sem `category`/`sub_category` (valores do catálogo não batem com os do Freshservice)
- **Notificações**: `POST /api/support/webhooks/freshservice?secret=…` → `notification_worker.py` (idempotente via UNIQUE `(freshservice_ticket_id, event_type)`)
- **Schema**: `schema_support.sql` na raiz — rodar no Supabase antes do primeiro deploy; `support_users` tem coluna `empresa`
- **Instância WhatsApp**: `SUPPORT_WHATSAPP_INSTANCE` (default `voetur-support`); JID completo (`@lid`/`@s.whatsapp.net`) passado no sendText; `linkPreview: false` em todos os envios
- **Rotas admin**: `GET /api/support/conversations|tickets|users` — requer role `admin` ou `support`
- **URL de suporte**: `https://suporte.voetur.com.br/` — aparece nas mensagens de erro de ticket

## Módulo Gastos TI (expenses-service:8006)

Lê ERP Benner via `pyodbc` (SQL Server `10.141.0.111:1444`, `BennerSistemaCorporativo`).
- **Filtro base**: `PAR.EMPRESA = 1` + `K_GESTOR = 23` (gestor de TI)
- **Endpoints**: `GET /api/expenses/dashboard?year=&filial=&tipo=` · `GET /api/expenses/forecast` · `GET /api/expenses/empresas` · `GET /api/expenses/comparativo?ano1=2025&ano2=2026`
- **Forecast**: regressão linear + média móvel 3m, pure Python, janela Jul/2025 — gráfico corrigido para exibir corretamente tendência
- **Detalhamento**: nova aba com análise de despesas eventuais e comparações
- **PayFly**: 
  - Filtrado apenas pagamentos **liquidados** (`DATALIQUIDACAO IS NOT NULL`)
  - Separação entre despesas **contratuais** e **eventuais**
  - Incluído suporte a **parcelas pendentes** em contratos