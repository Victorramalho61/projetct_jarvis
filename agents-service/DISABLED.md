# ❌ SERVIÇO DESABILITADO

**Status:** Desabilitado manualmente em 2026-05-25  
**Motivo:** Consumo de recursos (CPU/RAM) causando lentidão geral no sistema  
**Responsável:** Victor Ramalho

## ⚠️ NÃO RELIGAR SEM AUTORIZAÇÃO HUMANA EXPLÍCITA

O agents-service (orquestrador de agentes LLM) está desabilitado intencionalmente.  
Já usa `restart: "no"` + `profiles: ["agents"]` — não sobe automaticamente.

## Para reativar (somente com autorização)

```bash
# Usar o profile "agents" para subir o conjunto:
docker compose --profile agents up -d
```
