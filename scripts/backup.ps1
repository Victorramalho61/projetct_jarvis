# Backup Jarvis - PostgreSQL (postgres + evolution)
# Agendado via Task Scheduler: diario, 01:00

$ErrorActionPreference = "Stop"
$BACKUP_DIR = "E:\claudecode\claudecode\backups"
$RETENTION_DAYS = 14
$TIMESTAMP = Get-Date -Format "yyyyMMdd_HHmmss"
$BACKUP_PATH = "$BACKUP_DIR\$TIMESTAMP"
$ERRORS = @()

function log($msg) { Write-Host "[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] $msg" }

function assert-size($file, $label, $minMB = 1) {
    $sizeMB = [math]::Round((Get-Item $file).Length / 1MB, 1)
    if ($sizeMB -lt $minMB) {
        $script:ERRORS += "$label gerou arquivo de ${sizeMB}MB (minimo esperado: ${minMB}MB)"
        log "AVISO: $label - ${sizeMB}MB (suspeito)"
    } else {
        log "$label - ${sizeMB}MB - ok"
    }
    return $sizeMB
}

New-Item -ItemType Directory -Force -Path $BACKUP_PATH | Out-Null
log "Iniciando backup Jarvis -> $BACKUP_PATH"

# PostgreSQL banco principal (postgres) - formato custom (-Fc) ja comprimido
log "PostgreSQL [postgres]: iniciando pg_dump -Fc..."
$dumpFile = "$BACKUP_PATH\postgres_${TIMESTAMP}.dump"
docker exec jarvis-db-1 bash -c 'pg_dump -U postgres -d postgres -Fc --no-owner --no-acl' > $dumpFile
assert-size $dumpFile "postgres" 10 | Out-Null

# PostgreSQL banco evolution (sessoes WhatsApp) - container desabilitado mas banco persiste
log "PostgreSQL [evolution]: iniciando pg_dump -Fc..."
$evoDbFile = "$BACKUP_PATH\evolution_db_${TIMESTAMP}.dump"
docker exec jarvis-db-1 bash -c 'pg_dump -U postgres -d evolution -Fc --no-owner --no-acl' > $evoDbFile
assert-size $evoDbFile "evolution_db" 0.05 | Out-Null

# Rotacao
log "Rotacao: removendo backups com mais de $RETENTION_DAYS dias..."
Get-ChildItem $BACKUP_DIR -Directory |
    Where-Object { $_.CreationTime -lt (Get-Date).AddDays(-$RETENTION_DAYS) } |
    Remove-Item -Recurse -Force -ErrorAction SilentlyContinue

$totalSize = [math]::Round((Get-ChildItem $BACKUP_PATH -Recurse | Measure-Object Length -Sum).Sum / 1MB, 1)
log "Backup concluido - total: ${totalSize}MB em $BACKUP_PATH"

if ($ERRORS.Count -gt 0) {
    log "ERROS DETECTADOS:"
    $ERRORS | ForEach-Object { log "  - $_" }
    exit 1
}
