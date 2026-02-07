# filepath: e:\Innogative\rfid-marathon\build_all.ps1
# Build all components in sequence

$ErrorActionPreference = "Stop"

$root = $PSScriptRoot

Write-Host "Building database setup..."
Set-Location (Join-Path $root "database")
.\build_database.ps1

Write-Host "Building frontend..."
Set-Location (Join-Path $root "frontend")
npm run package

Write-Host "Building backend v2..."
Set-Location (Join-Path $root "backend\v2")
.\build_exe.ps1

Write-Host "Building proxy v2..."
Set-Location (Join-Path $root "proxy\v2")
.\build_rfid_listener.ps1

Write-Host "Building UDP server..."
Set-Location (Join-Path $root "udp_server")
.\build_udp_server.ps1

Write-Host "Building Control Hub..."
Set-Location (Join-Path $root "control-hub")
.\build_control_hub.ps1

Write-Host "All builds completed successfully!"