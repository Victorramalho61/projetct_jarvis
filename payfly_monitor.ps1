# Carrega credenciais do .env (nunca hardcode aqui)
$envFile = "E:\claudecode\claudecode\.env"
$PAYFLY_CLIENT_ID     = ""
$PAYFLY_CLIENT_SECRET = ""
if (Test-Path $envFile) {
    Get-Content $envFile | Where-Object { $_ -match "^PAYFLY_V2_CLIENT_ID=|^PAYFLY_V2_CLIENT_SECRET=" } | ForEach-Object {
        $k, $v = $_ -split "=", 2
        if ($k -eq "PAYFLY_V2_CLIENT_ID")     { $script:PAYFLY_CLIENT_ID     = $v.Trim() }
        if ($k -eq "PAYFLY_V2_CLIENT_SECRET") { $script:PAYFLY_CLIENT_SECRET = $v.Trim() }
    }
}
if (-not $PAYFLY_CLIENT_ID -or -not $PAYFLY_CLIENT_SECRET) {
    Write-Host "ERRO: PAYFLY_V2_CLIENT_ID e PAYFLY_V2_CLIENT_SECRET nao encontrados no .env"
    exit 1
}

while ($true) {
    $now = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    try {
        $body = "{`"clientId`":`"$PAYFLY_CLIENT_ID`",`"clientSecret`":`"$PAYFLY_CLIENT_SECRET`"}"
        $r = Invoke-WebRequest "https://api.payfly.com.br/prod/api/v2/auth/token" `
            -Method POST -ContentType "application/json" `
            -Body $body `
            -TimeoutSec 10 -UseBasicParsing -ErrorAction Stop
        Add-Content "E:\claudecode\claudecode\payfly_monitor.log" "$now OK $($r.StatusCode)"
        Write-Host "$now API VOLTOU!"
        break
    } catch {
        $code = $_.Exception.Response.StatusCode.value__
        Add-Content "E:\claudecode\claudecode\payfly_monitor.log" "$now FAIL $code"
        Write-Host "$now still down ($code)"
    }
    Start-Sleep 600
}
