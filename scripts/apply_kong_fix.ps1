# Aplica correcao do kong.yml (upstream + health check ativo) pra eliminar
# os 502 que aconteciam durante o boot de containers recem-deployados.
# Faz backup do kong.yml atual, aplica o novo, reinicia o Kong, valida as
# rotas e faz rollback automatico se algo der errado. Roda via Task Scheduler
# (tarefa unica, ver scripts/register_kong_fix_task.ps1).

$ErrorActionPreference = "Stop"
$SCRIPT_DIR   = Split-Path -Parent $MyInvocation.MyCommand.Path
$REPO_DIR     = Split-Path -Parent $SCRIPT_DIR
$KONG_DIR     = Join-Path $REPO_DIR "volumes\api"
$KONG_LIVE    = Join-Path $KONG_DIR "kong.yml"
$KONG_NEW     = Join-Path $KONG_DIR "kong.yml.new"
$BACKUP_DIR   = Join-Path $KONG_DIR "kong_backups"
$TIMESTAMP    = Get-Date -Format "yyyyMMdd_HHmmss"
$KONG_BACKUP  = Join-Path $BACKUP_DIR "kong_$TIMESTAMP.yml"
$LOG_FILE     = Join-Path $BACKUP_DIR "kong_fix_apply.log"

New-Item -ItemType Directory -Force -Path $BACKUP_DIR | Out-Null

$ENV_BACKUP = "$SCRIPT_DIR\.env.backup"
$SMTP_HOST = "smtp.office365.com"; $SMTP_PORT = 587
$SMTP_USER = ""; $SMTP_PASS = ""; $SMTP_FROM = ""; $NOTIFY_TO = ""
if (Test-Path $ENV_BACKUP) {
    Get-Content $ENV_BACKUP | Where-Object { $_ -match "^\s*[^#]" } | ForEach-Object {
        $parts = $_ -split "=", 2
        if ($parts.Count -eq 2) {
            $k = $parts[0].Trim(); $v = $parts[1].Trim()
            switch ($k) {
                "SMTP_HOST" { $script:SMTP_HOST = $v }
                "SMTP_PORT" { $script:SMTP_PORT = [int]$v }
                "SMTP_USER" { $script:SMTP_USER = $v }
                "SMTP_PASS" { $script:SMTP_PASS = $v }
                "SMTP_FROM" { $script:SMTP_FROM = $v }
                "NOTIFY_TO" { $script:NOTIFY_TO = $v }
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
        $smtp.Send($msg)
        log "Email enviado para $NOTIFY_TO"
    } catch {
        log "AVISO: falha ao enviar email - $_"
    }
}

function wait-kong-healthy($timeoutSec = 40) {
    $elapsed = 0
    while ($elapsed -lt $timeoutSec) {
        $status = docker inspect --format "{{.State.Health.Status}}" jarvis-kong-1 2>$null
        if ($status -eq "healthy") { return $true }
        Start-Sleep -Seconds 2
        $elapsed += 2
    }
    return $false
}

function verify-routes() {
    # Confere via Admin API interna do Kong (nao exposta ao host) se os
    # upstreams recem-criados estao com pelo menos 1 alvo saudavel.
    $upstreams = @(
        "monitoring-upstream","freshservice-upstream","moneypenny-upstream",
        "agents-upstream","expenses-upstream","support-upstream",
        "performance-upstream","fiscal-upstream","financeiro-upstream",
        "cards-upstream","experiencia-upstream","core-upstream"
        # hermes-upstream fica de fora: servico esta desligado deliberadamente
    )
    $failed = @()
    foreach ($u in $upstreams) {
        $out = docker exec jarvis-kong-1 sh -c "wget -qO- http://127.0.0.1:8001/upstreams/$u/health 2>&1"
        if ($out -notmatch '"HEALTHY"' -and $out -notmatch '"health":"HEALTHY"') {
            $failed += "$u -> $out"
        }
    }
    return $failed
}

log "=========================================="
log "Iniciando aplicacao da correcao do Kong (upstream + healthcheck)"

if (-not (Test-Path $KONG_NEW)) {
    log "ERRO FATAL: $KONG_NEW nao encontrado. Abortando sem tocar em nada."
    send-email "[Jarvis] Kong fix ABORTADO" "kong.yml.new nao encontrado em $KONG_NEW. Nada foi alterado."
    exit 1
}

log "Backup do kong.yml atual -> $KONG_BACKUP"
Copy-Item $KONG_LIVE $KONG_BACKUP -Force

log "Aplicando novo kong.yml"
Copy-Item $KONG_NEW $KONG_LIVE -Force

log "Reiniciando container do Kong..."
docker restart jarvis-kong-1 | Out-Null

log "Aguardando Kong ficar healthy..."
$healthy = wait-kong-healthy -timeoutSec 40

$rollback = $false
$reason = ""

if (-not $healthy) {
    $rollback = $true
    $reason = "Kong nao ficou healthy apos restart (timeout 40s)"
} else {
    log "Kong healthy. Verificando upstreams..."
    Start-Sleep -Seconds 5   # da tempo do healthcheck ativo rodar pelo menos 1 ciclo
    $failed = verify-routes
    if ($failed.Count -gt 0) {
        $rollback = $true
        $reason = "Upstreams sem alvo saudavel: `n" + ($failed -join "`n")
    }
}

if ($rollback) {
    log "FALHA NA VALIDACAO: $reason"
    log "Restaurando kong.yml anterior (rollback automatico)..."
    Copy-Item $KONG_BACKUP $KONG_LIVE -Force
    docker restart jarvis-kong-1 | Out-Null
    $rbHealthy = wait-kong-healthy -timeoutSec 40
    log "Kong apos rollback: $(if ($rbHealthy) {'healthy'} else {'AINDA COM PROBLEMA - VERIFICAR MANUALMENTE'})"
    log "=========================================="
    send-email "[Jarvis] Kong fix FALHOU - rollback aplicado" "A correcao do kong.yml (upstream + healthcheck) falhou na validacao e foi revertida automaticamente.`n`nMotivo:`n$reason`n`nKong apos rollback: $(if ($rbHealthy) {'healthy'} else {'AINDA COM PROBLEMA - VERIFICAR MANUALMENTE, URGENTE'})`n`nBackup usado no rollback: $KONG_BACKUP`nLog completo: $LOG_FILE"
    exit 1
} else {
    log "Validacao OK - todos os upstreams com pelo menos 1 alvo saudavel."
    log "Correcao aplicada com sucesso."
    log "=========================================="
    send-email "[Jarvis] Kong fix aplicado com sucesso" "kong.yml atualizado para usar upstream + health check ativo em todos os microsservicos.`n`nBackup do config anterior: $KONG_BACKUP`nLog completo: $LOG_FILE`n`nProximo deploy de qualquer microsservico nao deve mais gerar 502 pros usuarios."
    exit 0
}
