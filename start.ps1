<#
.SYNOPSIS
    PDX Save Analyzer — One-click startup script.
    Activates the Python venv, installs deps if needed,
    starts the FastAPI backend, the Vite dev server, and opens the browser.

.USAGE
    .\start.ps1              # Normal start
    .\start.ps1 -Verbose     # With debug logging on the backend
    .\start.ps1 -SkipInstall # Skip dependency checks (faster restart)
#>

param(
    [switch]$Verbose,
    [switch]$SkipInstall
)

$ErrorActionPreference = "Continue"
$ProjectRoot = $PSScriptRoot

# ---------------------------------------------------------------------------
# Colors & helpers
# ---------------------------------------------------------------------------

function Write-Step($msg)  { Write-Host "[*] $msg" -ForegroundColor Cyan }
function Write-Ok($msg)    { Write-Host "[+] $msg" -ForegroundColor Green }
function Write-Warn($msg)  { Write-Host "[!] $msg" -ForegroundColor Yellow }
function Write-Err($msg)   { Write-Host "[x] $msg" -ForegroundColor Red }

# ---------------------------------------------------------------------------
# 1. Check Python venv exists
# ---------------------------------------------------------------------------

$VenvPython = Join-Path $ProjectRoot "venv\Scripts\python.exe"
$VenvPip    = Join-Path $ProjectRoot "venv\Scripts\pip.exe"
$VenvActivate = Join-Path $ProjectRoot "venv\Scripts\Activate.ps1"

if (-not (Test-Path $VenvPython)) {
    Write-Err "Python venv not found at venv\Scripts\python.exe"
    Write-Host "  Create it with:  python -m venv venv"
    exit 1
}

Write-Step "Activating Python virtual environment"
& $VenvActivate

# ---------------------------------------------------------------------------
# 2. Install Python deps if needed
# ---------------------------------------------------------------------------

if (-not $SkipInstall) {
    Write-Step "Checking Python dependencies..."
    #& $VenvPip install -r (Join-Path $ProjectRoot "requirements.txt") --quiet 2>&1 | Out-Null
    & $VenvPip install -r (Join-Path $ProjectRoot "requirements.txt") --quiet --no-warn-script-location
    Write-Ok "Python dependencies OK"
}

# ---------------------------------------------------------------------------
# 3. Install Node deps if needed
# ---------------------------------------------------------------------------

$FrontendDir = Join-Path $ProjectRoot "frontend"
$ViteBin = Join-Path $FrontendDir "node_modules\vite\bin\vite.js"

if (-not $SkipInstall) {
    if (-not (Test-Path $ViteBin)) {
        Write-Step "Vite not found. Installing/Repairing frontend dependencies..."
        Push-Location $FrontendDir
        npm install
        Pop-Location
        Write-Ok "Frontend dependencies synchronized"
    } else {
        Write-Step "Vite binary found, skipping npm install"
    }
}

# ---------------------------------------------------------------------------
# 4. Start the FastAPI backend (background job)
# ---------------------------------------------------------------------------

Write-Step "Starting FastAPI backend on http://127.0.0.1:8000"

$BackendArgs = @(
    (Join-Path $ProjectRoot "run_server.py")
)
if ($Verbose) { $BackendArgs += "--verbose" }

$BackendJob = Start-Job -ScriptBlock {
    param($python, $args_list, $workdir)
    Set-Location $workdir
    & $python @args_list
} -ArgumentList $VenvPython, $BackendArgs, $ProjectRoot

# Give the backend a moment to boot
Start-Sleep -Seconds 2

if ($BackendJob.State -eq "Failed") {
    Write-Err "Backend failed to start!"
    Receive-Job $BackendJob
    exit 1
}
Write-Ok "Backend running (Job ID: $($BackendJob.Id))"

# ---------------------------------------------------------------------------
# 5. Start the Vite dev server (background job)
# ---------------------------------------------------------------------------

Write-Step "Starting Vite dev server on http://localhost:5173"

$FrontendJob = Start-Job -ScriptBlock {
    param($frontendDir)
    Set-Location $frontendDir
    npm run dev 2>&1
} -ArgumentList $FrontendDir

Start-Sleep -Seconds 3

if ($FrontendJob.State -eq "Failed") {
    Write-Err "Frontend failed to start!"
    Receive-Job $FrontendJob
    Stop-Job $BackendJob; Remove-Job $BackendJob
    exit 1
}
Write-Ok "Frontend running (Job ID: $($FrontendJob.Id))"

# ---------------------------------------------------------------------------
# 6. Open the browser
# ---------------------------------------------------------------------------

Write-Step "Opening http://localhost:5173 in your default browser"
Start-Process "http://localhost:5173"

# ---------------------------------------------------------------------------
# 7. Wait for Ctrl+C, then clean up
# ---------------------------------------------------------------------------

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  PDX Save Analyzer is running!" -ForegroundColor Green
Write-Host "  Dashboard:  http://localhost:5173" -ForegroundColor White
Write-Host "  API:        http://127.0.0.1:8000" -ForegroundColor White
Write-Host "  Press Ctrl+C to stop everything" -ForegroundColor Yellow
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

try {
    # Stream backend + frontend output to console.
    # Uvicorn writes INFO logs to stderr, which PowerShell surfaces as
    # ErrorRecords on the job. We use -ErrorAction SilentlyContinue so
    # those don't throw and kill the loop.
    while ($true) {
        # Check if either job has died
        if ($BackendJob.State -eq "Completed" -or $BackendJob.State -eq "Failed") {
            Write-Warn "Backend process exited (state: $($BackendJob.State))"
            Receive-Job $BackendJob -ErrorAction SilentlyContinue 2>&1 | ForEach-Object { Write-Host "[backend] $_" }
            break
        }
        if ($FrontendJob.State -eq "Completed" -or $FrontendJob.State -eq "Failed") {
            Write-Warn "Frontend process exited (state: $($FrontendJob.State))"
            Receive-Job $FrontendJob -ErrorAction SilentlyContinue 2>&1 | ForEach-Object { Write-Host "[frontend] $_" }
            break
        }

        # Print any new output from both jobs (stderr included via 2>&1)
        Receive-Job $BackendJob  -ErrorAction SilentlyContinue 2>&1 | ForEach-Object { Write-Host "[backend]  $_" -ForegroundColor DarkGray }
        Receive-Job $FrontendJob -ErrorAction SilentlyContinue 2>&1 | ForEach-Object { Write-Host "[frontend] $_" -ForegroundColor DarkGray }

        Start-Sleep -Milliseconds 500
    }
}
finally {
    Write-Step "Shutting down..."
    Stop-Job $BackendJob  -ErrorAction SilentlyContinue
    Stop-Job $FrontendJob -ErrorAction SilentlyContinue
    Remove-Job $BackendJob  -Force -ErrorAction SilentlyContinue
    Remove-Job $FrontendJob -Force -ErrorAction SilentlyContinue
    Write-Ok "All processes stopped. Goodbye!"
}