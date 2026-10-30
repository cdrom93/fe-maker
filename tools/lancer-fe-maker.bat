@echo off
rem FE Maker: first launch installs what it needs in .venv (Python 3.10 or later required), then starts.
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
    py -3 -m venv .venv 2>nul || python -m venv .venv
    if errorlevel 1 (
        echo Python 3.10 or later is needed: https://www.python.org/downloads/
        pause
        exit /b 1
    )
    ".venv\Scripts\python.exe" -m pip install --quiet -e .\server
)
".venv\Scripts\python.exe" -m fe_maker
