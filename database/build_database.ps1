$ErrorActionPreference = "Stop"

function Get-EnvMap {
    param([string]$EnvPath)

    if (-not (Test-Path -LiteralPath $EnvPath)) {
        throw "Env file not found: $EnvPath"
    }

    $map = @{}
    Get-Content -LiteralPath $EnvPath | ForEach-Object {
        $line = $_.Trim()
        if ($line.Length -eq 0 -or $line.StartsWith("#")) {
            return
        }
        $parts = $line.Split("=", 2)
        if ($parts.Count -ne 2) {
            return
        }
        $key = $parts[0].Trim()
        $value = $parts[1].Trim()
        $map[$key] = $value
    }
    return $map
}

function Resolve-RepoPath {
    param([string]$RepoRoot, [string]$PathValue)

    if ([string]::IsNullOrWhiteSpace($PathValue)) {
        return $null
    }
    $cleanValue = $PathValue.Trim().Trim('"')
    if ([string]::IsNullOrWhiteSpace($cleanValue)) {
        return $null
    }
    if ($cleanValue -match '^[A-Za-z]:\\') {
        $cleanValue = $cleanValue -replace '\\\\', '\\'
    }
    if ([System.IO.Path]::IsPathRooted($cleanValue)) {
        return $cleanValue
    }
    return Join-Path $RepoRoot $cleanValue
}

$repoRoot = Split-Path -Parent $PSScriptRoot
$envPath = Join-Path $PSScriptRoot ".env"
$envMap = Get-EnvMap -EnvPath $envPath

$hostName = $envMap["DB_HOST"]
$port = $envMap["DB_PORT"]
$appDb = $envMap["DB_NAME"]
$appUser = $envMap["DB_USER"]
$appPassword = $envMap["DB_PASSWORD"]
$adminUser = $envMap["DB_ADMIN_USER"]
$adminPassword = $envMap["DB_ADMIN_PASSWORD"]
$dataDir = Resolve-RepoPath -RepoRoot $repoRoot -PathValue $envMap["DB_LOCAL_DATA_DIR"]
$binDir = Resolve-RepoPath -RepoRoot $repoRoot -PathValue $envMap["DB_LOCAL_BIN_DIR"]
$sourceBinDir = Resolve-RepoPath -RepoRoot $repoRoot -PathValue $envMap["DB_SOURCE_BIN_DIR"]

$required = @{
    DB_HOST = $hostName
    DB_PORT = $port
    DB_NAME = $appDb
    DB_USER = $appUser
    DB_PASSWORD = $appPassword
    DB_ADMIN_USER = $adminUser
    DB_ADMIN_PASSWORD = $adminPassword
    DB_LOCAL_DATA_DIR = $dataDir
    DB_LOCAL_BIN_DIR = $binDir
}

foreach ($key in $required.Keys) {
    if ([string]::IsNullOrWhiteSpace($required[$key])) {
        throw "Missing required env var: $key"
    }
}


$bundleRoot = Join-Path $repoRoot "RFID-Marathon-Automation"
$bundleDir = Join-Path $bundleRoot "database-setup"
$scriptDir = (Resolve-Path -LiteralPath $PSScriptRoot).Path
$scriptLeaf = Split-Path -Leaf $scriptDir

if ($scriptLeaf -ne "database-setup") {
    if (-not (Test-Path -LiteralPath $bundleRoot)) {
        New-Item -ItemType Directory -Path $bundleRoot -Force | Out-Null
    }
    New-Item -ItemType Directory -Path $bundleDir -Force | Out-Null
    Copy-Item -LiteralPath $envPath -Destination (Join-Path $bundleDir ".env") -Force

    $initSqlPath = Join-Path $PSScriptRoot "init.sql"
    if (Test-Path -LiteralPath $initSqlPath) {
        Copy-Item -LiteralPath $initSqlPath -Destination (Join-Path $bundleDir "init.sql") -Force
    }
    Copy-Item -LiteralPath $PSCommandPath -Destination (Join-Path $bundleDir "build_database.ps1") -Force

    $targetBinDir = Join-Path $bundleDir "postgres\bin"
    if (-not (Test-Path -LiteralPath (Join-Path $targetBinDir "postgres.exe"))) {
        if (-not [string]::IsNullOrWhiteSpace($sourceBinDir) -and (Test-Path -LiteralPath $sourceBinDir)) {
            $sourcePathItem = Get-Item -LiteralPath $sourceBinDir
            if (-not $sourcePathItem.PSIsContainer) {
                $sourceBinDir = $sourcePathItem.DirectoryName
            }
            if (Test-Path -LiteralPath (Join-Path $sourceBinDir "postgres.exe")) {
                $sourceRoot = Split-Path -Parent $sourceBinDir
                $sourceBinDir = $sourceBinDir
            } elseif (Test-Path -LiteralPath (Join-Path $sourceBinDir "bin\postgres.exe")) {
                $sourceRoot = $sourceBinDir
                $sourceBinDir = Join-Path $sourceRoot "bin"
            } else {
                throw "postgres.exe not found under DB_SOURCE_BIN_DIR: $sourceBinDir"
            }
            if (-not (Test-Path -LiteralPath (Join-Path $sourceRoot "share\postgres.bki"))) {
                Write-Host "postgres.bki not found under share; using bin parent may be incorrect." -ForegroundColor Yellow
            }
            Write-Host "Copying PostgreSQL files from: $sourceRoot"
                        Write-Host "[debug] Copy start: $(Get-Date -Format o)"
            New-Item -ItemType Directory -Path $targetBinDir -Force | Out-Null
            Copy-Item -Path (Join-Path $sourceBinDir "*") -Destination $targetBinDir -Recurse -Force
                        Write-Host "[debug] Copy finished: $(Get-Date -Format o)"
            $targetRoot = Split-Path -Parent $targetBinDir
            $targetShareDir = Join-Path $targetRoot "share"
            $targetLibDir = Join-Path $targetRoot "lib"
            if (Test-Path -LiteralPath (Join-Path $sourceRoot "share")) {
                New-Item -ItemType Directory -Path $targetShareDir -Force | Out-Null
                Copy-Item -Path (Join-Path $sourceRoot "share\*") -Destination $targetShareDir -Recurse -Force -Container
            }
            if (Test-Path -LiteralPath (Join-Path $sourceRoot "lib")) {
                New-Item -ItemType Directory -Path $targetLibDir -Force | Out-Null
                Copy-Item -Path (Join-Path $sourceRoot "lib\*") -Destination $targetLibDir -Recurse -Force -Container
            }
            $copied = Get-ChildItem -LiteralPath $targetBinDir -File -ErrorAction SilentlyContinue
            if (-not $copied -or $copied.Count -eq 0) {
                throw "Copy completed but no files found in target bin: $targetBinDir"
            }
            if (-not (Test-Path -LiteralPath (Join-Path $targetShareDir "postgres.bki"))) {
                throw "postgres.bki not found after copy. Ensure share folder is included."
            }
            Write-Host "Copied $($copied.Count) files into: $targetBinDir"
        } else {
            throw "PostgreSQL binaries not found for bundling. Set DB_SOURCE_BIN_DIR in database\.env to your Postgres bin folder."
        }
    }

    Write-Host "Database setup bundle prepared at: $bundleDir"
    Write-Host "Run build_database.ps1 from the bundle on the target system."
    return
}

$initdbExe = Join-Path $binDir "initdb.exe"
$pgCtlExe = Join-Path $binDir "pg_ctl.exe"
$postgresExe = Join-Path $binDir "postgres.exe"
$pgIsReadyExe = Join-Path $binDir "pg_isready.exe"
$shareDir = Join-Path (Split-Path -Parent $binDir) "share"

if (-not (Test-Path -LiteralPath $initdbExe)) {
    throw "PostgreSQL binaries not found. Expected: $initdbExe"
}
if (-not (Test-Path -LiteralPath $pgCtlExe)) {
    throw "PostgreSQL binaries not found. Expected: $pgCtlExe"
}
if (-not (Test-Path -LiteralPath $postgresExe)) {
    throw "PostgreSQL binaries not found. Expected: $postgresExe"
}

if (-not (Test-Path -LiteralPath $dataDir)) {
    New-Item -ItemType Directory -Path $dataDir | Out-Null

    $pwFile = Join-Path $env:TEMP ("pg_pw_" + [System.Guid]::NewGuid().ToString("N") + ".txt")
    Set-Content -LiteralPath $pwFile -Value $adminPassword -Encoding ASCII

    try {
        Write-Host "[debug] Running initdb at $(Get-Date -Format o) - dataDir=$dataDir shareDir=$shareDir"
        if (Test-Path -LiteralPath (Join-Path $shareDir "postgres.bki")) {
            & $initdbExe -D $dataDir -U $adminUser -A password --pwfile $pwFile -L $shareDir | Out-Null
        } else {
            & $initdbExe -D $dataDir -U $adminUser -A password --pwfile $pwFile | Out-Null
        }
        Write-Host "[debug] initdb completed with exit code $LASTEXITCODE at $(Get-Date -Format o)"
    } finally {
        Remove-Item -LiteralPath $pwFile -Force -ErrorAction SilentlyContinue
    }
}

& $pgCtlExe -D $dataDir -o "-p $port" -l (Join-Path $PSScriptRoot "postgres.log") status | Out-Null
$wasRunning = ($LASTEXITCODE -eq 0)
if ($wasRunning) {
    & $pgCtlExe -D $dataDir -m fast stop | Out-Null
}

$initSqlPath = Join-Path $PSScriptRoot "init.sql"
if (-not (Test-Path -LiteralPath $initSqlPath)) {
    throw "init.sql not found: $initSqlPath"
}

$sqlRaw = Get-Content -LiteralPath $initSqlPath -Raw
$sqlRaw = $sqlRaw.Replace("__APP_USER__", $appUser)
$sqlRaw = $sqlRaw.Replace("__APP_PASSWORD__", $appPassword)
$sqlRaw = $sqlRaw.Replace("__APP_DB__", $appDb)

$statements = $sqlRaw -split ";" | ForEach-Object { $_.Trim() } | Where-Object { $_ }
foreach ($stmt in $statements) {
    $sqlLine = $stmt + ";"
    try {
        Write-Host "[debug] Executing SQL at $(Get-Date -Format o): $sqlLine"
        $sqlLine | & $postgresExe --single -D $dataDir postgres | Out-Null
        Write-Host "[debug] SQL exit code: $LASTEXITCODE at $(Get-Date -Format o)"
        if ($LASTEXITCODE -ne 0) {
            Write-Host "SQL returned exit code $LASTEXITCODE`: $sqlLine" -ForegroundColor Yellow
        }
    } catch {
        Write-Host "SQL execution failed: $sqlLine" -ForegroundColor Yellow
        Write-Host "[debug] Exception: $_ at $(Get-Date -Format o)"
    }
}

& $pgCtlExe -D $dataDir -o "-p $port" -l (Join-Path $PSScriptRoot "postgres.log") start | Out-Null
Write-Host "[debug] pg_ctl start returned $LASTEXITCODE at $(Get-Date -Format o)"

if (Test-Path -LiteralPath $pgIsReadyExe) {
    $ready = $false
    for ($i = 0; $i -lt 30; $i++) {
        Write-Host "[debug] pg_isready attempt $i at $(Get-Date -Format o)"
        & $pgIsReadyExe -h $hostName -p $port | Out-Null
        Write-Host "[debug] pg_isready exit $LASTEXITCODE at $(Get-Date -Format o)"
        if ($LASTEXITCODE -eq 0) {
            $ready = $true
            break
        }
        Start-Sleep -Seconds 1
    }
    if (-not $ready) {
        Write-Host "[debug] pg_isready timed out at $(Get-Date -Format o)" -ForegroundColor Yellow
        throw "PostgreSQL did not become ready in time."
    }
}

Write-Host "Local PostgreSQL is ready."
Write-Host "Host: $hostName Port: $port Database: $appDb User: $appUser"
Write-Host "[debug] build_database.ps1 finished at $(Get-Date -Format o)"
