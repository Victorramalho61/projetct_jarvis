# Jarvis — Claude Code Instructions

Documentação completa do projeto em `docs/arquitetura.md`.

## Regras de desenvolvimento

- **Código compartilhado** (`db.py`, `auth.py`, `limiter.py`, `app_logger.py`) existe em cópia em cada serviço — mudanças devem ser replicadas nos 7 serviços.
- **Autenticação**: rotas admin usam `Depends(require_role("admin"))`, nunca `get_current_user` diretamente.
- **Deploy**: `docker compose up -d --build <serviço>`. CI/CD via GitHub Actions (self-hosted runner no servidor).
- **Kong**: `volumes/api/kong.yml` — declarativo, restart do Kong aplica mudanças.
- **Portas**: apenas 80/443/8181 expostas. Microsserviços 8001–8007 são internos à rede Docker.
- **Rate-limiting global no Kong removido** — causava 429 entre microsserviços.

## Roteamento rápido

```
core-service:8001      /api/auth, /api/users, /api/admin
monitoring-service:8002  /api/monitoring/*
freshservice-service:8003  /api/freshservice/*
moneypenny-service:8004  /api/moneypenny/*
agents-service:8005    /api/agents/*
expenses-service:8006  /api/expenses/*
support-service:8007   /api/support/*
```
