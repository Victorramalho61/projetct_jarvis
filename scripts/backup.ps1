# Backup Jarvis - PostgreSQL
# Task Scheduler: diario 01:00
# Retencao: fiscal_documents=7 dias, resto=30 dias
# Notificacao: e-mail ao concluir ou falhar
#
# Credenciais SMTP: definir em scripts\.env.backup (nao commitado)
# Exemplo: scripts\.env.backup.example

$ErrorActionPreference = "Stop"
$SCRIPT_DIR  = Split-Path -Parent $MyInvocation.MyCommand.Path
$BACKUP_DIR  = "E:\claudecode\claudecode\backups"
$RET_FISCAL  = 7
$RET_GERAL   = 30
$TIMESTAMP   = Get-Date -Format "yyyyMMdd_HHmmss"
$BACKUP_PATH = "$BACKUP_DIR\$TIMESTAMP"
$ERRORS      = @()
$LOG_FILE    = "$BACKUP_DIR\backup.log"

# Carrega credenciais SMTP do arquivo de configuracao (nao versionado)
$ENV_BACKUP = "$SCRIPT_DIR\.env.backup"
$SMTP_HOST   = "smtp.office365.com"
$SMTP_PORT   = 587
$SMTP_USER   = ""
$SMTP_PASS   = ""
$SMTP_FROM   = ""
$NOTIFY_TO   = ""

if (Test-Path $ENV_BACKUP) {
    Get-Content $ENV_BACKUP | Where-Object { $_ -match "^\s*[^#]" } | ForEach-Object {
        $parts = $_ -split "=", 2
        if ($parts.Count -eq 2) {
            $k = $parts[0].Trim(); $v = $parts[1].Trim()
            switch ($k) {
                "SMTP_HOST"  { $script:SMTP_HOST  = $v }
                "SMTP_PORT"  { $script:SMTP_PORT  = [int]$v }
                "SMTP_USER"  { $script:SMTP_USER  = $v }
                "SMTP_PASS"  { $script:SMTP_PASS  = $v }
                "SMTP_FROM"  { $script:SMTP_FROM  = $v }
                "NOTIFY_TO"  { $script:NOTIFY_TO  = $v }
            }
        }
    }
}

function log($msg) {
    $line = "[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] $msg"
    Write-Host $line
    Add-Content -Path $LOG_FILE -Value $line -Encoding UTF8
}

function send-email($subject, $body) {
    if (-not $SMTP_USER -or -not $NOTIFY_TO) {
        log "Email ignorado: SMTP nao configurado em $ENV_BACKUP"
        return
    }
    try {
        $smtp = New-Object Net.Mail.SmtpClient($SMTP_HOST, $SMTP_PORT)
        $smtp.EnableSsl = $true
        $smtp.Credentials = New-Object Net.NetworkCredential($SMTP_USER, $SMTP_PASS)
        $smtp.Timeout = 30000
        $msg = New-Object Net.Mail.MailMessage
        $msg.From = $SMTP_FROM
        $msg.To.Add($NOTIFY_TO)
        $msg.Subject = $subject
        $msg.Body = $body
        $msg.IsBodyHtml = $false
        $smtp.Send($msg)
        log "Email enviado para $NOTIFY_TO"
    } catch {
        log "AVISO: falha ao enviar email - $_"
    }
}

function check-size($file, $label, $minMB = 0.1) {
    if (-not (Test-Path $file)) {
        $script:ERRORS += "${label}: arquivo nao gerado"
        log "ERRO: ${label} - arquivo nao encontrado"
        return
    }
    $rawMB  = (Get-Item $file).Length / 1MB
    $sizeMB = [math]::Round($rawMB, 2)
    if ($rawMB -lt $minMB) {
        $script:ERRORS += "${label}: ${sizeMB}MB (minimo: ${minMB}MB)"
        log "AVISO: ${label} - ${sizeMB}MB (suspeito)"
    } else {
        log "${label} - ${sizeMB}MB - ok"
    }
}

function run-volume-backup($volumeName, $label) {
    # tar.gz do volume inteiro via container temporario (alpine), sem parar nada
    $outFile = "$BACKUP_PATH\${label}_${TIMESTAMP}.tar.gz"
    log "${label}: iniciando backup do volume ${volumeName}..."
    docker run --rm -v "${volumeName}:/data:ro" -v "${BACKUP_PATH}:/backup" alpine `
        tar czf "/backup/${label}_${TIMESTAMP}.tar.gz" -C /data .
    if ($LASTEXITCODE -ne 0) {
        $script:ERRORS += "${label}: tar do volume falhou (exit $LASTEXITCODE)"
        log "ERRO: ${label} - tar retornou $LASTEXITCODE"
        return
    }
    # limiar bem baixo (so pega arquivo zerado/corrompido) - alguns volumes
    # (evolution, storage) sao stubs quase vazios legitimamente (~100-150 bytes
    # de tar.gz), falha real de tar ja e pega pelo exit code acima
    check-size $outFile $label 0.00001
}

function run-dump($label, $pgArgs, $outFile, $minMB) {
    # Grava dentro do container e copia para evitar corrupcao binaria do PowerShell
    $tmp = "/tmp/bkp_$([System.IO.Path]::GetFileName($outFile))"
    log "${label}: iniciando pg_dump..."
    docker exec jarvis-db-1 bash -c "pg_dump $pgArgs -f $tmp"
    if ($LASTEXITCODE -ne 0) {
        $script:ERRORS += "${label}: pg_dump falhou (exit $LASTEXITCODE)"
        log "ERRO: ${label} - pg_dump retornou $LASTEXITCODE"
        return
    }
    docker cp "jarvis-db-1:$tmp" $outFile
    docker exec jarvis-db-1 rm -f $tmp
    check-size $outFile $label $minMB
}

New-Item -ItemType Directory -Force -Path $BACKUP_PATH | Out-Null
$startTime = Get-Date
log "=========================================="
log "Iniciando backup Jarvis -> $BACKUP_PATH"

# 1. fiscal_documents (~1 GB, retencao 7 dias)
$f1 = "$BACKUP_PATH\fiscal_documents_${TIMESTAMP}.dump"
run-dump "fiscal_documents" "-U postgres -d postgres -Fc -Z 9 --no-owner --no-acl --table=public.fiscal_documents" $f1 50

# 2. Resto do banco sem fiscal_documents (retencao 30 dias)
$f2 = "$BACKUP_PATH\postgres_main_${TIMESTAMP}.dump"
run-dump "postgres_main" "-U postgres -d postgres -Fc -Z 9 --no-owner --no-acl --exclude-table=public.fiscal_documents" $f2 5

# 3. banco evolution (WhatsApp)
$f3 = "$BACKUP_PATH\evolution_db_${TIMESTAMP}.dump"
run-dump "evolution_db" "-U postgres -d evolution -Fc -Z 9 --no-owner --no-acl" $f3 0.01

# 4. Volumes Docker sem cobertura do pg_dump (protege contra crash do vhdx do WSL2)
# jarvis_ollama_data fora da lista de proposito: sao modelos baixados (reproduziveis), nao dados unicos
$VOLUMES_TO_BACKUP = @(
    @{ Volume = "jarvis_evolution_data";    Label = "vol_evolution" },
    @{ Volume = "jarvis_waha_data";         Label = "vol_waha" },
    @{ Volume = "jarvis_hermes_data";       Label = "vol_hermes" },
    @{ Volume = "jarvis_storage_data";      Label = "vol_storage" },
    @{ Volume = "jarvis_letsencrypt_certs"; Label = "vol_letsencrypt" },
    @{ Volume = "jarvis_acme_data";         Label = "vol_acme" }
)
foreach ($v in $VOLUMES_TO_BACKUP) {
    run-volume-backup $v.Volume $v.Label
}

# Rotacao
log "Rotacao: fiscal<=${RET_FISCAL}d, geral<=${RET_GERAL}d..."
Get-ChildItem $BACKUP_DIR -Recurse -Filter "fiscal_documents_*.dump" |
    Where-Object { $_.LastWriteTime -lt (Get-Date).AddDays(-$RET_FISCAL) } |
    Remove-Item -Force -ErrorAction SilentlyContinue
Get-ChildItem $BACKUP_DIR -Directory |
    Where-Object { $_.CreationTime -lt (Get-Date).AddDays(-$RET_GERAL) } |
    Remove-Item -Recurse -Force -ErrorAction SilentlyContinue

$elapsed = [math]::Round(((Get-Date) - $startTime).TotalMinutes, 1)
$totalMB  = [math]::Round((Get-ChildItem $BACKUP_PATH -Recurse | Measure-Object Length -Sum).Sum / 1MB, 1)
$files    = (Get-ChildItem $BACKUP_PATH -Recurse |
             ForEach-Object { "  $($_.Name) - $([math]::Round($_.Length/1MB,1))MB" }) -join "`n"

if ($ERRORS.Count -gt 0) {
    log "ERROS ($($ERRORS.Count)):"
    $ERRORS | ForEach-Object { log "  - $_" }
    log "=========================================="
    $errMsg = $ERRORS -join "`n- "
    send-email "[Jarvis] FALHA backup $TIMESTAMP" "Backup FALHOU em ${elapsed}min.`n`nErros:`n- $errMsg`n`nLog: $LOG_FILE"
    exit 1
} else {
    log "Concluido - ${totalMB}MB em ${elapsed}min"

    # ── Upload OneDrive (Backup/jarvis_dump_YYYYMMDD, diario 30d + copia mensal dia 1) ──
    log "OneDrive: enviando dumps..."
    Push-Location "E:\claudecode\claudecode"
    $prevEAP = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    $oneDriveOutput = & docker compose run --rm -v "${BACKUP_PATH}:/backup:ro" moneypenny-service `
        python /app/scripts/upload_backup_onedrive.py /backup $TIMESTAMP 2>$null
    $oneDriveOk = $LASTEXITCODE -eq 0
    $ErrorActionPreference = $prevEAP
    Pop-Location
    $oneDriveOutput | ForEach-Object { log "  [onedrive] $_" }
    if ($oneDriveOk) { log "OneDrive: ok" } else { log "OneDrive: FALHOU (backup local esta OK, so o envio pro OneDrive falhou)" }

    # ── Limpeza automatica do Docker (build cache + imagens sem uso) ──
    # docker compose/build acumula cache a cada deploy - sem isso, o disco
    # do WSL2 so cresce (nunca encolhe por si so). image prune sem -a so
    # remove imagens verdadeiramente orfas (sem tag/container usando).
    log "Docker: limpando build cache e imagens sem uso..."
    $prevEAP2 = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    $dockerCleanOutput = & docker builder prune -f 2>$null
    $dockerCleanOutput += & docker image prune -f 2>$null
    $ErrorActionPreference = $prevEAP2
    $dockerCleanOutput | Select-Object -Last 5 | ForEach-Object { log "  [docker] $_" }
    log "Docker: limpeza concluida"

    log "=========================================="
    $oneDriveMsg = if ($oneDriveOk) { "OneDrive: enviado com sucesso." } else { "OneDrive: FALHOU (ver log) - backup local esta intacto em $BACKUP_PATH." }
    send-email "[Jarvis] Backup OK $TIMESTAMP" "Backup OK em ${elapsed}min.`nTotal: ${totalMB}MB`n$oneDriveMsg`n`nArquivos:`n$files`n`nPasta: $BACKUP_PATH"
    exit 0
}
