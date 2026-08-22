@echo off
setlocal
cd /d "%~dp0"

set "PY=.venv\Scripts\python.exe"

if not exist "%PY%" (
    echo Creating virtual environment in .venv ...
    python -m venv .venv
    if errorlevel 1 (
        echo ERROR: could not create .venv. Install Python 3.11+ and put it on PATH.
        exit /b 1
    )
)

echo Checking dependencies ...
"%PY%" -m pip install --quiet --disable-pip-version-check -r requirements.txt
if errorlevel 1 (
    echo ERROR: dependency install failed. See the pip output above.
    exit /b 1
)

echo Checking fonts ...
"%PY%" -m tools.check_setup
if errorlevel 1 exit /b 1

"%PY%" wsgi.py
endlocal
