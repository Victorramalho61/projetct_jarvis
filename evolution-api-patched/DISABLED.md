# ❌ SERVIÇO DESABILITADO

**Status:** Desabilitado manualmente em 2026-05-25  
**Motivo:** Consumo de 52% de CPU causando lentidão geral no sistema  
**Responsável:** Victor Ramalho

## ⚠️ NÃO RELIGAR SEM AUTORIZAÇÃO HUMANA EXPLÍCITA

Este serviço (Evolution API — WhatsApp Gateway) foi desligado intencionalmente.  
Antes de reativar, verifique:

1. O servidor tem CPU disponível (monitor com `docker stats`)
2. O consumo esperado está dentro do aceitável para a carga atual
3. Victor Ramalho ou responsável técnico autorizou expressamente
4. O suporte VoeIA (support-service) tolerará ausência do webhook até a reativação

## Impacto enquanto desabilitado

- Bot WhatsApp VoeIA (`support-service`) ficará sem receber mensagens
- Instâncias do WhatsApp conectadas perderão sessão após ~15 min sem heartbeat
- Reconexão exigirá novo QR Code após reativação

## Configurações de proteção aplicadas

- `docker-compose.yml`: `restart: "no"` (não sobe automaticamente)
- O container não será reiniciado em caso de falha ou reboot do host

## Para reativar (somente com autorização)

```bash
# 1. Alterar no docker-compose.yml:
#    restart: "no"  →  restart: unless-stopped
# 2. Remover este arquivo ou mover para DISABLED.md.bak
# 3. Subir o serviço:
docker compose up -d evolution-api
# 4. Reconectar WhatsApp se necessário (novo QR Code)
```
