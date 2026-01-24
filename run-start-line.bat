@echo off
REM Start START LINE Backend Server

echo ========================================
echo   START LINE Backend Server
echo ========================================
echo.

cd /d "%~dp0backend\start-line"

echo Starting server on port 8000...
python app.py

pause
