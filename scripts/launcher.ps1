# BESS Optimizer System Launcher (PowerShell)
param (
    [string]$Action = "start"
)

$RootDir = Split-Path -Parent $PSScriptRoot
$LogsDir = Join-Path $RootDir "logs"
if (-not (Test-Path $LogsDir)) { New-Item -ItemType Directory -Path $LogsDir -Force | Out-Null }

$MlPidFile = Join-Path $LogsDir "ml_service.pid"
$BackendPidFile = Join-Path $LogsDir "backend.pid"
$FrontendPidFile = Join-Path $LogsDir "frontend.pid"

function Stop-AppProcesses {
    Write-Host 'Stopping all application background services...' -ForegroundColor Cyan
    $pidFiles = @($FrontendPidFile, $BackendPidFile, $MlPidFile)
    foreach ($file in $pidFiles) {
        if (Test-Path $file) {
            $p = Get-Content $file -ErrorAction SilentlyContinue
            if ($p) {
                Write-Host "Stopping process PID $p..." -ForegroundColor Gray
                Stop-Process -Id $p -Force -ErrorAction SilentlyContinue
            }
            Remove-Item $file -Force -ErrorAction SilentlyContinue
        }
    }
    Write-Host 'All registered application processes stopped.' -ForegroundColor Green
}

function Test-PortListening ($port) {
    try {
        return (Test-NetConnection -Port $port -ComputerName 127.0.0.1 -WarningAction SilentlyContinue -InformationLevel Quiet)
    } catch {
        return $false
    }
}

if ($Action -eq "stop") {
    Stop-AppProcesses
    exit 0
}

if ($Action -eq "status") {
    Write-Host '=== BESS Optimizer Service Status ===' -ForegroundColor Cyan
    $ports = @(
        @{ Name = "Frontend UI"; Port = 3230 },
        @{ Name = "Rust Core API"; Port = 8230 },
        @{ Name = "ML Engine (Python)"; Port = 8231 }
    )
    foreach ($item in $ports) {
        $listening = Test-PortListening $item.Port
        $status = if ($listening) { "RUNNING / ACTIVE" } else { "DOWN / NOT LISTENING" }
        $color = if ($listening) { "Green" } else { "Yellow" }
        Write-Host "$($item.Name) (Port $($item.Port)): $status" -ForegroundColor $color
    }
    exit 0
}

Write-Host '==========================================================' -ForegroundColor Cyan
Write-Host '  AI ALGORITHMIC TRADING AND BESS ARBITRAGE OPTIMIZER      ' -ForegroundColor Cyan
Write-Host '==========================================================' -ForegroundColor Cyan

# 1. Prerequisite verification
Write-Host '[1/5] Checking prerequisites...' -ForegroundColor White
$hasRust = Get-Command cargo -ErrorAction SilentlyContinue
$hasNode = Get-Command node -ErrorAction SilentlyContinue
$hasPython = Get-Command python -ErrorAction SilentlyContinue

if (-not $hasRust -or -not $hasNode -or -not $hasPython) {
    Write-Host 'Error: Missing required tools (Cargo, Node, or Python).' -ForegroundColor Red
    exit 1
}
Write-Host '  [OK] Rust/Cargo, Node.js, and Python detected.' -ForegroundColor Green

# 2. Port conflict check
Write-Host '[2/5] Checking target ports (8231, 8230, 3230)...' -ForegroundColor White
foreach ($p in 8231, 8230, 3230) {
    if (Test-PortListening $p) {
        Write-Host "Warning: Port $p is currently in use. Attempting to clean up previous instances..." -ForegroundColor Yellow
        Stop-AppProcesses
        Start-Sleep -Seconds 1
        break
    }
}

# 3. Start Python ML Service (Port 8231)
Write-Host '[3/5] Starting Python ML Service (XGBoost and PyTorch PPO) on port 8231...' -ForegroundColor White
$mlDir = Join-Path $RootDir "ml_service"
$mlPsi = New-Object System.Diagnostics.ProcessStartInfo
$mlPsi.FileName = "python"
$mlPsi.Arguments = "-m uvicorn service:app --host 127.0.0.1 --port 8231"
$mlPsi.WorkingDirectory = $mlDir
$mlPsi.UseShellExecute = $true
$mlPsi.WindowStyle = [System.Diagnostics.ProcessWindowStyle]::Minimized
$mlProcess = [System.Diagnostics.Process]::Start($mlPsi)
$mlProcess.Id | Out-File $MlPidFile -Encoding ASCII
Write-Host "  [OK] ML Service started (PID: $($mlProcess.Id))." -ForegroundColor Green

# 4. Start Rust Control Plane (Port 8230)
Write-Host '[4/5] Starting Rust Control Plane API on port 8230...' -ForegroundColor White
$backendDir = Join-Path $RootDir "backend"
$backendPsi = New-Object System.Diagnostics.ProcessStartInfo
$backendPsi.FileName = "cargo"
$backendPsi.Arguments = "run"
$backendPsi.WorkingDirectory = $backendDir
$backendPsi.UseShellExecute = $true
$backendPsi.WindowStyle = [System.Diagnostics.ProcessWindowStyle]::Minimized
$backendProcess = [System.Diagnostics.Process]::Start($backendPsi)
$backendProcess.Id | Out-File $BackendPidFile -Encoding ASCII
Write-Host "  [OK] Rust API starting (PID: $($backendProcess.Id))." -ForegroundColor Green

# 5. Start Frontend Dev Server (Port 3230)
Write-Host '[5/5] Starting Frontend Dev Terminal on port 3230...' -ForegroundColor White
$frontendDir = Join-Path $RootDir "frontend"
$frontendPsi = New-Object System.Diagnostics.ProcessStartInfo
$frontendPsi.FileName = "node"
$frontendPsi.Arguments = "./node_modules/vite/bin/vite.js --port 3230"
$frontendPsi.WorkingDirectory = $frontendDir
$frontendPsi.UseShellExecute = $true
$frontendPsi.WindowStyle = [System.Diagnostics.ProcessWindowStyle]::Minimized
$frontendProcess = [System.Diagnostics.Process]::Start($frontendPsi)
$frontendProcess.Id | Out-File $FrontendPidFile -Encoding ASCII
Write-Host "  [OK] Frontend UI starting (PID: $($frontendProcess.Id))." -ForegroundColor Green

# Wait and Probe Health Checks
Write-Host ''
Write-Host 'Waiting for service readiness...' -ForegroundColor White
$ready = $false
for ($i = 0; $i -lt 30; $i++) {
    Start-Sleep -Seconds 2
    try {
        $resp = Invoke-RestMethod -Uri "http://127.0.0.1:8230/api/health" -TimeoutSec 2 -ErrorAction SilentlyContinue
        if ($resp -and $resp.status -eq "healthy") {
            $ready = $true
            break
        }
    } catch {}
    Write-Host -NoNewline '.'
}

Write-Host ''
if ($ready) {
    Write-Host ''
    Write-Host '==========================================================' -ForegroundColor Green
    Write-Host '  ALL SERVICES SUCCESSFULLY LAUNCHED AND READY!          ' -ForegroundColor Green
    Write-Host '==========================================================' -ForegroundColor Green
    Write-Host '  Frontend Trading Terminal : http://localhost:3230' -ForegroundColor Cyan
    Write-Host '  Rust Control Plane API    : http://localhost:8230/api/health' -ForegroundColor Cyan
    Write-Host '  Python ML Engine (XGB/PPO): http://localhost:8231/health' -ForegroundColor Cyan
    Write-Host '==========================================================' -ForegroundColor Green
    Write-Host 'To view status : run .\status.bat' -ForegroundColor Gray
    Write-Host 'To stop cleanly: run .\stop.bat' -ForegroundColor Gray
} else {
    Write-Host 'Services are launching. Check http://localhost:3230 in your browser.' -ForegroundColor Yellow
}
