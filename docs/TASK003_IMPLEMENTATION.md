# Task003 implementation record — 2026-11-08

The requested desktop adapter is implemented. Qt became the default on 2026-11-08
at the owner's request after double-click launch still showed the legacy interface.
This supersedes the original default-switch gate in Task003. `--ui tk` retains
Tkinter; native Windows manual/scaling checks remain unverified.
No manual acceptance or Linux result is inferred from automated Windows tests.
The planning note about Plan mode and a future Task033 document in the brief is
not a runtime requirement; the actual brief remains docs/task/Task003.md.

Implemented: six Qt screens, worker-confined SQLite/services, independent cancellable
previews, asynchronous shutdown, global paginated search/sorting, direct groups,
dashboard estimates/warnings, scan counters/errors/reports, selected keeper,
frozen-plan confirmation with RAW/legacy consent, journal history/selected restore,
Dark/Light/System, preserved settings and next-scan matching thresholds.
Recognition still emits only EXACT/VISUAL. Language selection is intentionally
inactive; Serbian messages use stable translation keys and fallback.

## Changed files

- `.gitignore`: allow the new distribution and implementation records.
- `photo_agent.py`, `app/services/preflight.py`, `requirements.txt`,
  `start_windows.bat`, `start_linux.sh`: selected toolkit and Qt dependency.
- `app/core/queries.py`: immutable query/result/progress/matching contracts.
- `app/services/application.py`, `state.py`, `indexing.py`, `queries.py`,
  `preview.py`: service extensions, atomic merged settings, global SQLite queries,
  scan progress and full-content-validated preview cache.
- `app/matching/matcher.py`, `indexed.py`, `app/scanning/scanner.py`: optional
  thresholds, with original defaults and algorithm retained.
- `app/scanning/decoder.py`: independent preview size up to 2048 px, unchanged
  fingerprint scaling and subprocess isolation.
- `app/safety/operations.py`: optional selected restore ID; same eligibility/checks.
- `app/ui/qt/__init__.py`, `bootstrap.py`, `controller.py`, `workers.py`,
  `window.py`, `screens.py`, `models.py`, `components.py`, `themes.py`, `strings.py`:
  the Qt desktop adapter.
- `app/ui/qt/resources/photoagent.svg`, `resources/resources.qrc`, `resources_rc.py`:
  offline SVG and checked-in generated Qt resources.
- `tests/test_task003_services.py`, `tests/test_qt.py`, `tests/conftest.py`: synthetic
  service/Qt regressions and decoder argument containment for optional preview size.
- `tools/check_environment.py`: PySide6/shiboken diagnostics.
- `README.md`, `docs/ARCHITECTURE.md`, `SECURITY.md`, `CHANGELOG.md`, `ROADMAP.md`,
  `TESTING.md`, `QT_DISTRIBUTION.md`, this record: behavior/evidence/distribution.
  README was normalized from UTF-16 to UTF-8 for editing.

The SQLite schema and authoritative operation-journal format are unchanged.
No commits, push, real-photo operations, installer or system package changes were made.
PySide6 was installed only into the project .venv with permission.

## Verification and acceptance

See [TESTING.md](TESTING.md) for exact commands/results. Tested runtime:
Python 3.12.10 / PySide6 and Qt 6.12.0 / Windows. Full tests use isolated temporary
synthetic images/index data; QtTest runs real event loops. Heartbeat validation
asserts gaps below 250 ms during a controlled slow worker scan on this host.
Offscreen theme/RAW-confirmation checks supplement native Windows Qt checks.

Results: full post-cancellation-fix regression **131 passed, 2 skipped** in 341.97s;
final three affected Qt checks after cache/presentation refinements **3 passed** in
44.65s; separate offscreen checks **2 passed** in 3.13s. Diff whitespace checks pass.
The two skips are the unavailable valid licensed RAW fixture and native Linux test.

Still open: native manual Windows launchers, full keyboard/resize/dialog review,
100/150/200% scaling, Linux, valid licensed RAW, physical removable drives,
offline wheelhouse rehearsal and future frozen packaging. The owner-requested default
switch is not evidence of manual acceptance; Linux needs its own acceptance record.
System theme availability depends on Qt's platform integration. OS filesystem
calls have no guaranteed cancellation deadline; closing waits asynchronously.
The 64 MiB limit covers decoded preview cache, not GUI pixmaps/in-flight buffers.
History is journal-backed and currently reads manifests before slicing a page;
very large operation histories and frozen plans may need future performance work.
