# Task017 — Dashboard and Scan verification — 2026-11-10

Environment: Windows, CPython 3.12.10, Qt/Fusion offscreen. All application homes,
Qt settings, indexes, journals and photographs in these checks are disposable
synthetic fixtures. No real collection, quarantine approval or file move was
used by the new tests/capture tool. Existing quarantine/restore regression tests
use their own synthetic fixtures and explicit test approvals.

## Implemented behavior

- Dashboard starts with first-scan guidance or the latest session and a next
  step. Its primary action changes between Scan and Review duplicates using
  session status and actual candidate counts. During scanning review is disabled.
- Cards distinguish indexed physical photographs, EXACT candidate copies,
  VISUAL direct pairs and EXACT groups. Session measurements are unavailable
  before the first scan. No savings estimate is displayed.
- Add folder is available in the Scan toolbar, including an empty collection.
  Each source retains its full path in tooltip/accessibility and a named remove
  control. Copy/tooltip explains that removal affects only the source list.
- Advanced ordering, detailed counters, reports and technical errors use the
  existing disclosure components. Important source/report warnings and error
  summaries remain outside hidden technical content. Tab reaches Reports after
  opening Scan details.
- Ready, running, complete with/without candidates, incomplete, cancelled and
  failed scans have distinct guidance. Existing worker/cancellation/generation
  checks remain. An attempt cancelled during source checks survives a late
  source response and refresh; retry can produce a new successful session.
- Rebinding primary/secondary action icons preserves contrast in both themes.
  Matching, traversal, indexing, recovery and quarantine algorithms are unchanged.

Changed files: `app/ui/qt/dashboard_scan.py`, `window.py`, `components.py`;
`app/i18n/en.ts`, `sr_Latn.ts` and generated JSON/QM/`resources_rc.py`;
`tests/test_task017.py`, `test_qt.py`, `test_localization.py`;
`tools/capture_task017.py`; `.gitignore` (include this evidence directory);
`README.md`, `README_SR.md`, `docs/ARCHITECTURE.md`, `CHANGELOG.md`,
`LOCALIZATION.md`, `TESTING.md`, `docs/design/DESIGN_SYSTEM.md`,
`QT_TEXT_INVENTORY.json`, this record and captures. The local ignored
`task/Task017.md` also records completion and verification limits.

## Commands

```powershell
$env:QT_QPA_PLATFORM='offscreen'
.venv/Scripts/python.exe -B -m tools.build_translations
.venv/Scripts/python.exe -B -m tools.build_translations --check
```

434/434 finished messages in each language; editable TS, generated JSON/QM and
embedded resources agree. No tool downloaded packages or contacted a service.
Windows Store Python requires execution outside this environment's filesystem
sandbox; the existing environment was used without installation or repair.

New coverage in `tests/test_task017.py` exercises EN/SR × Dark/Light, narrow/wide
layouts, real overlapping roots, a missing source, removal without file changes,
pre-session cancellation, late responses and retry. Existing tests check worker
thread ownership, heartbeat/cancellation, stale previews, failed and empty scans,
explicit plans, localization, System themes and the retained Tk interface.

Executed regression command during implementation:

```powershell
.venv/Scripts/python.exe -B -u -m pytest -q tests/test_qt.py tests/test_task012.py tests/test_task016.py tests/test_task017.py tests/test_ui.py tests/test_scanning.py tests/test_localization.py tests/test_qt_design_system.py
# 108 passed, 3 failed in 633.53s; no skips.
```

The failures identified a source accessibility label overwritten with historical
scan completion, an old savings-card assertion, and TS/runtime parity while a
translation rebuild overlapped that early process. The source label mapping and
metric assertion were corrected; catalogs were finalized before fresh checks.
An intermediate label rerun still failed because the mapping had been applied
to progress instead of finish; the final mapping is confined to finish.

Final focused commands, in fresh processes:

```powershell
$env:QT_SCALE_FACTOR='1'
.venv/Scripts/python.exe -B -u -m pytest -q tests/test_task017.py tests/test_qt_design_system.py tests/test_localization.py tests/test_qt.py::test_report_failure_does_not_change_scan_result_and_no_matches_is_distinct
# 42 passed in 130.69s; exit 0, no skips.
$env:QT_SCALE_FACTOR='1.5'
.venv/Scripts/python.exe -B -u -m pytest -q tests/test_task017.py
# 6 passed in 63.94s; exit 0, no skips.
$env:QT_SCALE_FACTOR='1'
.venv/Scripts/python.exe -B -u -m pytest -q tests/test_task012.py::test_live_pages_filters_models_previews_and_restart tests/test_task017.py
# 7 passed in 89.07s after the final source-label correction; no skips.
```

Earlier diagnostic runs also exposed a removed `size_text` re-export used by the
gallery and the absence of an enabled empty-Scan toolbar action. Keeping that
compatibility import and moving Add folder to the toolbar corrected both;
the corresponding existing Qt tests passed in the regression above. One early
quiet diagnostic batch was interrupted; it is not counted as passing evidence.
The entire 111-test command was not repeated after focused corrections.

## Captures

```powershell
$env:QT_SCALE_FACTOR='1'
.venv/Scripts/python.exe -B -m tools.capture_task017 --output docs/design/verification/task017-20261110/100
$env:QT_SCALE_FACTOR='1.5'
.venv/Scripts/python.exe -B -m tools.capture_task017 --output docs/design/verification/task017-20261110/150
```

The tool captures actual Qt windows and workers. Empty and completed Dashboard
and Scan have EN/SR × Dark/Light × 853×480/1440×900 logical coverage. Further
captures show a successful scan without candidates, corruption plus unavailable
storage, active work, cancellation, failure and expanded error details.
Extraction is paused to capture active work; failure injects a service exception
before session creation. These two injections are identified in each manifest.

Each normal capture asserts no page horizontal scroll, toolbar overlap or
toolbar overflow. Manifests record language/theme, scan state, dimensions, DPR,
layout measurements and SHA-256. Expanded errors are an additional screenshot
outside the manifest. The tool checks original synthetic photograph bytes and
closes all workers before removing its temporary home.

Both final capture commands exited 0: **39 manifest captures plus expanded
errors at each scale (80 PNGs total)**. Expected `qt_service_failure` log entries
come from the deliberately injected failure, not a capture failure. An independent
read verified all 80 PNG files, all 78 recorded SHA-256 hashes, DPR/physical size
agreement, and all recorded toolbar/page layout assertions.

Representative final renders visually inspected include:

- [EN/Light wide Scan, 100%](100/complete-en-light-1440-scan.png): successful
  results, primary Review, available source, full path and collapsed sections.
- [SR/Dark narrow Dashboard, 150%](150/complete-sr_Latn-dark-853-dashboard.png):
  primary Review, latest-session guidance and two-column metric layout.
- [Expanded errors, 100%](100/errors-expanded.png): explicit count and selectable
  raw error details after scrolling; long diagnostics require further scrolling.

Earlier representative reviews also covered empty, no-match, unavailable-source,
active, cancelled and failed states. Vertical scrolling on short windows is
intentional. Final `git diff --check` passed; no core/scanning/matching/storage/
safety/service source files changed. No commit or push was created.

## Limits

Offscreen Windows/Fusion rendering is not native Linux, physical monitor DPI,
real OS theme events or NVDA/Narrator acceptance. No new installer/package build,
real removable drive or valid RAW asset was tested. The service still supplies
indeterminate progress rather than an invented total/percentage. Long source
lists and technical details intentionally require vertical scrolling. Dashboard
candidate thumbnail loading keeps its existing asynchronous behavior; loading
placeholders in captures are not a claim of successful decoding.
