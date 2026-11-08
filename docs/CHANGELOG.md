# Changelog

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
