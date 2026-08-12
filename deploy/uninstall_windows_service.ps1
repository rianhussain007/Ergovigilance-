# ErgoVigilance — Windows Service Uninstaller
# Run from an elevated PowerShell:
#   powershell -ExecutionPolicy Bypass -File deploy\uninstall_windows_service.ps1

$ErrorActionPreference = "Stop"
$script:ServiceName = "ErgoVigilance"

$identity = [Security.Principal.WindowsIdentity]::GetCurrent()
$principal = New-Object Security.Principal.WindowsPrincipal($identity)
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    Write-Host "ERROR: Run from an elevated (Administrator) PowerShell." -ForegroundColor Red
    exit 1
}

$nssmCandidates = @(
    (Join-Path $PSScriptRoot "tools\nssm-2.24\win64\nssm.exe")
)
$nssm = $nssmCandidates | Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $nssm) {
    # Fall back to sc.exe if NSSM is gone
    sc.exe stop $script:ServiceName 2>$null | Out-Null
    sc.exe delete $script:ServiceName 2>$null | Out-Null
    Write-Host "Service removed via sc.exe (NSSM binary not found)." -ForegroundColor Green
    exit 0
}

& $nssm stop $script:ServiceName 2>$null | Out-Null
& $nssm remove $script:ServiceName confirm
if ($LASTEXITCODE -eq 0) {
    Write-Host "ErgoVigilance service removed." -ForegroundColor Green
} else {
    Write-Host "Removal may have partially failed (exit $LASTEXITCODE). Check services.msc." -ForegroundColor Yellow
}
