# ❌ SERVIÇO DESABILITADO

**Status:** Desabilitado manualmente em 2026-05-25  
**Motivo:** Consumo excessivo de CPU causando lentidão geral no sistema  
**Responsável:** Victor Ramalho

## ⚠️ NÃO RELIGAR SEM AUTORIZAÇÃO HUMANA EXPLÍCITA

Este serviço foi desligado intencionalmente. Antes de reativar, verifique:

1. O servidor tem CPU disponível (monitor com `docker stats`)
2. O consumo esperado está dentro do aceitável para a carga atual
3. Victor Ramalho ou responsável técnico autorizou expressamente

## Configurações de proteção aplicadas

- `docker-compose.yml`: `restart: "no"` (não sobe automaticamente)
- O container não será reiniciado em caso de falha ou reboot do host

## Para reativar (somente com autorização)

```bash
# 1. Alterar no docker-compose.yml:
#    restart: "no"  →  restart: unless-stopped
# 2. Remover este arquivo ou mover para DISABLED.md.bak
# 3. Subir o serviço:
docker compose up -d hermes-service
```
