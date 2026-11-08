# PhotoAgent v2.2 architecture

The Tkinter interface remains in use, with 200-row result pages. v2.2 adds a
disposable SQLite index and application orchestration to the stabilized v2.1 core.
PySide6, themes, full language switching and packaging remain future work.

## Actual components

| Component | Responsibility |
|---|---|
| `photo_agent.py` | Runtime preflight and desktop entry point. Importing it does not start Tk. |
| `app/core/` | Frozen models including ScanSummary; cancellable streaming SHA-256. |
| `app/scanning/scanner.py` | Compatible in-memory scan adapter for small collections and regressions. |
| `app/scanning/discovery.py`, `inspection.py` | Safe sorted traversal with disk spooling; metadata between stable full-content snapshots. |
| `app/scanning/decoder.py`, `fingerprints.py` | Disposable decoder, perceptual hashes and optional bounded preview bitmap. Index mode omits PNG encoding. |
| `app/matching/matcher.py`, `indexed.py`, `quality.py` | Reference/disk-backed direct matching and the separate original quality heuristic. |
| `app/storage/index.py` | Migrations, independent index writer lease, thread-confined SQLite, cache and paged results. |
| `app/safety/paths.py` | No-redirection paths, file/root identities, streaming SHA-256, XMP discovery. |
| `app/safety/native.py` | Native no-replace rename and safe directory creation; no copy/delete fallback. |
| `app/safety/journal.py` | OS writer lock, versioned per-operation JSON manifests, durable atomic writes, legacy import. |
| `app/safety/operations.py` | Frozen operation plans, approval validation, quarantine, recovery and restore. |
| `app/services/` | Application orchestration, incremental indexing, settings, streaming reports and preflight. |
| `app/ui/tk_app.py` | Existing desktop layout, main-thread dialogs/widgets, background coordination. |
| `app/i18n/` | New safety/status resources and fallback; existing UI remains Serbian Latin. |
| `tests/` | Synthetic fixtures, native filesystem, process interruption and hidden Tk regressions. |

Core, matching and safety do not import Tkinter. The controller dispatches scanning,
verification, reports, planning, recovery and operations to one executor thread.
Decoder subprocesses return JSON; preview mode adds a PNG thumbnail. The main thread creates
Tk images from that bounded bitmap; it never opens the original for decoding.
Preview generation tokens discard results from a previous selection or scan.
Closing cancels pending work and waits for the active operation to finish or retain
its recovery intent. Queue polling is rescheduled in a finally block.

## Matching and state

Every accepted file has a fresh full SHA-256 snapshot. A cache hit requires matching
identity, size, handle mtime/ctime, SHA-256, root identity, decoder version and valid
fingerprint data. It skips decoding, not reading bytes. Cache misses retain full
before/after decoding checks. Failed decoding is retried.
Exact groups choose one keeper by selected-root order, then path. N files produce
N-1 candidates. Overlapping roots retain selection priority; path and device/inode
indexes remove repeats and hardlink aliases. A visual follower never becomes a matching
representative, preventing transitive A-B-C conclusions. Equal visual hashes can be
false positives (including solid colors); only equal SHA-256 means EXACT.
DERIVATIVE and SIMILAR_CAPTURE are defined identifiers, not inferred categories.

Settings remain at `~/.photo_agent_state.json`. Legacy move entries are preserved
there and backed up byte-for-byte before import. New operation manifests live at
`~/.photo_agent_operations/<id>.json`; reports at `~/PhotoAgentReports`.
Quarantine stays under the selected source root. No photographs are transcoded
by an operation and no binary images are stored in the journal.

The approved plan freezes source, keeper, destination, identities, metadata and full
hashes. Execution rechecks them through open file handles, durably records intent,
performs the native no-replace rename, verifies the result and records completion.
Restore creates a new operation referencing the old one. History is retained.
See [SECURITY.md](SECURITY.md) for failure states and platform limits.

## SQLite schema version 1

Default: `~/.photo_agent_index.sqlite3`; tests/services can inject another path.
`PRAGMA user_version` selects ordered transactional migrations. A non-empty unknown
database or newer schema is refused; upgrades use SQLite's backup API first.
Foreign keys, UNIQUE/CHECK constraints, parameterized SQL, WAL and synchronous FULL
are enabled. Connections belong to their executor thread. One independent OS lease
owns index writes; competing instances use private temporary indexes. Transactions
contain bounded units (one file, root transition or match). Decoding/hashing never
occur inside a write transaction. Lock waits are bounded to five seconds and
cancellable; SQL progress callbacks also honor cancel.

| Table | Data / responsibility |
|---|---|
| scan_roots | Original/normalized path, device/inode and availability; replaced roots keep separate identities. |
| scan_sessions | UUID, lifecycle, timestamps and measured counters. |
| scan_session_roots | Selected root order and traversal outcome. |
| photo_files | Root/path identity, size, nanosecond times, SHA-256, snapshot, last-seen generation, state/error. |
| image_fingerprints | Dimensions, actual format, RAW flag and hashes in a typed JSON payload; pipeline version/checksum. |
| scan_entries | Session snapshots, discovery order, searchable matching fields and per-path errors. |
| match_results | Direct keeper/duplicate relationships, kind and distances; no transitive visual groups. |
| quarantine_operations | Rebuildable JSON-manifest projection, never recovery authority. |

Path, physical identity, scan generation, exact grouping and quality queries have
indexes. File identities use decimal TEXT because Windows file IDs can exceed
SQLite's signed 64-bit range. Image bytes are not stored.

Only complete enumeration of the same root marks unseen files missing. Offline,
partially read, cancelled or replaced roots cannot sweep old records. Verified
same-identity/same-hash renames mark the old path moved; indexing never moves files.
On restart, running sessions become interrupted. Committed cache rows require fresh
validation. Cancelled sessions expose no pairs. Incomplete sessions retain reviewable
matches/CSV but cannot authorize quarantine.

Exact grouping uses ordered SQL. Visual matching uses TEMP BK-tree nodes, members
and a disk-backed search frontier. SQLite's page cache is 8 MiB; TEMP storage is on
disk. Directory enumeration, reports and result pages do not retain the collection
in Python. The compatibility adapter and frozen operation plans still materialize
their results/moves; they are not constant-memory APIs.

Application runs on the existing executor. ScanSummary carries counts; page queries
return at most 200 pairs/photos. CSV and bulk selection cover the entire session.
Candidates are freshly inspected before plan confirmation, then verified again
through pinned handles immediately before moving. Index-only image_format metadata
is omitted from version-1 journal manifests to preserve v2.1 recovery compatibility.

No automatic retention policy deletes scan history. Disk usage grows with sessions.
A corrupt/newer index is preserved and bypassed with a temporary index. Rebuilding
the disposable index never replaces operation manifests or settings.
