@echo off
REM Start END LINE Proxy Server

echo ========================================
echo   END LINE Proxy Server
echo ========================================
echo.

cd /d "%~dp0proxy-9090\end-line"

echo Starting proxy on port 9090...
echo Backend URL: http://localhost:8002
echo.

python proxy.py

pause
