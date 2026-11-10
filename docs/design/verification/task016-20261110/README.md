# Task016 verification — 2026-11-10

Environment: Windows, existing CPython 3.12.10 / PySide6 6.12.0, Fusion,
`QT_QPA_PLATFORM=offscreen`. No packages installed. All application homes,
settings, databases, journals, reports and photographs were isolated synthetic
fixtures. No real collection was read or modified.

## Implementation

- `app/ui/qt/navigation.py`: default 64 px icon rail, 208 px expanded labels,
  nonblocking 160 ms reversible animation, 44 px controls, keyboard toggle,
  localized accessible names/tooltips/state, persistent selected shape marker.
- `app/ui/qt/window.py`: include the toggle before the five destinations in the
  existing visual Tab chain. No navigation or service call during resizing.
- `app/ui/qt/themes.py`: centered compact glyphs, subtle checked surface without
  a decorative outline, retained contrasting focus outline.
- `app/i18n/en.ts`, `sr_Latn.ts`: two new action messages; generated JSON, QM and
  `resources_rc.py` rebuilt with the existing translation tool (420 keys each).
- `tests/test_task016.py`: focused interaction/state checks;
  `tests/test_qt.py`: replace the obsolete fixed 208 px startup expectation.
- `tools/capture_task016.py`: real-window capture driver using disposable
  generated PNG originals. Never approves or performs a move.
- `.gitignore`: allow the Task016 verification directory alongside prior evidence.
- README/README_SR, ARCHITECTURE, CHANGELOG, TESTING, ACCESSIBILITY, text inventory
  and Task016 status document the implemented behavior and verification limits.

No matcher, index/schema, decoder, quarantine, restoration, approval, recovery,
file-verification or worker implementation changed.

## Executed focused checks

```powershell
$env:QT_QPA_PLATFORM='offscreen'
.venv/Scripts/python.exe -B -m tools.build_translations
# 420 finished entries per language; JSON/QM/embedded resources regenerated.
.venv/Scripts/python.exe -B -m tools.build_translations --check
# en: 420/420; sr_Latn: 420/420; exit 0.
.venv/Scripts/python.exe -B -m pytest tests/test_task016.py tests/test_qt_design_system.py -q
# 31 passed in 60.25s; exit 0, no skips.
$env:QT_SCALE_FACTOR='1.5'
.venv/Scripts/python.exe -B -m pytest tests/test_task016.py -q
# 6 passed in 56.30s; exit 0, no skips.
```

An earlier focused run had 5 passes and one test failure (60.36s): the new scan
test incorrectly assumed `start_scan()` navigates from Dashboard to Scan. The
fixture now explicitly opens Scan first. No product behavior was changed to
accommodate that assumption. Both final focused commands above passed afterwards.

Coverage includes all five routes in Dark/Light × EN/SR, 1280×720 and 853×480
logical layouts, native checked/focusable accessibility state, action names,
state descriptions, tooltip bindings, label fit, minimum click targets,
Tab/Shift+Tab via existing regressions, Enter/Return/Space, focus paint and
selection marker after focus leaves. Locale changes do not reveal hidden labels.

The real synthetic comparison keeps its filters/query, pair/group context,
selected rows, retained choice, preview generation, pending pair, nonzero scroll
and original page instances through repeated resizing. No service requests are
emitted. An open real plan confirmation keeps its frozen plan, Cancel focus and
unapproved state. Original fixture bytes remain identical. A paused real scan
worker survives repeated mid-animation reversals while a Qt heartbeat continues;
the same scan completes normally and route changes retain the sidebar mode.

## Captures and review

```powershell
$env:QT_SCALE_FACTOR='1'
.venv/Scripts/python.exe -B -m tools.capture_task016 --output docs/design/verification/task016-20261110/100
$env:QT_SCALE_FACTOR='1.5'
.venv/Scripts/python.exe -B -m tools.capture_task016 --output docs/design/verification/task016-20261110/150
# Each command: 16 captures; synthetic originals unchanged; no approvals; exit 0.
```

[100% manifest](100/manifest.json) and [150% manifest](150/manifest.json) record
SHA-256, DPR, logical/physical sizes, scroll ranges and toolbar geometry. Each
contains both modes on all five EN/Dark routes plus Compare, and SR/Light Scan
and Compare. Windows are 853×480 logical pixels: 853×480 physical at DPR 1 and
1280×720 physical at DPR 1.5. Every capture passed sidebar containment, no page
horizontal scrolling, no toolbar overflow and no toolbar overlap assertions.

Eight representative saved renders were visually inspected:

- [100% EN/Dark expanded Dashboard](100/en-dark-dashboard-expanded.png)
- [100% SR/Light compact Compare](100/sr_Latn-light-compare-compact.png)
- [150% EN/Dark compact Duplicates](150/en-dark-duplicates-compact.png)
- [150% SR/Light expanded Compare](150/sr_Latn-light-compare-expanded.png)
- [150% EN/Dark expanded Settings](150/en-dark-settings-expanded.png)
- [100% EN/Dark expanded Scan](100/en-dark-scan-expanded.png)
- [100% EN/Dark compact History](100/en-dark-history-compact.png)
- [150% SR/Light expanded Scan](150/sr_Latn-light-scan-expanded.png)

Logo, localized navigation labels, selected marker, keyboard outline and bottom
Settings remain legible and contained. Narrow expanded Compare uses the existing
stacked layout; vertical scrolling makes the rest of the page available. Existing
gallery thumbnail loading and long report-path presentation remain outside this
navigation task.

## Existing Qt and localization regressions

```powershell
$env:QT_QPA_PLATFORM='offscreen'
.venv/Scripts/python.exe -B -m pytest tests/test_qt.py tests/test_task008.py tests/test_task009.py tests/test_task010.py tests/test_task011.py tests/test_task012.py tests/test_localization.py -q -o faulthandler_timeout=120
# 89 passed in 905.08s (15m05s); exit 0, no skips. Default DPR 1.
```

This includes existing five-route/toolbar/keyboard checks, compare/back context,
scan heartbeat/cancellation/close, explicit plan approval/rejection, synthetic
quarantine/restore/restart/conflict, settings, runtime locale and compiled catalog
fallback/parity checks. No test timeout limit was increased to obtain a pass;
`faulthandler_timeout` requests diagnostics and does not alter worker/test waits.
Final `git diff --check` passed. All 32 capture SHA-256 values were independently
recomputed from the saved PNGs and matched their manifests.

## Limits

Offscreen rendering and QAccessible queries are not native assistive-technology
acceptance. Physical high-DPI displays, real OS theme events, NVDA/Narrator and
native Linux remain unverified. No new packaging build, valid RAW asset or real
photo-library test was run. Collapse state intentionally lasts only for the
current window session. An open modal confirmation blocks pointer interaction
with the sidebar; its preservation test invokes the resize API directly.
