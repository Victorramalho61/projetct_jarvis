while ($true) {
    $now = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    try {
        $r = Invoke-WebRequest "https://api.payfly.com.br/prod/api/v2/auth/token" `
            -Method POST -ContentType "application/json" `
            -Body '{"clientId":"payfly-test","clientSecret":"payfly123"}' `
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
