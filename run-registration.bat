@echo off
REM Start REGISTRATION Backend Server

echo ========================================
echo   REGISTRATION Backend Server
echo ========================================
echo.

cd /d "%~dp0backend\registration"

echo Starting server on port 8003...
python app.py

pause
