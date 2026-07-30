@echo off
call "%~dp0start_server.bat" %*
if errorlevel 1 (
    echo.
    echo Server stopped with errors. Check output above.
    pause
)
exit /b %errorlevel%
