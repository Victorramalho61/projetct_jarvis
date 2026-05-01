# Jarvis — Claude Code Instructions

## Arquitetura

5 microsserviços FastAPI (Python 3.11) + React frontend + Supabase self-hosted, orquestrados via Docker Compose. Kong roteia `/api/*` para cada serviço.

```
nginx:443 → Kong:8000 → core-service:8001        (/api/auth, /api/users, /api/admin, /api/health)
                      → monitoring-service:8002   (/api/monitoring/*)
                      → freshservice-service:8003 (/api/freshservice/*)
                      → moneypenny-service:8004   (/api/moneypenny/*)
                      → agents-service:8005       (/api/agents/*)
                      → expenses-service:8006     (/api/expenses/*)
```

Inter-serviço: `agents-service` chama `freshservice-service` via HTTP interno com JWT gerado em `agents-service/services/agent_runner.py`.

## Regras importantes

- **Código compartilhado** (`db.py`, `auth.py`, `limiter.py`, `app_logger.py`) existe em cópia em cada serviço — mudanças devem ser replicadas em todos os 5.
- **Autenticação**: rotas admin usam `Depends(require_role("admin"))`, nunca `get_current_user` diretamente em rotas protegidas.
- **Deploy**: `deploy.sh` na raiz → `docker compose up -d --build`. CI/CD via GitHub Actions (self-hosted runner no servidor).
- **Kong config**: `volumes/api/kong.yml` — declarativo, restart do Kong aplica mudanças.
- **Portas expostas ao host**: apenas 80/443 (nginx) e 127.0.0.1 para Supabase/Evolution/monitor-agent. Microsserviços 8001-8005 são internos.

## Módulo Gastos TI (expenses-service:8006)

Lê ERP Benner via `pyodbc` (SQL Server `10.141.0.111:1444`, `BennerSistemaCorporativo`).
- **Filtro base**: `PAR.EMPRESA = 1` + `K_GESTOR = 23` (gestor de TI)
- **Endpoints**: `GET /api/expenses/dashboard?year=&filial=&tipo=` · `GET /api/expenses/forecast` · `GET /api/expenses/empresas`
- **Forecast**: regressão linear + média móvel 3m, pure Python, janela Jul/2025
- **Frontend**: `ExpensesPage.tsx` + `components/expenses/` (KPICard, ForecastChart, DonutOrigem, FornecedoresRadial)
- **Env vars novas**: `SQL_SERVER_HOST`, `SQL_SERVER_PORT`, `SQL_SERVER_DB`, `SQL_SERVER_USER`, `SQL_SERVER_PASSWORD`

## Schemas do banco

- `schema.sql` — tabelas core
- `schema_freshservice.sql` — tabelas Freshservice
