# ErgoVigilance — Windows Service Installer
# ===========================================
# Registers the FastAPI backend as a Windows service so a pilot site can run
# the system without a terminal open, surviving reboots and crashing processes.
#
# Requirements:
#   - Run from an elevated (Administrator) PowerShell:
#       powershell -ExecutionPolicy Bypass -File deploy\install_windows_service.ps1
#   - The venv must already exist (project venv/ is the default).
#
# What it does:
#   1. Locates the venv Python + project root.
#   2. Downloads NSSM (Non-Sucking Service Manager) to deploy\tools\ if missing.
#   3. Installs service "ErgoVigilance" running uvicorn (app.main:app).
#   4. Loads backend_api\.env into the service environment (AUTH_JWT_SECRET etc).
#   5. Writes stdout/stderr to deploy\logs\.
#   6. Configures auto-restart on crash (5s delay) + starts the service.

$ErrorActionPreference = "Stop"
$script:ProjectRoot = Split-Path -Parent $PSScriptRoot
$script:BackendDir = Join-Path $script:ProjectRoot "backend_api"
$script:ServiceName = "ErgoVigilance"

# ── 0. Admin check ──────────────────────────────────────────────────────────
$identity = [Security.Principal.WindowsIdentity]::GetCurrent()
$principal = New-Object Security.Principal.WindowsPrincipal($identity)
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    Write-Host "ERROR: Run this script from an elevated (Administrator) PowerShell." -ForegroundColor Red
    exit 1
}

# ── 1. Locate Python + project paths ────────────────────────────────────────
$pythonCandidates = @(
    (Join-Path $script:ProjectRoot "venv\Scripts\python.exe"),
    (Join-Path $script:BackendDir "venv\Scripts\python.exe")
)
$python = $pythonCandidates | Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $python) {
    Write-Host "ERROR: venv python.exe not found. Create it first:" -ForegroundColor Red
    Write-Host "  python -m venv venv"
    Write-Host "  venv\Scripts\pip install -r backend_api\requirements.txt"
    Write-Host "  venv\Scripts\python -m playwright install chromium"
    exit 1
}
Write-Host "Python: $python"
Write-Host "Backend dir: $script:BackendDir"

# ── 2. NSSM (download if missing) ───────────────────────────────────────────
$toolsDir = Join-Path $PSScriptRoot "tools"
$nssmDir  = Join-Path $toolsDir "nssm-2.24"
$nssmExe  = Join-Path $nssmDir "win64\nssm.exe"
if (-not (Test-Path $nssmExe)) {
    Write-Host "Downloading NSSM 2.24 (Non-Sucking Service Manager)..."
    New-Item -ItemType Directory -Force -Path $toolsDir | Out-Null
    $zip = Join-Path $toolsDir "nssm.zip"
    [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
    Invoke-WebRequest -Uri "https://nssm.cc/release/nssm-2.24.zip" -OutFile $zip
    Expand-Archive -Path $zip -DestinationPath $toolsDir -Force
    Remove-Item $zip -Force
}
if (-not (Test-Path $nssmExe)) {
    Write-Host "ERROR: NSSM extraction failed. Manually place nssm.exe at $nssmExe" -ForegroundColor Red
    exit 1
}
Write-Host "NSSM: $nssmExe"

# ── 3. Stop + remove any existing instance ──────────────────────────────────
& $nssmExe stop $script:ServiceName 2>$null | Out-Null
& $nssmExe remove $script:ServiceName confirm 2>$null | Out-Null
Start-Sleep -Milliseconds 500

# ── 4. Install the service ──────────────────────────────────────────────────
$logDir = Join-Path $PSScriptRoot "logs"
New-Item -ItemType Directory -Force -Path $logDir | Out-Null

& $nssmExe install $script:ServiceName $python "-m" "uvicorn" "app.main:app" "--host" "0.0.0.0" "--port" "8000"
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: nssm install failed (exit $LASTEXITCODE)." -ForegroundColor Red
    exit 1
}

& $nssmExe set $script:ServiceName AppDirectory $script:BackendDir
& $nssmExe set $script:ServiceName DisplayName "ErgoVigilance — AI Ergonomics Monitoring"
& $nssmExe set $script:ServiceName Description "Real-time posture risk monitoring API (camera -> pose -> risk -> alerts -> reports). Runs fully on-prem; video never leaves the building."
& $nssmExe set $script:ServiceName Start SERVICE_AUTO_START
& $nssmExe set $script:ServiceName AppStdout (Join-Path $logDir "service-stdout.log")
& $nssmExe set $script:ServiceName AppStderr (Join-Path $logDir "service-stderr.log")
& $nssmExe set $script:ServiceName AppRotateFiles 1
& $nssmExe set $script:ServiceName AppRotateBytes 10485760   # 10 MB per log file
& $nssmExe set $script:ServiceName AppExit Default Restart
& $nssmExe set $script:ServiceName AppRestartDelay 5000       # 5s between restarts

# ── 5. Load .env into the service environment ───────────────────────────────
$envFile = Join-Path $script:BackendDir ".env"
if (Test-Path $envFile) {
    Write-Host "Loading environment from $envFile"
    Get-Content $envFile | ForEach-Object {
        $line = $_.Trim()
        if ($line -and -not $line.StartsWith("#") -and $line.Contains("=")) {
            $idx = $line.IndexOf("=")
            $key = $line.Substring(0, $idx).Trim()
            $val = $line.Substring($idx + 1).Trim()
            # Strip surrounding quotes if present
            if ($val.Length -ge 2 -and (($val.StartsWith('"') -and $val.EndsWith('"')) -or ($val.StartsWith("'") -and $val.EndsWith("'")))) {
                $val = $val.Substring(1, $val.Length - 2)
            }
            if ($key -match '^[A-Za-z_][A-Za-z0-9_]*$') {
                & $nssmExe set $script:ServiceName AppEnvironmentExtra ("{0}={1}" -f $key, $val) | Out-Null
            }
        }
    }
} else {
    Write-Host "WARNING: backend_api\.env not found — service will use defaults (DEV mode)." -ForegroundColor Yellow
}

# ── 6. Start it ─────────────────────────────────────────────────────────────
& $nssmExe start $script:ServiceName
if ($LASTEXITCODE -eq 0) {
    Write-Host ""
    Write-Host "ErgoVigilance service installed and started." -ForegroundColor Green
    Write-Host "  Service:    $script:ServiceName"
    Write-Host "  API:        http://localhost:8000  (or http://<this-machine-ip>:8000 from the LAN)"
    Write-Host "  Logs:       $logDir"
    Write-Host "  Manage:     services.msc  ->  ErgoVigilance"
    Write-Host "  Uninstall:  powershell -ExecutionPolicy Bypass -File deploy\uninstall_windows_service.ps1"
} else {
    Write-Host "Service installed but failed to start. Check $logDir\service-stderr.log" -ForegroundColor Yellow
    exit 1
}
