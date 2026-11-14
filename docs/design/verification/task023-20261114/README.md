# Task023 evidence — 2026-11-14

Authoritative [A–J report](../../UI_REFINEMENT_VERIFICATION.md), including the nine
requirements, current test results, limits and repeatable native/manual checklist.
Source at the start of work: `b6837256ecfc5c9db0fb51b2959a31ee131d1fb9`;
initial working tree was clean. Earlier Task014–Task022 artifacts were not changed.

## Captures and integrity

- [100-verified/manifest.json](100-verified/manifest.json): 141 original Qt captures.
- [150-verified/manifest.json](150-verified/manifest.json): 141 original Qt captures.
- `history-100/` and `history-150/`: three loaded replacement history frames per
  scale, recorded separately after visual inspection found asynchronous preview
  loading in the active-history/restart/conflict frames. Original images remain
  unchanged. The old 150% restart frame also used a smaller default window.
- [review/index.json](review/index.json): hashes/dimensions/DPR/layout validation,
  contact-sheet membership, comparison inputs, explicit rejected/replacement paths
  and actual visual-review annotations. Creating sheets does not mark them reviewed.
- `review/100-01.jpg`–`100-18.jpg`, `review/150-01.jpg`–`150-18.jpg` and six
  `before-after-*.jpg`: all opened and inspected. Contact sheets show the whole
  screenshot at reduced size; representative originals were inspected separately.
- `100/`: first diagnostic 141-frame attempt, retained locally and excluded from
  version control. The capture driver then synchronized displayed language/theme
  selections with the presentation being captured. This attempt is not final proof.

Main matrix, per scale: six experiences × EN/sr_Latn × Dark/Light × compact/expanded
sidebar × 1280×720/853×480 logical windows = 96 frames. Additional states cover
empty pages, read-only folder chooser, active scanning, Keep Both, confirmation,
history, restore conflict, VISUAL/RAW/backup warnings, missing files and OS-launch
error wording. RAW/backup flags and launch-failure wording are presentation fixtures;
they are never moved or presented as a successful RAW decode/native launch.

The capture journey uses real Qt widgets, workers, scanning, SQLite, preflight,
confirmation, move and restore services. Only generated PNG/JPEG files are involved.
It verifies Cancel, an unseen third member, one approved move, stopped-worker
window/service restart, conflict refusal and explicit restoration of every original
byte. The conflicting synthetic file is preserved too. Restart here recreates the
window/service within one Qt process; separate process/crash tests have their own
evidence. No original photograph is permanently deleted or overwritten.

## Environment and boundaries

Windows 11 build 26100, Python 3.12.10, PySide6/Qt 6.12.0, Fusion/offscreen and
process-local Segoe UI registration. Full dependency and screen API values are
in each manifest. Offscreen DPI/screen geometry are virtual; requested scale is
verified against each actual pixmap DPR and dimensions. The host Windows API
reported primary resolution 1536×864 and system DPI 96. This is not an observed
physical DPI transition. No native Linux desktop or valid RAW fixture is available.

Manifests are capture-time records; `visually_reviewed: false` inside them is
intentionally preserved. The separate review index records the subsequent image
inspection and rejected/supplemented frames. Geometry checks are not a substitute
for visual review, a human keyboard journey or native assistive technology.

## Native Windows evidence

[native/manifest.json](native/manifest.json) records real Compare PNG events and
the actual Qt OS adapter: no request for one click, one accepted request for a
double-click, and one accepted request for the explicit button. The owner replied
“Da, vidim tu sliku i naziv” to the exact filename/content question for
`Task023-ac7b554c05-0-čćžšđ.png` (red rectangle, green ellipse, blue diagonals).
This is a human PNG display observation, separate from accepted OS requests.

The two initial desktop-rectangle screenshots captured an occluding window. Both
were visually rejected and renamed `*.rejected.png`; their pixels are excluded
from version control. The direct-HWND diagnostic was blank and rejected too.
The probe now uses `ImageGrab(window=HWND)` and never substitutes desktop pixels.
These images supply no viewer display proof; the owner observation does. A
read-only process query identified `Photos.exe` for both title-matched synthetic
windows; the current PNG UserChoice ProgID is retained in the native manifest.
Each independent launch, JPEG/RAW, all photo contexts, native
quarantine/missing-file behavior and Linux display remain outside this confirmation.
Synthetic viewer files/home remain ignored locally; the probe may leave the viewer
open and never closes an existing OS window.

## Diagnostics and current-run tests

Raw logs/JUnit and the per-module progress record live under ignored
`build/task023/`. The final machine-readable module summary and exact commands are
linked from the A–J report and `docs/TESTING.md`; prior task counts are not reused.

- Original combined focused run: interrupted after prolonged inactivity around
  the existing Task019 conflict/restart case; no clean-suite result is claimed.
  Isolated conflict/offline replay: **2 passed in 62.86s**.
- New journey first attempt: **1 failed in 21.91s**, because the driver reapplied
  an already retained left choice after Keep Both. Corrected to click the right
  retention control, matching actual toggle semantics. Replay: **1 passed in
  56.18s**. Production behavior was unchanged.
- Windows execution policy refused the temporary `.ps1` test launcher. No policy
  was changed; equivalent pytest commands run directly in PowerShell, each module
  in a fresh process. An early diagnostic caption print also needed ASCII-safe
  output for the host's cp1252 console; it was not a product/decoding failure.
- Expected `destination_occupied` and missing-file worker tracebacks in capture
  logs are deliberate refusal checks, followed by confirmed unchanged/restored
  bytes. They are not represented as silent successes or real-library operations.

## Replay

Use a new output root each time. Do not overwrite this evidence or point these
tools at a real library. In PowerShell, with the existing project environment:

```powershell
$env:QT_QPA_PLATFORM = 'offscreen'
$env:QT_SCALE_FACTOR = '1'
.venv/Scripts/python.exe -B -m tools.capture_task023 --output NEW_ROOT/100-verified
$env:QT_SCALE_FACTOR = '1.5'
.venv/Scripts/python.exe -B -m tools.capture_task023 --output NEW_ROOT/150-verified
.venv/Scripts/python.exe -B -m tools.review_task023 --root NEW_ROOT
```

For existing loading-frame repairs, use `capture_task023 --history-only --output
NEW_ROOT/history-100` at scale 1 and `.../history-150` at scale 1.5, then
`review_task023 --history-supplements-only --root NEW_ROOT`. These still run the
synthetic safety journey and refuse existing destinations. The final capture
driver now waits for history preview before taking the ordinary full matrix too.
The review tool's before/after reference expects a sibling `task014-20261110/`;
place a new root alongside that existing baseline for comparison generation.

Native Windows only: `python -B -m tools.verify_task023_native --output NEW_NATIVE_ROOT`.
It generates its own photos/home and uses real OS associations. Inspect the target
viewer or obtain an explicit human filename/content observation; a returned true
launch value or a blank HWND image must not be counted as successful display.
Follow section J of the A–J report for complete manual acceptance on each OS.
