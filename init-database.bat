@echo off
REM Initialize Database

echo ========================================
echo   Database Initialization
echo ========================================
echo.

cd /d "%~dp0backend\shared"

echo Running database initialization...
echo.

python init_db.py

echo.
pause
