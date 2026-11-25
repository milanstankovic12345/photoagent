@echo off
setlocal
cd /d "%~dp0"

if exist ".venv\Scripts\python.exe" goto CHECK_EXISTING
for /f %%V in (packaging\windows-source-versions.txt) do (
    py -%%V -I -c "import sysconfig; assert sysconfig.get_platform() == 'win-amd64'" >nul 2>&1
    if not errorlevel 1 (
        py -%%V -m venv .venv
        if errorlevel 1 goto ERROR
        goto CHECK_LIBRARIES
    )
)
goto PYTHON_ERROR

:CHECK_EXISTING
".venv\Scripts\python.exe" -I -c "import pathlib,sys,sysconfig; sys.exit(0 if sysconfig.get_platform() == 'win-amd64' and (str(sys.version_info.major)+'.'+str(sys.version_info.minor)) in pathlib.Path('packaging/windows-source-versions.txt').read_text().split() else 1)"
if errorlevel 1 goto PYTHON_ERROR

:CHECK_LIBRARIES
echo Proveravam Python biblioteke...
".venv\Scripts\python.exe" -B -m app.services.preflight %*
if errorlevel 1 (
    ".venv\Scripts\python.exe" -m pip install -r requirements.txt
    if errorlevel 1 goto ERROR
)

".venv\Scripts\python.exe" -B -m app.services.preflight %*
if errorlevel 1 goto ERROR

echo Pokrecem PhotoAgent...
".venv\Scripts\python.exe" -B photo_agent.py %*

if errorlevel 1 goto ERROR
exit /b 0

:ERROR
echo.
echo GRESKA! Pogledaj prethodnu poruku ili koristi PhotoAgent-Setup.exe.
pause
exit /b 1

:PYTHON_ERROR
echo Za instalaciju bez podesavanja Pythona koristi PhotoAgent-Setup.exe.
echo Proverene x64 verzije za rad iz izvornog koda:
type packaging\windows-source-versions.txt
pause
exit /b 1
