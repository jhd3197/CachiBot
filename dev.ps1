# Start CachiBot backend + frontend for development.
# Usage: .\dev.ps1
#
# Prerequisites:
#   pip install -e .          (backend in dev mode)
#   cd frontend; npm install  (frontend deps)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path

# Start backend
Write-Host "[dev] Starting backend on " -ForegroundColor Cyan -NoNewline
Write-Host "http://127.0.0.1:6392" -ForegroundColor Green
$backend = Start-Process -NoNewWindow -PassThru -FilePath "cachibot" -ArgumentList "server","--port","6392","--reload"

# Start frontend
Write-Host "[dev] Starting frontend on " -ForegroundColor Cyan -NoNewline
Write-Host "http://localhost:5173" -ForegroundColor Green
$frontend = Start-Process -NoNewWindow -PassThru -FilePath "npm" -ArgumentList "run","dev" -WorkingDirectory "$Root\frontend"

Write-Host ""
Write-Host "[dev] Both servers running. Press Ctrl+C to stop." -ForegroundColor Cyan
Write-Host ""

try {
    # Wait for either to exit
    while (!$backend.HasExited -and !$frontend.HasExited) {
        Start-Sleep -Milliseconds 500
    }
} finally {
    Write-Host "[dev] Shutting down..." -ForegroundColor Cyan
    if (!$backend.HasExited) { Stop-Process -Id $backend.Id -Force -ErrorAction SilentlyContinue }
    if (!$frontend.HasExited) { Stop-Process -Id $frontend.Id -Force -ErrorAction SilentlyContinue }
    Write-Host "[dev] Done." -ForegroundColor Green
}
