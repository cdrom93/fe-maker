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
    rem a desktop shortcut with FE Maker's icon, made once
    powershell -NoProfile -Command "$s = (New-Object -ComObject WScript.Shell).CreateShortcut([Environment]::GetFolderPath('Desktop') + '\FE Maker.lnk'); $s.TargetPath = '%~dp0lancer-fe-maker.bat'; $s.WorkingDirectory = '%~dp0'; $s.IconLocation = '%~dp0server\fe_maker\fe-maker.ico,0'; $s.Save()" >nul 2>&1
)
".venv\Scripts\python.exe" -m fe_maker
