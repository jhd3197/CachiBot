# CachiBot dev launcher.
#
# Usage:
#   .\dev.ps1                  # backend + frontend in browser (default)
#   .\dev.ps1 backend          # backend only
#   .\dev.ps1 frontend         # frontend only (Vite dev server)
#   .\dev.ps1 desktop          # backend + frontend + Electron
#   .\dev.ps1 all              # backend + frontend + browser + Electron

param(
    [ValidateSet("browser", "backend", "frontend", "desktop", "all")]
    [string]$Mode = "browser"
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$procs = @()

$startBackend = $Mode -in "backend", "browser", "desktop", "all"
$startFrontend = $Mode -in "frontend", "browser", "desktop", "all"

# --- Kill stale processes on required ports ---
$ports = @()
if ($startBackend)  { $ports += 6392 }
if ($startFrontend) { $ports += 5173 }

foreach ($port in $ports) {
    $lines = netstat -ano | Select-String ":$port\s.*LISTENING"
    foreach ($line in $lines) {
        if ($line -match '\s(\d+)\s*$') {
            $stalePid = $Matches[1]
            Write-Host "[dev] Killing stale process on port $port (PID $stalePid)" -ForegroundColor Yellow
            Stop-Process -Id $stalePid -Force -ErrorAction SilentlyContinue
        }
    }
}
$startElectron = $Mode -in "desktop", "all"

# --- Backend ---
if ($startBackend) {
    Write-Host "[dev] backend  -> " -ForegroundColor Cyan -NoNewline
    Write-Host "http://127.0.0.1:6392" -ForegroundColor Green
    $procs += Start-Process -NoNewWindow -PassThru -FilePath "cachibot" `
        -ArgumentList "server","--port","6392","--reload"
}

# --- Frontend (Vite) ---
if ($startFrontend) {
    Write-Host "[dev] frontend -> " -ForegroundColor Cyan -NoNewline
    Write-Host "http://localhost:5173" -ForegroundColor Green
    $procs += Start-Process -NoNewWindow -PassThru -FilePath "npm" `
        -ArgumentList "run","dev" -WorkingDirectory "$Root\frontend"
}

# --- Electron ---
if ($startElectron) {
    Start-Sleep -Seconds 3
    $env:ELECTRON_DEV_URL = "http://localhost:5173"
    Write-Host "[dev] electron -> " -ForegroundColor Cyan -NoNewline
    Write-Host "loading from Vite" -ForegroundColor Green
    $procs += Start-Process -NoNewWindow -PassThru `
        -FilePath "$Root\desktop\node_modules\.bin\electron.cmd" `
        -ArgumentList "$Root\desktop" -WorkingDirectory "$Root\desktop"
}

Write-Host "[dev] Running ($Mode). Press Ctrl+C to stop." -ForegroundColor DarkGray
Write-Host ""

try {
    while ($true) {
        foreach ($p in $procs) {
            if ($p.HasExited) { throw "exit" }
        }
        Start-Sleep -Milliseconds 500
    }
} catch {} finally {
    Write-Host ""
    Write-Host "[dev] Shutting down..." -ForegroundColor Cyan
    foreach ($p in $procs) {
        if (-not $p.HasExited) { Stop-Process -Id $p.Id -Force -ErrorAction SilentlyContinue }
    }
    Remove-Item Env:\ELECTRON_DEV_URL -ErrorAction SilentlyContinue
    Write-Host "[dev] Done." -ForegroundColor Green
}
