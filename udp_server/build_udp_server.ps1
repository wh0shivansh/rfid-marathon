# Build a standalone Windows .exe for backend v2
# Usage (from PowerShell):
#   Set-Location e:\Innogative\udp-marathon\backend\v2
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

# Build one-folder executables using spec files
pyinstaller --noconfirm udp-listener.spec
Write-Host "Listener Build complete. Output: dist\udp-listener\udp-listener.exe"

pyinstaller --noconfirm udp-sender.spec
Write-Host "Sender Build complete. Output: dist\udp-sender\udp-sender.exe"

Write-Host "Place .env next to the exe before running."