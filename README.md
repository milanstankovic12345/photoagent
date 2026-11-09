# PhotoAgent v2.4 (Qt acceptance pending)

Offline desktop application for reviewing exact and visually similar photographs.
Qt supports English and Serbian Latin; the retained Tk interface uses Serbian Latin.
Python 3.12+; Windows 10/11 and Linux
source adapters. Native Linux execution and valid RAW decoding are not yet verified.

## Install and run

Windows: run `start_windows.bat`. It creates a project `.venv` with Python 3.12 if
needed, checks Python/dependencies/the selected toolkit, installs missing requirements,
then starts `photo_agent.py`. Tcl/Tk is needed only for `--ui tk`.

Double-click `start_windows.bat` to open the new Qt interface. Qt is also the default
for `bash start_linux.sh` and `python -B photo_agent.py`. The five destinations are
Dashboard, Scan, Duplicates, Quarantine history and Settings. Open a selected pair
with Enter, double-click or Compare inside Duplicates. Back to group (Alt+Left)
preserves filters, sorting, group, result page and selection without reloading.
Use `start_windows.bat --ui tk` (or `python -B photo_agent.py --ui tk`) for Tkinter.
The theme defaults to Dark and respects any saved theme preference.
Settings groups Appearance, Language, Scanning, Similarity Detection, Safety,
Storage and About. Dashboard and Settings share the same Dark/Light/System control;
theme changes save immediately. Source folders are listed in their saved priority
order, with a link to edit them on Scan. Settings → Language switches between
English and Srpski (latinica) immediately, including open confirmations and previews,
without losing review choices or approving an operation. The preference saves on the
service worker (after a running scan); a failed save restores the last saved choice.
A fresh installation without `.photo_agent_state.json` starts in English. Existing
`en`/`sr_Latn` choices are preserved; an existing state file without `language` keeps
Serbian Latin. Invalid language values fall back to English with a warning.
Task010 adds explicit keyboard focus order, distinct accessible preview names,
readable error summaries with technical details on request, and wrapping paths and
preview actions. Confirmation opens on Cancel; Enter never approves. At narrow
logical widths comparison stacks the photographs vertically. Task012 adds complete
Qt EN/SR catalogs, including service-error summaries, tooltips, accessibility labels,
and the framework controls used in folder selection and text context menus. Missing
translations fall back to English; unknown keys and bad formatting show a readable
message. Paths, hashes, stored identifiers, CSV fields and raw technical diagnostics
remain unchanged. `RAW` remains the exact confirmation token in both languages.
See [accessibility behavior and verification limits](docs/design/ACCESSIBILITY.md).
Task011 adds an isolated Qt capture/geometry driver and regression evidence for
1280×720, 1366×768, 1650×900 and 1920×1080 at actual offscreen DPR 1/1.25/1.5.
See the [Stage H verification report](docs/design/TASK011_VERIFICATION.md) for
screenshots, exact commands, findings and remaining native display checks.
The full Prompt 6.1 acceptance gate remains open for native platform verification.
For a normal launch with your saved application state:
`.\.venv\Scripts\python.exe -B photo_agent.py --ui qt`.
Use the isolated capture tool for testing; the CLI has no `--home` option.
Qt mode needs PySide6 >=6.8,<7; preflight checks only the selected toolkit.
See [Qt distribution notes](docs/QT_DISTRIBUTION.md).

Linux: provide Python 3.12+ and venv through your distribution, then run
`bash start_linux.sh`. The launcher does not install system packages.
Tkinter is optional and needed only for `--ui tk`.

Dependency installation requires available packages (network or a local wheelhouse).
Once installed, all application work is offline; no accounts, telemetry or external
AI services are used. To install offline into an existing environment:

```text
python -m pip install --no-index --find-links /path/to/wheels -r requirements.txt
python -B photo_agent.py
```

## Review workflow

Qt Dashboard separates the whole local index from the latest scan's EXACT
candidates and direct VISUAL links. Start your first scan, add folders, then Start
Scan; advanced source ordering and error details are collapsed initially. Progress
shows actual counts and elapsed time without inventing a percentage. Review Results
opens Duplicates; a dashboard candidate opens its direct group. Up to three real
candidates have previews loaded only while visible. Completed scans without matches
are distinct from an application with no scan. CSV reports remain a secondary action;
a report failure does not discard the scan. Failed, interrupted and cancelled scans
cannot authorize quarantine.

1. Add folders in priority order and start a scan. Missing/inaccessible sources and
   decoding failures produce an explicit incomplete result. Stop cancels work.
2. EXACT means full SHA-256 equality. VISUAL means similarity only: review both
   photographs, edits and RAW/rendered representations. Quality ranking is heuristic.
3. Browse group cards in Grid/List, search names/paths, choose All, Exact Copies or
   Similar Photos, and sort across the whole session. Open a group or select a row
   for side-by-side previews. A failed preview does not prevent binary
   exact comparison, but disqualifies the pair from bulk operations.
4. Qt: explicitly select Keep This Photo on either card. EXACT groups allow multiple
   retained versions: checked photos remain; only explicitly reviewed, unchecked
   photos enter the proposal (up to 200 reviewed photos per plan). Other group
   members remain untouched. Expand the member list to browse pages. VISUAL choices
   apply only to the displayed direct pair. Keep Both clears the move proposal.
   Then prepare a plan and read its source/keeper/destination preview. Technical
   details start collapsed; RAW/legacy/XMP/backup/non-exact warnings remain visible.
   Approval requires the explicit button; Enter does not approve. RAW sources
   additionally require typing RAW.
5. Bulk accepts only decoded EXACT pairs within the same selected root, without RAW
   on either side or XMP sidecars. Copies across roots require individual review
   because they may be deliberate backups. XMP is never automatically moved.
6. Qt: after one successful quarantine, contextual Restore targets that exact
   operation ID through a new preparation/confirmation. History also permits
   restoring a selected eligible row. Tkinter: restore the latest
   eligible entry. The application verifies bytes and
   identity again and never overwrites an existing original path. Legacy entries
   require an additional individual warning because their earlier bytes are unknown.

Quarantine history shows the original name/location, recorded move completion time
in UTC, manifest size, status and operation type. Missing legacy data and the actual
move time of an operation discovered during crash recovery show “Nije dostupno”.
The latest journal transition is not presented as the original move date. Selecting
a row loads an optional thumbnail from its verified current quarantine destination;
a failed preview does not prevent history review or service-based restore preparation.
Selection is bound to the operation ID, including after refresh/pagination.
Open Quarantine Folder opens that record's actual per-root folder, never a global
quarantine directory. Existing restore destinations are preserved without fallback.

Similarity search presets apply to the **next scan** after Save Settings:

| Preset | pHash / dHash maximum distance |
|---|---|
| Strict | 2 / 3 |
| Balanced (existing defaults) | 4 / 6 |
| Broader Search | 8 / 10 |
| Custom / Advanced | Existing or manually edited values, each 0–64 |

These choices describe search breadth and are not qualitatively calibrated.
Stricter settings can miss candidates; broader settings can include more false
candidates. VISUAL always requires review. Custom thresholds survive theme changes
and restarts; unknown settings keys and legacy history are retained on every write.
Storage shows the active index path (including temporary fallback) and the number
of indexed physical files excluding records marked missing/moved. Offline records
remain counted. Preview cache is an in-memory LRU budget of 64 MiB, not measured disk
usage or a cap on total process memory. History thumbnails are uncached. Recovery
data cannot be cleared from Settings.

The application moves photographs into `.photo_agent_quarantine/YYYY-MM-DD/` under
the source root; it never permanently deletes them. It does not copy/delete across
drives. Do not edit or reorganize the library while approving/executing a plan.

Qt uses 24 group/member rows per page by default (service maximum: 200); Tk uses
200 result rows per page. CSV and bulk EXACT selection cover the whole scan.
Incomplete scans remain reviewable but do not authorize moves. The disposable
index is `~/.photo_agent_index.sqlite3`; its loss never removes recovery history.
Settings: `~/.photo_agent_state.json`. Journal: `~/.photo_agent_operations/`.
Reports: `~/PhotoAgentReports/`. Legacy history is backed up before import. Do not
remove manifests or backups while an operation needs recovery. A second application
instance may scan, but only one instance may write settings/history or move files.

Qt search/sorting cover the entire session; groups use direct keeper links.
Dashboard space estimates are not approved plans. Quarantine on the same disk does
not free space. Dark/Light/System themes persist across restarts. Language switching
is inactive in this milestone. pHash/dHash thresholds (0–64, defaults 4/6) apply only
to the next scan; aspect stays 0.025. Preview zoom/pan/Fit uses a bitmap up to 2048 px;
100% means preview pixels. Focus, noise and edit provenance are not measured.
Enlarged previews use the same bounded bitmap, never original full resolution.
Photo Details exposes full paths/SHA and available metadata. Gallery review status
records only UI decisions during the current scan/application session; it is not
persisted and is independent of the operation journal. Qt hides unsupported
DERIVATIVE/SIMILAR_CAPTURE/RAW+JPEG classifications.

## Synthetic demo and tests

Choose a NEW destination; an existing directory is refused:

```powershell
.\.venv\Scripts\python.exe -B napravi_demo.py .\demo_photo_collection
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -B -m pytest -p no:cacheprovider tests
git diff --check
```

Linux uses `.venv/bin/python`. Tests redirect application state, reports, decoder
inputs and file operations to isolated synthetic temporary directories. They never
use an actual photo collection. See [test evidence](docs/TESTING.md).

## Formats and limits

Standard extensions: JPEG, PNG, TIFF, BMP, WebP, HEIC/HEIF, AVIF. RAW extensions
include NEF, CR2/CR3, ARW, DNG, RAF, ORF, RW2 and others supported by LibRaw.
Actual codec support depends on Pillow, pillow-heif and rawpy/LibRaw. Successful
valid RAW decoding remains unverified without a suitable test fixture. Corrupt RAW
and PNG/JPEG/WebP paths have automated coverage.

Decoding runs in a disposable process with a 100 megapixel / 60 second request
limit; this is not a strict memory sandbox. Hashes are revalidated before each
operation. The SQLite index reuses validated image metadata and perceptual hashes; every scan still reads each file fully for SHA-256. DERIVATIVE and
SIMILAR_CAPTURE identifiers exist but are not automatically inferred. PySide6 and
themes and English/Serbian language switching are available through `--ui qt`.
Tk language switching, native Linux/DPI acceptance and release packaging remain open.

Process-exit tests are not proof against physical power loss. Linux namespace races,
network filesystems, real removable-media behavior and packaged distribution still
require further validation. See [safety and recovery](docs/SECURITY.md),
[architecture](docs/ARCHITECTURE.md), [historical audit](docs/REVERSE_ENGINEERING.md)
and [roadmap](docs/ROADMAP.md).
