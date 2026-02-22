# CachiBot dev launcher.
#
# Usage:
#   .\dev.ps1                  # backend + frontend in browser (default)
#   .\dev.ps1 backend          # backend only
#   .\dev.ps1 frontend         # frontend only (Vite dev server)
#   .\dev.ps1 desktop          # backend + frontend + Electron
#   .\dev.ps1 all              # backend + frontend + browser + Electron
#   .\dev.ps1 watch-lint       # watch Python + TS files and lint on changes

param(
    [ValidateSet("browser", "backend", "frontend", "desktop", "all", "watch-lint")]
    [string]$Mode = "browser"
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$procs = @()

# --- watch-lint mode ---
if ($Mode -eq "watch-lint") {
    $pyPath = "$Root\src\cachibot"
    $tsPath = "$Root\frontend\src"
    Write-Host "[dev] Watching for lint + type + test errors (Python + TypeScript)" -ForegroundColor Cyan
    Write-Host "[dev]   Python  : $pyPath" -ForegroundColor DarkGray
    Write-Host "[dev]   Frontend: $tsPath" -ForegroundColor DarkGray
    Write-Host "[dev] Press Ctrl+C to stop." -ForegroundColor DarkGray
    Write-Host ""

    function Invoke-AllLint {
        $ts = Get-Date -Format "HH:mm:ss"
        Write-Host "[$ts] " -ForegroundColor DarkGray -NoNewline
        Write-Host "Running linters..." -ForegroundColor Cyan
        Write-Host ""

        # --- Python: ruff check ---
        Write-Host "  ruff check      " -ForegroundColor Cyan -NoNewline
        $out = & ruff check $pyPath 2>&1
        if ($LASTEXITCODE -eq 0) {
            Write-Host "ok" -ForegroundColor Green
        } else {
            Write-Host "fail" -ForegroundColor Red
            $out | ForEach-Object { Write-Host "    $_" -ForegroundColor DarkGray }
        }

        # --- Python: ruff format (auto-fix) ---
        Write-Host "  ruff format     " -ForegroundColor Cyan -NoNewline
        $out = & ruff format --check $pyPath 2>&1
        if ($LASTEXITCODE -eq 0) {
            Write-Host "ok" -ForegroundColor Green
        } else {
            & ruff format $pyPath 2>&1 | Out-Null
            $fixed = ($out | Select-String "^Would reformat:").Count
            Write-Host "fixed $fixed files" -ForegroundColor Yellow
        }

        # --- Python: mypy type check ---
        Write-Host "  mypy            " -ForegroundColor Cyan -NoNewline
        $out = & mypy $pyPath 2>&1
        if ($LASTEXITCODE -eq 0) {
            Write-Host "ok" -ForegroundColor Green
        } else {
            $errCount = ($out | Select-String "^Found \d+ error").Count
            if ($errCount -gt 0) {
                $summary = ($out | Select-String "^Found \d+ error").Line
                Write-Host "fail ($summary)" -ForegroundColor Red
            } else {
                Write-Host "fail" -ForegroundColor Red
            }
            $out | Where-Object { $_ -match "error:" } | ForEach-Object { Write-Host "    $_" -ForegroundColor DarkGray }
        }

        # --- Frontend: ESLint ---
        Write-Host "  eslint          " -ForegroundColor Cyan -NoNewline
        Push-Location "$Root\frontend"
        $out = & npm run lint 2>&1
        $exitCode = $LASTEXITCODE
        Pop-Location
        if ($exitCode -eq 0) {
            $warnCount = ($out | Select-String "warning").Count
            if ($warnCount -gt 0) {
                Write-Host "ok ($warnCount warnings)" -ForegroundColor Yellow
            } else {
                Write-Host "ok" -ForegroundColor Green
            }
        } else {
            Write-Host "fail" -ForegroundColor Red
            $out | Where-Object { $_ -match "(error|warning)" } | ForEach-Object { Write-Host "    $_" -ForegroundColor DarkGray }
        }

        # --- Python: pytest ---
        Write-Host "  pytest          " -ForegroundColor Cyan -NoNewline
        $out = & pytest --tb=short -q 2>&1
        if ($LASTEXITCODE -eq 0) {
            $passLine = ($out | Select-String "passed").Line
            if ($passLine) {
                Write-Host "ok ($passLine)" -ForegroundColor Green
            } else {
                Write-Host "ok" -ForegroundColor Green
            }
        } else {
            $failLine = ($out | Select-String "failed|error").Line | Select-Object -First 1
            if ($failLine) {
                Write-Host "fail ($failLine)" -ForegroundColor Red
            } else {
                Write-Host "fail" -ForegroundColor Red
            }
            $out | Where-Object { $_ -match "FAILED|ERROR" } | ForEach-Object { Write-Host "    $_" -ForegroundColor DarkGray }
        }

        Write-Host ""
    }

    Invoke-AllLint

    # Watch both Python and TypeScript files
    $pyWatcher = [System.IO.FileSystemWatcher]::new($pyPath, "*.py")
    $pyWatcher.IncludeSubdirectories = $true
    $pyWatcher.NotifyFilter = [System.IO.NotifyFilters]::LastWrite -bor
                              [System.IO.NotifyFilters]::FileName -bor
                              [System.IO.NotifyFilters]::CreationTime
    $pyWatcher.EnableRaisingEvents = $true

    $tsWatcher = [System.IO.FileSystemWatcher]::new($tsPath)
    $tsWatcher.IncludeSubdirectories = $true
    $tsWatcher.NotifyFilter = [System.IO.NotifyFilters]::LastWrite -bor
                              [System.IO.NotifyFilters]::FileName -bor
                              [System.IO.NotifyFilters]::CreationTime
    $tsWatcher.EnableRaisingEvents = $true

    # Shared state for debouncing
    $lastRun = [datetime]::MinValue

    $handler = {
        $now = Get-Date
        $script:lastChange = $now
    }

    $script:lastChange = [datetime]::MinValue

    Register-ObjectEvent $pyWatcher Changed -Action $handler | Out-Null
    Register-ObjectEvent $pyWatcher Created -Action $handler | Out-Null
    Register-ObjectEvent $pyWatcher Renamed -Action $handler | Out-Null
    Register-ObjectEvent $tsWatcher Changed -Action $handler | Out-Null
    Register-ObjectEvent $tsWatcher Created -Action $handler | Out-Null
    Register-ObjectEvent $tsWatcher Renamed -Action $handler | Out-Null

    try {
        while ($true) {
            Start-Sleep -Milliseconds 500
            if ($script:lastChange -ne [datetime]::MinValue -and
                ((Get-Date) - $script:lastChange).TotalMilliseconds -gt 800 -and
                $script:lastChange -ne $lastRun) {
                $lastRun = $script:lastChange
                Invoke-AllLint
            }
        }
    } finally {
        $pyWatcher.Dispose()
        $tsWatcher.Dispose()
        Get-EventSubscriber | Unregister-Event
        Write-Host "[dev] Watcher stopped." -ForegroundColor Green
    }
    return
}

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

# --- Clear __pycache__ to avoid stale bytecode ---
if ($startBackend) {
    Write-Host "[dev] Clearing __pycache__..." -ForegroundColor DarkGray
    Get-ChildItem -Path "$Root\src" -Recurse -Directory -Filter __pycache__ |
        Remove-Item -Recurse -Force -ErrorAction SilentlyContinue

    # Remove debug log artifact if leftover
    $debugLog = "$Root\src\cachibot\api\room_ws_debug.log"
    if (Test-Path $debugLog) { Remove-Item $debugLog -Force }
}

# --- Ensure latest editable installs (CachiBot + owned libs) ---
if ($startBackend) {
    Write-Host "[dev] Syncing editable installs..." -ForegroundColor DarkGray
    $prompturePath = Join-Path (Split-Path $Root) "prompture"
    $tukuyPath = Join-Path (Split-Path $Root) "Tukuy"
    try {
        if (Test-Path $prompturePath) {
            $out = & pip install -e $prompturePath -q 2>&1
            if ($LASTEXITCODE -ne 0) { Write-Host "[dev]   prompture FAILED: $out" -ForegroundColor Red }
            else { Write-Host "[dev]   prompture -> $prompturePath" -ForegroundColor DarkGray }
        }
        if (Test-Path $tukuyPath) {
            $out = & pip install -e $tukuyPath -q 2>&1
            if ($LASTEXITCODE -ne 0) { Write-Host "[dev]   tukuy FAILED: $out" -ForegroundColor Red }
            else { Write-Host "[dev]   tukuy     -> $tukuyPath" -ForegroundColor DarkGray }
        }
        Push-Location $Root
        $out = & pip install -e ".[dev]" -q 2>&1
        if ($LASTEXITCODE -ne 0) { Write-Host "[dev]   cachibot FAILED: $out" -ForegroundColor Red }
        else { Write-Host "[dev]   cachibot  -> $Root (editable)" -ForegroundColor DarkGray }
        Pop-Location
    } catch {
        Write-Host "[dev] Warning: pip sync failed: $_" -ForegroundColor Yellow
        Pop-Location -ErrorAction SilentlyContinue
    }

    # Verify editable install points to source tree
    $installPath = & python -c "import cachibot; print(cachibot.__path__[0])" 2>&1
    $expectedPath = "$Root\src\cachibot"
    if ($installPath -ne $expectedPath) {
        Write-Host "[dev] WARNING: cachibot is loading from $installPath" -ForegroundColor Red
        Write-Host "[dev]          Expected: $expectedPath" -ForegroundColor Red
        Write-Host "[dev]          Run: pip uninstall cachibot -y && pip install -e '.[dev]'" -ForegroundColor Yellow
    }
}

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
