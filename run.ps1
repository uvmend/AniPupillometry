# Launcher for Bat Pupil Tracking Application in PowerShell
Write-Host "Starting Bat Pupil Tracking Application..." -ForegroundColor Cyan

$venvPython = ".\.venv\Scripts\python.exe"
if (-not (Test-Path $venvPython)) {
    Write-Host "Virtual environment (.venv) not found. Creating and installing requirements..." -ForegroundColor Yellow
    python -m venv .venv
    & $venvPython -m pip install --upgrade pip
    & $venvPython -m pip install -r requirements.txt
}

& $venvPython "Code\app.py"
