# Task020 — Photo-first review — 2026-11-11

Windows CPython 3.12.10, PySide6 6.12.0, Qt Fusion/offscreen. All photographs,
application homes, settings, indexes, reports and journals are temporary synthetic
fixtures. No packages were installed and no real photo library was accessed.
The existing Windows Store Python required execution outside the process sandbox.

## Implemented behavior

- Review remains inside the existing five-route Duplicates flow. Back and direct
  pair navigation share a compact toolbar. Filename, format, dimensions and size
  precede aligned previews with a minimum height of 240 logical pixels. Narrow
  windows stack the photos and scroll; zoom, Fit and enlarged preview remain.
- Suggested keeper, explicit retention and proposed quarantine have separate
  labels. EXACT suggestions explain source/path ordering; VISUAL suggestions
  retain the existing heuristic and its uncertainties. Full paths, SHA-256,
  pHash/dHash and explanations are in expandable photograph details.
- The decision and action row stays outside the photo scroll area. It shows the
  count and first three selected copy names, with all selected paths in its
  tooltip and in confirmation. Keep Both clears the proposal and marks both
  photographs retained, including in the member table. No choice moves a file.
- Previous/Next pair and the selector traverse stored direct links, paging as
  needed. Merely browsing never adds an unseen copy to the plan. Visual choices
  remain specific to one direct pair; no transitive edges are inferred. The
  existing bounded EXACT multiple-keeper behavior is retained.
- Move to quarantine still calls the existing service preflight and opens the
  frozen PlanDialog. Explicit approval remains mandatory. RAW/backup/derivative
  warnings remain outside disclosures. XMP protections, sidecar warnings in the
  prepared plan, RAW consent, full identity/hash/containment checks and restart
  recovery remain in the unchanged safety/service layers.
- Member/group/filter/scan changes invalidate plans. Preview request IDs reject
  late results. Returning restores list query, page, selected pair, scroll and
  focus. Context restore still prepares a separate confirmed restore plan.

## Executed checks

All Python commands use `.venv/Scripts/python.exe -u -B` with
`QT_QPA_PLATFORM=offscreen`. Results below distinguish intermediate checks from
final verification; interrupted/failed runs are not counted as passes.

```powershell
.venv/Scripts/python.exe -u -B -m pytest tests/test_task020.py -x -q -o faulthandler_timeout=120
# Intermediate: 14 passed in 331.23s, before the final compact header/toolbar
# refinement and the final VISUAL Keep Both member-table annotation.

.venv/Scripts/python.exe -u -B -m pytest tests/test_operations.py tests/test_recovery.py tests/test_additional_safety.py tests/test_native_races.py -q -o faulthandler_timeout=120
# 40 passed, 1 skipped in 39.13s. Native Linux no-replace cannot run on Windows.

.venv/Scripts/python.exe -u -B -m pytest tests/test_task020.py::test_initial_compact_header_and_pair_selector_localize -q -o faulthandler_timeout=120
# 1 passed in 3.40s, DPR 1.

$env:QT_SCALE_FACTOR='1.5'
.venv/Scripts/python.exe -u -B -m pytest tests/test_task020.py::test_initial_compact_header_and_pair_selector_localize tests/test_task020.py::test_visual_direct_links_keep_both_and_recommendation_are_separate -q -o faulthandler_timeout=120
# 2 passed in 7.83s, after the final VISUAL annotation correction.

.venv/Scripts/python.exe -u -B -m pytest tests/test_task020.py -q -o faulthandler_timeout=120
# Task020, DPR 1.5: 15 passed in 356.92s, no skips, before adding long-name case.

.venv/Scripts/python.exe -u -B -m pytest tests/test_task020.py::test_long_copy_names_do_not_displace_bottom_actions 'tests/test_task020.py::test_photos_choices_sticky_footer_and_keyboard[light-sr_Latn]' -q -o faulthandler_timeout=120
# Final filename elision / expanded-sidebar case: 2 passed in 31.27s, DPR 1.5.

.venv/Scripts/python.exe -u -B -m tools.build_translations
.venv/Scripts/python.exe -u -B -m tools.build_translations --check
# 467/467 finished messages per language, no unfinished entries; TS/JSON parity.
```

The combined Qt/review/localization run at DPR 1 completed successfully:

```powershell
.venv/Scripts/python.exe -u -B -m pytest tests/test_task020.py tests/test_task008.py tests/test_task010.py tests/test_task018.py tests/test_qt.py tests/test_task012.py tests/test_localization.py -q -o faulthandler_timeout=120
# 98 passed in 1405.02s (23:25), no skips.
```

It was started after the compact layout refinement and before the last
VISUAL Keep Both member-table annotation; the complete DPR 1.5 run above includes
that correction and the extra initial-header test. The last filename-only UI
refinement elides each of the first three copy names to 200 logical pixels;
complete paths remain in the tooltip/confirmation. The last focused two-case
run verifies three long synthetic names with expanded sidebar at 853×480, then
rechecks ordinary SR/Light choices and keyboard behavior. No service code changed.

Early diagnostics: the first broad Qt invocation was interrupted after producing
one dot. A separate Task008 run with a 30-second faulthandler timeout ended with
a Windows access violation while the preview thread read package metadata. This
was not a passing run or a conclusively diagnosed root cause. Subsequent runs use
120 seconds for diagnostic dumps. New-test failures exposed a hidden Restore
button incorrectly included in a geometry assertion, a test indentation error,
and the need to stack photos at narrow widths; those were corrected. Capture
driver failures were an incorrect `review_results` argument and a missing wait
for filter debounce. A transient clipped first header frame prompted explicit
layout activation/assertions in the capture tool and a focused header test;
the verified replacement first frame is complete.

## Captures and manual inspection

```powershell
$env:QT_SCALE_FACTOR='1'
.venv/Scripts/python.exe -u -B -m tools.capture_task020 docs/design/verification/task020-20261111/100-verified
$env:QT_SCALE_FACTOR='1.5'
.venv/Scripts/python.exe -u -B -m tools.capture_task020 docs/design/verification/task020-20261111/150
```

Each run completed 16 real-window captures. The EXACT matrix is EN/SR ×
Dark/Light × 1440×900 / 853×480 logical pixels, with extra bottom-scroll narrow
views. Additional captures show Keep Both, confirmation, VISUAL and a RAW/backup
warning fixture. That fixture changes presentation metadata only and never
approves or moves a fake RAW file. Each driver rejects a plan, verifies unchanged
bytes, explicitly approves one generated file's quarantine, explicitly approves
its restore and verifies every original byte afterward.

Representative full-size images were manually inspected for both languages,
themes, narrow/wide widths and both DPR values. See `review.json` for the exact
inspected filenames and artifact hash/dimension checks. Narrow windows intentionally
use vertical scrolling; the toolbar and bottom operation controls stay reachable.
Ellipsized filenames remain literal and have complete paths in Details/confirmation.

## Changed files and limits

- UI: `app/ui/qt/screens.py`, `components.py`, `window.py`.
- Localization: EN/SR TS sources, JSON fallbacks, QM catalogs and embedded
  `app/i18n/resources_rc.py`; `docs/design/QT_TEXT_INVENTORY.json`.
- Tests/tools: `tests/test_task020.py`, `tools/capture_task020.py`.
- Documentation: README/README_SR, ARCHITECTURE, CHANGELOG, LOCALIZATION, TESTING,
  this evidence directory, `.gitignore`, and local ignored `task/Task020.md` status.

No service, decoder, matching, safety, database schema or journal format changed.
`git diff --check` passes. The artifact integrity script
`.venv/Scripts/python.exe -B .benchmarks/verify_task020.py` validates all 32 retained
captures and records the 11 inspected originals in `review.json` (the small
one-off script stays in the ignored workspace benchmark directory).
No full-suite/release/packaging run, native Linux, physical monitor/DPI transition,
screen reader, real drive/library, valid RAW decode or power-loss test was performed.
Photo opening remains Task021. The early native Qt crash is recorded above; these
offscreen checks do not certify native platform acceptance.
