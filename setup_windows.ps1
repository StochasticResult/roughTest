param(
  [switch]$Simulate,
  [switch]$SkipDrivers
)

$ErrorActionPreference = "Stop"

function Write-Info([string]$msg) { Write-Host "[INFO] $msg" -ForegroundColor Cyan }
function Write-Warn([string]$msg) { Write-Host "[WARN] $msg" -ForegroundColor Yellow }
function Write-Err([string]$msg) { Write-Host "[ERROR] $msg" -ForegroundColor Red }

$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Root

Write-Info "Project root: $Root"

function Resolve-PythonExe {
  if (Test-Path ".\.venv\Scripts\python.exe") { return (Resolve-Path ".\.venv\Scripts\python.exe").Path }
  $py = Get-Command py -ErrorAction SilentlyContinue
  if ($py) { return "py -3" }
  $python = Get-Command python -ErrorAction SilentlyContinue
  if ($python) { return "python" }
  return $null
}

function Ensure-Venv {
  if (Test-Path ".\.venv\Scripts\python.exe") {
    Write-Info "Using existing venv: .venv"
    return
  }

  $sysPy = Resolve-PythonExe
  if (-not $sysPy) {
    Write-Err "Python not found. Install Python 3.10+ and re-run this script."
    throw "Python not found"
  }

  Write-Info "Creating venv: .venv"
  if ($sysPy -eq "py -3") {
    & py -3 -m venv .venv
  } else {
    & $sysPy -m venv .venv
  }
}

function Ensure-PipAndDeps {
  $venvPy = (Resolve-Path ".\.venv\Scripts\python.exe").Path
  Write-Info "Upgrading pip/setuptools/wheel"
  & $venvPy -m pip install --upgrade pip setuptools wheel

  if (-not (Test-Path ".\requirements.txt")) {
    Write-Err "requirements.txt not found."
    throw "requirements.txt missing"
  }

  Write-Info "Installing Python dependencies from requirements.txt"
  & $venvPy -m pip install -r .\requirements.txt
}

function Print-DriverNotes {
  if ($SkipDrivers) { return }

  Write-Warn "Hardware prerequisites (only needed for real meters):"
  Write-Host "  - NI-VISA (or R&S VISA) installed" -ForegroundColor Gray
  Write-Host "  - For R&S NRP sensors: R&S NRP Toolkit + NRP NI-VISA Passport (recommended)" -ForegroundColor Gray
  Write-Host "  - If VISA can't see sensors but Windows can: install the above, then reboot" -ForegroundColor Gray
  Write-Host ""
}

function Create-HelperShortcuts {
  $start = Join-Path $Root "start_rf_lambda_app.bat"
  $startSim = Join-Path $Root "start_rf_lambda_app_simulation.bat"
  if (-not (Test-Path $start)) {
    Write-Warn "start_rf_lambda_app.bat not found (ok)."
  }
  if (-not (Test-Path $startSim)) {
    Write-Warn "start_rf_lambda_app_simulation.bat not found (ok)."
  }
}

try {
  Ensure-Venv
  Ensure-PipAndDeps
  Print-DriverNotes
  Create-HelperShortcuts

  $venvPy = (Resolve-Path ".\.venv\Scripts\python.exe").Path
  if ($Simulate) {
    Write-Info "Launching app (simulation mode)..."
    & $venvPy .\main.py --simulate
  } else {
    Write-Info "Setup complete."
    Write-Host "Run:" -ForegroundColor Green
    Write-Host "  .\start_rf_lambda_app.bat" -ForegroundColor Green
    Write-Host "or (no hardware):" -ForegroundColor Green
    Write-Host "  .\start_rf_lambda_app_simulation.bat" -ForegroundColor Green
  }
} catch {
  Write-Err $_.Exception.Message
  Write-Host ""
  Write-Host "If scripts are blocked, run PowerShell as:" -ForegroundColor Yellow
  Write-Host "  PowerShell -ExecutionPolicy Bypass -File .\setup_windows.ps1" -ForegroundColor Yellow
  exit 1
}

