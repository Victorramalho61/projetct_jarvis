# ❌ SERVIÇO DESABILITADO

**Status:** Desabilitado manualmente em 2026-05-25  
**Motivo:** Consumo excessivo de RAM (2 GB reservado) em servidor com recursos limitados  
**Responsável:** Victor Ramalho

## ⚠️ NÃO RELIGAR SEM AUTORIZAÇÃO HUMANA EXPLÍCITA

O Ollama (LLM local) está desabilitado intencionalmente.  
Já usa `restart: "no"` + `profiles: ["agents"]` — não sobe automaticamente.

## Para reativar (somente com autorização)

```bash
# Sobe junto com o agents-service via profile:
docker compose --profile agents up -d
```
