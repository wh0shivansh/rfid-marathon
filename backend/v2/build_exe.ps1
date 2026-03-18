# Build a standalone Windows .exe for backend v2
# Usage (from PowerShell):
#   Set-Location backend\v2
#   .\build_exe.ps1

$ErrorActionPreference = "Stop"

Set-Location $PSScriptRoot

# check if the file exist then delete the folder
if (Test-Path "..\..\RFID-Marathon-Automation\rfid-backend") {
    Remove-Item "..\..\RFID-Marathon-Automation\rfid-backend" -Recurse -Force
}

# Create a clean virtual environment for reproducible builds (optional)
if (-not (Test-Path ".venv")) {
    python -m venv .venv
}

. .\.venv\Scripts\Activate.ps1

python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m pip install pyinstaller

# Build single-file executable
pyinstaller --noconfirm --clean rfid-backend.spec

Write-Host "Placing .env next to the exe."
Copy-Item -Path ".env" -Destination "dist\rfid-backend\" -Force

Write-Host "Moving dist folder to root level"
Move-Item -Path "dist\rfid-backend" -Destination "..\..\RFID-Marathon-Automation" -Force
Remove-Item "dist" -Recurse -Force
Remove-Item "build" -Recurse -Force