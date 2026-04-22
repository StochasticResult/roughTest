param(
  [string]$OutDir = ".\\release",
  [string]$ZipName = ""
)

$ErrorActionPreference = "Stop"

function Write-Info([string]$msg) { Write-Host "[INFO] $msg" -ForegroundColor Cyan }
function Write-Err([string]$msg) { Write-Host "[ERROR] $msg" -ForegroundColor Red }

$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Root

$AbsOut = Resolve-Path -LiteralPath $Root | Select-Object -ExpandProperty Path
$ReleaseDir = Join-Path $AbsOut $OutDir

if ([string]::IsNullOrWhiteSpace($ZipName)) {
  $stamp = Get-Date -Format "yyyyMMdd_HHmmss"
  $ZipName = "rf_lambda_test_assistant_$stamp.zip"
}

$ZipPath = Join-Path $AbsOut $ZipName

Write-Info "Cleaning output dir: $ReleaseDir"
if (Test-Path $ReleaseDir) { Remove-Item -Recurse -Force $ReleaseDir }
New-Item -ItemType Directory -Path $ReleaseDir | Out-Null

function Copy-Tree([string]$rel) {
  $src = Join-Path $AbsOut $rel
  if (-not (Test-Path $src)) { return }
  $dst = Join-Path $ReleaseDir $rel
  New-Item -ItemType Directory -Path (Split-Path -Parent $dst) -Force | Out-Null
  Copy-Item -Recurse -Force $src $dst
}

# Required source
Copy-Tree "main.py"
Copy-Tree "models"
Copy-Tree "services"
Copy-Tree "ui"
Copy-Tree "tests"

# Entry/help files
Copy-Tree "requirements.txt"
Copy-Tree "README.md"
Copy-Tree "requirement.md"
Copy-Tree "start_rf_lambda_app.bat"
Copy-Tree "start_rf_lambda_app_simulation.bat"
Copy-Tree "setup_windows.ps1"

# Remove junk
$junkPatterns = @(
  "__pycache__",
  "*.pyc",
  "*.pyo",
  ".pytest_cache",
  ".venv",
  ".git",
  ".idea",
  ".vscode"
)

foreach ($p in $junkPatterns) {
  Get-ChildItem -Path $ReleaseDir -Recurse -Force -ErrorAction SilentlyContinue |
    Where-Object { $_.Name -like $p -or $_.FullName -like "*\\$p\\*" } |
    ForEach-Object {
      try {
        if ($_.PSIsContainer) { Remove-Item -Recurse -Force $_.FullName }
        else { Remove-Item -Force $_.FullName }
      } catch { }
    }
}

Write-Info "Creating zip: $ZipPath"
if (Test-Path $ZipPath) { Remove-Item -Force $ZipPath }
Compress-Archive -Path (Join-Path $ReleaseDir "*") -DestinationPath $ZipPath -Force

Write-Info "Done."
Write-Host "Release folder: $ReleaseDir"
Write-Host "Zip file:       $ZipPath"

