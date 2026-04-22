@echo off
setlocal

cd /d "%~dp0"
title RF Lambda Test Assistant

set "PYTHON_EXE="

if exist ".venv\Scripts\python.exe" (
    set "PYTHON_EXE=.venv\Scripts\python.exe"
) else (
    where py >nul 2>nul
    if not errorlevel 1 (
        set "PYTHON_EXE=py -3"
    ) else (
        where python >nul 2>nul
        if not errorlevel 1 (
            set "PYTHON_EXE=python"
        )
    )
)

if "%PYTHON_EXE%"=="" (
    echo [ERROR] Python was not found.
    echo Please install Python 3.10+ or create a .venv first.
    pause
    exit /b 1
)

echo Using Python: %PYTHON_EXE%
echo Cleaning up previous RF Lambda instances...
powershell -NoProfile -Command ^
  "$procs = Get-CimInstance Win32_Process | Where-Object { $_.Name -eq 'python.exe' -and $_.CommandLine -match 'roughTest\\\\main.py' }; " ^
  "if ($procs) { $procs | ForEach-Object { Stop-Process -Id $_.ProcessId -Force } }" >nul 2>nul

echo Checking dependencies...
%PYTHON_EXE% -c "import PySide6, pyvisa, numpy" >nul 2>nul
if errorlevel 1 (
    echo Installing required packages...
    %PYTHON_EXE% -m pip install -r requirements.txt
    if errorlevel 1 (
        echo [ERROR] Failed to install dependencies.
        pause
        exit /b 1
    )
)

echo Launching RF Lambda Test Assistant...
%PYTHON_EXE% main.py

if errorlevel 1 (
    echo.
    echo [ERROR] The application exited with an error.
    pause
)

endlocal
