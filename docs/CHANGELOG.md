# Changelog

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
