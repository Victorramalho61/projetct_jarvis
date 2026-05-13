# Jarvis — Arquitetura e Documentação

## Visão Geral

Sistema interno da Voetur/VTCLog com autenticação própria e sete módulos:

| Módulo | Serviço | Porta | Descrição |
|---|---|---|---|
| Core | core-service | 8001 | Autenticação, usuários, administração |
| Monitoramento | monitoring-service | 8002 | Health checks agendados, dashboard em tempo real |
| Freshservice | freshservice-service | 8003 | Dashboard e sync de tickets do helpdesk |
| Moneypenny | moneypenny-service | 8004 | Resumo diário de e-mails e agenda via Microsoft 365 |
| Agentes | agents-service | 8005 | Jobs agendados + criação de agentes via Claude AI |
| Gastos TI | expenses-service | 8006 | Dashboard financeiro executivo — despesas de TI via ERP Benner |
| VoeIA | support-service | 8007 | Bot WhatsApp de suporte com abertura de chamados no Freshservice |

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
        │                                     └─ /api/support/*
        │                                           └─► support-service:8007
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
| 8181 | nginx (Evolution API proxy) | 0.0.0.0 | sim |
| 5432 | PostgreSQL | 127.0.0.1 | bloqueado |
| 9100 | Monitor Agent | 127.0.0.1 | bloqueado |
| 8080 | Evolution API | 127.0.0.1 | bloqueado |
| 54321 | Supabase Kong | 127.0.0.1 | bloqueado |
| 54323 | Supabase Studio | 127.0.0.1 | bloqueado |

Microsserviços (8001–8007): sem portas expostas ao host, apenas rede interna Docker.

---

## VoeIA — support-service:8007

Bot de suporte via WhatsApp que gerencia onboarding de usuários e abertura/acompanhamento de chamados no Freshservice.

**Fluxo geral:**
```
WhatsApp user → Evolution API → POST /api/support/webhooks/whatsapp
                                       │
                                       ▼
                              ConversationFSM (13 estados)
                               ├── lookup/salva support_users
                               ├── salva support_conversations
                               └── chama FreshserviceConnector
                                       │ resposta
                                       ▼
                              Evolution API POST /message/sendText/voetur-support

Freshservice evento → POST /api/support/webhooks/freshservice?secret=…
                              │
                              ▼
                      notification_worker (idempotente)
                       └── Evolution API POST /message/sendText/voetur-support
```

**FSM — estados:**
`onboarding_email` → `onboarding_confirm_fs` | `onboarding_name` → `onboarding_company` → `onboarding_location` → `onboarding_final_confirm` → `onboarding_empresa` → `selecting_catalog` → `selecting_subcategory` → `selecting_action` → `collecting_description` → `confirming_ticket` → `idle`

**Catálogo de departamentos:**

| # | Departamento | workspace_id Freshservice |
|---|---|---|
| 1 | TI | 2 |
| 2 | Financeiro | 5 |
| 3 | RH / Pessoal | 6 |
| 4 | Operações | 13 |
| 5 | Suprimentos | 18 |

**Particularidades desta instância Freshservice (voetur1.freshservice.com):**
- Campo `empresa` é custom_field obrigatório em todos os tickets; valores: `VTC OPERADORA LOGÍSTICA (Matriz)`, `VOETUR TURISMO (Matriz)`, `VIP CARGAS BRASÍLIA (Matriz)`, `VIP SERVICE CLUB MARINA (Matriz)`, `VIP CARGAS RIO (MATRIZ)`
- Agents (admins) devem usar `requester_id` na criação de ticket — campo `email` é silenciosamente ignorado pela API
- Busca de usuário: `/requesters` primeiro, fallback `/agents` com resolução de `location_id` e `department_ids`
- `category`/`sub_category` não enviados — valores do catálogo interno não correspondem aos do Freshservice

**Configuração WhatsApp:**
- Instância: `SUPPORT_WHATSAPP_INSTANCE` (default `voetur-support`)
- JID completo (`@lid` ou `@s.whatsapp.net`) passado no `sendText` — não apenas o número
- `linkPreview: false` em todos os envios
- URL de suporte nas mensagens de erro: `https://suporte.voetur.com.br/`

**Schema:** `schema_support.sql` na raiz — aplicar no Supabase antes do primeiro deploy.
Tabelas: `support_users` (+ coluna `empresa`), `support_conversations`, `support_messages`, `support_tickets`, `support_notifications`.

**Rotas admin:** `GET /api/support/conversations|tickets|users` — requer role `admin` ou `support`.

---

## VoeIA — Changelog

### 2026-05-13 — Fix deduplicação webhook + health check Docker

**Problema:** A Evolution API entrega o mesmo evento webhook duas vezes; sem deduplicação o bot processava e respondia em duplicata. O health check do container travava indefinidamente (uvicorn sem timeout→Docker matava com ExitCode -1).

**Arquivos:** `support-service/routes/webhook.py`, `docker-compose.yml`

- `webhook.py`: adicionado `_is_duplicate(msg_id)` — cache `OrderedDict` com TTL de 60s e limite de 1000 entradas; retorna 200 imediatamente para mensagens já vistas
- `docker-compose.yml`: `urlopen` no health check recebe `timeout=4`; `start_period` aumentado de 10s para 30s

---

### 2026-05-13 — Missão 1: Auto-detecção de empresa via Freshservice

**Problema:** Após encontrar o usuário no Freshservice e confirmar os dados, o bot ainda pedia para escolher manualmente entre as 5 empresas — passo redundante.

**Arquivos:** `support-service/services/freshservice_connector.py`, `support-service/services/conversation.py`

- `freshservice_connector.py`: `search_requester_by_email()` agora extrai `company_id` e resolve o nome via `GET /companies/{id}` (novo método `_resolve_company()`); retorna campo `company_name`
- `conversation.py`: adicionado `_FS_COMPANY_TO_EMPRESA_KEY` (mapeamento nome FS → chave 1–5) e `_match_empresa_key()`; quando Freshservice retorna empresa reconhecida, o campo `empresa` é salvo automaticamente e o passo `onboarding_empresa` é pulado

**Fallback:** Se `company_id` for nulo ou o nome não bater com nenhuma chave → fluxo original (usuário escolhe manualmente).

**Mapeamento atual:**

| Nome no Freshservice | Empresa local |
|---|---|
| `voetur turismo` | VOETUR TURISMO (Matriz) |
| `vtc operadora logística` | VTC OPERADORA LOGÍSTICA (Matriz) |
| `vip cargas brasília` | VIP CARGAS BRASÍLIA (Matriz) |
| `vip service club marina` | VIP SERVICE CLUB MARINA (Matriz) |
| `vip cargas rio` | VIP CARGAS RIO (MATRIZ) |

Para adicionar/corrigir: editar `_FS_COMPANY_TO_EMPRESA_KEY` em `conversation.py`.

---

### 2026-05-13 — Missão 2: Navegação "voltar" nas fases de abertura de chamado

**Problema:** Usuário sem poder voltar ao menu de departamentos após avançar nas etapas — precisava recomeçar a conversa.

**Arquivo:** `support-service/services/conversation.py`

Adicionada função `_is_back(text)` que reconhece: `0`, `voltar`, `menu`, `início`, `inicio`.

Nos estados abaixo, digitar qualquer dessas palavras retorna imediatamente ao menu de departamentos (`selecting_catalog`) sem resetar o cadastro do usuário:

| Estado | Trigger de volta |
|---|---|
| `selecting_subcategory` | `0` / `voltar` |
| `selecting_action` | `0` / `voltar` |
| `collecting_description` | `0` / `voltar` |
| `confirming_ticket` | `0` / `voltar` |

Mensagens atualizadas para exibir a opção `0 - ↩️ Voltar` visualmente.

---

### 2026-05-13 — Missão 3: Docker auto-start no boot do Windows Server

**Problema:** Após reinicialização do servidor, os containers não subiam automaticamente — `setup-autostart.ps1` nunca havia sido executado.

**Solução:** Executar como Administrador:
```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
E:\claudecode\claudecode\setup-autostart.ps1
```

Isso registra a task `Jarvis-Docker-Startup` no Task Scheduler do Windows com:
- Trigger: `AtStartup`
- Principal: `NT AUTHORITY\SYSTEM` (Highest)
- Ação: executa `E:\claudecode\claudecode\jarvis-startup.bat`

O script `jarvis-startup.bat`: inicia Docker Desktop → aguarda até 120s → `docker compose up -d` → aplica memory limits.

**Verificação:**
```powershell
Get-ScheduledTask -TaskName "Jarvis-Docker-Startup"
# State: Ready
```

**Log de execução:** `C:\Windows\Temp\jarvis-startup.log`

---

## Módulo Gastos TI — expenses-service:8006

Lê ERP Benner via `pyodbc` (SQL Server `10.141.0.111:1444`, `BennerSistemaCorporativo`).

- **Filtro base**: `PAR.EMPRESA = 1` + `K_GESTOR = 23` (gestor de TI)
- **Endpoints**: `GET /api/expenses/dashboard?year=&filial=&tipo=` · `GET /api/expenses/forecast` · `GET /api/expenses/empresas` · `GET /api/expenses/comparativo?ano1=&ano2=`
- **Forecast**: regressão linear + média móvel 3m, pure Python
- **Resiliência**: `CircuitBreaker("benner")` + `@sql_retry` (3 tentativas, 2s→10s backoff) em `services/resilience.py`; `TTLCache(ttl=300)` nos serviços pesados; cache Supabase via `POST /api/expenses/sync`
- **PayFly**: apenas pagamentos liquidados (`DATALIQUIDACAO IS NOT NULL`); separação entre despesas contratuais e eventuais; suporte a parcelas pendentes

---

## Observabilidade

- `app_logs.trace_id` — correlaciona logs entre serviços pelo mesmo `X-Trace-ID`
- `run_error_growth_check()` em `monitoring-service/services/log_monitor.py` — roda a cada 6h, detecta crescimento ≥ 80% de erros e abre GitHub issue
- `/ready` padronizado: `{status, service, uptime_seconds, components: {...}}`
- Índice em `agent_messages(to_agent, status, created_at)` para performance de consultas

---

## Integrações externas

- **Microsoft 365 / Azure AD**: app Moneypenny, tenant `fb902eca-dc08-4dec-9e2c-7ce70ee14cf5`
- **ERP Benner**: SQL Server `10.141.0.111:1444`, banco `BennerSistemaCorporativo`, user `usr_jarvis_read`
- **Freshservice**: `voetur1.freshservice.com`, autenticação via API key
- **WhatsApp**: Evolution API (instâncias `voetur` e `voetur-support`)
- **SMTP**: `smtp.office365.com`, `noreply@voetur.com.br`
