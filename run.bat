@echo off
setlocal
echo Starting Bat Pupil Tracking Application...

if not exist ".venv\Scripts\activate.bat" (
    echo Virtual environment (.venv) not found.
    echo Creating virtual environment and installing dependencies...
    python -m venv .venv
    call .venv\Scripts\activate.bat
    python -m pip install --upgrade pip
    pip install -r requirements.txt
) else (
    call .venv\Scripts\activate.bat
)

python Code\app.py
pause
