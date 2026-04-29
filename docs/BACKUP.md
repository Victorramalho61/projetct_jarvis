# Jarvis — Backup e Restauração

## O que é salvo

| Item | Método | Arquivo gerado |
|---|---|---|
| PostgreSQL | `pg_dump` (SQL completo) | `postgres_TIMESTAMP.sql.gz` |
| Evolution API | `tar.gz` do volume Docker | `evolution_TIMESTAMP.tar.gz` |
| Storage (opcional) | `tar.gz` do volume Docker | `storage_TIMESTAMP.tar.gz` |

---

## Configuração

```bash
cp .env.backup.example .env.backup
# edite .env.backup conforme necessário
```

Variáveis disponíveis:

| Variável | Padrão | Descrição |
|---|---|---|
| `BACKUP_DIR` | `/opt/jarvis/backups` | Diretório de destino |
| `RETENTION_DAYS` | `7` | Dias de retenção (rotação automática) |
| `BACKUP_STORAGE` | `false` | Incluir volume de storage |

---

## Executar backup

```bash
bash scripts/backup.sh
```

Saída esperada:
```
[2026-04-29 03:00:00] Iniciando backup Jarvis → /opt/jarvis/backups/20260429_030000
[2026-04-29 03:00:02] PostgreSQL: iniciando pg_dump...
[2026-04-29 03:00:15] PostgreSQL: 48M — ok
[2026-04-29 03:00:15] Evolution API: copiando volume jarvis_evolution_data...
[2026-04-29 03:00:18] Evolution: 2.1M — ok
[2026-04-29 03:00:18] Rotação: removendo backups com mais de 7 dias...
[2026-04-29 03:00:18] Backup concluído — total: 50M
```

---

## Agendar via cron

```bash
crontab -e
# Backup diário às 3h da manhã:
0 3 * * * cd /opt/jarvis && bash scripts/backup.sh >> /var/log/jarvis-backup.log 2>&1
```

---

## Restauração

### PostgreSQL

```bash
# 1. Descompactar
gunzip backups/20260429_030000/postgres_20260429_030000.sql.gz

# 2. Restaurar (banco deve existir e estar vazio ou aceitar sobreposição)
docker exec -i jarvis-db-1 bash -c \
  "PGPASSWORD='SUA_SENHA' psql -U postgres -d postgres" \
  < backups/20260429_030000/postgres_20260429_030000.sql
```

### Evolution API

```bash
# Parar Evolution antes de restaurar
docker compose stop evolution-api

# Restaurar o volume
docker run --rm \
  -v jarvis_evolution_data:/data \
  -v $(pwd)/backups/20260429_030000:/backup:ro \
  alpine sh -c "cd /data && tar xzf /backup/evolution_20260429_030000.tar.gz"

docker compose start evolution-api
```

### Storage (se aplicável)

```bash
docker compose stop storage

docker run --rm \
  -v jarvis_storage_data:/data \
  -v $(pwd)/backups/20260429_030000:/backup:ro \
  alpine sh -c "cd /data && tar xzf /backup/storage_20260429_030000.tar.gz"

docker compose start storage
```

---

## Monitoramento

Verificar último backup:
```bash
ls -lht /opt/jarvis/backups/ | head -5
```

Verificar integridade do dump PostgreSQL:
```bash
gunzip -c backups/TIMESTAMP/postgres_TIMESTAMP.sql.gz | tail -5
# Deve terminar com: "PostgreSQL database dump complete"
```

---

## Troubleshooting

**`docker exec` falha com "No such container"**
```bash
docker ps --filter name=jarvis-db
# ajuste o nome do container se necessário
```

**Sem espaço em disco**
```bash
df -h /opt/jarvis/backups
# reduza RETENTION_DAYS ou desabilite BACKUP_STORAGE
```

**Backup corrompido**
O script usa `set -euo pipefail` — qualquer falha aborta e não deixa arquivo parcial na pasta de destino.
