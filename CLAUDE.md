# Jarvis — Claude Code Instructions

## Modo padrão de resposta

Antes de executar qualquer pedido, aplique o **token-efficiency** mode:
- Respostas compactas, sem introduções ou frases de conexão desnecessárias
- Uma ideia por frase
- Terminologia abreviada quando possível (fn, impl, cfg, svc)
- Símbolos de estado: OK, FAIL, WARN, SKIP
- Redução de 30–50% de tokens versus output padrão, mantendo >=95% da informação

Documentação completa do projeto em `docs/arquitetura.md`.

## Regras de desenvolvimento

- **Código compartilhado** (`db.py`, `auth.py`, `limiter.py`, `app_logger.py`) existe em cópia em cada serviço — mudanças devem ser replicadas nos 7 serviços.
- **Autenticação**: rotas admin usam `Depends(require_role("admin"))`, nunca `get_current_user` diretamente.
- **Deploy**: `docker compose up -d --build <serviço>`. CI/CD via GitHub Actions (self-hosted runner no servidor).
- **Kong**: `volumes/api/kong.yml` — declarativo, restart do Kong aplica mudanças.
- **Portas**: apenas 80/443/8181 expostas. Microsserviços 8001–8008 são internos à rede Docker.
- **Rate-limiting global no Kong removido** — causava 429 entre microsserviços.

## Roteamento rápido

```
core-service:8001        /api/auth, /api/users, /api/admin
monitoring-service:8002  /api/monitoring/*
freshservice-service:8003  /api/freshservice/*
moneypenny-service:8004  /api/moneypenny/*
agents-service:8005      /api/agents/*
expenses-service:8006    /api/expenses/*
support-service:8007     /api/support/*
performance-service:8008 /api/performance/*
fiscal-service:8009      /api/fiscal/*
```

## fiscal-service — Regras críticas

- **Certificados A1**: nunca em arquivo — Fernet-encrypted no banco. Decriptado via `extract_pem_for_requests()` (context manager, deleta tempfile ao sair).
- **Scheduler**: 02:00 NFe/CTe · 04:00 retry · 05:00 NDD · toda hora cheia Portal NFS-e (filtra `portal_nfse_hora_sync == hora_atual`).
- **cStat 656 (SEFAZ/ADN)**: bloqueio salvo em `sefaz_nfe_bloqueado_ate`; sync pulado automaticamente; botão "Sync agora" desabilitado na UI com alerta de risco de bloqueio do CNPJ.
- **Heartbeat NFe**: `sefaz_nfe_ultima_consulta_hb` atualizado a cada consulta; alerta de erro em log se > 55 dias (perda permanente de documentos após 60 dias de inatividade na SEFAZ).
- **Backoff**: `retry_utils.with_backoff()` para erros de rede transientes (5s→10s→20s). Não aplicar a auth errors ou cStat 656.
- **Export**: sempre requer `company_id`; filtro de data recomendado (sem data, exporta tudo — pode ser lento).
- **Busca por chave**: `POST /api/fiscal/fetch-by-key` — percorre banco → ADN → SEFAZ; valida 44 dígitos e `isdigit()`.
- **Schema da empresa**: novas colunas em migration 004 + 005 (`fonte`, `xml_hash`, `tipo_schema`, `nsu_nacional`, guards SEFAZ, `portal_nfse_hora_sync`).
