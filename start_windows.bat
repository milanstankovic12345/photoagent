@echo off
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo Kreiram Python virtuelno okruzenje...
    py -3.12 -m venv .venv
    if errorlevel 1 goto ERROR
)

echo Proveravam Python biblioteke...
".venv\Scripts\python.exe" -B -m app.services.preflight
if errorlevel 1 (
    ".venv\Scripts\python.exe" -m pip install -r requirements.txt
    if errorlevel 1 goto ERROR
)

".venv\Scripts\python.exe" -B -m app.services.preflight
if errorlevel 1 goto ERROR

echo Pokrecem PhotoAgent...
".venv\Scripts\python.exe" -B photo_agent.py

if errorlevel 1 goto ERROR
exit /b 0

:ERROR
echo.
echo GRESKA! Proveri instalaciju Python 3.12.
pause
exit /b 1
