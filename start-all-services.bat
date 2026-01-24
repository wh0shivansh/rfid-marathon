@echo off
REM Start ALL Services in separate windows

echo ========================================
echo   RFID Marathon System
echo   Starting All Services...
echo ========================================
echo.

echo Starting services in separate windows...
echo.

REM Start backends
start "START LINE Backend (8000)" cmd /k "%~dp0run-start-line.bat"
timeout /t 2 /nobreak >nul

start "END LINE Backend (8002)" cmd /k "%~dp0run-end-line.bat"
timeout /t 2 /nobreak >nul

start "REGISTRATION Backend (8003)" cmd /k "%~dp0run-registration.bat"
timeout /t 2 /nobreak >nul

REM Start proxies
start "START LINE Proxy (9090)" cmd /k "%~dp0run-start-proxy.bat"
timeout /t 2 /nobreak >nul

start "END LINE Proxy (9090)" cmd /k "%~dp0run-end-proxy.bat"

echo.
echo ========================================
echo   All Services Started!
echo ========================================
echo.
echo Services:
echo   - START LINE Backend:     http://localhost:8000
echo   - END LINE Backend:       http://localhost:8002
echo   - REGISTRATION Backend:   http://localhost:8003
echo   - START LINE Proxy:       http://localhost:9090
echo   - END LINE Proxy:         http://localhost:9090
echo.
echo Press any key to close this window...
pause >nul
