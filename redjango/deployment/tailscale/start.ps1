[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..\..")).Path
$serverPort = 8003

function Resolve-TailscaleExecutable {
    $command = Get-Command tailscale.exe -ErrorAction SilentlyContinue
    if ($command) {
        return $command.Source
    }

    $installedPath = Join-Path $env:ProgramFiles "Tailscale\tailscale.exe"
    if (Test-Path -LiteralPath $installedPath -PathType Leaf) {
        return $installedPath
    }

    throw "Tailscale non è installato. Installalo da https://tailscale.com/download/windows e accedi, poi riprova."
}

function Read-TailscaleStatus([string]$tailscaleExecutable) {
    $rawStatus = & $tailscaleExecutable status --json 2>&1
    if ($LASTEXITCODE -ne 0) {
        throw "Impossibile leggere lo stato Tailscale: $($rawStatus -join ' ')"
    }
    return ($rawStatus -join "`n" | ConvertFrom-Json)
}

function Ensure-ApplicationSecret([string]$root) {
    $stateDirectory = Join-Path $root ".redjango"
    $secretPath = Join-Path $stateDirectory "django-secret-key"
    New-Item -ItemType Directory -Path $stateDirectory -Force | Out-Null

    if (-not (Test-Path -LiteralPath $secretPath -PathType Leaf)) {
        $secretBytes = New-Object byte[] 64
        $generator = [Security.Cryptography.RandomNumberGenerator]::Create()
        try {
            $generator.GetBytes($secretBytes)
        }
        finally {
            $generator.Dispose()
        }
        $secret = [Convert]::ToBase64String($secretBytes)
        [IO.File]::WriteAllText($secretPath, "$secret`n", (New-Object Text.UTF8Encoding($false)))
    }

    $storedSecret = (Get-Content -LiteralPath $secretPath -Raw).Trim()
    if ($storedSecret.Length -lt 50) {
        throw "La chiave privata in $secretPath è troppo corta. Non verrà sostituita automaticamente."
    }
    return $storedSecret
}

$tailscale = Resolve-TailscaleExecutable
$status = Read-TailscaleStatus $tailscale
if ([string]$status.BackendState -ne "Running") {
    throw "Tailscale non è connesso (stato: $($status.BackendState)). Apri Tailscale, accedi e riprova."
}

$dnsName = ([string]$status.Self.DNSName).Trim().TrimEnd(".")
if (-not $dnsName) {
    throw "Tailscale non ha assegnato un nome DNS a questo computer. Abilita MagicDNS/HTTPS nel pannello Tailscale."
}

$publicOrigin = "https://$dnsName"
$env:REDJANGO_ACCESS_MODE = "online"
$env:REDJANGO_PUBLIC_ORIGIN = $publicOrigin
$env:REDJANGO_SECRET_KEY = Ensure-ApplicationSecret $projectRoot
$env:REDJANGO_TRUSTED_PROXIES = "127.0.0.0/8,::1/128"
$env:REDJANGO_DEBUG = "0"

Write-Host "Configurazione Tailscale Serve per ReDjango..."
& $tailscale serve --bg --https=443 "http://127.0.0.1:$serverPort"
if ($LASTEXITCODE -ne 0) {
    throw "Tailscale Serve non è stato configurato. Segui l'eventuale URL di autorizzazione mostrato sopra e riprova."
}

Write-Host ""
Write-Host "ReDjango remoto privato: $publicOrigin"
Write-Host "Il computer deve restare acceso, connesso e senza sospensione."
Write-Host "La pubblicazione è privata nella rete Tailscale; il login ReDjango resta obbligatorio."
Write-Host ""

Push-Location $projectRoot
try {
    & (Join-Path $projectRoot "start_server.bat") online
    $serverExitCode = $LASTEXITCODE
}
finally {
    Pop-Location
}

if ($serverExitCode -ne 0) {
    throw "ReDjango si è arrestato con codice $serverExitCode. Esegui diagnose.ps1 per separare errori locali e Tailscale."
}
