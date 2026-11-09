# PhotoAgent test evidence

## Task010 accessibility and translation preparation (2026-11-09)

Windows, Python 3.12.10, PySide6 6.12.0 / Fusion / offscreen. Existing Microsoft
Store Python cannot launch within the filesystem sandbox; the existing `.venv`
was run through the approved external runner. No packages were installed. All
photos, settings, indexes, journals, quarantine moves and restores were temporary
synthetic fixtures. Existing uncommitted Task007–009 work was retained.

Final passing regression runs, **89 distinct cases, zero skips**:

```powershell
$env:QT_QPA_PLATFORM = 'offscreen'
.\.venv\Scripts\python.exe -B -m pytest -p no:cacheprovider tests/test_task008.py tests/test_task009.py tests/test_task010.py tests/test_operations.py tests/test_recovery.py tests/test_additional_safety.py -x -q -o faulthandler_timeout=90
# 63 passed in 354.31s; this collection preceded the added empty-plan case.
.\.venv\Scripts\python.exe -B -m pytest -p no:cacheprovider tests/test_qt.py tests/test_qt_design_system.py tests/test_task010.py::test_empty_plan_message_is_nonblocking_and_cannot_approve -x -q -o faulthandler_timeout=90
# 26 passed in 269.37s, including the added empty-plan case.
git -c core.safecrlf=false diff --check
# Passed.
```

The final Task010 module contains 11 cases: ten in the first command and the new
empty-plan case in the second. Coverage includes actual keyboard source addition
(folder chooser returns a fixture path), filters, group activation, comparison,
Keep Both, cancelled and explicitly approved synthetic quarantine, history restore,
Settings save, RAW/legacy consent, visible contextual warnings, Enter rejection,
initial Cancel focus and focus return. Tests also check safe missing-key/format
fallback and all 291 inventory keys; shared English resources and Serbian settings
are preserved. Errors retain selectable plain-text diagnostics behind a keyboard
toggle. Other checks cover distinct accessible preview names, `QAccessible` names,
Unicode glyph support through `inFontUcs4`, long paths and expanded future labels,
read-only table/editor Tab escape, enlarged-preview Close/focus return, painted
focus/selection differences and thumbnails remaining visible under gallery focus.
Existing contrast checks cover text >=4.5:1 and control/focus outlines >=3:1 in
both themes. Existing RAW/XMP/backup/no-overwrite/recovery/cancellation checks ran.

During development, new tests exposed hidden-row gallery focus, initial dialog
focus replacement, an approval button missing from Tab order, table Tab trapping,
enlarged-preview focus return and narrow comparison overflow. These were fixed.
Visual review found the gallery focus rectangle filling over the card and a poor
icon-only enlarge action; the rectangle is now unfilled and enlargement has a
readable text button. A combined regression first failed after 14 passes because a
hidden gallery refresh cancelled Dashboard thumbnails; the isolated test passed
after ownership-aware cancellation, and the final Qt run covers it with an added
late-refresh assertion. An initial glyph assertion used `inFont(str)`; explicit
Unicode codepoint checks with `inFontUcs4` passed in both themes.

One subsequent long combined offscreen process stopped making progress at
`test_exact_multiple_keepers_pagination_and_no_default_move` and was terminated;
it is **not** reported as a passing run. The case passed alone in 28.67s and in
the final fresh group above. Its original hang was not reproduced or conclusively
diagnosed. The empty-plan message was also changed to a nonblocking, localized
Close-only message and given its own passing test; this is not claimed as proof
of that earlier hang's cause. The final evidence consists of the two clean groups,
not a single complete repository-suite invocation. Earlier baseline design checks
passed 5 cases and the initial focused design/query/sidebar set passed 8 cases.

Capture commands (each scale uses a fresh Qt process; choose a new output
directory on subsequent runs):

```powershell
$env:QT_QPA_PLATFORM = 'offscreen'
$env:QT_SCALE_FACTOR = '1'
.\.venv\Scripts\python.exe -B -m tools.capture_task010 --output docs/design/verification/task010/current/100
$env:QT_SCALE_FACTOR = '1.25'
.\.venv\Scripts\python.exe -B -m tools.capture_task010 --output docs/design/verification/task010/current/125
$env:QT_SCALE_FACTOR = '1.5'
.\.venv\Scripts\python.exe -B -m tools.capture_task010 --output docs/design/verification/task010/current/150
.\.venv\Scripts\python.exe -B -m tools.review_task010 docs/design/verification/task010/current
# 20 captures per scale verified: SHA-256, image dimensions and actual DPR.
# Six review sheets created and opened; 60 original captures retained.
```

Captured logical sizes are 1280×720, 1024×576 and 853×480; actual Qt DPR is 1,
1.25 and 1.5 respectively, producing 1280×720 pixel main-window captures (subject
to Qt rounding). These are real `QT_SCALE_FACTOR` runs, not resized screenshots.
Main pages, selected comparison, unavailable preview/open details, normal and
RAW/legacy/VISUAL/XMP confirmations and Settings diagnostics were reviewed in both
themes. Long generated names/paths contain Serbian diacritics. The driver checks
zero primary-page horizontal overflow and unchanged bytes of all generated photos;
it never executes a move. Warning/preview failures are injected presentation
fixtures, not successful RAW decoding or real disk failures. Gallery thumbnails
are decoded through actual services. Tall content remains vertically scrollable.
Only this session's superseded Task010 captures were removed; earlier task evidence
was preserved. Final manifests and review sheets are under
`docs/design/verification/task010/current/{100,125,150}/`.

Manual NVDA/Narrator and other assistive-technology testing, native Windows/Linux
physical-display DPI behavior, native folder chooser interaction, Task011's full
resolution/state matrix, valid RAW decoding, physical-drive unplug/power loss and
packaging were **not verified** in Task010. No full repository suite is claimed.
Runtime language switching, English installation defaults and full catalog coverage
remain Task012. `app/services/state.py` and shared `app/i18n/` resources were not
changed by Task010.

Task010 changed files: `.gitignore`, `README.md`,
`app/ui/qt/{components,dashboard_scan,gallery,models,quarantine_settings,screens,strings,themes,window}.py`,
`tests/{test_qt,test_qt_design_system,test_task010}.py`,
`tools/{capture_task010,review_task010}.py`,
`docs/{ARCHITECTURE,CHANGELOG,ROADMAP,TESTING}.md`,
`docs/design/{ACCESSIBILITY.md,QT_TEXT_INVENTORY.json}`, the Task010 capture directory
and the local `task/Task010.md` status. Other pre-existing working-tree changes
were retained. Safety services, matching, decoder, schema and journal formats were
not modified by this task.

## Task009 quarantine and settings (2026-11-09)

Windows, Python 3.12.10, PySide6 6.12.0 / Fusion / offscreen. Every photograph,
index, journal, collision and move uses synthetic fixtures and isolated temporary
directories. Existing Microsoft Store Python requires the approved external runner;
no dependency installation or original-library access occurred.

```powershell
$env:QT_QPA_PLATFORM = 'offscreen'
.\.venv\Scripts\python.exe -B -m pytest -p no:cacheprovider tests/test_qt.py::test_five_destinations_scan_compare_query_and_theme_restart -x -q
# 1 passed in 33.20s
.\.venv\Scripts\python.exe -B -m pytest -p no:cacheprovider tests/test_task009.py -x -q
# 13 passed in 148.02s
# Final repeat after readable columns/dates and folder-ID assertions:
# 13 passed in 155.68s
.\.venv\Scripts\python.exe -B -m pytest -p no:cacheprovider tests/test_task009.py::test_history_real_preview_confirmation_restart_and_empty_failure tests/test_task009.py::test_history_settings_errors_toolbar_and_unavailable_features -x -q
# 3 passed in 87.66s after long-path wrapping.
# Final repeat after empty/failure layout adjustment: 3 passed in 92.18s.
.\.venv\Scripts\python.exe -B -m pytest -p no:cacheprovider tests -q
# 177 passed, 2 skipped in 1124.46s (18:44).
.\.venv\Scripts\python.exe -B -m tools.capture_task009 --output docs/design/verification/task009
# Completed: 20 PNGs and manifest.json; expected destination_occupied refusal logged.
git diff --check
# Passed.
```

The full run skipped exactly the licensed valid RAW fixture
(`tests/test_decoder_and_services.py:145`) and native Linux execution
(`tests/test_native_races.py:116`) on this Windows host. Corrupt/undecodable RAW,
Windows file-operation safeguards, recovery and cancellation tests ran.

An initial command also named a nonexistent `test_close_during_plan_does_not_execute`;
collection rejected it and ran no tests. The corrected existing test above passed.
Task009 cases cover read-only manifest observations versus later transitions,
unknown legacy/reconciled dates, correct destination thumbnails and replacement
identity rejection, per-root folders, actual fallback index location, ID-specific
restart restore/collision/no-fallback, preset/custom/theme persistence, unknown
keys/legacy/source ordering, refresh/page/stale-preview selection, actual Qt
restore confirmation/restart, empty/load-error views, and both themes at 853×480.

The full regression run started before the final column/date/wrapping/empty-state
presentation adjustments and the additional folder-ID assertion. The final 13-case
repeat covered readable dates/columns and folder-ID rejection; the final 3-case
repeat covered long-path wrapping and the empty/failure layout. Safety movement,
matching, decoding, storage schema and settings persistence were unchanged between
these runs.

Capture evidence is generated by `tools/capture_task009.py` under
`docs/design/verification/task009/` (20 PNGs and manifest). It drives real workers,
explicitly approves only synthetic quarantine, rejects restore plans, and verifies
the real occupied-destination failure. The history-load failure is injected into
presentation; it does not claim an actual disk failure. Captures include empty and
populated history, Settings top/storage, and restore dialogs in Dark/Light at
1280×800 and 853×480. Native OS folder launching and physical display interaction
are outside this offscreen run; full English/Serbian switching is deferred to Task012.

Changed Task009 sources: `app/__init__.py`, `app/core/queries.py`,
`app/services/{application,queries,quarantine}.py`,
`app/ui/qt/{components,controller,dashboard_scan,quarantine_settings,screens,strings,window,workers}.py`,
`tests/test_task009.py`, `tools/capture_task009.py`, README, ARCHITECTURE,
CHANGELOG, TESTING and `task/Task009.md`. Existing working-tree changes were retained.

## Task008 duplicate gallery and comparison (2026-11-09)

Windows 11, Python 3.12.10, PySide6/Fusion/offscreen. Every scan, preview,
quarantine, restore and collision uses generated files, isolated home/index/journal
and temporary directories. Microsoft Store Python could not launch inside the
filesystem sandbox; existing `.venv` execution used the approved external runner.
No package installation, commit, original-library access or safety-format change.

Task008 changes core `GroupRow`, read-only group queries, Qt `gallery.py` (new),
`components.py`, `models.py`, `screens.py`, `window.py`, `strings.py`, `controller.py`,
`workers.py`, `tests/test_task008.py` (new), `tests/test_qt.py`,
`tests/test_task003_services.py`, `tools/capture_task008.py` (new), the existing
audit driver's explicit keeper choice, README, ARCHITECTURE, CHANGELOG and this
document. Pre-existing Task005–007 working-copy changes are retained.

New cases cover actual gallery images, Grid/List and Back context, group expansion
beyond the search result, 3+ EXACT members, multiple retained photos across pages,
Keep Both invalidation, no default movement, VISUAL A–B/B–C without A–C inference,
Enter rejection and collapsed plan details, operation-specific Restore through
restart and a no-overwrite collision, whole-session group search/numeric sort,
bounded samples and byte estimates, coalesced requests/stale responses, and
no-scan/filter/loading/query-error/stale presentation. Existing operations/recovery,
RAW/XMP/backup guards, stale source/keeper and cancellation assertions are preserved.

```powershell
$env:QT_QPA_PLATFORM = 'offscreen'
.\.venv\Scripts\python.exe -B -m pytest -p no:cacheprovider tests -q
# 160 passed, 2 skipped in 788.46s
```

This full collection ran before the final photo-first layout, cached Back-context
adjustments and additional query/state/navigation tests. It skipped the licensed valid RAW asset and native Linux
race test on Windows; corrupt/undecodable RAW and Windows safety paths ran.

The final affected Qt/service collection and a later navigation race case passed:

```powershell
.\.venv\Scripts\python.exe -B -m pytest -p no:cacheprovider tests/test_task008.py tests/test_qt.py tests/test_qt_design_system.py tests/test_task003_services.py -x -q
# 53 passed in 595.22s
.\.venv\Scripts\python.exe -B -m pytest -p no:cacheprovider tests/test_task008.py::test_late_group_response_does_not_navigate_after_leaving_duplicates -x -q
# 1 passed in 19.05s
.\.venv\Scripts\python.exe -B -m pytest -p no:cacheprovider tests/test_task008.py::test_gallery_group_open_images_modes_back_and_explicit_decision tests/test_task008.py::test_late_group_response_does_not_navigate_after_leaving_duplicates -x -q
# 2 passed in 56.10s after the final opening-intent invalidation changes
```

The race case was added after the 53-test collection started. It verifies that
leaving Duplicates cancels an in-flight group-opening intent; an old query response
cannot navigate the user back. Sorting, filtering, selection, paging and new scans
also invalidate that opening intent. Concurrent verification runs share host CPU;
these timings are evidence of execution, not performance benchmarks.

The final keeper-label/reset change was checked at 150% Qt scale:

```powershell
$env:QT_SCALE_FACTOR = '1.5'
.\.venv\Scripts\python.exe -B -m pytest -p no:cacheprovider tests/test_qt_design_system.py tests/test_qt.py::test_sidebar_keyboard_and_context_actions_at_small_viewport tests/test_task008.py::test_exact_multiple_keepers_pagination_and_no_default_move -x -q
# 8 passed in 54.97s
```

Visual verification used:

```powershell
.\.venv\Scripts\python.exe -B -m tools.capture_task008 --output .benchmarks/task008-verified
```

21 local screenshots plus a manifest are in `.benchmarks/task008-verified/`
(ignored generated evidence; use a new output directory to repeat). Both Dark and
Light cover Grid/List, comparison, compact unavailable preview and rejected plan
at 1280×800 and 853×480. The no-session state is also captured. Real images/workers
are used; the unavailable-state image injects a view error, as documented in the
manifest. All plans are rejected and the driver verifies unchanged fixture bytes.
Inspected large/small comparison, grid, confirmation and unavailable screenshots;
both photos retain proportions and all four comparison captures measured zero
horizontal overflow. Short windows scroll vertically to actions/member details.
Initial inspection exposed below-fold photos and an oversized All Groups tile;
these were corrected. Development tests also exposed Back focus changing scroll
and a zero-timestamp fixture unsupported by Windows; both were corrected.

Limits: previews/enlargement remain <=2048 px; review decisions last only for the
current scan/application session. Estimates are cached potential EXACT bytes,
never an approved plan or space freed by same-disk quarantine. Native Linux,
licensed valid RAW, physical DPI/display/media, full accessibility acceptance,
large real-library benchmarks and packaging were not performed in Task008.

## Task007 Dashboard and Scan (2026-11-09)

Windows 11, Python 3.12.10, PySide6 6.12.0, Fusion/offscreen. Photographs, home,
index, reports and operations remain confined to generated temporary fixtures.

Task007 changes `app/core/queries.py`, `app/services/queries.py`, Qt
`dashboard_scan.py`, `screens.py`, `window.py`, `controller.py`, `workers.py`,
`strings.py`, `tests/test_qt.py`, `tests/test_task003_services.py`,
`tools/capture_task007.py`, README, ARCHITECTURE, CHANGELOG and this document.
Pre-existing Task005/006 work is retained; no commit or dependency install was made.

Service cases check empty/no-session, one photo, exact pair and 3+ copies,
whole-index versus latest-session counts, actual group versus candidate counts,
bounded candidate samples, physical hardlinks, overlapping roots, simulated drives,
offline roots, stale results and read-only queries. VISUAL bytes never contribute
to the estimate. Existing approval/recovery/RAW/XMP guarantees remain under the
regression suite. GUI cases cover the first-scan flow, source availability/order/
removal, collapsed sections, real thumbnails, viewport bounds, stale thumbnail
responses, cancelled/failed scans, retry, report failure and no-match completion.
Failures both during matching and before a session exists keep their details and
cannot turn an older successful session into a successful new attempt.

```powershell
$env:QT_QPA_PLATFORM = 'offscreen'
.\.venv\Scripts\python.exe -B -m pytest -p no:cacheprovider tests -q
# 153 passed, 2 skipped in 442.61s
.\.venv\Scripts\python.exe -B -m pytest -p no:cacheprovider tests/test_qt.py -k 'thumbnail_visibility or failure_before_new_session or source_availability_order' -x -q
# 3 passed, 17 deselected in 49.70s
$env:QT_SCALE_FACTOR = '1.5'
.\.venv\Scripts\python.exe -B -m pytest -p no:cacheprovider tests/test_qt.py -k sidebar_keyboard -q
# 2 passed, 18 deselected in 7.86s
.\.venv\Scripts\python.exe -B -m pytest -p no:cacheprovider tests/test_qt.py -k 'dashboard_to_scan or thread_ownership or sidebar_keyboard' -q
# 4 passed, 16 deselected in 21.94s
```

The full collection skipped the licensed valid RAW fixture and a native Linux
race test on Windows. It ran before the last presentation-only adjustment moving
the activity card above sources. The final four Qt tests above ran after that
adjustment and assert that status/elapsed controls fit the short viewport, as well
as cancellation, worker ownership, close and keyboard behavior. No service or
safety code changed after the full collection was launched.

Development runs exposed an obsolete header-title assertion and a new thumbnail
test checking the replacement cancellation event rather than the in-flight event.
The extended focused run before correcting that test had 35 passed, 1 failed in
349.02s. The corrected cancellation assertion passes in the focused run above.
An initial capture run also retained the generated bad RAW between themes; each
theme now starts with the same five valid generated photographs.

```powershell
$env:QT_SCALE_FACTOR = '1'
.\.venv\Scripts\python.exe -B -m tools.capture_task007 --output .benchmarks/task007-complete-normal --width 1280 --height 720
$env:QT_SCALE_FACTOR = '1.5'
.\.venv\Scripts\python.exe -B -m tools.capture_task007 --output .benchmarks/task007-complete-scaled --width 853 --height 480
```

Both final runs completed: 22 screenshots and five scenario checks each. All 44
PNG SHA-256 values were verified against their manifests. Inspected empty, active,
complete, failed and candidate/error detail views in both themes, including the
short 150% viewport. Status, counts, elapsed time and Cancel remain visible at the
top while working; other content scrolls. Manifests are in
`.benchmarks/task007-complete-{normal,scaled}/manifest.json`. `git diff --check`
passed after the final source/documentation review.

Captures include empty Dashboard/Scan, available sources, actual scan progress,
completion, candidate thumbnails and metrics, malformed RAW/offline errors,
on-demand details and a matching fault in both themes. The matching exception is
explicit fault injection; the worker, persisted failed session, result queries and
UI failure path are real. All source bytes remain unchanged; workers stop before
temporary cleanup. Screenshots and manifests are local ignored `.benchmarks`
artifacts. No native Windows display DPI, Linux display, screen reader, licensed
valid RAW, actual removable drive or distribution packaging was tested here.
Full language switching remains Task012; new labels use stable Serbian keys.

Earlier 100%/150% captures found activity below the fold on the short viewport;
the activity card now moves first during scans and for results. The capture tool
also allows 50 ms for queued layouts/painting to settle before grabbing wrapped
labels. A diagnostic three-frame capture confirmed the 48 px two-line status
height at 150%; no fixed height or truncation was added to the product.

## Task006 shell and navigation (2026-11-09)

Windows 11, Python 3.12.10, PySide6 6.12.0, Fusion/offscreen. All photograph,
home/index, report and quarantine inputs were synthetic and temporary.

```powershell
$env:QT_QPA_PLATFORM = 'offscreen'
.\.venv\Scripts\python.exe -B -m pytest -p no:cacheprovider tests -q
# 140 passed, 2 skipped, 0 failed in 319.60s
$env:QT_SCALE_FACTOR = '1.5'
.\.venv\Scripts\python.exe -B -m pytest -p no:cacheprovider tests/test_qt.py -k sidebar_keyboard -q
# 2 passed, 12 deselected, 0 failed, 0 skipped in 7.20s
```

New Qt regressions exercise five named destinations, sidebar Tab/Shift+Tab/Enter,
toolbar reachability and non-overlapping geometry at 1280x720 and 853x480 logical
pixels, table Enter and Alt+Left, and at most one dominant action per visible view.
A six-photo fixture exercises two actual EXACT groups with more than two members,
nonzero group/result pages, descending sort, text/category filters and selection.
Dispatch observers confirm opening, leaving, returning and Back issue no service
queries or preview requests. Plan tests cover navigation during preparation,
rejection without movement, removing selection, keeper change, cancellation,
dialog focus restoration and close. Existing thread ownership, heartbeat,
preview/cache, theme restart, explicit approval and recovery assertions are retained.

The initial focused Qt/design-system run passed 15 tests. Development checks
exposed a 30s timeout for six decoder processes under parallel load (the scan-only
helper now waits up to 90s), Qt button-group Tab skipping, and modal focus being
overridden during hide. The intermediate full run had 139 passed, 1 failed (the
new modal-focus assertion), 2 skipped. After deferring focus restoration with an
epoch guard, the isolated extended plan/focus test passed in 44.23s.

The updated capture tool retains its isolated scan/quarantine/restart/restore,
incomplete-scan refusal and persisted-theme assertions. These two runs completed,
each with 23 captures and five scenario checks; all 46 PNG hashes matched their
manifests in the ignored local `.benchmarks/` directory:

```powershell
$env:QT_SCALE_FACTOR = '1'
.\.venv\Scripts\python.exe -B -m tools.capture_ux_audit --output .benchmarks/task006-normal --width 1280 --height 720
$env:QT_SCALE_FACTOR = '1.5'
.\.venv\Scripts\python.exe -B -m tools.capture_ux_audit --output .benchmarks/task006-scaled --width 853 --height 480
```

Inspected selected scan/list/comparison/settings captures at both scales and scaled
dashboard/history. The scaled run renders at DPR 1.5, approximately 1280x720 physical
pixels. Headers, sidebar and contextual actions remain accessible; the existing
comparison body can require horizontal/vertical scrolling on the narrow viewport.
The expected logged `incomplete_scan` exception is the captured safety refusal.
Both capture runs preceded the final keyboard/focus/selection corrections. This is
Qt scaling evidence, not a native Windows display-DPI or multi-monitor test.
Physical DPI, native Linux, licensed valid RAW, screen readers and the full Task011
matrix remain unverified. No real photograph library or physical drive was used.
Sandbox launch of Store Python failed; tests/captures used the approved external
runner against the existing project environment, without dependency installation.

The full run above completed before the final small Qt current-row clearing change.
That change clears the table's current row along with controller selection, allowing
the same pair to be selected again after cancellation. The final Qt/design-system
run below verifies the resulting UI revision, including that extra assertion.

```powershell
$env:QT_SCALE_FACTOR = '1'
.\.venv\Scripts\python.exe -B -m pytest -p no:cacheprovider tests/test_qt.py tests/test_qt_design_system.py -q
# 19 passed, 0 failed, 0 skipped in 200.50s
git diff --check
# passed
```

The full run's two skips are the licensed valid RAW fixture (unavailable) and native
Linux execution (Windows host). Corrupt RAW is covered. Final diff review found
changes only in Qt presentation/navigation, its tests/capture helper and docs;
no backend, schema, decoder, journal or Tk changes.

## Task005 design system (2026-11-09)

Windows 11, Python 3.12.10, Qt 6.12.0, Fusion/offscreen. Only temporary synthetic
fixtures were used. The gallery does not create a home/index/journal and contains
no photographs or fabricated collection metrics.

```powershell
$env:QT_QPA_PLATFORM = 'offscreen'
.\.venv\Scripts\python.exe -B -m pytest -p no:cacheprovider tests/test_qt_design_system.py tests/test_qt.py tests/test_task003_services.py tests/test_operations.py tests/test_recovery.py -q -ra
# 43 passed, 0 failed, 0 skipped in 133.93s
.\.venv\Scripts\python.exe -B -m pytest -p no:cacheprovider tests/test_qt_design_system.py tests/test_qt.py::test_themes_system_fallback_and_text_contrast -q -ra
# Final palette/link/tooltip revision: 6 passed, 0 failed, 0 skipped in 1.64s
.\.venv\Scripts\python.exe -B -m tools.capture_design_system --output docs/design/verification/task005
```

The first capture found a stale Dark tooltip background after switching to Light.
After explicit QToolTip palette updates and allowing the hide delay to finish,
the second capture used `--output docs/design/verification/task005-review`, then
was moved to accepted `task005`. The rejected run is retained in ignored
`task005-tooltip-rejected`. Eight accepted images were inspected: components,
dialogs, menus and tooltips in both themes. The manifest records DPR, dimensions
and SHA-256. Segoe UI is loaded only into the capture process.

New tests cover text/semantic/disabled/action/link contrast, focus/control
boundaries, actual focus painting, stable geometry, Tab/Space, collapsible
content, SVG rendering and preview loading/failure/ready/reset. Existing tests
cover theme persistence/System fallback, approval/RAW/legacy, stale previews,
cancellation, worker ownership, quarantine and restart recovery. Early focused
failures exposed low selection-border contrast and an unloaded Windows SVG
runtime; both were corrected. The sandbox Python launch failed; actual tests
ran with the approved external runner. A focused intermediate run passed 5 tests.

Final `git diff --check` passed. All eight accepted PNG SHA-256 values matched
the manifest; seven unchanged captures also matched the previously inspected
images byte-for-byte. Diff review found no changes to matching, decoding, schema,
settings persistence or safety services. Existing Task004 work was preserved.

Tested text meets 4.5:1 and indicators 3:1; card dividers are decorative. These
scoped checks do not establish complete accessibility. No full-suite, native
Linux/physical DPI, screen reader, full keyboard/screen matrix, packaging,
real-photo, physical-drive or power-loss checks were run. No pytest skips in the
listed runs. Full redesign acceptance remains Task011, localization/release
Task012/013. See [DESIGN_SYSTEM.md](design/DESIGN_SYSTEM.md).

## Task004 UX audit (2026-11-09)

Stage A produced an [evidence-based redesign plan](design/UX_REDESIGN_PLAN.md),
not a redesigned application. Production code and existing tests were unchanged.
The capture tool uses generated images and a private temporary home/index/journal;
it closes all worker threads before cleanup. No real library was scanned.

Executed from the repository root on Windows 11, Python 3.12.10, PySide6 6.12.0:

```powershell
.\.venv\Scripts\python.exe -B -m tools.capture_ux_audit --output docs/design/verification/task004
.\.venv\Scripts\python.exe -B -m pytest -p no:cacheprovider tests/test_qt.py tests/test_task003_services.py -q -ra
# 21 passed, 0 failed, 0 skipped in 189.95s
.\.venv\Scripts\python.exe -B -m pytest -p no:cacheprovider tests/test_operations.py tests/test_recovery.py -q -ra
# 17 passed, 0 failed, 0 skipped in 34.85s
git diff --check
# passed
```

Also verified all 24 PNG SHA-256 values against the manifest, all local links in
the redesign plan and trailing whitespace in the new script/document. Diff review
confirmed no changes under `app/` or `tests/`. Narrow `.gitignore` exceptions keep
the plan/accepted evidence reviewable without exposing the older ignored references.

Capture result: **24 saved and individually inspected screenshots**, with dimensions,
DPR and SHA-256 in [manifest.json](design/verification/task004/manifest.json).
The first attempt completed its scenarios but rendered missing-font boxes in Windows
offscreen mode. It was rejected, moved to ignored
`docs/design/verification/task004-font-rejected/`, and replaced by a complete fresh
run after the tool loaded installed Segoe UI regular/bold fonts into its own process.
The accepted run uses Fusion/offscreen, 1280×800 logical pixels, DPR 1.0.
It preserves the rendered PNGs exactly. The output path must not exist when rerunning;
choose a new path to keep this evidence.

Scenario assertions cover a real complete scan (5 photos, 2 EXACT links, 1 VISUAL
link, an EXACT group with 3 members), rejected confirmation with unchanged bytes,
one synthetic quarantine, new window/service instances, selected-ID restore with
all original bytes verified, incomplete scan with malformed RAW/missing source,
disabled bulk, worker-level rejection, and saved Light theme after service restart.
The logged `SafetyError: incomplete_scan` is the expected refusal captured in the
error dialog, not a failed scenario. Actions use Qt window slots and real workers;
native mouse input/folder-dialog navigation are not exercised. Existing pytest Qt
tests used the host platform plugin (the command did not set `QT_QPA_PLATFORM`);
the offscreen setting is local to the separate capture process.

Focused regression total: **38 passed, 0 failed, 0 skipped**. No new tests were
added for this documentation/capture change. No full-suite, native Linux, licensed
valid RAW, physical-media/power-loss, screen-reader, full keyboard, full Dark/Light
screen matrix, native DPI or packaging checks were run. Existing Qt tests do cover
worker ownership/heartbeat/cancellation/close, stale previews, keeper-change plan
invalidation, RAW/legacy consent and theme fallback/contrast; those passes do not
close the manual acceptance gaps. Full redesign verification remains Task011;
localization and release/packaging remain Task012/013.

## Task003 verification (2026-11-08)

Launcher correction: Qt is now the default for the entry point and preflight,
including double-click start_windows.bat. The selected-toolkit and six-screen
restart smoke tests passed together (2 passed in 35.42s):

```powershell
.\.venv\Scripts\python.exe -B -m pytest -p no:cacheprovider tests\test_qt.py::test_preflight_checks_only_selected_toolkit tests\test_qt.py::test_six_screens_scan_compare_query_and_theme_restart -q
```

The selected-toolkit test also exercises no-argument preflight with Tkinter blocked.
This default change is owner-authorized; it does not claim manual scaling acceptance.

Runtime: Windows, Python 3.12.10, PySide6/Qt/shiboken6 6.12.0; existing image
libraries are unchanged. All images, state, journals and indexes are synthetic.

Executed during implementation:

```powershell
.\.venv\Scripts\python.exe -B tools\check_environment.py
.\.venv\Scripts\python.exe -m pip install "PySide6>=6.8,<7"
.\.venv\Scripts\pyside6-rcc.exe app/ui/qt/resources/resources.qrc -o app/ui/qt/resources_rc.py
.\.venv\Scripts\python.exe -B -m pytest -p no:cacheprovider tests\test_task003_services.py tests\test_indexing.py -x -q
# 39 passed (before the later added edge cases)
.\.venv\Scripts\python.exe -B -m pytest -p no:cacheprovider tests\test_qt.py -x -q
# 7 passed (initial Qt suite)
.\.venv\Scripts\python.exe -B -m pytest -p no:cacheprovider tests -q
# Initial full regression: 123 passed, 2 skipped
# Expanded regression: 130 passed, 1 failed, 2 skipped (preparation cancellation)
$env:QT_QPA_PLATFORM = 'offscreen'
.\.venv\Scripts\python.exe -B -m pytest -p no:cacheprovider tests\test_qt.py::test_themes_system_fallback_and_text_contrast tests\test_qt.py::test_raw_legacy_confirmation_requires_both -q
# 2 passed in 3.13s (separate process environment)
git -c core.safecrlf=false diff --check
# passed
```

The expanded-run failure concerned cancellation being routed through generic error
handling and a pending-preparation assertion. Cancellation now has a separate worker
signal/result path, clears pending preparation and refreshes partial execution state.
Post-fix checks:

```powershell
.\.venv\Scripts\python.exe -B -m pytest -p no:cacheprovider tests\test_qt.py::test_preparation_cancel_and_keeper_change_invalidate_plan -q
# 1 passed in 31.31s
.\.venv\Scripts\python.exe -B -m pytest -p no:cacheprovider tests -q
# 131 passed, 2 skipped in 341.97s
```

The two skips are the existing unavailable licensed valid RAW fixture and native
Linux execution unavailable on Windows. A final focused Qt run additionally
checks the last cache-accounting/preview-size assertions and presentation tweaks.

```powershell
.\.venv\Scripts\python.exe -B -m pytest -p no:cacheprovider tests\test_qt.py::test_six_screens_scan_compare_query_and_theme_restart tests\test_qt.py::test_preview_source_changes_orientation_cache_and_corrupt_raw tests\test_qt.py::test_themes_system_fallback_and_text_contrast -q
# 3 passed in 44.65s (after the final cache/presentation changes)
```

Coverage includes settings/history preservation from both adapters, global numeric
sort/search over multiple pages, direct groups, hardlink/overlap estimates, offline
dashboard warnings, per-session thresholds, selected restore/no fallback, report
failure, corrupt settings with read-only scanning, six screens, theme restart/System
fallback/contrast, slow-scan heartbeat below 250 ms, scan/preview/preparation cancellation,
close during work/confirmation, stale/changed previews, cache bounds, EXIF orientation,
corrupt RAW, RAW/legacy consent and existing safety/recovery/Tk regressions.

Not performed: manual Windows launcher and 100/150/200% scaling acceptance, full
keyboard/resize review, native Linux, valid licensed RAW, physical removable media,
offline wheelhouse rehearsal or installer validation. Qt subsequently became the
default at the owner's request; those acceptance limitations remain unchanged.
See [implementation record](TASK003_IMPLEMENTATION.md) and [distribution notes](QT_DISTRIBUTION.md).

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
