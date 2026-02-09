# Build a standalone Windows .exe for control hub
# Usage (from PowerShell):
#   Set-Location e:\Innogative\rfid-marathon\control-hub
#   .\build_control_hub.ps1

$ErrorActionPreference = "Stop"

Set-Location $PSScriptRoot

# Create a clean virtual environment for reproducible builds (optional)
if (-not (Test-Path ".venv")) {
    python -m venv .venv
}

. .\.venv\Scripts\Activate.ps1

python -m pip install --upgrade pip
python -m pip install pyinstaller

# Build single-file executable
pyinstaller --noconfirm --onefile --noconsole --name control-hub control-hub.py

Write-Host "Moving dist folder to root level"
Move-Item -Path "dist\control-hub.exe" -Destination "..\RFID-Marathon-Automation\control-hub.exe" -Force
Remove-Item "dist" -Recurse -Force
Remove-Item "build" -Recurse -Force