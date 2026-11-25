# Run inside a disposable Windows Sandbox with networking disabled.
# Map the installer directory at C:\Candidate (read-only) and a fresh evidence
# directory at C:\Evidence (writable). Only synthetic photos are generated.
param([string]$ExternalPythonDirectory)

$ErrorActionPreference = 'Stop'
if ($env:USERNAME -ne 'WDAGUtilityAccount') { throw 'Run in Windows Sandbox.' }
$setup = 'C:\Candidate\PhotoAgent-Setup.exe'
$proof = 'C:\Evidence'
$library = Join-Path $env:TEMP 'PhotoAgent-smoke'
$appDir = Join-Path $env:LOCALAPPDATA 'Programs\PhotoAgent'
$link = Join-Path ([Environment]::GetFolderPath('Programs')) 'PhotoAgent.lnk'
$shell = New-Object -ComObject WScript.Shell

function Install-Candidate {
    $proc = Start-Process -FilePath $setup -WindowStyle Hidden -ArgumentList '/VERYSILENT','/NORESTART','/SUPPRESSMSGBOXES' -Wait -PassThru
    if ($proc.ExitCode -ne 0) { throw "Setup failed ($($proc.ExitCode))" }
    if (-not (Test-Path -LiteralPath $link)) { throw 'Missing Start shortcut' }
    $target = $shell.CreateShortcut($link).TargetPath
    if (-not $target.StartsWith("$appDir\versions\")) { throw 'Unexpected shortcut target' }
    return (Split-Path (Split-Path $target))
}

try {
    if ((Test-Path $appDir) -or (Test-Path $library)) { throw 'Fresh sandbox required' }
    Start-Transcript -LiteralPath "$proof\install.log"
    $first = Install-Candidate
    Start-Process -FilePath $link
    $deadline = (Get-Date).AddSeconds(60)
    do {
        Start-Sleep -Milliseconds 500
        $window = Get-Process pythonw -ErrorAction SilentlyContinue | Where-Object {
            $_.Path -eq "$first\.runtime\pythonw.exe" -and $_.MainWindowTitle -like '*PhotoAgent*'
        }
    } until ($window -or (Get-Date) -ge $deadline)
    if (-not $window) { throw 'Start shortcut did not open a window' }
    $null = $window.CloseMainWindow()
    if (-not $window.WaitForExit(30000)) { throw 'Application did not close cleanly' }
    & "$first\.runtime\python.exe" -X utf8 -B "$first\tools\release_smoke.py" --output $library
    if ($LASTEXITCODE -ne 0) { throw 'Installed smoke failed' }
    Copy-Item "$library\results.json" $proof
    $photos = Get-ChildItem -LiteralPath $library -Directory -Filter 'fotografije-*'
    @'
import csv
import sys
from pathlib import Path
from threading import Event
from app.services.application import Application

home, photos = map(Path, sys.argv[1:])
home.mkdir()
service = Application(home)
try:
    service.initialize()
    result, report, error, page, _, _ = service.scan_with_report([str(photos)], None, Event())
    assert result.complete and not error
    with report.open(encoding="utf-8-sig", newline="") as stream:
        assert len(list(csv.reader(stream, delimiter=";"))) == result.pair_count + 1
    previews = service.previews(page[0][0], Event())
    assert len(previews) == 2 and all(image["preview"] and not error for image, error in previews)
    stop = Event()
    stop.set()
    assert not service.scan([str(photos)], None, stop).complete
finally:
    service.close()
'@ | & "$first\.runtime\python.exe" -B - (Join-Path $env:TEMP 'PhotoAgent-preview-csv') $photos.FullName
    if ($LASTEXITCODE -ne 0) { throw 'Preview, CSV or cancellation check failed' }
    # Leave a synthetic approved move pending across upgrade and reinstallation.
    $recovery = Join-Path $env:TEMP 'PhotoAgent-recovery'
    New-Item -ItemType Directory -Path "$recovery\home" -Force | Out-Null
    $newPhotos = New-Item -ItemType Directory -Path (Join-Path $recovery $photos.Name)
    Get-ChildItem -LiteralPath $photos.FullName -File | Copy-Item -Destination $newPhotos.FullName
    & "$first\.runtime\python.exe" -X utf8 -B "$first\tools\release_smoke.py" --phase scan --output $recovery
    if ($LASTEXITCODE -ne 0) { throw 'Recovery fixture scan failed' }
    & "$first\.runtime\python.exe" -X utf8 -B "$first\tools\release_smoke.py" --phase interrupt --output $recovery
    if ($LASTEXITCODE -ne 73) { throw 'Expected simulated interrupted move' }
    $second = Install-Candidate
    if ($first -eq $second) { throw 'Upgrade reused an existing payload' }
    $uninstall = Start-Process "$appDir\unins000.exe" -WindowStyle Hidden -ArgumentList '/VERYSILENT','/SUPPRESSMSGBOXES','/NORESTART' -Wait -PassThru
    if ($uninstall.ExitCode -ne 0 -or (Test-Path $link)) { throw 'Uninstall failed' }
    $third = Install-Candidate
    & "$third\.runtime\python.exe" -X utf8 -B "$third\tools\release_smoke.py" --phase restore --output $recovery
    if ($LASTEXITCODE -ne 0) { throw 'Restore after reinstall failed' }
    if ($ExternalPythonDirectory) {
        $external = (Resolve-Path -LiteralPath $ExternalPythonDirectory).Path
        $env:Path = "$external;$env:Path"
        $before = python.exe --version
        if ($LASTEXITCODE -ne 0 -or $before -notlike 'Python 3.*') { throw 'Invalid external Python' }
        $fourth = Install-Candidate
        $private = & "$fourth\.runtime\python.exe" --version
        if ($LASTEXITCODE -ne 0 -or $private -ne 'Python 3.12.10' -or (python.exe --version) -ne $before) {
            throw 'Unexpected interpreter after upgrade'
        }
        Write-Output "External interpreter $before; installed interpreter $private"
    }
    Set-Content "$proof\status.txt" 'passed'
} catch {
    Set-Content "$proof\status.txt" "failed: $_"
    throw
} finally {
    Stop-Transcript -ErrorAction SilentlyContinue
}
