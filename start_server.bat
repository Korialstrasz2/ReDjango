@echo off
setlocal

cd /d "%~dp0"

set "PYTHON=python"
if exist ".venv\Scripts\python.exe" set "PYTHON=.venv\Scripts\python.exe"

%PYTHON% -c "import django" >nul 2>nul
if errorlevel 1 (
    echo Django is not available; creating local virtual environment...
    if not exist ".venv\Scripts\python.exe" python -m venv .venv
    set "PYTHON=.venv\Scripts\python.exe"
    echo Installing Python dependencies...
    %PYTHON% -m pip install --upgrade pip
    %PYTHON% -m pip install -r requirements.txt
)

echo Applying database migrations...
%PYTHON% manage.py migrate --noinput
if errorlevel 1 goto :error

echo Seeding minimum local data...
%PYTHON% manage.py seed_minimum_data
if errorlevel 1 goto :error

echo Starting ReDjango on http://0.0.0.0:8003/
%PYTHON% manage.py runserver 0.0.0.0:8003
goto :eof

:error
echo ReDjango failed to start.
exit /b 1
