#!/usr/bin/env bash
# Backup dos volumes críticos do Jarvis: PostgreSQL + Evolution API + Storage (opcional)
# Uso: bash scripts/backup.sh
# Config: copie .env.backup.example para .env.backup e ajuste

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="$SCRIPT_DIR/../.env.backup"
[ -f "$ENV_FILE" ] && source "$ENV_FILE"

BACKUP_DIR="${BACKUP_DIR:-/opt/jarvis/backups}"
RETENTION_DAYS="${RETENTION_DAYS:-7}"
BACKUP_STORAGE="${BACKUP_STORAGE:-false}"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_PATH="$BACKUP_DIR/$TIMESTAMP"

mkdir -p "$BACKUP_PATH"

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*"; }

log "Iniciando backup Jarvis → $BACKUP_PATH"

# ── PostgreSQL ──────────────────────────────────────────────────────────────
log "PostgreSQL: iniciando pg_dump..."
docker exec jarvis-db-1 bash -c \
  'PGPASSWORD="$POSTGRES_PASSWORD" pg_dump -U postgres -d postgres --no-owner --no-acl' \
  > "$BACKUP_PATH/postgres_${TIMESTAMP}.sql"
gzip "$BACKUP_PATH/postgres_${TIMESTAMP}.sql"
log "PostgreSQL: $(du -sh "$BACKUP_PATH/postgres_${TIMESTAMP}.sql.gz" | cut -f1) — ok"

# ── Evolution API ───────────────────────────────────────────────────────────
log "Evolution API: copiando volume jarvis_evolution_data..."
docker run --rm \
  -v jarvis_evolution_data:/data:ro \
  -v "$BACKUP_PATH:/backup" \
  alpine tar czf "/backup/evolution_${TIMESTAMP}.tar.gz" -C /data .
log "Evolution: $(du -sh "$BACKUP_PATH/evolution_${TIMESTAMP}.tar.gz" | cut -f1) — ok"

# ── Storage (opcional) ──────────────────────────────────────────────────────
if [ "$BACKUP_STORAGE" = "true" ]; then
  log "Storage: copiando volume jarvis_storage_data..."
  docker run --rm \
    -v jarvis_storage_data:/data:ro \
    -v "$BACKUP_PATH:/backup" \
    alpine tar czf "/backup/storage_${TIMESTAMP}.tar.gz" -C /data .
  log "Storage: $(du -sh "$BACKUP_PATH/storage_${TIMESTAMP}.tar.gz" | cut -f1) — ok"
fi

# ── Rotação ─────────────────────────────────────────────────────────────────
log "Rotação: removendo backups com mais de ${RETENTION_DAYS} dias..."
find "$BACKUP_DIR" -maxdepth 1 -mindepth 1 -type d -mtime +"$RETENTION_DAYS" \
  -exec rm -rf {} + 2>/dev/null || true

log "Backup concluído — total: $(du -sh "$BACKUP_PATH" | cut -f1)"
