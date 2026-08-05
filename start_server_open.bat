@echo off
rem Open launcher: LAN mode with local HTTPS certificate (0.0.0.0:8003).
rem Forces LAN regardless of the persisted access mode.
call "%~dp0start_server.bat" lan
if errorlevel 1 (
    echo.
    echo Server stopped with errors. Check output above.
    pause
)
exit /b %errorlevel%
