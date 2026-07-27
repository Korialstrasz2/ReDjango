@echo off
setlocal

cd /d "%~dp0"

set "PYTHON=python"
set "BIND_ADDRESS=127.0.0.1:8003"
set "RUN_MODE=local"
if /I "%~1"=="lan" (
    set "BIND_ADDRESS=0.0.0.0:8003"
    set "RUN_MODE=lan"
)
if exist "venv\Scripts\python.exe" set "PYTHON=venv\Scripts\python.exe"
if exist ".venv\Scripts\python.exe" set "PYTHON=.venv\Scripts\python.exe"

%PYTHON% -c "import django" >nul 2>nul
if errorlevel 1 (
    echo Django non e disponibile; creazione dell'ambiente virtuale locale...
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

echo.
echo Pagina principale di ReDjango: http://127.0.0.1:8003/
if /I "%RUN_MODE%"=="lan" (
    echo Modalita LAN attiva. Indirizzo di ascolto: 0.0.0.0:8003
) else (
    echo Modalita locale attiva. Per consentire client LAN, esegui: start_server.bat lan
)
echo Apri o usa Ctrl+clic sull'indirizzo della pagina principale indicato sopra.
echo.
%PYTHON% manage.py runserver %BIND_ADDRESS%
goto :eof

:error
echo Avvio di ReDjango non riuscito.
exit /b 1
