# Changelog

## Task010 — Accessibility and translation preparation — 2026-11-09

- Inventoried Qt/shared text keys with English intentions for Task012, preserving
  Serbian display, shared resources and language validation. Unknown translation
  keys and formatting failures now produce a readable fallback.
- Centralized readable action/error copy. Raw diagnostics remain in collapsed,
  selectable plain-text details rather than normal messages or thumbnail tooltips.
- Defined page keyboard order, named source/filter/progress/preview controls and
  text-based choices. Fixed keyboard entry into the group gallery's hidden row
  and initial Cancel focus after asynchronous confirmation opening.
- Wrapped long paths and preview controls; narrow comparisons stack vertically.
  Added explicit enlarged-preview Close and focus return. Approval/RAW/legacy
  checks and visible warnings remain mandatory; safety services are unchanged.
- Kept hidden gallery/dashboard refreshes from cancelling the visible page's
  thumbnail batch, discovered by the existing end-to-end Dashboard regression.
- Added synthetic keyboard, accessibility API, rendered state and fallback tests,
  plus a real Qt scale-factor capture driver. Native assistive technologies and
  physical-display DPI behavior remain outside the offscreen verification.

## Task009 — Quarantine and Settings — 2026-11-09

- Replaced the technical history table with original names/locations, manifest move
  dates and sizes, readable states and selected-file previews. Missing dates stay
  unavailable; previews validate the current quarantine destination, never old source.
- Bound selection, restore preparation and per-root folder opening to operation IDs.
  Empty/load-failure states and no-overwrite errors remain explicit; optional thumbnail
  failure does not block history or authorize a different operation.
- Grouped Settings into Appearance, Language, Scanning, Similarity Detection, Safety,
  Storage and About. Shared theme control persists immediately. Added documented
  Strict 2/3, Balanced 4/6 and Broader 8/10 choices with preserved Custom thresholds,
  existing source order, unknown keys and legacy history. Language remains Serbian Latin.
- Reported the actual active index path/physical-file count and explained the memory
  cache budget, offline behavior and version. Journal, matcher, schema and movement
  safety checks are unchanged. Added synthetic service/Qt tests and capture driver.

## Task008 — Duplicate gallery and integrated comparison — 2026-11-09

- Added bounded Qt Grid/List group cards with actual thumbnails, full-session
  search/sort, supported Exact/Similar filters, member counts, session-only review
  decisions and physical EXACT byte estimates. Unsupported classifications are hidden.
- Put fitted photos first, with readable size/format/dimensions, explicit retain
  choices, collapsed details, bounded enlarged previews, and paginated direct members.
  Back restores the listing query/page/selection/scroll. EXACT allows multiple
  retained versions; VISUAL never infers a transitive match. Keep Both cancels proposals.
- Kept Plan/Approval execution and all fresh verification. Confirmation separates
  source/keeper/destination from technical details, keeps contextual warnings and
  RAW/legacy consent visible, and prevents Enter approval. Single-move Restore uses
  the completed operation ID and a new preparation/confirmation. Errors never report success.
- Coalesced stale preview/thumbnail work and added synthetic UI/service/restart
  coverage plus a repeatable dark/light capture tool. Safety, decoder, matcher,
  schema, recovery formats and original photographs are unchanged.

## Task007 — Dashboard and Scan — 2026-11-09

- Added four Dashboard statistic cards, a recent-session summary, first-scan and
  completed-without-matches states, theme/settings controls and direct review links.
  At most three actual candidates show classification, format, dimensions and
  asynchronous thumbnails, requested only for visible cards with stale-response guards.
- Extended the compatible read-only dashboard contract with session photo count,
  actual EXACT group count, finished time and bounded candidate rows. Whole-index
  counts remain distinct from session candidates/links. Estimated bytes exclude
  retained physical files, hardlink aliases and VISUAL guesses.
- Added readable sources and availability, collapsed priority/error controls,
  pre-scan source checks, actual progress counts and elapsed time, cancellation,
  state-specific completion and Review Results. CSV failures remain secondary to
  successful scans. Incomplete/failed/cancelled sessions retain operation restrictions.
- Added synthetic service/UI coverage and a repeatable dark/light capture tool.
  Matching, RAW extraction, schema, journal and operation verification are unchanged.

## Task006 — Qt shell and navigation — 2026-11-09

- Replaced six peer pages with five named destinations and a persistent comparison
  view inside Duplicates. Back/Alt+Left preserves the group, query, pages and selection
  without new service requests; Enter/double-click opens comparison.
- Added a 208 px sidebar with distinct local Qt icons, Settings at the bottom,
  one shared title/purpose header, wrapping contextual actions and explicit Tab order.
  Main actions remain above scrollable content; each view has at most one dominant action.
- Reject stale plans on navigation and keeper/selection changes; preserve explicit
  approval, cancellation, worker-owned SQLite and asynchronous close. Restore focus
  after plan dialogs and stop debounced search on scan/close.
- Added navigation/state/focus/viewport regression coverage and adapted the existing
  synthetic capture tool to named routes and configurable viewport dimensions.
  Backend services and Tk fallback are unchanged; physical DPI/Linux/full Task011
  accessibility acceptance remain open.

## Task005 — Qt design system — 2026-11-09

- Extended Dark/Light themes with semantic colors, readable action text, stable
  focus/hover, typography and shared dialog/menu/list/table styles.
- Added reusable headers/cards/stats/empty states/status badges/sections and action
  variants, plus worker-fed preview loading/unavailable/reset states.
- Bundled three original CC0 SVGs and loaded QtSvg before Windows icon engines.
- Added contrast/keyboard/preview tests and eight inspected component captures.
  Settings format, matcher, decoder, schema and safety services are unchanged.
  Native DPI/Linux and full accessibility acceptance remain open.

## Task004 — UX audit and redesign plan — 2026-11-09

- Audited all six existing Qt pages with 24 newly rendered synthetic screenshots,
  including confirmation, incomplete/offline errors and selected restore after
  service restart. Added a repeatable isolated capture tool and evidence manifest.
- Documented per-screen improvements, actual metric sources and contract gaps,
  3+ member review, retained copies, Back context and stale-plan invalidation.
- Preserved production behavior and separated future redesign (Task005–011),
  localization (Task012) and release/packaging (Task013). Focused regression:
  38 passed; native DPI/Linux/full manual accessibility acceptance remains open.

## Launcher default correction - 2026-11-08

- Changed the application and preflight defaults to Qt at the owner's request:
  double-clicking start_windows.bat now opens the six-screen interface, with Dark
  as the default theme. Saved theme preferences remain respected; `--ui tk`
  selects the retained legacy adapter. Manual scaling/platform acceptance remains open.

## v2.4 - Task003 - 2026-11-08 (manual acceptance pending)

- Added optional six-screen Qt desktop, Dark/Light/System themes, Serbian keyed
  messages, worker-owned services, asynchronous previews/shutdown and cancellation.
- Added whole-session queries/direct groups, dashboard estimates, progress,
  preserved preferences, per-session matching thresholds and selected restore IDs.
- Added 2048 px previews and a content-validated 64 MiB decoded cache; frozen-plan
  dialogs retain RAW/legacy confirmations and all existing safety checks.
- Added Qt/offline distribution notes and regression tests. Tkinter remains available
  and default until manual acceptance. No installer, language switching or new classifiers.

## Task002 - Windows measurement evidence - 2026-11-08

- Added a separate synthetic Tkinter heartbeat benchmark without production changes.
  Three cold/warm 20-photo repetitions with 50 ms worker-read delay met the 250 ms
  target; worst measured gap was 84.746 ms. Raw intervals are under ignored
  `.benchmarks/task002-ui-final-20261108/`.
- Added pair-identity digests to the existing synthetic index benchmark tool.
  The requested 1k/10k index and compatible-baseline attempts stopped before a
  completed scenario; time/RAM budgets and pair equivalence remain open.
- Reconciled M2/M3 evidence and current test counts. Linux remains untested; neither
  cross-platform milestone is declared complete.

## v2.2 - Modular core and SQLite index - 2026-11-08

- Added schema version 1 with transactional migrations, backup support for upgrades,
  WAL, constraints/indexes, an independent OS writer lease and thread-confined access.
- Added full-SHA validated incremental scans, per-root availability/generations,
  interrupted-session handling, rename/replacement detection and preserved
  corrupt/newer databases with private temporary-index fallback.
- Separated byte hashing, discovery, inspection, perceptual hashing and quality.
  Index decoder mode omits unused PNG previews. Disk-backed directory spooling
  and BK-tree matching bound Python collection memory.
- Moved orchestration to Application; Tkinter now loads 200-row pages. CSV and bulk
  selection cover the entire session. Partial results remain review-only.
- Kept JSON recovery authority and version-1 manifest shape. Fresh plan preparation
  and existing pinned-handle verification protect against forged cache eligibility.
- Added synthetic index/migration/concurrency/crash/pagination tests and a seeded
  benchmark tool. TESTING.md records measured results and remaining gates.

Changed files relative to the existing uncommitted v2.1 working tree:
`.gitignore`, `README.md`; `app/core/{models,hashing}.py`;
`app/scanning/{scanner,decoder,discovery,inspection,fingerprints}.py`;
`app/matching/{matcher,indexed,quality}.py`; `app/storage/{__init__,index}.py`;
`app/services/{application,indexing,reports}.py`; `app/safety/{paths,journal}.py`;
`app/ui/tk_app.py`; `app/i18n/__init__.py`; `tests/{conftest,test_indexing,test_ui}.py`;
`tools/benchmark_index.py`; architecture, roadmap, security, testing and changelog docs.

Limitations: native Linux, licensed valid RAW assets, physical drive unplug/replug,
network filesystems, packaging and physical power-loss validation remain unverified.
Cold scans retain per-file decoding and two full SHA reads. Scan history grows on
disk; immutable operation plans still scale in memory with approved moves.

## v2.1 - Task001 - 2026-11-08

- Extracted immutable models, stable match categories, scanning/matching services
  and native safety operations from the Tkinter entry point. Existing desktop
  layout, side-by-side previews, quality heuristic and CSV workflow remain.
- Added full-content snapshots, root identity, physical deduplication, incomplete
  scan reporting, non-transitive visual matching and protected operation plans.
- Added native no-replace quarantine/restore, one OS-locked journal writer, durable
  pre-move intent, retained transitions, restart reconciliation and legacy backup/
  import. No unverified rollback, copy/delete fallback or permanent photo deletion.
- Bulk excludes VISUAL, undecodable, RAW on either side, XMP and cross-root copies.
  Individual previews list all paths/hashes; RAW and legacy restore add confirmation.
- Moved decoding to bounded child processes (100 MP / 60 s) and file/report work to
  background services; cancellation, stale previews, dependency invalidation and
  shutdown have regressions. Polling survives errors; reports use unique exclusive names.
- Repaired demo generation and startup preflight; added dev requirements, pytest
  configuration, 77 synthetic cases and maintained project documentation.

### Changed files

- Entry/runtime: photo_agent.py, start_windows.bat, start_linux.sh, napravi_demo.py,
  requirements-dev.txt, pytest.ini, .gitignore, .gitattributes.
- Domain/services: app/__init__.py; app/core/{__init__,models}.py;
  app/matching/{__init__,matcher}.py; app/scanning/{__init__,scanner,decoder}.py;
  app/safety/{__init__,paths,native,journal,operations}.py;
  app/services/{__init__,state,reports,preflight}.py; app/i18n/__init__.py;
  app/ui/{__init__,tk_app}.py.
- Tests: tests/__init__.py, conftest.py, crash_worker.py, test_operations.py,
  test_scanning.py, test_recovery.py, test_processes.py, test_native_races.py,
  test_decoder_and_services.py, test_ui.py, test_additional_safety.py.
- Documentation: README.md; docs/ARCHITECTURE.md, REVERSE_ENGINEERING.md,
  ROADMAP.md, SECURITY.md, TESTING.md, CHANGELOG.md. Task source remains ignored.

Validation: 75 passed, 0 failed, 2 skipped (native Linux and valid RAW fixture).
See TESTING.md for commands and prior development-run corrections. Linux adapter,
valid RAW, real media and packaging remain unverified; process-exit tests do not
establish physical power-loss safety. General localization, themes, SQLite and
PySide6 are future milestones. Existing tools/check_environment.py was not changed.
