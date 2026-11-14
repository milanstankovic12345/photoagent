# Task022 — Clear EN/SR workflow wording — 2026-11-14

Windows CPython 3.12.10 / PySide6 6.12.0 / Qt Fusion offscreen. Every photograph,
application home, settings file, index, report and operation journal used for
verification was synthetic and isolated. Windows Store Python required execution
outside the process sandbox. No packages were installed, no real collection was
used, and no OS viewer was launched.

## Scope and files

- `app/i18n/en.ts`, `sr_Latn.ts`: consistent action names, clearer explanations,
  proposal/preparation/approval/results and restore direction. Six new stable keys;
  existing keys, placeholder contracts and plural rules retained.
- Generated `en.json`, `sr_Latn.json`, `en.qm`, `sr_Latn.qm`, `resources_rc.py`:
  built with the existing translation tool. Both languages have **480/480**
  finished messages. All 480 English intents match `QT_TEXT_INVENTORY.json`.
- `app/ui/qt/components.py`: bound photo Show/Hide Details action, preparation
  and restore tooltips, final-confirmation description and restore plan summary.
- `app/ui/qt/screens.py`: Keep Both describes clearing a proposal without moving.
- `app/ui/qt/window.py`: successful restore and quarantine messages are distinct.
  No scanning, matching, SQLite, move verification or recovery code changed.
- `tests/test_task022.py`: vocabulary/inventory and live state/focus/consent tests.
  `tests/test_localization.py`: assert the new restore-direction summary.
- `tools/capture_task022.py`: disposable real-window capture driver, preserving
  synthetic bytes; no confirmation is approved. RAW/legacy flags are presentation
  fixtures only. No invented RAW file is decoded or moved.
- `.gitignore`: allow this report and the final reviewed captures. Initial capture
  diagnostics remain local and ignored. Localization, testing and changelog docs
  describe implemented behavior and actual verification limits.

## Commands and results

All commands use `.venv/Scripts/python.exe -B`; Qt commands set
`QT_QPA_PLATFORM=offscreen`. Test base directories are under `build/`.

```text
python -B -m tools.build_translations
python -B -m tools.build_translations --check
```

Both builds and the final parity check completed: **480 finished messages per
language**, matching keys and placeholders, no unfinished entries. The compiled
resource regression compares every embedded QM entry with the generated fallback.

The focused `tests/test_task022.py -q` run passed **8 tests in 89.36s**, no skips.
These cover both themes, collapsed navigation labels/tooltips, current selection,
query, choice, zoom, disclosure state, focus, frozen plan, typed RAW/legacy consent,
localized errors with literal technical details, and a real synthetic confirmed
quarantine/restore with byte equality. Selecting or changing language never creates
an Approval.

Final regression results and diagnostic outcomes are recorded in
[TESTING.md](../../../TESTING.md#task022--clear-ensr-workflow-wording-2026-11-14).
The final combined run had **57 passed, 1 native-Linux skip and 1 setup timeout**;
the timeout case and extra group/navigation checks then passed **10/10**. The
broader intermediate Qt run had **114 passed and 1 old restore-text assertion
failure**; the updated assertion passed in the final localization run. These are
separate actual runs, not a claim that one full invocation had no failures.

## Visual evidence

```powershell
$env:QT_QPA_PLATFORM='offscreen'
$env:QT_SCALE_FACTOR='1'
.venv/Scripts/python.exe -B -m tools.capture_task022 --output docs/design/verification/task022-20261114/100-verified
```

The final driver captures **52 states**: EN/SR × Dark/Light; active Scan, comparison
at 1440×900 and 853×480, expanded details, quarantine tooltips, open RAW/legacy
confirmation, external-open error and all five main pages with a collapsed sidebar.
Each image's language, theme, logical/physical size, DPR, SHA-256 and layout metrics
are recorded in [100-verified/manifest.json](100-verified/manifest.json). The driver
asserts no page horizontal scrolling or primary-toolbar overlap/out-of-window
controls and verifies that the original synthetic photo bytes remain identical.

The initial capture iteration showed that the driver was on Dashboard during
scanning and positioned the details scrollbar before Qt completed expansion. The
final driver navigates to Scan explicitly, waits for layout and brings the expanded
detail toggle into view. This was a capture-driver correction, not a product layout
change. Theme selectors are synchronized with the forced capture palette. The final
route captures also use the normal Back action before leaving comparison, keeping
the Duplicates header and toolbar consistent with the visible list.

Sixteen final images were opened and visually inspected (the remaining captures
have automated layout/hash checks, not a claimed individual manual review):

| State | Inspected variants |
|---|---|
| Comparison | EN/Dark/1440, EN/Light/853, SR/Dark/1440, SR/Light/853 |
| Expanded photo details | SR/Dark/853, SR/Light/853 |
| Duplicate list | EN/Dark, SR/Light |
| Active Scan | EN/Light, SR/Dark |
| RAW/legacy confirmation | SR/Dark, SR/Light |
| External-open error | SR/Dark, SR/Light |
| Quarantine tooltip | SR/Dark, SR/Light |

Serbian action labels, longer explanations, confirmation warnings and tooltip text
fit in the inspected views in both themes. Narrow comparison deliberately stacks
photos and scrolls while the bottom actions stay reachable. Collapsed navigation
retains icons and localized tooltip/accessibility labels; live tests verify the
hidden labels do not reappear on language changes. The observed CJK font limitation
below remains explicit.

## Limits

- Catalog coverage is not certification of every OS/Qt string or professional
  linguistic proofreading. Tk remains Serbian only; OS dialogs, file managers,
  error diagnostics and external viewers retain their own language.
- Offscreen captures establish rendered wording/layout at DPR 1. They do not
  establish native Windows/Linux display, physical DPI or screen-reader acceptance.
  Linux, valid RAW assets and real removable media were not exercised here.
- Segoe UI renders Serbian Latin in these captures; some CJK fixture filename
  glyphs display as boxes with this host's font fallback. Unicode path bytes remain
  literal and are covered by the synthetic scan/quarantine/restore tests.
- No full repository suite, packaging build or live viewer handoff was run for
  Task022. Packaged catalog loading is covered by the localization regression.
