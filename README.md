# PhotoAgent

PhotoAgent is a local desktop application for finding and reviewing duplicate
photographs across folders, internal drives and removable storage. Compare copies
side by side, choose what to keep, and move approved copies into a reversible
quarantine.

Your photographs stay on your computer. After installation, PhotoAgent works
offline, without accounts, telemetry, cloud uploads or external AI services.

The default interface supports **English and Serbian Latin**, with **Dark, Light
and System** themes. Serbian documentation: [README_SR.md](README_SR.md).

**Current status:** v2.5 development candidate. The standalone installer passed
offline installation and recovery checks in a clean Windows 11 x64 Sandbox.
Windows 10, native Linux and successful valid RAW decoding still need acceptance
testing. See [test evidence](docs/TESTING.md) and
[release status](docs/RELEASE.md) for the remaining checks.

## What you can do

- Scan several folders recursively, including folders on connected external drives.
- Find byte-identical files using SHA-256, even when their names differ.
- Find visually similar images using pHash and dHash for individual review.
- Compare previews, dimensions, file sizes and available metadata.
- Filter and search results, review groups, and export CSV reports.
- Confirm quarantine moves and restore eligible photographs after restarting.
- Reuse a local SQLite index on later scans. Each scan still reads the full file
  for SHA-256 verification.

**Visual similarity is not proof that two photographs are duplicates.** Edits,
resized exports, RAW/JPEG versions and burst photographs can all be worth keeping.
Quality recommendations are heuristics, not a measurement of artistic value.

## Install on another computer

Choose the instructions that match the files you received:

| Files you have | Installation method |
| --- | --- |
| `PhotoAgent-Setup.exe` | On Windows 10/11 x64, double-click the installer, then open PhotoAgent from Start. Includes Python and all dependencies. Works offline. |
| Source folder containing `photo_agent.py`, `app/` and `start_windows.bat` / `start_linux.sh` | [Windows](#windows-1011-source-installation) or [Linux](#linux-source-installation); first setup normally needs internet |
| Prepared bundle containing `install_offline.py`, `release-manifest.json` and `wheelhouse/` | [Offline Windows installation](#offline-windows-installation) |

Copying the source folder does **not** install Python or its dependencies. Create a
new environment on each computer; do not copy `.venv` or `.runtime` from another
machine. Git and VS Code are not required to use the application.

### Windows 10/11: source installation

1. Install **64-bit Python 3.12, 3.13 or 3.14**, including the Python launcher (`py`) and `pip`.
   Python is a separate prerequisite; PhotoAgent does not install it.
2. Copy the complete application source folder, or extract its source ZIP, into a
   writable location such as `C:\Users\YourName\Apps\PhotoAgent`. Keep `app/`,
   `photo_agent.py`, `requirements.txt` and the launch scripts together. Extract
   the ZIP before starting the application.
3. Open PowerShell in that folder. Confirm that Python is available:

   ```powershell
   py --list
   ```

4. Start PhotoAgent:

   ```powershell
   .\start_windows.bat
   ```

   You can also double-click `start_windows.bat` in File Explorer. On first launch,
   it creates `.venv`, checks the runtime, installs missing requirements with pip,
   and opens the Qt interface. Allow the dependency installation to finish.
5. Use the same launcher on subsequent visits. You can create a desktop shortcut
   to it; keep the application folder in place.

The launcher may contact the package index when dependencies are missing. Once
installation succeeds, normal application use needs no internet connection.

For manual setup in a fresh source folder, run these commands instead:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -B -m app.services.preflight --ui qt
.\.venv\Scripts\python.exe -B photo_agent.py
```

No environment activation or PowerShell execution-policy change is needed.

### Linux: source installation

Linux support needs native acceptance testing. Use a desktop session and try the
synthetic demo before working with your collection.

1. Provide **Python 3.12 or newer**, `venv` and `pip` through your distribution.
   The launcher does not install system packages. A working Qt desktop environment
   and its platform libraries are also required.
2. Copy or extract the complete source into a writable folder.
3. Open a terminal in that folder and run:

   ```bash
   python3 --version
   bash start_linux.sh
   ```

The launcher uses `python3`, creates `.venv`, installs missing requirements and
starts PhotoAgent. Initial dependency installation normally needs internet.

If `python3` is older than 3.12, use a suitable installed interpreter explicitly,
for example:

```bash
python3.12 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -B -m app.services.preflight --ui qt
.venv/bin/python -B photo_agent.py
```

Use `.venv/bin/python -B photo_agent.py` for later launches with that environment.
Windows environments and Windows wheel bundles cannot be reused on Linux.

### Offline Windows installation

This method requires a **prepared source bundle with all dependency wheels**;
an ordinary source ZIP is not enough. The existing packaging target is
**CPython 3.12, Windows x64**. Python itself is not included.

On the destination computer:

1. Install Python 3.12 x64 before disconnecting, or transfer its installer separately.
2. Transfer the prepared PhotoAgent ZIP, for example using a USB drive. Compare its
   SHA-256 checksum with the checksum supplied separately by the person who built it.
3. Extract into a **new, writable folder**. Open PowerShell there and run:

   ```powershell
   py -3.12 -B install_offline.py
   .\start_offline.bat
   ```

The installer verifies the recorded platform, Python version and file hashes,
creates `.runtime`, and installs only the included wheels. The packaged launcher
never downloads dependencies. Use `start_offline.bat` for subsequent launches.

The installer refuses an existing `.runtime`. If installation fails partway through,
extract the bundle into a fresh folder and retry. Preserve any existing user data.

To **prepare a bundle on the original Windows computer**, use its working Python
3.12 x64 source environment. The first command downloads packages and needs internet;
the builder then packages the source and local wheels:

```powershell
.\.venv\Scripts\python.exe -B -m pip download --only-binary=:all: --no-cache-dir --dest build/transfer-wheelhouse -r packaging/runtime-win-amd64-py312.txt
.\.venv\Scripts\python.exe -B -m tools.build_release --wheelhouse build/transfer-wheelhouse --lock packaging/runtime-win-amd64-py312.txt --output dist/PhotoAgent-2.5-win-amd64-py312-candidate.zip
Get-FileHash -Algorithm SHA256 dist/PhotoAgent-2.5-win-amd64-py312-candidate.zip
```

Choose unused wheelhouse and output paths when repeating the procedure. Transfer
the resulting ZIP and retain its checksum separately. Bundles are development
candidates; clean-computer validation and public redistribution requirements remain
open. See [release preparation and verification](docs/RELEASE.md).

## Try it with sample photographs

The source checkout includes a generator for synthetic photographs. Choose a
destination that **does not already exist**, then run from the application folder:

```powershell
.\.venv\Scripts\python.exe -B napravi_demo.py .\demo_photo_collection
```

On Linux:

```bash
.venv/bin/python -B napravi_demo.py ./demo_photo_collection
```

Add the generated folder on the Scan page. It contains an exact copy, rendered and
resized variants, and a different image. The generator refuses existing directories.
Prepared offline bundles do not include this generator.

## Your first scan and review

1. **Choose your preferences.** In Settings, select English or Srpski (latinica)
   and Dark, Light or System. Preferences survive restart. Fresh installations
   start in English with the Dark theme.
2. **Add sources.** On Scan, choose Add folder for each location. Put preferred
   source folders first. Connect external drives before scanning. Removing a source
   from the list does not remove its files.
3. **Start the scan.** Progress shows counts and elapsed time. Stop cancels the
   scan. Missing drives, unreadable files and decoding failures are reported;
   incomplete or cancelled scans cannot authorize quarantine.
4. **Browse Duplicates.** Choose Exact Copies or Similar Photos, search filenames
   or paths, and open Review group. Use Previous pair / Next pair to review direct
   comparisons. Back to group (`Alt+Left`) returns to your results.
5. **Compare before choosing.** Expand Photograph details for full paths, hashes
   and recommendation explanations. Use Keep this photograph to propose a keeper,
   or Keep both to retain both. Browsing or opening a photograph does not approve
   a move. In exact groups, checked photographs remain; only explicitly reviewed,
   unchecked members enter the proposal.
6. **Read the move preview.** Move to quarantine prepares a plan showing the source,
   retained photograph and destination. Review every entry and warning. Only the
   explicit confirmation button approves movement; Cancel leaves files in place.
   RAW sources require the additional `RAW` confirmation token.

Double-click an individual preview, or use Open in Default Viewer, to ask your
system's associated application to open the file. RAW viewing depends on that
application. PhotoAgent cannot confirm that the external viewer displayed it.

CSV reports are written to `PhotoAgentReports` in your user home. Find their
location under Scan details. A report-writing failure is shown separately and does
not discard the scan results.

## Quarantine and restore

PhotoAgent **never permanently deletes photographs**. Approved moves go into
`.photo_agent_quarantine/YYYY-MM-DD/` inside the source root. This is movement on
the same filesystem, so **quarantine does not free disk space**. Cross-device
copy-and-delete movement is not used.

Before movement, PhotoAgent rechecks the source, keeper, paths, file identity and
full content hashes. Changed files, unsafe paths and existing destinations cause
the operation to be refused. Do not edit or reorganize the collection while a plan
is being confirmed or executed.

Bulk quarantine is restricted to eligible, decodable **EXACT** copies in the same
selected root, with neither RAW files nor XMP sidecars on either side. Cross-root
copies require individual review because they may be deliberate backups. Visual
matches always require review. XMP sidecars are never automatically moved.

To restore a photograph:

1. Open Quarantine history and select the eligible entry.
2. Prepare the restore, review the original destination and confirm explicitly.
3. Keep the source drive connected until the operation finishes.

A contextual Restore photograph action is also available after a single successful
move. If a file already occupies the original path, restore refuses to overwrite it.
Keep both files and resolve the conflict before retrying. History remains available
across application restarts.

If recovery is blocked after an interruption or disconnected drive, reconnect the
original storage and restart to recheck it. Preserve the journal and both recorded
file locations; do not erase history to force a move. See
[safety and recovery](docs/SECURITY.md).

## Settings, reports and moving to a new computer

Application data is stored in the current user's home folder, independently of the
application installation. On Windows this is usually `C:\Users\YourName`; on Linux,
`/home/yourname`.

| Location relative to your home folder | Purpose |
| --- | --- |
| `.photo_agent_state.json` | Preferences, source folders and legacy history |
| `.photo_agent_operations/` | Persistent operation manifests and recovery history; preserve this folder |
| `.photo_agent_index.sqlite3` | Rebuildable scan cache; not a replacement for recovery history |
| `PhotoAgentReports/` | CSV reports |

Each scanned root holds its own `.photo_agent_quarantine/` folder. Keep it with the
retained originals and recovery history. Maintain an independent photo backup.

For a **fresh installation on another computer**, transfer the application files,
install as above and add that computer's photo folders. Do not copy the old virtual
environment. Saved source paths from one computer may not exist on another.

For **existing quarantine history**, copying only the application or SQLite database
is insufficient. Close all PhotoAgent instances before backing up settings,
operation manifests and legacy backups together with the corresponding originals
and quarantine folders. Recovery depends on recorded paths and storage identity;
moving or renaming folders or drives can prevent automatic restoration. Restore
pending items on the original computer before migration where possible. See
[backup, upgrade and removal](docs/RELEASE.md#backup-upgrade-rollback-and-removal).

Use a new application folder for a compatible update and create its environment
there. Preserve home data and photo folders. Do not run an incompatible older
version against newer recovery history. There is no automatic upgrade or uninstall.

## Formats and practical limits

- Recognized standard extensions: JPEG, PNG, TIFF, BMP, WebP, HEIC/HEIF and AVIF.
- Recognized RAW extensions include NEF, CR2/CR3, ARW, DNG, RAF, ORF and RW2.
  Actual decoding depends on Pillow, pillow-heif and rawpy/LibRaw and the camera
  format. Recognition alone does not guarantee a working preview.
- Automated coverage includes PNG/JPEG/WebP and corrupt RAW. Successful valid RAW
  decoding and all HEIF/AVIF variants remain unverified.
- Decoding has a 100-megapixel and 60-second request limit; it is not a strict
  process-memory limit. Previews are bounded to 2048 pixels; preview 100% is not
  necessarily the original photograph's full resolution.
- Focus, noise and edit provenance are not measured. RAW+JPEG labels describe
  formats, not proof that both files share an original.
- Similarity sensitivity in Settings affects the next scan. Broader searches can
  include more false matches. Review choices belong to the current session;
  confirmed file-operation history is persistent.
- Native Linux, physical removable-media behavior, network filesystems, display
  scaling and power-loss resilience need further validation. Process-interruption
  tests do not prove physical power-loss safety.

## Troubleshooting

| Problem | What to check |
| --- | --- |
| `py` is not recognized, or Python 3.12 is missing | Install Python 3.12 with the Windows launcher, reopen PowerShell and retry `py -3.12 --version`. |
| Installation cannot download dependencies | Check connectivity for source installation, or use a complete offline bundle matching the destination platform and Python version. |
| A copied `.venv` cannot start Python | Use a fresh application folder and create its environment on this computer; virtual environments are not portable. |
| `venv` is unavailable on Linux | Provide your distribution's venv support for the selected Python version, then retry. |
| Qt fails to start or reports a platform-plugin error | Run the preflight command below and check the terminal error. Linux needs the native Qt platform libraries and a desktop session. |
| RAW/HEIF preview fails | Check codec and camera support. Read the scan error; an unavailable preview is not evidence that the file is disposable. |
| A drive is missing or a scan is incomplete | Reconnect the drive and run a complete scan before preparing moves. |
| Settings or moves are locked | Close other PhotoAgent instances. Only one instance may write settings/history or move files. |
| Restore reports a conflict or recovery warning | Preserve the files and journal, check the original destination and storage, and follow the recovery documentation. |

Read-only runtime check, from the source folder:

```powershell
.\.venv\Scripts\python.exe -B -m app.services.preflight --ui qt
```

On Linux, use `.venv/bin/python`. For an offline installation, use
`.runtime\Scripts\python.exe` instead of `.venv\Scripts\python.exe`.
To retain startup errors in the terminal, launch directly with the same interpreter
and `-B photo_agent.py`.

The older Serbian Tkinter interface is available from a source installation with
`--ui tk`, for example `start_windows.bat --ui tk` or
`bash start_linux.sh --ui tk`. It requires Tcl/Tk and does not offer the Qt language
switcher. Qt remains the default interface.

## Further documentation

- [Safety and recovery](docs/SECURITY.md)
- [Release preparation, offline verification and distribution limits](docs/RELEASE.md)
- [Opening photographs in the system viewer](docs/PHOTO_OPENING.md)
- [Testing commands, results and skipped checks](docs/TESTING.md)
- [Architecture](docs/ARCHITECTURE.md) and
  [changelog](docs/CHANGELOG.md)
- [Localization](docs/LOCALIZATION.md) and [Qt distribution notes](docs/QT_DISTRIBUTION.md)

For development, install `requirements-dev.txt` in the project environment and use
the commands in the testing guide. Automated tests use isolated synthetic files;
never point them at a real photo library.
