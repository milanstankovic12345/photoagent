@echo off
setlocal
cd /d "%~dp0"
if not exist ".runtime\Scripts\python.exe" (
    echo Run Python 3.12 install_offline.py first. No network installation is attempted.
    exit /b 1
)
".runtime\Scripts\python.exe" -X utf8 -E -s -B photo_agent.py %*
exit /b %errorlevel%
