# PhotoAgent Task001 test evidence

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
