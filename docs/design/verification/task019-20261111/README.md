# Task019 — Quarantine and Settings — 2026-11-11

Windows, CPython 3.12.10, Qt Fusion/offscreen. All photographs, application homes,
settings, indexes, reports and journals are synthetic and temporary. Only the
generated fixtures are moved/restored, through explicit test/harness approvals.
No real libraries, packages, external services or account settings are used.

## Implemented behavior

- History has photograph, original location and status columns. Selected-item
  details show a verified optional thumbnail and origin. Operation ID, recorded
  source/destination, recorded move date, size and action expand on request.
- Pending/blocked recovery, recorded conflicts and unavailable storage retain
  readable messages outside technical disclosures. Restore failures survive
  history refresh. Missing file/root OS errors get a stable localized UI summary;
  the original OS diagnostics remain available. A failed thumbnail does not
  disable otherwise eligible restore preparation or erase operation selection.
- Completed restore records say Restored. The original quarantine record says
  Restore recorded when a restore intent/blocked/completed record references it;
  the UI does not claim a pending restore has completed. Stable operation IDs,
  existing restore preparation/confirmation and no-overwrite checks are retained.
- Recorded paths are explicitly historical. Open quarantine folder still opens
  the service-verified per-root folder. Photograph opening remains Task021.
- Settings has Appearance, Language, Scanning, Safety and Storage. Existing
  presets stay 2/3, 4/6 and 8/10; unrecognized pairs remain Custom. Source lists,
  numeric thresholds, protection and storage information use disclosures. No
  persisted setting, detection rule or safety-disable control is added.
- Theme/language still save automatically; sensitivity still uses Save for the
  next scan. Failed writes restore the latest successful preference snapshot,
  including a successful write superseded by a later queued theme request.
  Errors remain visible on Settings. New disclosures participate in Tab order.

## Executed checks

All commands use the existing `.venv/Scripts/python.exe -B` interpreter. The
Windows Store interpreter requires execution outside this session's sandbox;
the existing project environment was used without installing dependencies.

Early focused runs:

```powershell
$env:QT_QPA_PLATFORM='offscreen'
.venv/Scripts/python.exe -B -m pytest tests/test_task009.py -q
# 13 passed in 91.97s
.venv/Scripts/python.exe -B -m pytest tests/test_task019.py -q
# 20 passed in 123.08s
$env:QT_SCALE_FACTOR='1.5'
.venv/Scripts/python.exe -B -m pytest tests/test_task019.py -q
# 20 passed in 117.43s, before the final missing-file summary/focus refinement
```

The first broader regression command was:

```powershell
.venv/Scripts/python.exe -B -m pytest tests/test_localization.py tests/test_operations.py tests/test_recovery.py tests/test_native_races.py tests/test_task012.py tests/test_qt_design_system.py -q
# 83 passed, 1 failed, 1 skipped in 243.65s
```

The sole failure was the old history localization assertion reading column 4;
the redesigned status is column 2 and says In quarantine for an active record.
That assertion was updated, retaining the in-place language/selection checks.
The already-running process retained the old test bytecode while its failure
trace displayed the edited source line. The skip is native Linux no-replace
execution on Windows (`tests/test_native_races.py:116`). Other safety/recovery
tests in that run passed. No successful run is inferred from an earlier task.

Translation build/check:

```powershell
.venv/Scripts/python.exe -B -m tools.build_translations
.venv/Scripts/python.exe -B -m tools.build_translations --check
# 454/454 finished messages in each language; exit 0
```

Final Task019 run after all production changes:

```powershell
$env:QT_QPA_PLATFORM='offscreen'
$env:QT_SCALE_FACTOR='1.5'
.venv/Scripts/python.exe -B -m pytest tests/test_task019.py -q
# 20 passed in 119.78s; no skips
```

Final combined run at 100%, including the corrected history assertion, all new
tests, existing Task009 restore/settings, compiled/fallback localization and
Task010 keyboard/consent/accessibility regressions:

```powershell
$env:QT_QPA_PLATFORM='offscreen'
$env:QT_SCALE_FACTOR='1'
.venv/Scripts/python.exe -B -m pytest tests/test_task019.py tests/test_task009.py tests/test_localization.py tests/test_task012.py::test_history_and_error_dialog_retranslate_in_place tests/test_task010.py -q
# 55 passed in 438.14s; no skips
```

`git diff --check` passes. Review confirms no changes under safety, matching,
storage or scanning, and the preset numeric values remain unchanged.

## Captures and review

```powershell
$env:QT_QPA_PLATFORM='offscreen'
$env:QT_SCALE_FACTOR='1'
.venv/Scripts/python.exe -B -m tools.capture_task019 --output docs/design/verification/task019-20261111/100
$env:QT_SCALE_FACTOR='1.5'
.venv/Scripts/python.exe -B -m tools.capture_task019 --output docs/design/verification/task019-20261111/150
```

Each final run produces 14 captures. Real service workers scan generated PNG
copies, prepare/confirm quarantine, reject a synthetic destination collision,
observe a renamed/disconnected synthetic root, then prepare/confirm restoration.
Both original byte sequences are verified after restoration. Expected worker
error logs for collision/offline cases are evidence of rejection, not failed
capture runs. The tool switches the actual preference selectors and waits for
persistence; displayed language/theme choices match the captured presentation.

[100/manifest.json](100/manifest.json) and [150/manifest.json](150/manifest.json)
record screenshot SHA-256, dimensions, DPR and layout checks. All 28 hashes and
dimensions match; there is no page horizontal overflow, toolbar overlap or action
outside the window. EN/Dark uses 1280×900 and SR/Light uses 853×480 logical pixels.
[review.json](review.json) records the independent artifact checks. Both contact
sheets ([100](100/review.png), [150](150/review.png)) were visually inspected,
alongside full-size active, settings, offline and storage samples. Small windows
use vertical scrolling; technical paths remain selectable in disclosures.

The earlier 100% capture draft used direct presentation switches, leaving the
Settings selectors unchanged, and had a generic missing-file message. It was
replaced by the final captures above; the draft is ignored under build/.

## Files and limits

Changed production code: `app/ui/qt/{quarantine_settings,window,controller,workers}.py`.
Translations: both TS sources and generated JSON/QM/embedded resources; inventory
in `docs/design/QT_TEXT_INVENTORY.json`. Tests: `test_task019.py` and the updated
history localization assertion in `test_task012.py`. Added capture tooling and
this evidence directory, with a `.gitignore` exception. Updated both READMEs,
ARCHITECTURE, CHANGELOG, LOCALIZATION, SECURITY and TESTING documentation.

Safety operations, matching thresholds, journal format, SQLite schema and decoder
are unchanged. No full-suite/release/package run, native Linux, real drives/photo
libraries, physical DPI transitions, screen reader, valid RAW or power-loss check
was performed. Recovery status presentation uses typed synthetic history entries;
the existing recovery tests exercise the actual journal paths. System-theme
preference persistence is tested; physical OS theme-change transitions remain
outside this offscreen run. External photograph opening is deferred to Task021.
