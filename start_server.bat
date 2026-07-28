@echo off
setlocal enableextensions enabledelayedexpansion

cd /d "%~dp0"

set "PYTHON=python"
set "REQUESTED_MODE=%~1"
if /I "%REQUESTED_MODE%"=="local" set "REQUESTED_MODE=locked"
if defined REQUESTED_MODE if /I not "%REQUESTED_MODE%"=="locked" if /I not "%REQUESTED_MODE%"=="lan" if /I not "%REQUESTED_MODE%"=="online" (
    echo Modalita non valida: %REQUESTED_MODE%
    echo Usa: start_server.bat [locked^|lan^|online]
    goto :error
)
if defined REQUESTED_MODE set "REDJANGO_ACCESS_MODE=%REQUESTED_MODE%"
if exist "venv\Scripts\python.exe" set "PYTHON=venv\Scripts\python.exe"
if exist ".venv\Scripts\python.exe" set "PYTHON=.venv\Scripts\python.exe"

%PYTHON% -c "import cryptography, django, uvicorn, waitress, whitenoise" >nul 2>nul
if errorlevel 1 (
    echo Preparazione dell'ambiente virtuale locale...
    if not exist ".venv\Scripts\python.exe" python -m venv .venv
    set "PYTHON=.venv\Scripts\python.exe"
    echo Installazione delle dipendenze Python...
    %PYTHON% -m pip install --upgrade pip
    %PYTHON% -m pip install -r requirements.txt
)

where npm.cmd >nul 2>nul
if errorlevel 1 (
    echo Node.js e npm sono necessari per costruire l'interfaccia React.
    goto :error
)

if not exist "frontend\node_modules" (
    echo Installazione delle dipendenze frontend...
    pushd frontend
    call npm.cmd ci
    if errorlevel 1 (popd & goto :error)
    popd
)

echo Costruzione dell'interfaccia React...
pushd frontend
call npm.cmd run build
if errorlevel 1 (popd & goto :error)
popd

echo Applicazione delle migrazioni del database...
%PYTHON% manage.py migrate --noinput
if errorlevel 1 goto :error

echo Preparazione dei dati locali minimi...
%PYTHON% manage.py seed_minimum_data
if errorlevel 1 goto :error

echo Verifica dell'account amministratore...
%PYTHON% manage.py ensure_admin_login
if errorlevel 1 goto :error

if defined REQUESTED_MODE (
    echo Impostazione della modalita %REQUESTED_MODE%...
    %PYTHON% manage.py access_mode --set %REQUESTED_MODE%
    if errorlevel 1 goto :error
)

if exist ".redjango-restart-requested" del /q ".redjango-restart-requested"

:configure_runtime
set "ACCESS_MODE="
for /f "usebackq delims=" %%M in (`%PYTHON% manage.py access_mode`) do set "ACCESS_MODE=%%M"
if not defined ACCESS_MODE goto :error

set "REDJANGO_ACCESS_MODE=%ACCESS_MODE%"
set "REDJANGO_MANAGED_LAUNCHER=1"
set "BIND_ADDRESS=127.0.0.1:8003"
if /I "%ACCESS_MODE%"=="lan" (
    set "BIND_ADDRESS=0.0.0.0:8003"
    echo Preparazione del certificato HTTPS per la rete locale...
    %PYTHON% manage.py ensure_lan_certificate
    if errorlevel 1 goto :error
)
if /I "%ACCESS_MODE%"=="online" (
    if not defined REDJANGO_ONLINE_BIND set "REDJANGO_ONLINE_BIND=127.0.0.1:8003"
    set "BIND_ADDRESS=!REDJANGO_ONLINE_BIND!"
    echo Raccolta degli asset statici per la modalita online...
    %PYTHON% manage.py collectstatic --noinput
    if errorlevel 1 goto :error
)

echo.
echo Modalita di accesso attiva: %ACCESS_MODE%
echo Indirizzo di ascolto: %BIND_ADDRESS%
if /I "%ACCESS_MODE%"=="locked" echo ReDjango accetta richieste soltanto da questo computer.
if /I "%ACCESS_MODE%"=="lan" echo I client LAN devono accettare il certificato locale e verificarne l'impronta SHA-256.
if /I "%ACCESS_MODE%"=="online" echo Pubblicazione online protetta: usa HTTPS e un reverse proxy configurato.
if /I "%ACCESS_MODE%"=="lan" (
    echo Pagina principale locale: https://127.0.0.1:8003/
) else (
    echo Pagina principale locale: http://127.0.0.1:8003/
)
echo Apri o usa Ctrl+clic sull'indirizzo della pagina principale indicato sopra.
echo.

if /I "%ACCESS_MODE%"=="lan" (
    %PYTHON% -m uvicorn redjango.asgi:application --host 0.0.0.0 --port 8003 --ssl-keyfile .redjango\tls\lan-key.pem --ssl-certfile .redjango\tls\lan-cert.pem
) else (
    %PYTHON% -m waitress --listen=%BIND_ADDRESS% redjango.wsgi:application
)
set "SERVER_EXIT=%ERRORLEVEL%"
if exist ".redjango-restart-requested" (
    del /q ".redjango-restart-requested"
    echo Riavvio richiesto dall'interfaccia...
    goto :configure_runtime
)
if not "%SERVER_EXIT%"=="0" goto :error
goto :eof

:error
echo Avvio di ReDjango non riuscito.
exit /b 1
