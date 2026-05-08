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
                      → contracts-service:8007    (/api/contracts/*)
```

Inter-serviço: `agents-service` chama `freshservice-service` via HTTP interno com JWT gerado em `agents-service/services/agent_runner.py`.

## Regras importantes

- **Código compartilhado** (`db.py`, `auth.py`, `limiter.py`, `app_logger.py`) existe em cópia em cada serviço — mudanças devem ser replicadas em todos os 5.
- **Autenticação**: rotas admin usam `Depends(require_role("admin"))`, nunca `get_current_user` diretamente em rotas protegidas.
- **Deploy**: `deploy.sh` na raiz → `docker compose up -d --build`. CI/CD via GitHub Actions (self-hosted runner no servidor).
- **Kong config**: `volumes/api/kong.yml` — declarativo, restart do Kong aplica mudanças.
- **Portas expostas ao host**: apenas 80/443 (nginx) e 127.0.0.1 para Supabase/Evolution/monitor-agent. Microsserviços 8001-8007 são internos.
- **Health checks e polling**: intervalos reduzidos para 5 minutos (health check) e 60 segundos (polling interno); SSE ajustado de 2s para 5s para maior estabilidade.
- **Resiliência e priorização**: implementada priorização de proposals com base em `priority`, `effort` e `risk`; limitação de até 3 proposals por execução no `docker_intel` agent.

## Módulo Gastos TI (expenses-service:8006)

Lê ERP Benner via `pyodbc` (SQL Server `10.141.0.111:1444`, `BennerSistemaCorporativo`).
- **Filtro base**: `PAR.EMPRESA = 1` + `K_GESTOR = 23` (gestor de TI)
- **Endpoints**: `GET /api/expenses/dashboard?year=&filial=&tipo=` · `GET /api/expenses/forecast` · `GET /api/expenses/empresas` · `GET /api/expenses/comparativo?ano1=2025&ano2=2026`
- **Forecast**: regressão linear + média móvel 3m, pure Python, janela Jul/2025 — gráfico corrigido para exibir corretamente tendência
- **Detalhamento**: nova aba com análise de despesas eventuais e comparações KPIs ano corrente
- **Cache**: integração com Supabase para cache de consultas pesadas, reduzindo carga no ERP
- **Frontend**: `ExpensesPage.tsx` + `components/expenses/` (KPICard, ForecastChart, DonutOrigem, FornecedoresRadial, ComparativoAnual)
- **Env vars novas**: `SQL_SERVER_HOST`, `SQL_SERVER_PORT`, `SQL_SERVER_DB`, `SQL_SERVER_USER`, `SQL_SERVER_PASSWORD`

## Módulo Governança de Contratos TI (contracts-service:8007)

Novo microsserviço para gestão de contratos de TI.
- **Fonte de dados**: ERP Benner (mesma conexão do `expenses-service`)
- **Endpoints**: `GET /api/contracts/dashboard` · `GET /api/contracts/oportunidades` (oportunidades de renegociação)
- **Dashboard**: exibe contratos ativos, próximos vencimentos, alertas de revisão e indicadores de gasto
- **Oportunidades**: análise automatizada de contratos com potencial de economia (backlog de propostas)
- **Cruzamento Jarvis×Benner**: validação de aderência, totais financeiros sincronizados entre sistemas e verificação de consistência de dados
- **Frontend**: `ContractsPage.tsx` + `components/contracts/` (ContractCard, RenewalTimeline, SavingsOpportunities)
- **Env vars**: herda credenciais do `expenses-service` via variáveis compartilhadas em `docker-compose.yml`

## Schemas do banco

- `schema.sql` — tabelas core
- `schema_freshservice.sql` — tabelas Freshservice
- `schema_contracts.sql` — nova tabela `contracts` com campos: `id`, `nome`, `fornecedor`, `valor`, `inicio`, `fim`, `revisao`, `gestor`, `status`

## Integrações com ERP Benner

Ambos os módulos `expenses-service` e `contracts-service` utilizam a mesma conexão com o ERP Benner (`10.141.0.111:1444`, `BennerSistemaCorporativo`) via `pyodbc`. A autenticação é feita com credenciais centralizadas em variáveis de ambiente no `docker-compose.yml`, garantindo consistência e segurança no acesso aos dados financeiros e contratuais.