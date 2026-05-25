# Backup Jarvis - PostgreSQL + Evolution API
# Agendado via Task Scheduler: diario, 01:00

$ErrorActionPreference = "Stop"
$BACKUP_DIR = "E:\claudecode\claudecode\backups"
$RETENTION_DAYS = 14
$TIMESTAMP = Get-Date -Format "yyyyMMdd_HHmmss"
$BACKUP_PATH = "$BACKUP_DIR\$TIMESTAMP"

function log($msg) { Write-Host "[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] $msg" }

New-Item -ItemType Directory -Force -Path $BACKUP_PATH | Out-Null
log "Iniciando backup Jarvis -> $BACKUP_PATH"

# PostgreSQL - formato custom (-Fc) ja comprimido, sem carregar tudo em RAM
log "PostgreSQL: iniciando pg_dump -Fc..."
$dumpFile = "$BACKUP_PATH\postgres_${TIMESTAMP}.dump"
docker exec jarvis-db-1 bash -c 'pg_dump -U postgres -d postgres -Fc --no-owner --no-acl' > $dumpFile
$size = [math]::Round((Get-Item $dumpFile).Length / 1MB, 1)
log "PostgreSQL: ${size}MB - ok"

# Evolution API
log "Evolution API: copiando volume..."
docker run --rm -v jarvis_evolution_data:/data:ro -v "${BACKUP_PATH}:/backup" `
    alpine tar czf "/backup/evolution_${TIMESTAMP}.tar.gz" -C /data . 2>&1 | Out-Null
$evoSize = [math]::Round((Get-Item "$BACKUP_PATH\evolution_${TIMESTAMP}.tar.gz").Length / 1MB, 1)
log "Evolution: ${evoSize}MB - ok"

# Rotacao
log "Rotacao: removendo backups com mais de $RETENTION_DAYS dias..."
Get-ChildItem $BACKUP_DIR -Directory |
    Where-Object { $_.CreationTime -lt (Get-Date).AddDays(-$RETENTION_DAYS) } |
    Remove-Item -Recurse -Force -ErrorAction SilentlyContinue

$totalSize = [math]::Round((Get-ChildItem $BACKUP_PATH -Recurse | Measure-Object Length -Sum).Sum / 1MB, 1)
log "Backup concluido - total: ${totalSize}MB em $BACKUP_PATH"
