@echo off
setlocal enableextensions

cd /d "%~dp0"

rem Tailscale Serve uses the protected Windows service API. Relaunch this
rem launcher elevated when it was opened normally (for example by double-click).
net session >nul 2>&1
if not "%errorlevel%"=="0" (
    echo Richiesta autorizzazione Windows per configurare Tailscale e avviare ReDjango...
    powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "Start-Process -FilePath '%~f0' -Verb RunAs"
    if errorlevel 1 (
        echo L'autorizzazione amministratore e' necessaria per Tailscale Serve.
        pause
    )
    exit /b
)

title ReDjango + Tailscale privato
echo Avvio ReDjango tramite Tailscale Serve privato...
echo Questa finestra deve restare aperta mentre gli amici giocano.
echo.

powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0redjango\deployment\tailscale\start.ps1"
set "SERVER_EXIT=%errorlevel%"

if not "%SERVER_EXIT%"=="0" (
    echo.
    echo Avvio non riuscito. Leggi il messaggio sopra e riprova.
    pause
)

exit /b %SERVER_EXIT%
