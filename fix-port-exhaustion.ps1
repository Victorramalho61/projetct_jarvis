# fix-port-exhaustion.ps1 - Execute como Administrador

Write-Host "=== Corrigindo exaustao de portas efemeras ===" -ForegroundColor Cyan

# 1. Expandir range de portas efemeras
# Padrao Windows: 49152-65535 = 16384 portas
# Novo range:     10000-65535 = 55535 portas (3.4x mais)
Write-Host "[1/3] Expandindo range TCP/UDP..." -ForegroundColor Yellow
netsh int ipv4 set dynamicport tcp start=10000 num=55535
netsh int ipv4 set dynamicport udp start=10000 num=55535
netsh int ipv6 set dynamicport tcp start=10000 num=55535
netsh int ipv6 set dynamicport udp start=10000 num=55535

Write-Host "Novo range TCP:" -ForegroundColor Green
netsh int ipv4 show dynamicport tcp

# 2. Reduzir TIME_WAIT de 240s para 30s (requer reboot)
Write-Host "[2/3] Reduzindo TcpTimedWaitDelay para 30s..." -ForegroundColor Yellow
New-ItemProperty `
    -Path 'HKLM:\SYSTEM\CurrentControlSet\Services\Tcpip\Parameters' `
    -Name 'TcpTimedWaitDelay' `
    -Value 30 `
    -PropertyType DWORD `
    -Force | Out-Null

$val = (Get-ItemProperty 'HKLM:\SYSTEM\CurrentControlSet\Services\Tcpip\Parameters').TcpTimedWaitDelay
Write-Host "TcpTimedWaitDelay = $val segundos" -ForegroundColor Green

# 3. MaxUserPort
Write-Host "[3/3] Verificando MaxUserPort..." -ForegroundColor Yellow
$existing = (Get-ItemProperty 'HKLM:\SYSTEM\CurrentControlSet\Services\Tcpip\Parameters' -ErrorAction SilentlyContinue).MaxUserPort
if (-not $existing -or $existing -lt 65534) {
    New-ItemProperty `
        -Path 'HKLM:\SYSTEM\CurrentControlSet\Services\Tcpip\Parameters' `
        -Name 'MaxUserPort' `
        -Value 65534 `
        -PropertyType DWORD `
        -Force | Out-Null
    Write-Host "MaxUserPort definido para 65534" -ForegroundColor Green
} else {
    Write-Host "MaxUserPort ja esta em $existing - OK" -ForegroundColor Green
}

Write-Host ""
Write-Host "=== Concluido ===" -ForegroundColor Cyan
Write-Host "IMPORTANTE: TcpTimedWaitDelay requer REBOOT para efeito completo." -ForegroundColor Red
Write-Host "Range de portas (netsh) ja esta ativo imediatamente." -ForegroundColor Green
