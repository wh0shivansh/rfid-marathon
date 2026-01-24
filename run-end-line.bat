@echo off
REM Start END LINE Backend Server

echo ========================================
echo   END LINE Backend Server
echo ========================================
echo.

cd /d "%~dp0backend\end-line"

echo Starting server on port 8002...
python app.py

pause
