# PhotoAgent test evidence

## Task002 measurements (2026-11-08)

Only generated 80×60 PNG/JPEG/WebP files were used. Reference host: Windows 11
24H2, build 26100.9711 (`platform.platform()` reports Windows 11; the legacy
registry ProductName says Windows 10 Enterprise), 13th Gen Intel Core i5-1335U,
Python 3.12.10. Dependencies: Pillow 13.0.0, ImageHash 4.3.2, rawpy 0.28.0,
pillow-heif 1.8.1, NumPy 2.5.4, SciPy 1.18.1 and pytest 9.2.0. WSL/Linux was not run.

The hidden Tk window used the actual `PhotoApp` worker path. A wrapper delayed each
background full-content read by 50 ms. Tk scheduled a heartbeat every 25 ms; all
observed gaps, including the initial and final intervals, are in
`.benchmarks/task002-ui-final-20261108/results.json`. Each repetition generated 20
synthetic files and ran a cold then unchanged warm scan. The OS filesystem cache was
not flushed. These are elapsed times and UI scheduling gaps, not end-to-end GUI
interaction times.

| Repetition | Cold seconds | Cold max gap ms | Warm seconds | Warm max gap ms |
|---:|---:|---:|---:|---:|
| 1 | 25.274 | 43.307 | 1.353 | 39.420 |
| 2 | 25.756 | 46.998 | 1.426 | 51.033 |
| 3 | 25.656 | 84.746 | 1.362 | 30.976 |

All six scans completed with 20 photos. Every measured maximum is below the M2
target of 250 ms on this host. The first UI attempt stopped with a cross-thread
SQLite access error in the measurement tool; the second produced overlapping tick
chains. Their ignored directories are retained as invalid/partial evidence and
are excluded from the table. The final tool binds each tick chain to its scenario.

Run from the repository root with the project environment and a **new** output path:

```powershell
.\.venv\Scripts\python.exe -B -m tools.benchmark_ui --output .benchmarks/task002-ui-final-20261108 --repeats 3
.\.venv\Scripts\python.exe -B tools\benchmark_index.py --output .benchmarks/task002-index-20261108 --mode index --sizes 1000 10000 --repeats 3
.\.venv\Scripts\python.exe -B tools\benchmark_index.py --output .benchmarks/task002-baseline-20261108 --mode baseline --sizes 1000 10000 --repeats 3
.\.venv\Scripts\python.exe -B tools\benchmark_index.py --output .benchmarks/task002-smoke-index-20261108 --mode index --sizes 10 --repeats 1
.\.venv\Scripts\python.exe -B tools\benchmark_index.py --output .benchmarks/task002-smoke-baseline-20261108 --mode baseline --sizes 10 --repeats 1
.\.venv\Scripts\python.exe -B -m pytest -p no:cacheprovider tests\test_ui.py tests\test_indexing.py -q
.\.venv\Scripts\python.exe -B -m pytest -p no:cacheprovider tests -q
git diff --check
```

The 1k/10k index run was interrupted during its first 1k cold scan after prolonged
runtime, before any scenario completed. Its generated files and partial SQLite data
are retained under `.benchmarks/task002-index-20261108/attempt.json`; there is no
completed `results.json` for it. The compatible baseline attempt likewise stopped
during its first 1k scan; its status is in
`.benchmarks/task002-baseline-20261108/attempt.json`. Therefore no 1k/10k cold,
warm, changed, or baseline timings, SHA reads, decode counts, peak sampled RSS,
database sizes, or pair-identity
comparisons are claimed here. The tool measures parent plus live decoder RSS every
20 ms, not a hard memory cap, and retains full SHA reads on cache hits. A future
completed run must verify zero warm decodes and compare both pair count and the
`pair_identity_sha256` digest. `baseline` denotes the **current compatible scanner**,
not historical v1. No 125% time/RAM regression budgets are assigned to unmeasured
1k/10k scenarios. A separate performance task is needed to finish these measurements.

A one-repetition, 10-file **tool smoke check** completed in both modes under
`.benchmarks/task002-smoke-{index,baseline}-20261108/results.json`: cold index and
compatible baseline each found 8 pairs with the same identity digest
`a17bcf0047b6801e024867adfa42164142dfb7686407c2e0759c620131e080b0`.
The unchanged warm index scan had 0 decodes and 10 full SHA reads. This checks the
measurement path; it does not satisfy the requested 1k/10k performance gate.

Task002 focused tests: **41 passed, 0 failed, 0 skipped**. Full suite:
**110 passed, 0 failed, 2 skipped**; the skips are valid RAW decode (no licensed
fixture) and native Linux execution on Windows. The earlier Task001 count below is
historical. Neither M2 nor M3 is accepted on both platforms.

## Task001 historical evidence

Date: 2026-11-08. Windows, Python 3.12.10, pytest 9.2.0. No real photo library
was scanned or modified. Linux/WSL and a licensed valid RAW fixture are unavailable.

## Reproduce

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -B -m pytest -p no:cacheprovider tests
git diff --check
```

Linux equivalent is `.venv/bin/python -B -m pytest -p no:cacheprovider tests` in a
native environment; it was NOT run. Windows virtual environments are not portable.
Dependencies were installed only into the existing project .venv; no system packages
were installed. The existing untracked tools/check_environment.py was read/executed
but not modified. It verified Python, installed image dependencies and Tkinter;
pytest was initially absent and was installed from requirements-dev.txt.

Final full collection: **77 collected, 75 passed, 0 failed, 2 skipped**.
The two intentional skips are native Linux no-replace execution and valid RAW decode.
Corrupt RAW is tested. All six hidden Tk integration tests pass on this host.
`git diff --check` exits 0. Git emits CRLF normalization notices for existing files;
.gitattributes pins shell launchers to LF and batch launchers to CRLF.

## Isolation and scope

`tests/conftest.py` redirects HOME/USERPROFILE, temp directories, state/journal,
reports and decoder inputs to each tmp_path. Application path entry points and
subprocess decoder inputs reject access outside the synthetic sandbox. Filesystem
mutations use only generated PNG/JPEG/WebP, synthetic malformed RAW and temporary
JSON/sidecars. Crash helpers enforce the same sandbox in the child process.

The four process-boundary tests use real child processes terminated with os._exit
before intent, after intent, after rename and after completion. Another child probes
the OS writer lock. These test process termination, NOT physical power failure.
Missing/replaced storage is simulated with temporary directories/identities; there
was no physical drive unplug/replug test. The cross-device check uses a synthetic
device mismatch, not a physical second drive.

One Tcl/Tk interpreter hosts isolated hidden Toplevel windows. The earlier approach
of repeatedly destroying/recreating Tk roots was unstable with Microsoft Store
Python: an intermediate full run reported 57 passed / 4 skipped, including two
Tcl resource failures. The fixture was corrected; the final run has only the two
intentional platform/asset skips. Early development runs also found mismatched
Windows stat/fstat ctime semantics and a stale monkeypatched function alias in the
fixture; both were corrected and covered by passing current tests.

## Finding-to-regression map

The original H/D descriptions in REVERSE_ENGINEERING.md refer to historical source.
These references identify current executable cases, not claims based on the plan.

| Finding | Current evidence |
|---|---|
| H1 | test_native_races: late quarantine/restore conflicts retain both byte sequences; native no-replace adapter. |
| H2 | test_recovery: intent/final-write failures; test_processes: four actual child exits and repeated reconciliation. |
| H3 | test_native_races: quarantine tampering; test_additional_safety: legacy restore containment; restore conflict and retained history cases. |
| H4 | test_scanning: symlink/ancestor/junction and traversal; test_native_races: destination escape; test_additional_safety: pinned Windows handles. |
| H5 | test_scanning: explicitly selected nested quarantine directory and recursive exclusion. |
| H6 | test_operations: same size/mtime edits and self-comparison; test_native_races: inode replacement and root mismatch; hardlink dedup. |
| H7 | test_recovery: corrupt JSON, old history backup/import and lock; test_additional_safety: invalid settings types; test_processes: competing OS writer. |
| H8 | test_operations: both RAW flags, different roots, XMP, VISUAL excluded from bulk; solid-color hash collision remains VISUAL. Valid RAW decode is skipped. |
| H9 | test_ui: all results referencing a moved keeper are invalidated; stale preview generation is discarded. |
| H10 | test_ui: failed report plus a subsequent worker result; finally-scheduled polling after render exception. |
| H11 | test_scanning: cancellation each hash block; test_additional_safety: active decoder killed/reaped, cancellation after intent finishes active move; test_ui: responsive heartbeat and close wait. |
| H12 | test_decoder_and_services: pixel declaration >100 MP, request timeout, native child crash, multiframe and preview bitmap; test_scanning: corrupt RAW. |
| H13 | test_scanning: missing root and access failure produce incomplete scan; test_additional_safety: simulated disconnect/reconnect; recovery blocks wrong root identity. |
| H14 | test_decoder_and_services: inert demo import, explicit new destination, repeat refusal; README uses the correct filename. |
| D1 | Frozen typed models; test_additional_safety: core/scanning/safety import without Tkinter; UI service tests. |
| D2 | Historical finding only: git ls-files .venv returns no tracked paths in this baseline. No environment cleanup/removal was performed. |
| D3 | test_decoder_and_services: installed runtime preflight; test_additional_safety: unsupported Python rejected. Batch/bash edits inspected; native bash launcher not executed. |
| D4 | test_recovery and test_processes: retained original/restore manifests and transition history; logging has operation context and failed moves retain evidence. |
| D5 | test_decoder_and_services: unique reports, forced same-name collision refuses overwrite; GUI report-error regression. |
| D6 | test_decoder_and_services: EXIF orientation, editing description and ICC bytes survive move/restore unchanged; XMP stays; quality remains heuristic. |

Additional cases cover N-1 exact grouping, root order, overlapping roots, PNG/JPEG/
WebP compression/resolution variants, visual A-B-C non-transitivity, approval-plan
mismatch, cancelled preview without movement, unsafe keeper dependencies, duplicate
sources, unsupported platforms and simulated cross-device refusal.

## Checks executed during implementation

Focused groups were run before the full collection:

```powershell
.\.venv\Scripts\python.exe -B -m pytest -p no:cacheprovider tests\test_operations.py tests\test_scanning.py tests\test_recovery.py -x -q
# 31 passed
.\.venv\Scripts\python.exe -B -m pytest -p no:cacheprovider tests\test_processes.py tests\test_native_races.py tests\test_decoder_and_services.py -x -q
# 24 passed, 2 skipped
.\.venv\Scripts\python.exe -B -m pytest -p no:cacheprovider tests\test_ui.py -x -q
# 4 passed before the plan-preview cancellation case was added
.\.venv\Scripts\python.exe -B -m pytest -p no:cacheprovider tests\test_additional_safety.py tests\test_ui.py -x -q
# 15 passed, then 18 passed after additional cases
```

The full command above was then run successfully (73 passed / 2 skipped), and
repeated after type annotations. Malformed decoder output and closing the app while
the plan dialog is open were then added: the focused decoder/UI run passed 7 tests,
followed by the final full run (75 passed / 2 skipped). No results are simulated.
No packaging, real archive benchmark, valid RAW, physical media, Linux native run,
full visual/keyboard/scaling review or physical power-loss validation was performed.
Full localization/themes/SQLite are outside Task001 and are not tested as features.
See SECURITY.md for remaining Linux concurrent namespace and filesystem limits.
