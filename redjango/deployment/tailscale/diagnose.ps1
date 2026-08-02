[CmdletBinding()]
param()

$ErrorActionPreference = "Continue"
$serverPort = 8003
$failures = 0

function Resolve-TailscaleExecutable {
    $command = Get-Command tailscale.exe -ErrorAction SilentlyContinue
    if ($command) { return $command.Source }
    $installedPath = Join-Path $env:ProgramFiles "Tailscale\tailscale.exe"
    if (Test-Path -LiteralPath $installedPath -PathType Leaf) { return $installedPath }
    return $null
}

function Report-Check([bool]$ok, [string]$label, [string]$detail) {
    if ($ok) {
        Write-Host "[OK] $label - $detail" -ForegroundColor Green
    }
    else {
        Write-Host "[ERRORE] $label - $detail" -ForegroundColor Red
        $script:failures += 1
    }
}

$tailscale = Resolve-TailscaleExecutable
Report-Check ([bool]$tailscale) "Installazione" $(if ($tailscale) { $tailscale } else { "tailscale.exe non trovato" })
if (-not $tailscale) { exit 1 }

$rawStatus = & $tailscale status --json 2>&1
$statusOk = $LASTEXITCODE -eq 0
Report-Check $statusOk "Stato Tailscale" $(if ($statusOk) { "JSON disponibile" } else { $rawStatus -join " " })
if (-not $statusOk) { exit 1 }

$status = $rawStatus -join "`n" | ConvertFrom-Json
$running = [string]$status.BackendState -eq "Running"
Report-Check $running "Connessione" "BackendState=$($status.BackendState)"
$dnsName = ([string]$status.Self.DNSName).Trim().TrimEnd(".")
Report-Check ([bool]$dnsName) "MagicDNS" $(if ($dnsName) { $dnsName } else { "nome .ts.net assente" })

$serveStatus = & $tailscale serve status 2>&1
$serveOk = $LASTEXITCODE -eq 0 -and ($serveStatus -join " ") -match "127\.0\.0\.1:$serverPort"
Report-Check $serveOk "Tailscale Serve" ($serveStatus -join " ")

try {
    $local = Invoke-WebRequest "http://127.0.0.1:$serverPort/api/auth/session/" -UseBasicParsing -TimeoutSec 10
    Report-Check ($local.StatusCode -eq 200) "ReDjango locale" "HTTP $($local.StatusCode)"
}
catch {
    Report-Check $false "ReDjango locale" $_.Exception.Message
}

if ($dnsName) {
    try {
        $remote = Invoke-WebRequest "https://$dnsName/api/auth/session/" -UseBasicParsing -TimeoutSec 20
        Report-Check ($remote.StatusCode -eq 200) "ReDjango via Tailscale" "HTTP $($remote.StatusCode)"
    }
    catch {
        Report-Check $false "ReDjango via Tailscale" $_.Exception.Message
    }
}

if ($failures -gt 0) {
    Write-Host ""
    Write-Host "$failures controllo/i non superato/i. Consulta Guide > Accesso remoto privato · Tailscale > Full Tech Debug." -ForegroundColor Yellow
    exit 1
}

Write-Host ""
Write-Host "Tutti i controlli sono verdi. URL: https://$dnsName" -ForegroundColor Green
