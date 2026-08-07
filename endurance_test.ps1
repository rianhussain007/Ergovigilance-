# Endurance Test Script - 30 minutes, snapshots every 5 minutes
# Collects: FPS, RAM, CPU, alerts, history, errors

$sessionFile = "C:\GGS_intership\posture_analysis\endurance_results.json"
$results = @()
$startTime = Get-Date
$backendPid = (Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue).OwningProcess | Select-Object -First 1

Write-Host "============================================"
Write-Host "30-MINUTE ENDURANCE TEST"
Write-Host "Started: $($startTime.ToString('HH:mm:ss'))"
Write-Host "Backend PID: $backendPid"
Write-Host "============================================"
Write-Host ""

for ($minute = 5; $minute -le 30; $minute += 5) {
    # Wait until the target minute
    $targetTime = $startTime.AddMinutes($minute)
    $waitSeconds = [Math]::Max(0, ($targetTime - (Get-Date)).TotalSeconds)
    if ($waitSeconds -gt 0) {
        Write-Host "Waiting $([Math]::Round($waitSeconds))s until minute $minute..."
        Start-Sleep -Seconds $waitSeconds
    }

    $timestamp = Get-Date -Format "HH:mm:ss"
    Write-Host ""
    Write-Host "--- Snapshot at minute $minute ($timestamp) ---"

    # 1. Get session status (includes FPS)
    $status = $null
    try {
        $status = Invoke-RestMethod -Uri "http://127.0.0.1:8000/api/session/status" -Method GET -TimeoutSec 5
    } catch {
        Write-Host "ERROR getting session status: $_"
    }

    # 2. Get backend process RAM and CPU
    $ramMB = "N/A"
    $cpuPct = "N/A"
    if ($backendPid) {
        try {
            $proc = Get-Process -Id $backendPid -ErrorAction SilentlyContinue
            if ($proc) {
                $ramMB = [Math]::Round($proc.WorkingSet64 / 1MB, 1)
                $cpuPct = [Math]::Round($proc.CPU, 1)
            }
        } catch {
            # Fallback: use tasklist
            try {
                $taskInfo = tasklist /FI "PID eq $backendPid" /FO CSV /NH 2>$null
                if ($taskInfo) {
                    $parts = $taskInfo -split ","
                    $ramStr = ($parts[4] -replace '"', '') -replace ' K', '' -replace ',', ''
                    if ($ramStr -match '^\d+$') {
                        $ramMB = [Math]::Round([int]$ramStr / 1024, 1)
                    }
                }
            } catch {}
        }
    }

    # 3. Get alerts count
    $alertsCount = "N/A"
    try {
        $alerts = Invoke-RestMethod -Uri "http://127.0.0.1:8000/api/alerts" -Method GET -TimeoutSec 5
        if ($alerts -is [array]) {
            $alertsCount = $alerts.Count
        } elseif ($alerts.history) {
            $alertsCount = $alerts.summary.total_fired
        } else {
            $alertsCount = 0
        }
    } catch {
        Write-Host "ERROR getting alerts: $_"
    }

    # 4. Get history points count
    $historyCount = "N/A"
    try {
        $history = Invoke-RestMethod -Uri "http://127.0.0.1:8000/api/history" -Method GET -TimeoutSec 5
        if ($history -is [array]) {
            $historyCount = $history.Count
        } elseif ($history.points) {
            $historyCount = $history.points.Count
        } elseif ($history.history) {
            $historyCount = $history.history.Count
        } else {
            $historyCount = 0
        }
    } catch {
        Write-Host "ERROR getting history: $_"
    }

    # 5. Get current frame count from status
    $frameCount = "N/A"
    if ($status -and $status.current_frame) {
        $frameCount = $status.current_frame
    }

    # Print snapshot
    $fps = if ($status) { $status.fps } else { "N/A" }
    $riskLevel = if ($status) { $status.risk_level } else { "N/A" }
    $active = if ($status) { $status.active } else { "N/A" }

    Write-Host "  FPS: $fps"
    Write-Host "  RAM: $ramMB MB"
    Write-Host "  CPU: $cpuPct"
    Write-Host "  Alerts fired: $alertsCount"
    Write-Host "  History points: $historyCount"
    Write-Host "  Frame count: $frameCount"
    Write-Host "  Risk level: $riskLevel"
    Write-Host "  Active: $active"

    # Store result
    $results += @{
        minute = $minute
        timestamp = $timestamp
        fps = "$fps"
        ram_mb = "$ramMB"
        cpu = "$cpuPct"
        alerts = "$alertsCount"
        history = "$historyCount"
        frames = "$frameCount"
        risk = "$riskLevel"
        active = "$active"
    }
}

Write-Host ""
Write-Host "============================================"
Write-Host "30 MINUTES COMPLETE - Stopping session"
Write-Host "============================================"

# Stop session
try {
    $stopResult = Invoke-RestMethod -Uri "http://127.0.0.1:8000/api/session/stop" -Method POST -TimeoutSec 10
    Write-Host "Session stopped: $($stopResult | ConvertTo-Json -Compress)"
} catch {
    Write-Host "ERROR stopping session: $_"
}

Start-Sleep -Seconds 3

# Check if session file was saved
$sessionFiles = Get-ChildItem "C:\GGS_intership\posture_analysis\outputs\sessions\*.json" | Sort-Object LastWriteTime -Descending
$latestFile = $sessionFiles | Select-Object -First 1
Write-Host ""
Write-Host "Latest session file: $($latestFile.Name)"
Write-Host "File size: $($latestFile.Length) bytes"
Write-Host "Last modified: $($latestFile.LastWriteTime)"

# Read the file to check total_frames
if ($latestFile) {
    $sessionData = Get-Content $latestFile.FullName -Raw | ConvertFrom-Json
    Write-Host "total_frames in saved file: $($sessionData.total_frames)"
    Write-Host "session_duration_seconds: $($sessionData.session_duration_seconds)"
}

# Save results
$results | ConvertTo-Json -Depth 5 | Set-Content $sessionFile
Write-Host ""
Write-Host "Results saved to: $sessionFile"
Write-Host ""
Write-Host "=== RESULTS TABLE ==="
$results | ForEach-Object {
    Write-Host "Minute $($_.minute): FPS=$($_.fps) RAM=$($_.ram_mb)MB CPU=$($_.cpu) Alerts=$($_.alerts) History=$($_.history) Frames=$($_.frames) Risk=$($_.risk)"
}
