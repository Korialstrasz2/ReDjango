[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
$command = Get-Command tailscale.exe -ErrorAction SilentlyContinue
$tailscale = if ($command) { $command.Source } else { Join-Path $env:ProgramFiles "Tailscale\tailscale.exe" }
if (-not (Test-Path -LiteralPath $tailscale -PathType Leaf)) {
    throw "tailscale.exe non trovato."
}

& $tailscale serve --https=443 off
if ($LASTEXITCODE -ne 0) {
    throw "Non è stato possibile rimuovere la pubblicazione HTTPS di ReDjango."
}
Write-Host "Pubblicazione Tailscale Serve rimossa. ReDjango non è stato arrestato."
