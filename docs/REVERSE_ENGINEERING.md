> Historical audit of baseline 569e2a1, retained as evidence. The source/line
> descriptions below do NOT describe the current Task001 implementation.
> Task001 implementation status (2026-11-08): models/scanning/matching/safety/services
> are extracted into app/, durable intent and native no-replace operations are in
> place, and synthetic pytest regressions now exist. The environment is ignored and
> no .venv files are tracked in the current baseline (the earlier D2 observation is
> historical). See TESTING.md for H1-H14/D1-D6 mapping and actual results, SECURITY.md
> for remaining platform/race/durability limits, and ARCHITECTURE.md for current code.
# PhotoAgent: current implementation audit

Baseline: commit `569e2a1`, inspected on 2026-11-04. Source references below
refer to that baseline. This documentation change does not implement any fixes.

## Evidence and scope

- **S (source):** directly established by reading the repository.
- **R (runtime):** observed in the earlier audit's in-memory probes; mocked I/O
  proves control flow, not real filesystem durability.
- **U (unverified):** requires integration, platform, GUI, or asset testing.
- **Proposed:** future behavior, never a claim about the prototype.

The earlier audit ran 17 checks, recorded in [TESTING.md](TESTING.md). They were
not saved as a test suite and were not rerun for this documentation change.
No real photo library was scanned or modified. No project tests currently exist.

## Repository and entry points

```text
PhotoAgent/
  AGENTS.md
  photo_agent.py          # 1,836-line application
  napravi_demo.py         # synthetic demo generator; currently broken
  requirements.txt
  start_windows.bat
  start_linux.sh
  README.md
  .venv/                 # 5,136 tracked files, including Windows binaries
  docs/                  # these documentation files, added after the audit
```

There is no application package, SQLite index, project test directory, CI,
packaging configuration, or root `.gitignore`. `README_SR.md` does not exist.

| Entry | Behavior (S) |
|---|---|
| [photo_agent.py](../photo_agent.py), L1830 | Creates Tk root, `PhotoApp`, and the event loop. |
| [start_windows.bat](../start_windows.bat), L4-18 | Creates Python 3.12 venv if absent; checks three imports; may install requirements; launches GUI. |
| [start_linux.sh](../start_linux.sh), L6-14 | Uses `python3`, without a minimum-version check; otherwise similar startup. |
| [napravi_demo.py](../napravi_demo.py), L1-67 | Top-level generation into a fixed project directory; no main guard. Wrong `pillow` import fails first. |

Runtime operation is local; launcher dependency installation can require a
network. There are no application cloud services, telemetry, or AI APIs (S).

## Component and responsibility map

All application symbols below are in [photo_agent.py](../photo_agent.py).

| Symbols / lines | Responsibility |
|---|---|
| Constants, L38-68 | Extensions, skip names, home-directory state/reports, thresholds: pHash 4, dHash 6, aspect 0.025; SHA chunks 1 MiB. |
| `Photo`, L76 | Mutable path/root, size/mtime, dimensions, hashes, RAW flag, extension. |
| `load_state`, `save_state`, L94/113 | Read JSON roots/moves; write fixed `.tmp`, then replace state. |
| `file_sha`, L128 | Streaming SHA-256 without cancellation checks. |
| `open_picture`, `inspect`, L147/207 | Pillow/RAW decoding, orientation, metadata, thumbnails and perceptual hashes. |
| `quality`, `aspect`, `hamming_int`, L246/268/274 | Heuristic ranking, orientation-independent aspect, bit distance. |
| `BKTree.__init__/add/near`, L284/287/309 | Mutable Hamming-distance search tree. |
| `roots_for_scan`, L341 | Resolve/deduplicate roots; remove nested roots. |
| `scan`, L369; nested `walk_error`/`visual_quality`, L377/523 | Discovery, decode fallback, exact pairs, visual pairs, progress/errors. |
| `verify_and_move`, L642 | Revalidate source/keeper and rename into quarantine; no journal or confirmation boundary. |
| `pretty`, `make_report`, L766/775 | Display formatting, automatic CSV and optional error text. |
| `PhotoApp.__init__/setup_ui`, L856/894 | Load state; create folder list, table, comparison panels, action buttons. |
| `add_folder/remove_folder/save_roots`, L1220/1237/1246 | Source selection and immediate settings persistence. |
| `start_scan/worker/stop_scan/poll`, L1258/1301/1328/1340 | Daemon worker, queue handoff, cancellation event, UI result handling. |
| `show_choice`, L1440 | Decode two previews synchronously on the UI thread. |
| `move_pair/move_selected/move_exact`, L1509/1550/1633 | Confirmations, move coordination, history write, rollback, bulk filtering. |
| `restore_last/open_reports`, L1717/1789 | Restore latest accessible entry; launch platform report viewer. |

`PhotoApp` owns mutable `state`, `photos`, `pairs`, `busy`, preview references,
queue and cancellation event. `scan` also holds all metadata, groups, errors and
the BK-tree in RAM. Shared `Photo` instances have `sha256` populated during scan.
Pairs are dictionaries; `IDENTICAN` and `SLICAN` are both internal and displayed
values. UI, filesystem work, persistence and translated text are tightly coupled.

## Current behavior

1. Resolve selected roots; silently omit unavailable directories. Walk recursively
   with `followlinks=False`, name exclusions, direct symlink checks and path-string
   deduplication. This is not physical-file identity deduplication.
2. Read `stat` before decoding. Pillow applies EXIF transpose and rejects standard
   multiframe images. RAW uses an embedded thumbnail, or half-size 8-bit rendering
   when supported thumbnail extraction is unavailable. RAW dimensions come from
   sensor/image sizes, not necessarily the thumbnail orientation.
3. Reduce previews to at most 320x320, convert to RGB and calculate 64-bit pHash
   and dHash. Decode failures can retain size/mtime-only records for exact matching.
4. Hash only size groups with at least two members. Equal `(size, SHA-256)` groups
   select one keeper by root priority then path; N members produce N-1 pairs.
5. Exclude exact non-keepers from visual comparison. Rank remaining images by RAW,
   pixel count, extension preference, file size, root priority and path. Search
   pHash neighbors, filter by dHash/aspect and select one master. Matched followers
   do not enter the tree: similarity is not propagated through a transitive chain.
6. Queue results to the GUI. `poll` fills the table and writes a semicolon-delimited
   UTF-8-BOM CSV plus optional errors file. Previews reopen the selected files.
7. Individual moves require confirmation; RAW candidates additionally require
   typing `RAW`. Bulk accepts only exact non-RAW candidates with both previews
   successfully hashed. Backup protection is only a warning.
8. Recheck existence, direct symlinks, size and mtime for both candidates. Exact
   pairs receive another mutual SHA comparison; visual pairs another visual check.
   Check source containment, then rename to a dated UUID-prefixed quarantine path.
9. Append history **after** rename. On save failure, remove the entry and attempt
   rollback. Restore searches history backwards, checks source occupancy, confirms,
   renames and removes the history entry. No restore content digest is checked.

State is `~/.photo_agent_state.json`; reports are `~/PhotoAgentReports`;
quarantine is under the source root. Scan results and fingerprints are not persisted.
See [ARCHITECTURE.md](ARCHITECTURE.md) for component and data-flow diagrams.

## Finding register

H1-H14 preserve identifiers from the completed audit. D1-D6 make its additional
technical-debt findings explicit. Severity is impact; priority is implementation
order. All have high confidence in the stated source behavior. Real platform races,
power loss and decoder crashes remain U unless explicitly noted.

| ID | Priority / severity | Evidence and impact | Planned fix |
|---|---|---|---|
| H1 | P0 / critical | L1535, L1736-1761: unchecked rollback rename; restore check precedes dialog/rename. Linux replacement can overwrite a newly created file (S; OS race U). | S1: atomic no-overwrite operations on each supported platform. |
| H2 | P0 / high | L749, L1515-1545: rename precedes history; failed save+rollback loses in-memory entry (R). Crash can orphan recovery information. | S3: durable intent and restart reconciliation. |
| H3 | P0 / high | L1717-1765: restore trusts JSON paths without expected digest/containment; save failure follows history removal (R). | S2/S3: validate identity, boundaries and restore journal. |
| H4 | P0 / high | L347-351, L392-405, L723-749: junction, ancestor, keeper and destination checks incomplete; scan escape or redirected quarantine possible (S). | S2: root/volume/path policy and final verification. |
| H5 | P0 / medium | L386-405: explicitly selected dated quarantine subfolder is not excluded (S). | S2: quarantine ancestry/identity exclusion. |
| H6 | P0 / high | L650-749: no stable identity/final check; source=keeper reaches mocked rename (R, direct function call only). | S1/S2: different-file check, approved snapshot, stable identity and hash validation. |
| H7 | P0 / high | L94-121: malformed field types accepted, invalid JSON silently resets history (R); shared temp name and no multi-instance coordination (S). | S3: schema validation, locking, durable history. |
| H8 | P0 guardrails; P3 quality / high | L246-265, L1669-1677: RAW always outranks rendered versions; backups only warned. Different solid colors collide in both hashes (R). | S4 now; Q1 later: protect backups/derivatives and expose uncertainty. |
| H9 | P1 / medium | L542, L569-626: exact keeper can be visual candidate (R); moving it leaves dependent rows stale. | B2 invalidation; Q1 explicit group relationships. |
| H10 | P1 / medium | L1408-1433: report exception prevents next poll scheduling (R). | B3: isolate report failure and always restore polling. |
| H11 | P1 / medium | L128, L493-502, L1468, L1686: cancellation skips remainder-of-group checks (R); preview/moves block UI (S). | B2: cancellable workers and controlled shutdown. |
| H12 | P1 / medium | L147-200: full/native decoding in GUI process, no application resource policy (S). Pillow has its own pixel guard; no specific library exploit established. | B4: resource policy and malformed-input tests; decide process isolation from evidence. |
| H13 | P1 / medium | L349, L1733: unavailable roots/restore destinations silently skipped (S). | B2: per-source availability and incomplete-result status. |
| H14 | P1 / medium | `napravi_demo.py:3`, `README.md:40,44`: wrong import (R), nonexistent documented filename; fixed demo paths can overwrite fixtures (S). | T1: repair demo/docs and isolate synthetic output. |
| D1 | P1 / medium | L854-1822: monolithic controller, untyped pair dictionaries, translated identifiers/text in core. | B1: typed models, service boundaries and stable error codes. |
| D2 | P1 / medium | Git tracks 5,136 `.venv` files; `.venv/pyvenv.cfg:1-5` embeds machine paths. | B5: reproducible environments and separately reviewed Git cleanup. |
| D3 | P1 / medium | Launchers check only PIL/imagehash/rawpy; HEIF/version checks incomplete; Linux minimum Python not checked. | B5: capability/version preflight and offline installation instructions. |
| D4 | P0 history; P1 diagnostics / medium | L432, L1490, L1539, L1763: errors transient or suppressed; restore removes operation history. | S3 durable events; B3 structured diagnostics. |
| D5 | P1 / low | L782-794: second-resolution report name plus write mode can replace an existing report. | B3: exclusive unique report creation. |
| D6 | P1 evidence; P3 recommendation / medium | L76-87, L183-200, L246: no EXIF/edit/sidecar model. Rename avoids transcoding; XMP is left behind. Metadata preservation integration tests absent. | T1/B4 fixtures and extraction; Q1 derivative-aware recommendations. |

Every P0/P1 item maps to a backlog task in [ROADMAP.md](ROADMAP.md). Existing
SHA checks, confirmation, RAW defaults and non-transitive matching must survive fixes.

## Performance and gaps

Source-supported bottlenecks: decode every file before exact analysis (L427),
repeat all work on rescans, retain all results in RAM, repeatedly hash the same
keeper (L684), rewrite growing JSON after every move (L1519), and populate all
table rows at once (L1383). BK-tree worst-case performance is not logarithmically
guaranteed. No archive benchmark was run. B2/B3 address UI blocking; I1/I2 address
indexing and measured performance without weakening safety verification.

The application has only exact/visual pairs, no derivative/capture classification,
SQLite, migrations, themes, language switching, persistent audit, or packaged release.
Current GUI, RAW/HEIF/AVIF files, real move/restore, EXIF fidelity, Linux behavior,
power-loss recovery and concurrent instances remain unverified end to end.

Earlier local runtime snapshot: Python 3.12.10, Tk 8.6, Pillow 13.0.0,
ImageHash 4.3.2, rawpy 0.28.0 / LibRaw 0.22.2, pillow-heif 1.8.1,
NumPy 2.5.4, SciPy 1.18.1, PyWavelets 1.10.0, pip 25.0.1.
pytest and PySide6 were absent. These are observations, not pinned dependencies
or evidence that every codec/file variant works.

