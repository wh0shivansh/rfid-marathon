@echo off
REM Start START LINE Proxy Server

echo ========================================
echo   START LINE Proxy Server
echo ========================================
echo.

cd /d "%~dp0proxy-9090\start-line"

echo Starting proxy on port 9090...
echo Backend URL: http://localhost:8000
echo.

python proxy.py

pause
