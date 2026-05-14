# Jarvis — Arquitetura e Documentação

## Visão Geral

Sistema interno da Voetur/VTCLog com autenticação própria e oito módulos:

| Módulo | Serviço | Porta | Descrição |
|---|---|---|---|
| Core | core-service | 8001 | Autenticação, usuários, administração |
| Monitoramento | monitoring-service | 8002 | Health checks agendados, dashboard em tempo real |
| Freshservice | freshservice-service | 8003 | Dashboard e sync de tickets do helpdesk |
| Moneypenny | moneypenny-service | 8004 | Resumo diário de e-mails e agenda via Microsoft 365 |
| Agentes | agents-service | 8005 | Jobs agendados + criação de agentes via Claude AI / LangGraph |
| Gastos TI | expenses-service | 8006 | Dashboard financeiro executivo — despesas de TI via ERP Benner |
| VoeIA | support-service | 8007 | Bot WhatsApp de suporte com abertura de chamados no Freshservice |
| Desempenho | performance-service | 8008 | Gestão de ciclos, metas, avaliações e KPIs de desempenho |

---

## Arquitetura

```
Browser
  └─► nginx:443 (HTTPS — frontend container)
        ├─ /api/* ─────────────────────────► Kong:8000 (interno Docker)
        │                                     ├─ /api/performance/*
        │                                     │     └─► performance-service:8008
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
  performance-service → SQL Server externo 10.141.0.111:1444 (BennerRH — leitura para sync)

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

Microsserviços (8001–8008): sem portas expostas ao host, apenas rede interna Docker.

---

## Sistema de Roles

| Role | Módulos | Permissões-chave |
|---|---|---|
| `admin` | todos | gerenciar usuários, acessar todos os dados |
| `user` | core, monitoring, freshservice, moneypenny, agents | acesso padrão |
| `rh` | desempenho | criar metas, assinar avaliações, calibrar, fechar ciclo |
| `gestor` | desempenho | criar metas, avaliar liderados, gerenciar KPIs/PDI |
| `coordenador` | desempenho | criar metas, avaliar liderados, gerenciar PDI |
| `supervisor` | desempenho | criar metas, avaliar liderados, assinar avaliação |
| `colaborador` | desempenho | assinar metas recebidas, autoavaliação, tomar ciência |

---

## Banco de Dados — MER Completo

O banco PostgreSQL (Supabase self-hosted) contém **53 tabelas** distribuídas em 6 arquivos de schema.

### Schema Core (`schema.sql`) — 10 tabelas

```mermaid
erDiagram
    profiles {
        uuid id PK
        text username UK
        text display_name
        text email UK
        text role
        boolean active
        text password_hash
        text whatsapp_phone
        text anthropic_api_key
        timestamptz created_at
        timestamptz updated_at
    }

    connected_accounts {
        uuid id PK
        uuid user_id FK
        text provider
        text email
        text access_token
        text refresh_token
        timestamptz token_expiry
        timestamptz created_at
        timestamptz updated_at
    }

    notification_prefs {
        uuid id PK
        uuid user_id FK
        boolean active
        int send_hour_utc
        jsonb channels_config
        text teams_webhook_url
        text whatsapp_phone
        timestamptz updated_at
    }

    app_logs {
        bigserial id PK
        timestamptz created_at
        text level
        text module
        text message
        text detail
        uuid user_id FK
        text trace_id
    }

    monitored_systems {
        uuid id PK
        text name
        text description
        text url
        text system_type
        jsonb config
        int check_interval_minutes
        boolean enabled
        timestamptz last_alerted_at
        uuid created_by FK
        timestamptz created_at
        timestamptz updated_at
    }

    system_checks {
        bigserial id PK
        uuid system_id FK
        text status
        int latency_ms
        int http_status
        text detail
        jsonb metrics
        text checked_by
        timestamptz checked_at
    }

    agents {
        uuid id PK
        text name
        text description
        text agent_type
        jsonb config
        text schedule_type
        jsonb schedule_config
        boolean enabled
        uuid created_by FK
        timestamptz created_at
        timestamptz updated_at
    }

    agent_runs {
        bigserial id PK
        uuid agent_id FK
        text status
        timestamptz started_at
        timestamptz finished_at
        text output
        text error
    }

    password_reset_tokens {
        uuid id PK
        uuid user_id FK
        text token UK
        timestamptz expires_at
        timestamptz used_at
        timestamptz created_at
    }

    expenses_cache {
        serial id PK
        int year
        text cache_key
        jsonb payload
        timestamptz updated_at
        text status
        text error_msg
    }

    profiles ||--o{ connected_accounts : "user_id"
    profiles ||--o| notification_prefs : "user_id"
    profiles ||--o{ app_logs : "user_id"
    profiles ||--o{ monitored_systems : "created_by"
    profiles ||--o{ agents : "created_by"
    profiles ||--o{ password_reset_tokens : "user_id"
    monitored_systems ||--o{ system_checks : "system_id"
    agents ||--o{ agent_runs : "agent_id"
```

### Schema Freshservice (`schema_freshservice.sql`) — 5 tabelas

```mermaid
erDiagram
    freshservice_tickets {
        int id PK
        text subject
        smallint status
        smallint priority
        text type
        bigint group_id FK
        bigint responder_id FK
        bigint requester_id
        bigint company_id FK
        timestamptz created_at
        timestamptz updated_at
        timestamptz resolved_at
        timestamptz closed_at
        timestamptz due_by
        timestamptz fr_due_by
        timestamptz fr_responded_at
        boolean is_escalated
        smallint csat_rating
        text csat_comment
        int resolution_time_min
        int fr_time_min
        boolean sla_breached
        jsonb raw
        timestamptz ingested_at
    }

    freshservice_agents {
        bigint id PK
        text name
        text email
        timestamptz synced_at
    }

    freshservice_groups {
        bigint id PK
        text name
        timestamptz synced_at
    }

    freshservice_companies {
        bigint id PK
        text name
        timestamptz synced_at
    }

    freshservice_sync_log {
        bigserial id PK
        text sync_type
        timestamptz started_at
        timestamptz completed_at
        jsonb checkpoint
        int tickets_upserted
        text status
        text error
        jsonb summary_json
    }

    freshservice_groups ||--o{ freshservice_tickets : "group_id"
    freshservice_agents ||--o{ freshservice_tickets : "responder_id"
    freshservice_companies ||--o{ freshservice_tickets : "company_id"
```

**Funções SQL (RPC via PostgREST):**

| Função | Parâmetros | Retorno |
|---|---|---|
| `freshservice_summary` | `p_from, p_to: timestamptz` | JSON com totais, CSAT, SLA breach, resolução média |
| `freshservice_sla_by_group` | `p_from, p_to: timestamptz` | JSON com breach % e resolução por grupo |
| `freshservice_agents_monthly` | `p_year, p_month: int` | JSON com fechamentos por agente no mês |
| `freshservice_top_requesters` | `p_from, p_to, p_limit` | JSON com empresas que mais abriram chamados |
| `freshservice_csat_summary` | `p_from, p_to: timestamptz` | JSON com NPS detalhado: happy/neutral/unhappy por grupo |
| `upsert_csat_ratings` | `p_ratings: jsonb` | int (registros atualizados) — batch update de CSAT |

### Schema VoeIA Support (`schema_support.sql`) — 5 tabelas

```mermaid
erDiagram
    support_users {
        bigserial id PK
        text phone UK
        text name
        text email
        text company
        text location
        bigint freshservice_requester_id
        boolean profile_complete
        timestamptz created_at
        timestamptz updated_at
    }

    support_conversations {
        bigserial id PK
        text phone UK
        text state
        jsonb context
        timestamptz updated_at
    }

    support_messages {
        bigserial id PK
        bigint conversation_id FK
        text direction
        text content
        text message_id UK
        timestamptz created_at
    }

    support_tickets {
        bigserial id PK
        bigint freshservice_ticket_id UK
        text phone
        int status
        text subject
        timestamptz created_at
        timestamptz updated_at
    }

    support_notifications {
        bigserial id PK
        bigint freshservice_ticket_id
        text event_type
        text phone
        boolean sent
        jsonb payload
        timestamptz created_at
    }

    support_conversations ||--o{ support_messages : "conversation_id"
```

### Schema Governança de Contratos (`schema_governance.sql`) — 5 tabelas

```mermaid
erDiagram
    contracts {
        uuid id PK
        text benner_documento_match
        text numero
        text titulo
        text fornecedor_nome
        bigint fornecedor_benner_handle
        numeric valor_total
        numeric valor_mensal
        int qtd_parcelas
        date data_inicio
        date data_fim
        text modalidade
        text status
        text objeto
        jsonb sla_config
        text observacoes
        text arquivo_url
        uuid created_by FK
        timestamptz created_at
        timestamptz updated_at
    }

    contract_items {
        uuid id PK
        uuid contract_id FK
        text descricao
        numeric quantidade
        numeric valor_unitario
        numeric valor_total
        text unidade
        text periodicidade
        text conta_contabil
        timestamptz created_at
    }

    contract_occurrences {
        uuid id PK
        uuid contract_id FK
        text tipo
        numeric valor
        text descricao
        date data_ocorrencia
        text competencia
        text status
        boolean email_enviado
        text[] email_destinatarios
        text email_assunto
        text email_corpo
        timestamptz email_enviado_at
        uuid created_by FK
        timestamptz created_at
        timestamptz updated_at
    }

    contract_documents {
        uuid id PK
        uuid contract_id FK
        uuid occurrence_id FK
        text tipo
        text nome_arquivo
        text url
        bigint tamanho_bytes
        uuid uploaded_by FK
        timestamptz created_at
    }

    contract_sla_violations {
        uuid id PK
        uuid contract_id FK
        text sla_metrica
        numeric valor_contratado
        numeric valor_medido
        text periodo
        text impacto
        numeric penalidade_valor
        text status
        uuid created_by FK
        timestamptz created_at
    }

    contracts ||--o{ contract_items : "contract_id"
    contracts ||--o{ contract_occurrences : "contract_id"
    contracts ||--o{ contract_documents : "contract_id"
    contracts ||--o{ contract_sla_violations : "contract_id"
    contract_occurrences ||--o{ contract_documents : "occurrence_id"
```

### Schema Agentes / LangGraph (`schema_langgraph.sql`) — 8 tabelas

```mermaid
erDiagram
    langgraph_threads {
        uuid id PK
        uuid agent_id FK
        text thread_id UK
        text status
        timestamptz created_at
        timestamptz updated_at
    }

    langgraph_checkpoints {
        bigserial id PK
        text thread_id
        text checkpoint_id
        text parent_id
        jsonb state
        jsonb metadata
        timestamptz created_at
    }

    agent_messages {
        bigserial id PK
        text thread_id
        text from_agent
        text to_agent
        jsonb content
        text status
        timestamptz created_at
    }

    security_alerts {
        bigserial id PK
        text severity
        text category
        text description
        text affected_resource
        text status
        timestamptz resolved_at
        timestamptz created_at
    }

    quality_metrics {
        bigserial id PK
        text metric_name
        numeric metric_value
        text unit
        text service
        timestamptz measured_at
        jsonb metadata
    }

    change_requests {
        uuid id PK
        text title
        text description
        text change_type
        text priority
        text status
        text requested_by
        text approved_by
        text rollback_plan
        timestamptz implemented_at
        timestamptz validated_at
        timestamptz created_at
        timestamptz updated_at
    }

    documentation_updates {
        bigserial id PK
        text trigger_event
        text file_path
        text summary
        text diff_content
        text status
        timestamptz created_at
        timestamptz applied_at
    }

    improvement_proposals {
        uuid id PK
        text source_agent
        text proposal_type
        text title
        text description
        text proposed_action
        jsonb affected_files
        text priority
        text estimated_effort
        text risk
        boolean auto_implementable
        jsonb source_findings
        text status
        text cto_reasoning
        timestamptz created_at
        timestamptz decided_at
        timestamptz completed_at
    }

    agents ||--o{ langgraph_threads : "agent_id"
    langgraph_threads ||--o{ langgraph_checkpoints : "thread_id (text)"
```

**Tipos de agente LangGraph (constraint `agents_agent_type_check`):**
`langgraph_cto`, `langgraph_log_scanner`, `langgraph_log_improver`, `langgraph_fix_validator`, `langgraph_security`, `langgraph_code_security`, `langgraph_quality`, `langgraph_quality_validator`, `langgraph_uptime`, `langgraph_docs`, `langgraph_docker`, `langgraph_frontend`, `langgraph_backend`, `langgraph_infrastructure`, `langgraph_api`, `langgraph_automation`, `langgraph_itil_version`, `langgraph_change_mgmt`, `langgraph_change_validator`, `langgraph_integration_validator`, `langgraph_scheduling`

### Schema Desempenho (`schema_performance.sql`) — 20 tabelas

```mermaid
erDiagram
    performance_cycles {
        uuid id PK
        text name
        date period_start
        date period_end
        text status
        text created_by
        timestamptz created_at
    }

    performance_employees {
        uuid id PK
        text benner_id UK
        text name
        text email
        text role
        uuid department_id FK
        uuid manager_id FK
        boolean active
        timestamptz synced_at
    }

    performance_departments {
        uuid id PK
        text name
        uuid parent_id FK
        text director
        text cost_center UK
        text company_id
        timestamptz synced_at
    }

    performance_goals {
        uuid id PK
        text title
        text type
        text description
        text kpi_name
        text formula
        numeric target_value
        numeric current_value
        text unit
        numeric weight
        date period_start
        date period_end
        uuid owner_id FK
        uuid department_id FK
        text status
        uuid parent_goal_id FK
        text created_by
        timestamptz created_at
        timestamptz updated_at
    }

    performance_goal_acknowledgments {
        uuid id PK
        uuid goal_id FK
        uuid employee_id FK
        timestamptz acknowledged_at
        text ip_address
        text signature_text
    }

    performance_goal_templates {
        uuid id PK
        text title
        text type
        text department_type
        text kpi_name
        text formula
        numeric default_target
        text unit
        numeric weight_suggestion
        text description
    }

    performance_competencies {
        uuid id PK
        text name
        text description
        text category
        boolean is_mandatory
        timestamptz created_at
    }

    performance_reviews {
        uuid id PK
        uuid cycle_id FK
        uuid employee_id FK
        uuid reviewer_id FK
        text step
        text status
        numeric goals_score
        numeric competencies_score
        numeric behavior_score
        numeric compliance_score
        numeric raw_score
        numeric normalized_score
        numeric final_score
        text blocked_by
        text comments
        timestamptz manager_signed_at
        text manager_signature
        timestamptz submitted_at
        timestamptz created_at
        timestamptz updated_at
    }

    performance_competency_scores {
        uuid review_id FK
        uuid competency_id FK
        numeric score
        text justification
    }

    performance_review_acknowledgments {
        uuid id PK
        uuid review_id FK
        uuid employee_id FK
        text action
        timestamptz acknowledged_at
        text comments
    }

    performance_calibrations {
        uuid id PK
        uuid cycle_id FK
        uuid review_id FK
        numeric original_score
        numeric calibrated_score
        text justification
        text calibrated_by
        timestamptz calibrated_at
    }

    performance_evidences {
        uuid id PK
        uuid goal_id FK
        uuid employee_id FK
        text type
        text source
        numeric value
        text unit
        text description
        date evidence_date
        text created_by
        timestamptz created_at
    }

    performance_kpis {
        uuid id PK
        text name
        text department_type
        text formula
        text source
        text unit
        timestamptz created_at
    }

    performance_kpi_snapshots {
        uuid id PK
        uuid kpi_id FK
        uuid employee_id FK
        numeric value
        text period
        timestamptz captured_at
    }

    performance_pdis {
        uuid id PK
        uuid review_id FK
        uuid employee_id FK
        text status
        text created_by
        timestamptz created_at
        timestamptz updated_at
    }

    performance_pdi_actions {
        uuid id PK
        uuid pdi_id FK
        text action
        date deadline
        text responsible
        text status
        timestamptz created_at
    }

    performance_permissions {
        text code PK
        text description
    }

    performance_role_permissions {
        text role
        text permission_code FK
    }

    performance_audit_logs {
        uuid id PK
        text entity_type
        uuid entity_id
        text action
        jsonb old_data
        jsonb new_data
        text actor
        text ip_address
        text user_agent
        timestamptz ts
    }

    performance_review_versions {
        uuid id PK
        uuid review_id
        int version
        jsonb snapshot
        text changed_by
        timestamptz changed_at
    }

    performance_departments ||--o{ performance_departments : "parent_id"
    performance_departments ||--o{ performance_employees : "department_id"
    performance_employees ||--o{ performance_employees : "manager_id"
    performance_employees ||--o{ performance_goals : "owner_id"
    performance_departments ||--o{ performance_goals : "department_id"
    performance_goals ||--o{ performance_goals : "parent_goal_id"
    performance_goals ||--o{ performance_goal_acknowledgments : "goal_id"
    performance_employees ||--o{ performance_goal_acknowledgments : "employee_id"
    performance_cycles ||--o{ performance_reviews : "cycle_id"
    performance_employees ||--o{ performance_reviews : "employee_id"
    performance_employees ||--o{ performance_reviews : "reviewer_id"
    performance_reviews ||--o{ performance_competency_scores : "review_id"
    performance_competencies ||--o{ performance_competency_scores : "competency_id"
    performance_reviews ||--o{ performance_review_acknowledgments : "review_id"
    performance_employees ||--o{ performance_review_acknowledgments : "employee_id"
    performance_cycles ||--o{ performance_calibrations : "cycle_id"
    performance_reviews ||--o{ performance_calibrations : "review_id"
    performance_goals ||--o{ performance_evidences : "goal_id"
    performance_employees ||--o{ performance_evidences : "employee_id"
    performance_kpis ||--o{ performance_kpi_snapshots : "kpi_id"
    performance_employees ||--o{ performance_kpi_snapshots : "employee_id"
    performance_reviews ||--o{ performance_pdis : "review_id"
    performance_employees ||--o{ performance_pdis : "employee_id"
    performance_pdis ||--o{ performance_pdi_actions : "pdi_id"
    performance_permissions ||--o{ performance_role_permissions : "permission_code"
```

**Permissões por role:**

| Permission | colaborador | supervisor | coordenador | gestor | rh |
|---|:---:|:---:|:---:|:---:|:---:|
| `acknowledge_goal` | ✓ | | | | |
| `fill_self_review` | ✓ | | | | |
| `acknowledge_review` | ✓ | | | | |
| `create_goal` | | ✓ | ✓ | ✓ | ✓ |
| `fill_manager_review` | | ✓ | ✓ | ✓ | ✓ |
| `sign_review` | | ✓ | ✓ | ✓ | ✓ |
| `manage_pdi` | | | ✓ | ✓ | ✓ |
| `manage_kpis` | | | | ✓ | ✓ |
| `close_cycle` | | | | | ✓ |
| `calibrate` | | | | | ✓ |
| `view_financial_score` | | | | | ✓ |

**Score engine (`services/score_engine.py`):**
- Pesos: `goals=50%`, `competencies=25%`, `behavior=15%`, `compliance=10%`
- Bloqueio compliance: se `compliance_score < 2.0` → `final_score` capped em `2.5`
- Dois momentos de assinatura: Momento 1 (`performance_goal_acknowledgments`) e Momento 2 (`performance_review_acknowledgments`)

---

## Inventário de Rotas por Serviço

### core-service:8001
| Método | Rota | Acesso | Descrição |
|---|---|---|---|
| POST | `/api/auth/login` | público | login + JWT |
| POST | `/api/auth/logout` | autenticado | invalida sessão |
| POST | `/api/auth/refresh` | autenticado | renova JWT |
| POST | `/api/auth/forgot-password` | público | envia e-mail reset |
| POST | `/api/auth/reset-password` | público | conclui reset |
| GET | `/api/users/me` | autenticado | perfil próprio |
| PATCH | `/api/users/me` | autenticado | atualiza perfil |
| GET | `/api/admin/users` | admin | lista usuários |
| POST | `/api/admin/users` | admin | cria usuário |
| PATCH | `/api/admin/users/{id}` | admin | edita usuário |
| DELETE | `/api/admin/users/{id}` | admin | remove usuário |
| GET | `/api/health` | público | healthcheck |

### monitoring-service:8002
| Método | Rota | Acesso | Descrição |
|---|---|---|---|
| GET | `/api/monitoring/systems` | user | lista sistemas |
| POST | `/api/monitoring/systems` | admin | cria sistema |
| GET | `/api/monitoring/systems/{id}/checks` | user | histórico de checks |
| POST | `/api/monitoring/systems/{id}/check` | admin | força check manual |
| GET | `/api/monitoring/dashboard` | user | status em tempo real |

### freshservice-service:8003
| Método | Rota | Acesso | Descrição |
|---|---|---|---|
| GET | `/api/freshservice/summary` | user | resumo por período |
| GET | `/api/freshservice/sla` | user | SLA por grupo |
| GET | `/api/freshservice/agents` | user | produtividade por agente |
| GET | `/api/freshservice/csat` | user | CSAT detalhado |
| POST | `/api/freshservice/sync` | admin | dispara sync manual |

### expenses-service:8006
| Método | Rota | Acesso | Descrição |
|---|---|---|---|
| GET | `/api/expenses/dashboard` | user | despesas por ano/filial/tipo |
| GET | `/api/expenses/forecast` | user | previsão linear + média móvel |
| GET | `/api/expenses/empresas` | user | lista filiais disponíveis |
| GET | `/api/expenses/comparativo` | user | comparação entre dois anos |
| POST | `/api/expenses/sync` | admin | sincroniza cache do Benner |

### support-service:8007
| Método | Rota | Acesso | Descrição |
|---|---|---|---|
| POST | `/api/support/webhooks/whatsapp` | Evolution API | recebe mensagem WhatsApp |
| POST | `/api/support/webhooks/freshservice` | Freshservice | recebe evento de ticket |
| GET | `/api/support/conversations` | admin/support | lista conversas |
| GET | `/api/support/tickets` | admin/support | lista tickets |
| GET | `/api/support/users` | admin/support | lista usuários cadastrados |
| GET | `/api/support/health` | público | healthcheck |
| GET | `/api/support/ready` | público | readiness |

### performance-service:8008
| Método | Rota | Acesso | Descrição |
|---|---|---|---|
| GET | `/api/performance/goals` | todos os roles | lista metas |
| POST | `/api/performance/goals` | gestor/coord/supervisor/rh | cria meta |
| PATCH | `/api/performance/goals/{id}` | criador | atualiza meta |
| POST | `/api/performance/goals/{id}/acknowledge` | colaborador | Momento 1 — assina meta |
| GET | `/api/performance/evaluations/cycles` | todos | lista ciclos |
| POST | `/api/performance/evaluations/cycles` | rh | cria ciclo |
| GET | `/api/performance/evaluations/reviews` | todos | lista avaliações |
| POST | `/api/performance/evaluations/reviews` | rh | cria avaliação |
| PATCH | `/api/performance/evaluations/reviews/{id}` | reviewer/rh | atualiza scores |
| POST | `/api/performance/evaluations/reviews/{id}/sign` | gestor/coord/supervisor/rh | Momento 2 — assina |
| POST | `/api/performance/evaluations/reviews/{id}/acknowledge` | colaborador | Momento 2 — ciência |
| GET | `/api/performance/competencies` | todos | lista competências |
| POST | `/api/performance/competencies/{review_id}/scores` | reviewer | lança scores de competências |
| GET | `/api/performance/evidences` | todos | lista evidências |
| POST | `/api/performance/evidences` | todos | registra evidência |
| GET | `/api/performance/kpis` | gestor/rh | lista KPIs |
| POST | `/api/performance/kpis/{id}/snapshots` | gestor/rh | registra snapshot KPI |
| GET | `/api/performance/admin/employees` | rh/admin | lista colaboradores |
| POST | `/api/performance/admin/sync-benner` | rh/admin | sincroniza RH do Benner |
| GET | `/api/performance/admin/dashboard` | rh/admin | dashboard calibração |
| GET | `/api/performance/admin/audit-log` | rh/admin | trilha de auditoria |
| GET | `/api/performance/health` | público | healthcheck |
| GET | `/api/performance/ready` | público | readiness |

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

**Deduplicação de webhook:** cache `OrderedDict` TTL 60s, limite 1000 entradas — retorna 200 imediatamente para mensagens duplicadas.

**Configuração WhatsApp:**
- Instância: `SUPPORT_WHATSAPP_INSTANCE` (default `voetur-support`)
- JID completo (`@lid` ou `@s.whatsapp.net`) passado no `sendText`
- `linkPreview: false` em todos os envios

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

## Módulo Desempenho — performance-service:8008

Gestão completa de ciclos de avaliação de desempenho. Fase 1 MVP em produção; Fase 2 (PDI funcional, relatórios gerenciais) prevista.

**Sincronização Benner RH:**
- APScheduler cron diário 02:00 em `services/benner_sync.py`
- Lê `BennerRH` via `pyodbc` (variável `SQL_SERVER_BENNER_HR_DB`)
- Popula `performance_departments` e `performance_employees`
- CircuitBreaker + sql_retry idêntico ao expenses-service

**Momentos de assinatura:**
- **Momento 1** — colaborador recebe a meta e assina (`performance_goal_acknowledgments`)
- **Momento 2** — gestor assina o resultado + colaborador toma ciência (`performance_review_acknowledgments`)

**Ciclo de vida da avaliação:**
```
draft → open → evaluation → calibration → closed
```

**Status da meta:**
```
draft → pending_ack → active → in_review → completed | expired | cancelled
```

**Status da revisão:**
```
pending_self → pending_manager → pending_second_manager → pending_hr → pending_ack → completed | disputed | archived
```

---

## Observabilidade

- `app_logs.trace_id` — correlaciona logs entre serviços pelo mesmo `X-Trace-ID`
- `run_error_growth_check()` em `monitoring-service/services/log_monitor.py` — roda a cada 6h, detecta crescimento ≥ 80% de erros e abre GitHub issue
- `/ready` padronizado: `{status, service, uptime_seconds, components: {...}}`
- Índice em `agent_messages(to_agent, status, created_at)` para performance de consultas
- `performance_audit_logs` — trilha de auditoria para todas as operações de escrita no módulo de desempenho

---

## Integrações externas

- **Microsoft 365 / Azure AD**: app Moneypenny, tenant `fb902eca-dc08-4dec-9e2c-7ce70ee14cf5`
- **ERP Benner**: SQL Server `10.141.0.111:1444`, banco `BennerSistemaCorporativo`, user `usr_jarvis_read`
- **Benner RH**: SQL Server `10.141.0.111:1444`, banco configurado via `SQL_SERVER_BENNER_HR_DB`, user `usr_jarvis_read`
- **Freshservice**: `voetur1.freshservice.com`, autenticação via API key
- **WhatsApp**: Evolution API (instâncias `voetur` e `voetur-support`)
- **SMTP**: `smtp.office365.com`, `noreply@voetur.com.br`
