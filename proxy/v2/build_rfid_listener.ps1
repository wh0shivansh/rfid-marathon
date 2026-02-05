# Build a standalone Windows .exe for backend v2
# Usage (from PowerShell):
#   Set-Location e:\Innogative\rfid-marathon\backend\v2
#   .\build_exe.ps1

$ErrorActionPreference = "Stop"

Set-Location $PSScriptRoot

# Create a clean virtual environment for reproducible builds (optional)
if (-not (Test-Path ".venv")) {
    python -m venv .venv
}

. .\.venv\Scripts\Activate.ps1

python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m pip install pyinstaller

# Build single-file executable
pyinstaller --noconfirm --name rfid-listener run_rfid_listener.py

Write-Host "Build complete. Output: dist\rfid_listener.exe"
Write-Host "Place .env next to the exe before running."
