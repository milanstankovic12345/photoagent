# Local photograph opening (Task021)

One double-click on a concrete photograph sends at most one default-application
request. A single click keeps selection behavior. Opening neither changes keeper
choices nor prepares, approves or executes any operation. The explicit Enlarged
preview button retains PhotoAgent's internal preview, with zoom and fit.

| Context | Exact target | Secondary action |
|---|---|---|
| Dashboard candidate thumbnail | `row.match.dup` | Open in Default Viewer button (Tab/Space) |
| Duplicates Grid/List sample 0 / sample 1 | Corresponding `GroupRow.samples` member | Named context-menu actions; Alt+O / Alt+Shift+O while gallery has focus |
| Compare left / right photograph | That view's immutable `Photo` | Open in Default Viewer button (Tab/Space) |
| Explicit enlarged preview | Photo captured when the dialog opened | Open in Default Viewer button (Tab/Space) |
| Quarantine thumbnail | Operation ID resolved through the authoritative journal | Open in Default Viewer button (Tab/Space) |

The group heading, count, status, sample gap and pair/member table describe groups
or direct links; they are not individual photograph targets. Enter / Review group
still enters comparison. A placeholder has no photograph double-click action.
The explicit open action remains available when internal decoding fails (including
RAW); it verifies original file bytes without requiring an internal decode.
Scan, Settings, plan confirmations, icons and branding have no photograph target.

UI signals carry a frozen `Photo` or an operation ID to `Controller`. The existing
service worker calls `Application.resolve_photo`; no filesystem probes, hashing or
decoding run in the widget handler. Scan targets require root identity, containment,
non-redirected paths and a freshly computed full SHA-256 snapshot equal to the
reviewed snapshot. The quarantine resolver preserves the existing root, identity,
containment and full-content checks against the completed move manifest. It rejects
legacy, restored, pending, blocked and unknown records, including a different file
placed at an old source/destination. It does not repair history or guess locations.

A queued request stays attached to the clicked photo when selection or navigation
changes. A newer open supersedes an older pending open; cancellation, window close
and move/restore execution dispatch invalidate pending open results. Requests run
on the existing serialized service thread, so may wait behind scanning. Closing
cancels validation; no deferred launch is accepted after closing.

`DesktopViewer` calls only `QDesktopServices.openUrl(QUrl.fromLocalFile(path))` on
the GUI thread after validation. Spaces, Unicode, `%`, `#`, `&`, `$` and parentheses
remain literal path characters; no shell, conversion, upload, fallback viewer or
network URL is introduced. RAW requires an application associated with that format.
Missing/unreadable/offline files, changed content or identity and rejected launches
have EN/SR summaries with technical details. A false/exception result can indicate
a missing association; Qt does not reliably distinguish this from other OS errors.

There is an unavoidable gap between worker validation and a different application's
path-based read. External programs can change a file after validation; PhotoAgent
cannot guarantee another application's displayed bytes. OS acceptance also does
not prove a viewer launched successfully, decoded the file or displayed an image.
The status message says only that the request was sent. Windows and Linux share
the Qt adapter; native associations and desktop environments remain OS-owned.

## Task023 native supplement — 2026-11-14

The real Windows Qt probe submitted zero requests for one click, one for a photo
double-click and one for the explicit Compare button; both PNG requests were
accepted. The owner confirmed the expected generated image and exact filename.
This is a separate human PNG display observation, not proof of JPEG/RAW support,
every launch/context or Linux behavior. Automated rectangle captures showed the
wrong window and were rejected; direct HWND capture was blank and was rejected
too. The tool now captures the target HWND without substituting desktop pixels.
See [Task023 evidence and remaining gates](design/UI_REFINEMENT_VERIFICATION.md).

## Task021 verification record — 2026-11-14

Automated checks use synthetic temporary collections and mock every OS launch.
See [TESTING.md](TESTING.md) for executed checks and results. No real photo library
or system viewer is opened by these tests.

- Native Windows manual display/association check: **not performed** in this
  execution environment. Windows offscreen Qt tests do not establish native display.
- Native Linux manual check: **unverified**, no Linux desktop available.
- Valid RAW association/display: **unverified**; synthetic RAW handoff is tested
  without claiming successful RAW decoding.

On each available native desktop, create two synthetic PNG/JPEG files and a copy
under a path containing spaces and Unicode. Launch with an isolated application
home (as in the test/capture tools), scan only that directory, and test each row
above. Confirm a single click only selects and each double-click opens the expected
file once. Check keyboard/context actions, failed associations, disconnected source,
selection changes during validation, and confirmed quarantine/restore/restart.
Record OS, desktop, viewer association and actual displayed filename separately
from Qt's accepted/rejected launch result. Never use real photo libraries.

## Implementation files

- New service: `app/services/open_photo.py`; application entry point:
  `app/services/application.py`.
- New OS adapter: `app/ui/qt/desktop_viewer.py`; worker/request routing:
  `app/ui/qt/workers.py`, `controller.py`, `window.py`.
- Photo gestures, actions and targets: `app/ui/qt/components.py`, `gallery.py`,
  `dashboard_scan.py`, `quarantine_settings.py`.
- Translation sources: `app/i18n/en.ts`, `sr_Latn.ts`; generated JSON, QM and
  `app/i18n/resources_rc.py`; `docs/design/QT_TEXT_INVENTORY.json`.
- Tests: `tests/test_task021.py`.
- Source ZIP guide inclusion: `tools/build_release.py` and its synthetic fixture
  in `tests/test_task013.py`.
- Documentation: `README.md`, `README_SR.md`, `docs/ARCHITECTURE.md`,
  `SECURITY.md`, `CHANGELOG.md`, `LOCALIZATION.md`, `TESTING.md`, this guide and local
  `task/Task021.md` status; `docs/design/ACCESSIBILITY.md` records keyboard behavior.
  `.gitignore` allows this guide to be versioned.
