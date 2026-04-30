# Briefing: Deploy — Fluxo de Reset de Senha

## O que foi implementado
Feature de reset de senha seguro no JARVIS. Todas as mudanças de código já estão no disco. A migração do banco já foi aplicada.

## O que falta fazer
1. Reconstruir e subir `core-service` e `frontend` no Docker Compose
2. Verificar se os containers subiram sem erro

## Projeto
- Diretório: `E:\claudecode\claudecode\` (Linux path: `/e/claudecode/claudecode/`)
- Orquestração: Docker Compose (`docker-compose.yml` na raiz do projeto)

## Comandos a executar (em ordem)

```bash
# 1. Rebuild dos dois serviços afetados
docker compose build core-service frontend

# 2. Subir sem derrubar outros serviços
docker compose up -d --no-deps core-service frontend

# 3. Confirmar que estão rodando
docker compose ps core-service frontend

# 4. Checar logs do backend por erros de import ou startup
docker compose logs --tail=50 core-service
```

## Verificação de sucesso
- `docker compose ps` deve mostrar `core-service` e `frontend` com status `Up`
- Logs do `core-service` não devem ter `ImportError`, `ModuleNotFoundError` ou `Exception`
- Acessar `https://jarvis.voetur.com.br/login` e confirmar que o link "Esqueci a senha" está clicável

## Pendência para o admin
O arquivo `.env` precisa ter `SMTP_PASSWORD` preenchido com a senha da conta `noreply@voetur.com.br` para o envio de e-mail funcionar. O fluxo WhatsApp já funciona sem configuração adicional.
