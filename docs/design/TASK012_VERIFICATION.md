# Task012 — Qt EN/SR localization verification

Scope: the complete PhotoAgent Qt interface on the tested Windows / Python 3.12.10 /
PySide6 6.12.0 / Fusion runtime. Tk remains Serbian Latin. This is implementation
and synthetic verification evidence, not a native Linux or release-package claim.

## Implemented behavior

- `app/i18n/en.json` and `sr_Latn.json` each contain 418 matching keys, with matching
  format arguments. They cover pages, models, filters, statuses, errors, warnings,
  confirmations, tooltips, accessible names/descriptions and used Qt framework controls.
- Settings → Language changes existing controls immediately, including while the
  service worker scans and while a confirmation or enlarged preview is open.
  Review choices, selected IDs, filters, preview images, disclosure state, frozen
  plans, RAW text and legacy consent survive. Language changes never approve a move.
- State-file absence selects English. Existing `en`/`sr_Latn` values survive;
  legacy files without `language` retain Serbian. Invalid values select English and
  report a warning. Unknown settings and legacy move data remain intact.
- Preference writes use the service thread. During a scan they wait for that work;
  the display changes immediately. Every successful write remains the rollback
  baseline, including rapid consecutive choices; a failure restores that choice
  and shows localized feedback with separate technical details.
- Missing translations and unknown languages fall back to English. Unknown keys
  and formatting mistakes show a readable message. Group counts use correct EN/SR
  forms (including 11–14 / 21 / 22 / 25) and put the count first to survive elision.
- An application-owned manager changes the Qt locale and sends framework language
  changes through a QTranslator adapter into the same catalogs. The tested PySide6
  distribution has no Serbian Latin qtbase catalog; duplicate application .ts/.qm
  resources were therefore unnecessary. Qt framework sources outside the tested
  runtime use the framework's English fallback.
- The nonblocking folder picker opens in the first source (or application home),
  retains typed input during switching, and is read-only. Framework settings in
  automated checks/captures are redirected to disposable INI paths in both scopes.

Paths, SHA-256 values, format/enum/database identifiers, CSV fields, journal data,
raw diagnostics and the exact consent token `RAW` are not translated. OS-provided
file-type descriptions and regional file-manager date/size formatting can follow
the host system. Matching, verification, recovery and no-overwrite rules are unchanged.

## Changed source and checks

Shared resources: `app/i18n/{__init__.py,en.json,sr_Latn.json}` and
`app/services/state.py`. Qt presentation: `strings.py`, `localization.py`,
`qt_translations.py`, `components.py`, `controller.py`, `dashboard_scan.py`,
`gallery.py`, `models.py`, `navigation.py`, `quarantine_settings.py`, `screens.py`,
`window.py` and `workers.py` under `app/ui/qt/`.

Checks: `tests/test_task012.py`, the Qt framework-settings guard in
`tests/conftest.py`, and updated expectations/picker injection in `test_qt.py`,
`test_task009.py`, `test_task010.py`, `test_decoder_and_services.py`.
`tools/capture_task012.py` generates the localized evidence. README, architecture,
roadmap, changelog, distribution, accessibility/design-system notes, text inventory,
testing instructions and the evidence allowlist are updated. Existing uncommitted
Task011 work is preserved; no commits, dependency installs or real-library operations
were performed.

## Rendered evidence and limits

The final capture matrix is in [verification/task012/current](verification/task012/current/).
Each of `100`, `125`, `150` contains 32 PNGs, four review sheets and a finished
manifest with actual DPR, pixel sizes, hashes, page/toolbar geometry, and confirmation
that all generated original bytes remained unchanged. The eight surfaces are the
five main pages, loaded comparison, unapproved confirmation and folder picker.
Every surface appears in both languages and themes: 96 PNGs in total. Capture
confirmations are rejected; no file operation is executed by this driver.
All 12 final review sheets were visually inspected; [review.json](verification/task012/current/review.json)
records the inspected sheets and independent manifest/hash checks. Long labels wrap, source/plan
paths remain readable through their full-text controls, and group-count prefixes
survive card elision. Manifest hashes and completion flags are checked separately.

The screenshot size is 1280×720 physical pixels, using logical sizes adjusted for
each actual DPR. Automated tests additionally exercise 1280×720, 1366×768, 1650×900
and 1920×1080, in both themes/languages and three separate Qt scale processes.
Vertical scrolling and path/card elision are intentional; primary page horizontal
overflow and toolbar overlap/outside-window checks must stay zero. At 150%, the
comparison stacks vertically and secondary content requires scrolling. Gallery
captures may show genuine pending thumbnail states; comparison captures wait for
both real generated previews. History screenshots show the empty state; populated
history, approved synthetic quarantine and restart behavior are covered by tests.

Native Windows/Linux monitor changes, assistive technologies, native Linux execution,
other allowed Qt versions and frozen/offline packaging remain unverified. No licensed
valid RAW fixture is available; malformed RAW is covered by the safety regressions.
Tk language switching is deliberately outside Task012; its Serbian regressions run
separately. Source packaging must include both JSON catalogs.

Exact executed commands, results and development-run failures are recorded in
[TESTING.md](../TESTING.md).
