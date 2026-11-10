# Task014 evidence — 2026-11-10

Authoritative report: [UI_REFINEMENT_PLAN.md](../../UI_REFINEMENT_PLAN.md).
Authoritative evidence index: [audit.json](audit.json).

- `baseline/`: 116 current-run PNGs and the unchanged existing driver's manifest.
- `supplement-r2/`: 14 accepted supplemental PNGs, direct-pair identity observations
  and its manifest. Member/details/error content is scrolled into view.
- `review-final-01.jpg` through `review-final-17.jpg`: inspected contact sheets.
  Originals retain their actual pixel dimensions; contact sheets are review aids.
- `supplement/`, `audit-initial.json`, `review-01.jpg` through `review-16.jpg`:
  retained first attempt, superseded after visual review found some disclosures
  outside the captured viewport. They are excluded from final acceptance.
- `capture.py`, `supplement.py`, `review.py`: audit-only replay and evidence helpers;
  no production module or existing tool was edited.

Windows / Python 3.12.10 / Qt 6.12.0 / Fusion / offscreen / DPR 1.
Main six-surface matrix: 1280×720, 1366×768, 1650×900, 1920×1080 in Dark/Light.
Extended baseline states: 1650×900. Supplement: 1280×720, including representative
Serbian screens. This is not a full EN/SR×DPI or native platform acceptance matrix.

All file operations target generated photographs and disposable application state.
No OS photo viewer is launched; the double-click probe mocks `openUrl`.
Normal approved quarantine/restart/occupied-destination/restore is real synthetic
service execution; combined RAW/legacy warnings and loading/unavailable states are
presentation fixtures. Settings diagnostic content is injected, not a failed write.
The normal RAW failure/offline source/restore conflict are real service failures.
The existing driver still calls its temporary directory `photoagent-task011-*`;
these files were newly captured for Task014, not copied from Task011.

From the repository root, the commands used for the accepted captures were:

```powershell
.\.venv\Scripts\python.exe -B docs/design/verification/task014-20261110/capture.py
.\.venv\Scripts\python.exe -B docs/design/verification/task014-20261110/supplement.py --output docs/design/verification/task014-20261110/supplement-r2
.\.venv\Scripts\python.exe -B docs/design/verification/task014-20261110/review.py
```

Output paths must be new. To replay, copy these three scripts into a new sibling
evidence directory, use that directory in the commands and the supplement's output
path, and keep earlier artifacts. The scripts assume this repository layout and
reuse existing synthetic drivers. They install nothing. On this host Python needed
the approved external runner after sandbox process creation failed.

Open all generated review sheets and representative originals **before** using
`review.py --mark-reviewed`. The marker records actual visual inspection, not
automatic accessibility or functional certification. The source commit and command
results in the review script describe this run; update provenance for any new audit.

Executed tests (no new test files):

```powershell
.\.venv\Scripts\python.exe -B -m pytest tests/test_task008.py tests/test_task009.py tests/test_task010.py tests/test_task012.py tests/test_qt_design_system.py -q
```

Observed terminal result: `61 passed in 815.35s (0:13:35)`, exit 0, no skips.
Also verified: 130 original PNG hashes/dimensions/DPR/layouts, all report links and
`git diff --check`. Full regression, native Linux, physical Windows DPI, screen
readers, real drives, valid RAW decode, physical power loss and actual OS photo
viewer launch were not run. See the report and audit index for precise limits.
