# Task013: local release candidate

Requested 2026-11-09; owner selected **source ZIP + offline wheelhouse**. This
replaces the historical task deferral. Version remains 2.4. There is no public
release, frozen executable, bundled Python, automatic upgrade or uninstall.

## Contents and target

Allowlisted `app/` sources, `photo_agent.py`, EN/SR JSON catalogs, compiled Qt SVG
resources, offline installer/launchers, synthetic rehearsal, documentation, complete
runtime wheels, wheel license/notice bytes and `release-manifest.json` are included.
User photos/state/databases/quarantine, `.git`, development `.venv`, tests and
screenshots are excluded. See [ARCHITECTURE.md](ARCHITECTURE.md) for actual modules.

Reference: **CPython 3.12 / Windows AMD64**, exact 13-distribution lock in
`packaging/runtime-win-amd64-py312.txt`. Complete upstream Qt Addons/Pdf/WebEngine
wheels are included because PySide6 requires them, even though the app does not
import those features. Python/standard library/OS runtimes are external prerequisites.
Linux requires a separate native lock, wheelhouse and acceptance run. The Windows
ZIP is refused on other platforms/Python minor versions.

Discovery accepts JPEG/PNG/TIFF/BMP/WebP/HEIC/HEIF/AVIF and RAW extensions listed in
`app/scanning/decoder.py`. Recognition does not prove successful decoding. Multiframe,
oversized, corrupt and unsupported files do not become bulk candidates. Native valid
RAW and all HEIF/AVIF variants remain unverified. Tests cover PNG/JPEG/WebP and bad RAW.

## Build

Run these build commands from the repository. Download is an explicit online
step; the builder never downloads or installs:

```powershell
.venv/Scripts/python.exe -B -m pip --disable-pip-version-check download --only-binary=:all: --no-cache-dir --dest build/task013-wheelhouse -r packaging/runtime-win-amd64-py312.txt
.venv/Scripts/python.exe -B -m tools.build_release --wheelhouse build/task013-wheelhouse --lock packaging/runtime-win-amd64-py312.txt --output dist/PhotoAgent-2.4-win-amd64-py312-candidate.zip
Get-FileHash -Algorithm SHA256 dist/PhotoAgent-2.4-win-amd64-py312-candidate.zip
```

Choose a new output on repetition. Build refuses overwrite, redirected inputs,
missing/extra/repeated/wrong-version wheels. Manifest records build OS/Python,
dependency metadata, wheel/source/data SHA-256 and open gates. Requirements pin
every wheel with SHA-256; notices are copied verbatim. This is not a signed package
or a certification of licensing/platform readiness.

Reproduce extraction, offline installation and native Qt rehearsal from a base
Python (not the development venv) with:

```powershell
.venv/Scripts/python.exe -X utf8 -B -m tools.verify_release --archive dist/PhotoAgent-2.4-win-amd64-py312-candidate.zip --output build/task013-verification
```

Output must be new. The verifier rejects unsafe ZIP entries, records artifact SHA,
and retains install/smoke logs and phase results. `--offscreen` is optional and must
not be reported as native platform-plugin acceptance. It still uses this host's
base Python/OS and does not provision a clean Windows or Linux machine.

## Offline install and launch

Extract to a NEW writable directory. Install Python 3.12 x64 separately before
disconnecting. Compare the ZIP checksum to a separately retained build checksum;
the internal manifest detects damage, not malicious replacement of an unsigned ZIP.

```powershell
py -3.12 -B install_offline.py
start_offline.bat
```

Installer checks recorded Python/platform and all manifest hashes, creates a new
`.runtime` without system site packages, installs only local wheels with
`--no-index --no-cache-dir --only-binary=:all: --require-hashes`, then runs `pip check`
and Qt preflight. It never queries an index or modifies an existing `.runtime`.
After a partial failure extract a fresh directory. Packaged launchers ignore Python
environment/user-site injection and never run pip. Existing repository launchers
retain their development bootstrap behavior and are not included in the ZIP.
A fresh venv on this host is not clean-machine acceptance.

## Synthetic installed-runtime rehearsal

```powershell
.runtime/Scripts/python.exe -B tools/release_smoke.py --output smoke-čćž
```

Output must be NEW. Four generated PNG/JPEG/WebP files, HOME/state/journal/index,
reports, Qt INI settings and decoder temp files stay in that output. Phases check
cold/warm scans with zero warm decodes, malformed RAW, settings restart, explicitly
approved EXACT quarantine, process exit 73 after native movement before journal
completion, restart reconciliation, occupied restore refusal, byte-identical restore
and a real MainWindow using EN/SR and Dark/Light/System. Original fixture hashes
must match afterward. Each phase retains its log; unfinished output is not passed.
The tool requires the extracted `.runtime`, runs children outside the app directory
and rejects development `.venv` imports. It accepts no existing photo collection.

Python socket audit hooks deny socket connection/address/bind/send events in phase
and decoder children. This is a diagnostic guard, not an OS firewall for native DLLs
or proof of physical disconnection. Clean-machine offline acceptance stays open.
The app adds no network/account/telemetry features.

## Backup, upgrade, rollback and removal

Close all instances. Preserve `~/.photo_agent_operations/`,
`~/.photo_agent_state.json` and legacy backups together with every root's
`.photo_agent_quarantine/` and retained originals. Copy consistently with no active
writer; retain paths/media identity. SQLite is disposable; the journal is recovery
authority. Never retain only the index. See [SECURITY.md](SECURITY.md).

Extract compatible updates beside old builds; installation never reads or deletes
home history/photo libraries. Do not run incompatible old writers on newer history;
keep a compatible recovery reader. No uninstall/cleanup action is provided. Manual
removal must preserve libraries, quarantine, home journal/state/backups and any
needed smoke evidence. No procedure here authorizes deletion of photographs.

## Dependency/license assessment (2026-11-09)

The repository has no selected application license. **Public redistribution remains
blocked** until the owner chooses one and artifact-specific obligations, including
corresponding sources/offers, are satisfied. No license is selected automatically.

| Included component | Assessment and remaining work |
|---|---|
| PySide6/Qt/shiboken 6.12.0; Pdf/WebEngine 6.12.0.140 | Whole wheels include unused modules/tools. Preserve module/third-party notices; assess GPL-only parts and LGPLv3 replacement/relinking and source obligations. |
| rawpy 0.28.0 / LibRaw | Wrapper is MIT; LibRaw offers LGPL 2.1/CDDL 1.0 choices. Inspect actual binary notices and codec/runtime components; wrapper metadata alone is insufficient. |
| pillow-heif 1.8.1 | Python source is BSD-3-Clause. Upstream binary notice identifies GPLv2 from x265 alongside LGPL libheif/libde265 and Windows runtime notices. Do not label the wheel BSD-only or assume Qt's LGPL option resolves compatibility. |
| Pillow 13.0.0 | MIT-CMU metadata plus bundled codec notices; retain full wheel notices. |
| ImageHash 4.3.2, PyWavelets 1.10.0, NumPy 2.5.4, SciPy 1.18.1 | BSD/MIT and bundled-library/runtime licenses, including OpenBLAS where present. Actual wheel metadata and notice bytes are captured. |
| Python/OS runtime | External prerequisite. Review separately if embedding later. |

Official sources reviewed: [Qt licensing](https://doc.qt.io/qt-6/licensing.html),
[Qt for Python licenses](https://doc.qt.io/qtforpython-6/licenses.html),
[Qt LGPL obligations](https://www.qt.io/development/open-source-lgpl-obligations),
[rawpy license](https://github.com/letmaik/rawpy/blob/main/LICENSE),
[LibRaw licensing](https://www.libraw.org/docs),
[pillow-heif bundled licenses](https://github.com/bigcat88/pillow_heif/blob/master/LICENSES_bundled.txt).
Main branches can differ from shipped versions; actual wheel metadata/notices take
precedence. This engineering inventory does not constitute legal clearance.

## Release status

Executed results: [TESTING.md](TESTING.md). Candidate stays **not release ready**.
Required open gates:

- Clean Windows 10/11 OS install/launch/permissions/offline/upgrade/removal and
  removable-filesystem/drive matrix.
- Native Linux distro/filesystem/plugin matrix and complete safety regressions.
- Licensed valid RAW fixture and successful native RAW decoder acceptance.
- Physical monitor/DPI/assistive-technology acceptance.
- Completed 1k/10k cold/warm/changed and baseline comparisons with 125% budgets;
  interrupted old attempts are not results and this gate is not waived.
- Application-license and artifact-specific notice/source/offer decisions.

Tooling changes do not change matching/SHA verification, schema/journal formats,
RAW/XMP/backup protection, approval or native move primitives. Publication is separate.
