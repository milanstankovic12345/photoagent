# PhotoAgent v2.4 architecture

`app/ui/qt/`, selected with `--ui qt`, contains bootstrap, controller, workers,
screen components, named navigation, table model, themes and local SVG resources.
Qt is now the default; `--ui tk` selects the retained Tkinter adapter. Both share the existing core.
Qt supports English/Serbian runtime switching; Tk remains Serbian. Task013 adds a
source ZIP/wheelhouse candidate; full platform release acceptance remains open.

`tools/build_release.py` packages allowlisted sources, catalogs, resource modules,
hash-pinned runtime wheels and their notices. `packaging/install_offline.py` verifies
the manifest before creating a new isolated `.runtime`; packaged launchers never
bootstrap from the network. `tools/release_smoke.py` exercises the installed runtime
in fresh processes using generated fixtures and temporary application/Qt state.
The ordinary `python -m app.scanning.decoder` child dispatch is preserved; no frozen
dispatch, backend/schema/journal change or uninstall behavior is introduced.
See [RELEASE.md](RELEASE.md) for actual target, prerequisites and open gates.

Task012 stores the single authoritative catalogs in `app/i18n/en.json` and
`sr_Latn.json`. The framework-independent translator provides safe English fallback;
legacy Tk calls retain their Serbian default. Qt `strings.tr` returns readable text
with a stable key/argument recipe. `localization.set_text` binds that recipe to the
existing widget property; language changes rerender text with signals blocked,
without rebuilding widgets, resetting models, restarting workers or touching plans.
Models emit data/header changes; history cells and source accessibility roles update
in place. Bindings are QObject children, so destroyed controls disconnect naturally.
Composed messages retain their nested recipes; literal paths never become keys.

An application-owned `LanguageManager` coordinates the Qt thread. The small native
`QTranslator` adapter maps used framework strings to the same catalogs because the
tested PySide6 distribution has no Serbian Latin qtbase catalog. It translates file
picker and text-edit controls without maintaining duplicate application .ts/.qm files.
The folder chooser is read-only and nonblocking, with a bound caption.
Settings writes remain on the existing service thread; rapid choices retain every
successful write as the rollback baseline. A failed write restores that baseline
without changing a pending plan or consent. State-file absence selects English;
legacy files with no language select Serbian; invalid values select English and warn.
No database, matching or operation-journal format changes are involved.

Task011 adds verification tools, without changing application services, widgets,
matching, RAW extraction, SQLite schema or the recovery journal.
`tools/capture_task011.py` constructs `MainWindow(temporary_home)` and generated
photos, drives real workers and explicit synthetic operation approvals, and records
widget geometry, physical pixels, DPR, horizontal scroll and toolbar containment.
Each scale runs in a fresh Qt process. `tools/review_task011.py` verifies hashes
and the complete 4-size × 2-theme × 6-surface matrix per scale, then assembles
contact sheets. Its separate review marker records subsequent visual inspection;
automated geometry assertions alone do not constitute visual acceptance.
Stopped windows are disposed before opening replacements; completion is published
only after workers and sandbox cleanup finish. Output directories must be new,
so earlier evidence is retained. Temporary HOME,
settings/index/journal/reports and decoder environment are isolated and restored.
On Windows the shared Windows Temp path avoids putting real profile/library names
in public screenshots. See [Stage H evidence and limits](design/TASK011_VERIFICATION.md).

Historically, Task010 kept the Qt/shared Serbian catalogs. `strings.tr` preserved
known shared fallbacks while replacing unknown keys/formatting failures with a
readable message. `TechnicalDetails` presents raw diagnostics only on request;
workers and safety services retain their technical contracts. English intentions
were documentation in `docs/design/QT_TEXT_INVENTORY.json`. Task012 supersedes that
inventory with the implemented catalog keys; runtime text lives only in `app/i18n/`.
The shell defines per-screen keyboard order, while PlanDialog owns safe initial
Cancel focus and consent handling. Path labels constrain long values; comparison
stacks at narrow logical widths. See `docs/design/ACCESSIBILITY.md` for contracts
and the limits of offscreen accessibility evidence.

Task009 separates history/settings presentation into
`app/ui/qt/quarantine_settings.py`, re-exported by `screens.py`. `HistoryEntry`
adds optional manifest move-completion date and expected size, action and restore
reference status without changing journal version 1. `at` retains its old meaning
(latest transition and history sort order). Legacy import and recovery reconciliation
timestamps never substitute for an unknown actual move time.

`app/services/quarantine.py` resolves a selected operation's per-root quarantine
folder and verifies current thumbnail input using root identity, containment,
file identity, size, mtime and full SHA-256. Fresh ctime is used only after those
surviving rename fields pass; PreviewService then validates the fresh full snapshot
around decoding. The service worker prepares uncached 320 px history thumbnails;
the controller cancels stale requests and rejects stale replies without making
optional preview failures block Restore. Restore still uses the existing ID-specific
prepare/PlanDialog/Approval/execute path. UI selection and refreshed rows use
operation IDs; page changes clear selection and invalidate pending plans.

Settings uses the existing patch-merge persistence and MatchingOptions limits.
Presets 2/3, 4/6 and 8/10 describe search breadth without calibration claims;
unrecognized threshold pairs remain Custom. ThemeSelector is shared with Dashboard.
StorageSummary reads the actual active Index.path and physical-file count, including
offline records and excluding missing/moved records. No measured cache occupancy,
recovery cleanup, language switch, safety-disable control or schema migration is added.
The package version `app.__version__` matches the documented 2.4 baseline.

Task008 adds `app/ui/qt/gallery.py`: QListView/GroupModel/delegate render Grid/List
cards without per-file widgets. GroupRow adds at most two Photo samples and an
optional EXACT byte estimate. The read-only group query aggregates full direct
groups despite search filters; byte estimates deduplicate physical identities and
exclude files retained by any link. No matching/schema/journal changes are made.
The gallery requests at most 24 groups/page, keeps at most 48 rendered thumbnails,
and requests visible photos in batches of three at 320 px. Controller coalesces
preview and thumbnail work separately to one dispatched request plus one latest
pending request per channel. PreviewService still enforces its 64 MiB cache and
fresh full-snapshot checks, including cache hits. GUI models/QPixmap stay on the GUI
thread; all reads, validation and decoding remain in services/workers.

Opening a group fetches bounded pages of all its direct links, independently of
the gallery search. Direct-pair entry fetches the complete group when the current
page does not already contain it. Comparison keeps a bounded snapshot of the
listing query/page/rows/selection; Back restores that context and scroll without a
new query. New scans, filters/sorts and completed operations discard that snapshot.
Photo cards retain fit/zoom, compact error/loading states, an enlarged <=2048 px
preview and collapsed metadata/heuristic details. Member navigation is collapsed
below the photo actions; short windows scroll vertically.

Qt review state is a per-scan in-memory set of directly reviewed MatchRow IDs,
separate from journal transitions. It is not persisted. EXACT review tracks at most
200 explicitly reviewed photos plus retained choices in one group; unchecked
reviewed candidates can reference an explicitly retained SHA-identical photo.
Unreviewed members remain untouched and multiple keepers are allowed. VISUAL uses
only one displayed direct pair, never a transitive reanchoring. Keep Both clears
the move proposal. Selection/query/keeper/navigation changes invalidate plans;
debounced edits supersede old query/preparation responses immediately. Every
proposal still goes through Application.prepare and PlanDialog -> explicit
Approval -> Application.execute. Warnings and RAW/legacy consent remain visible;
Enter cannot approve. Successful single moves expose a Restore action for their
specific operation ID, rechecked through history and restore_plan. Failures report
details and defer recovery authority to the journal.

Task007 moves Dashboard/Scan presentation into `app/ui/qt/dashboard_scan.py`.
DashboardSummary retains its existing fields and adds session photo count, EXACT
group count, finished time and at most three MatchRow candidates. Read-only service
queries count inspected session photos separately from whole-index physical files;
EXACT groups use the existing grouping query. Estimated bytes count unique physical
EXACT candidates, excluding any retained physical file and all VISUAL links. These
cached estimates never authorize a move. No schema or matching changes are needed.

The dashboard uses the existing preview thread/cache, with a separate cancellation
event and request generation from comparison previews. Only viewport-intersecting
candidate cards request thumbnails (320 px, at most three). Hiding/replacing the
dashboard, starting a scan, cancellation and close supersede those responses.
Source availability is read on the service thread before scanning. Sources retain
their priority order, with reorder controls in a collapsed section. A scan-specific
timer/progress state is independent of other service activity: unknown totals remain
indeterminate, and overlapping discovered/processed/skipped/failed counts are never
summed into a percentage. The activity card moves above sources during work and
for results so status and elapsed time fit short windows. Completion uses the dashboard session query; report errors
and worker failures have separate presentation. Existing service safety checks remain
authoritative for all operations.

Task006 supplies five `Route` destinations in `navigation.py`: Dashboard, Scan,
Duplicates, Quarantine and Settings. The 208 logical-pixel sidebar uses the local
brand resource and distinct Qt standard icons; Settings sits below a layout stretch.
The shell owns one PageHeader, contextual toolbar area and status bar. Each screen
owns its actions and body; WrappingLayout keeps toolbar actions above the scrollable
content on narrow screens. Explicit Tab order follows the visible shell.
DuplicatesFlow retains its list and comparison widgets in a nested stack. Enter or
double-click opens a selected pair; Back/Alt+Left returns focus to the table. Named
navigation retains live views; Back restores the bounded cached listing without
fetching session data, so query, page/group offsets, sort, selection and scroll
remain in memory. Leaving and
returning to Duplicates also preserves its active inner view.

Navigation/Back invalidate pending plans and reject an open confirmation; they
never approve operations. Selection, filters, paging, sorting, root changes and new
scans invalidate old selection/preview/plan state. Keeper choices invalidate plans;
the fixed left/right photo previews retain their identity. The debounced search timer is stopped on scan/close. Service
coordination, SQLite thread ownership and asynchronous shutdown remain unchanged.

Task005 extends the same ThemeManager with semantic Dark/Light tokens, logical
spacing/type metrics and one application stylesheet. Shared cards, headers,
badges, collapsible sections and action variants live in `components.py`.
PhotoView handles presentation states only; decoded images still arrive from the
preview worker. See [DESIGN_SYSTEM.md](design/DESIGN_SYSTEM.md) for APIs/evidence.

`app/core/queries.py` supplies frozen query/page/dashboard/history/progress contracts
and matching options. `app/services/queries.py` executes whole-session SQLite
search/sort with parameters, allowlisted columns and stable IDs. Direct groups use
(kind, keeper). Journal records supply history; SQLite projections do not authorize
restore. A selected ineligible restore ID fails without choosing another entry.

Qt constructs, uses and closes Application/SQLite on one long-lived QObject/QThread.
A separate worker uses `app/services/preview.py` without SQLite; it creates QImage
off-thread. Only the GUI thread changes widgets/models or creates QPixmap.
Request tokens discard stale results; cancellation sets threading.Event directly.
Closing rejects plans and queues shutdown after active work, without terminate or
blocking waits on the GUI thread. Plans require fresh preparation and explicit Approval.

Settings updates merge atomically and preserve unknown fields and legacy history.
Invalid UI preferences fall back with warnings; damaged recovery data still blocks
operations. Matching parameters live in existing session metrics JSON; schema v1
and the journal format are unchanged. Progress is coalesced about every 150 ms.
Discovered counts yielded paths; skipped counts previously observed paths/identities;
processed counts indexed inspections (including decode failures); failed counts
inspection/decode/traversal/source failures. These counts can overlap.

Preview keys include path, full snapshot, size, preview version and library versions.
Full SHA is verified before/after preparation, including cache hits. The decoded
QImage cache is capped at 64 MiB (UI pixmaps/in-flight buffers are separate).
The 880→320 fingerprint path is unchanged; previews can grow to 2048 px.
ThemeManager applies global palette/styles with System/Unknown dark fallback.
UI messages use stable shared keys and translation fallback; Qt supports EN/SR,
while Tk continues to request Serbian text.

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
| `app/i18n/` | Shared EN/SR catalogs, parameterized messages and safe fallback. Qt switches live; Tk uses Serbian. |
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
