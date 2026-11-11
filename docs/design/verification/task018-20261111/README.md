# Task018 — Duplicate groups and filters — 2026-11-11

Windows, CPython 3.12.10, Qt/Fusion offscreen. All photographs are generated;
application homes, settings, SQLite and journals are temporary. The new tests
and captures approve no moves. Existing quarantine/restore regressions use only
their own synthetic fixtures and explicit test approvals.

## Behavior and category limits

- Grid/List cards show two sample photographs, the named anchor, full direct
  member count, session review coverage and Review group. Technical classification
  and EXACT byte estimates remain in accessible tooltips/details. The toolbar
  has Review group and explicitly scoped exact-copy preparation; its tooltip
  retains the whole-session scope. The existing confirmation is required.
- Search/filter/sort/direction/view mode share a wrapping toolbar. Search remains
  global and literal; existing numeric sorting, limits, page offsets and stable
  IDs remain service-owned. No matcher, schema, decoder or recovery change.
- Exact Copies means SHA-256-identical EXACT; Similar Photos means VISUAL direct
  links to the named photograph. The member count does not imply that all members
  are mutually similar, identical or derived from one original. No transitive
  expansion or automatic classification is added.
- RAW + JPEG appears only when the two displayed samples include a RAW flag
  and a non-RAW decoded JPEG format. Its accessible detail explicitly limits
  the observation to those samples and denies established common provenance.
  Filename extensions alone do not prove decoded JPEG. This is presentation
  coverage with synthetic Photo records, not verification of a valid RAW decode.
- Needs Review means zero directly reviewed MatchRow IDs for that anchor/kind
  in the current scan/application session; a partial set shows the count;
  at least members−1 shows Reviewed in this session. Keep/Keep Both records a
  decision, not an executed move or a safety approval. New scan/restart resets it.
  Global RAW+JPEG/Needs Review filters have no reliable service source and are
  absent, as are unsupported DERIVATIVE/SIMILAR_CAPTURE detection filters.
- Card Review, toolbar Review and Enter on a group open review. Double-clicking
  the two-photo thumbnail does not open review or choose an external file.
  External photo opening remains Task021. A previously selected pair in an
  already loaded group is reused, rather than reset to the first pair.
- Global query/debounce hides both old views immediately. Member loading hides
  old pairs while retaining the still-current gallery and table layout space.
  Global responses settle together; error/cancellation invalidates the sibling.
  Back restores search/category/sort/mode/page/selection, outer and inner scroll
  and focus. The original ID is restored even when review changed the selected
  member without changing model rows. Operations/new scans invalidate snapshots.

## Executed checks

```powershell
$env:QT_QPA_PLATFORM='offscreen'
.venv/Scripts/python.exe -B -m tools.build_translations
.venv/Scripts/python.exe -B -m tools.build_translations --check
```

442 finished entries per language; TS/JSON parity passes. The executed
localization tests also validate compiled QM resources and fallback behavior.

```powershell
$env:QT_SCALE_FACTOR='1'
.venv/Scripts/python.exe -B -u -m pytest tests/test_task018.py::test_debounce_rejects_old_query_and_query_error_cannot_resurrect_results tests/test_task018.py::test_cancelled_query_hides_results_and_invalidates_sibling tests/test_task012.py::test_live_pages_filters_models_previews_and_restart tests/test_localization.py tests/test_task010.py::test_focused_group_keeps_thumbnail_and_text_visible -q
```

**15 passed in 95.50s**, no failures/skips.

```powershell
$env:QT_SCALE_FACTOR='1'
.venv/Scripts/python.exe -B -u -m pytest tests/test_task018.py tests/test_task008.py tests/test_qt.py::test_compare_back_preserves_group_query_pages_selection_without_requests tests/test_qt.py::test_preparation_cancel_and_keeper_change_invalidate_plan tests/test_task010.py::test_keyboard_sources_filters_group_compare_confirmation_restore_settings -q
```

**24 passed in 477.29s**, no failures/skips. This run began before the final
pair-reuse/table-space correction and the second Back entry-point parameter.
It covers existing multiple keepers, global group search, VISUAL chain safety,
pending/stale responses, confirmation rejection, explicit synthetic moves,
restart recovery, restore conflict and keyboard interaction in both themes.
The final complete Task018 run (including both Back entry points) is:

```powershell
$env:QT_SCALE_FACTOR='1'
.venv/Scripts/python.exe -B -u -m pytest tests/test_task018.py -q
```

**11 passed in 242.78s**, no failures/skips, using final production/test code.

```powershell
.venv/Scripts/python.exe -B -u -m pytest tests/test_task003_services.py::test_global_search_numeric_sort_stable_ids tests/test_task003_services.py::test_group_gallery_global_sort_search_and_bounded_samples tests/test_task003_services.py::test_progress_options_and_direct_groups -q
```

**3 passed in 4.46s**, no failures/skips. These existing service checks exercise
221 direct rows, search outside the first page, literal `%`, numeric sorting,
stable IDs and bounded samples across 27 additional groups (28 total).

```powershell
$env:QT_SCALE_FACTOR='1.5'
.venv/Scripts/python.exe -B -u -m pytest tests/test_task018.py -q
```

**10 passed in 188.74s**, no failures/skips, before the final pair-reuse correction
and the second Back entry-point parameter. After that correction:

```powershell
$env:QT_SCALE_FACTOR='1.5'
.venv/Scripts/python.exe -B -u -m pytest tests/test_task018.py::test_back_restores_pair_identity_when_review_used_same_rows tests/test_task018.py::test_photo_double_click_is_separate_from_group_review -q
```

**4 passed in 135.58s**, no failures/skips. These use final code and exercise
Back through pair/group entry and thumbnail-versus-Review interaction in Grid/List.

The first diagnostic run of Task018 + Task008 + Qt Back was **19 passed,
1 failed in 361.74s**. The new error test called the desktop fixture's error
recorder instead of the real handler. It was corrected to retain/call the real
handler before fixture patching; the fresh 15-test command above passes. No
production behavior was weakened to accommodate that test. The first sandbox
Python launch failed before running: the existing Microsoft Store interpreter
requires the approved runner. No dependencies were installed.

## Capture and visual inspection

```powershell
$env:QT_SCALE_FACTOR='1'
.venv/Scripts/python.exe -B -u -m tools.capture_task018 --output docs/design/verification/task018-20261111/100
$env:QT_SCALE_FACTOR='1.5'
.venv/Scripts/python.exe -B -u -m tools.capture_task018 --output docs/design/verification/task018-20261111/150
.venv/Scripts/python.exe -B -m tools.review_task018 --root docs/design/verification/task018-20261111
```

Both captures exit 0: **33 each / 66 total**; synthetic originals unchanged.
The manifests record hash, physical/logical size, DPR, real group counts/kinds
and member counts. `review.json` validates all 66 hashes, sizes, unique names
and layout observations; all page horizontal maxima, toolbar overlap/outside
counts are zero. Each scale covers EN/SR × Dark/Light × 853×480/1440×900 for
empty, populated Grid/List and filtered-empty states, plus a loading capture.
The two real EXACT groups contain 2 and 3 photographs; a real VISUAL group is
also present. Some early captures retain an asynchronously loading thumbnail.

All eight generated `review-empty/grid/list/filtered.png` contact sheets were
opened and visually inspected, plus original 100% Grid EN Dark, List SR Light,
empty SR Dark, and loading SR Light originals at both scales. Labels and action
regions remain separate in both themes/languages. Short windows intentionally
scroll vertically; longer table values use internal scrolling/tooltips. The
screenshots precede the final selected-pair reuse/table-space correction; those
changes affect loading/interaction only, not these settled state layouts.

## Files and remaining limits

Production: `app/ui/qt/gallery.py`, `screens.py`, `models.py`, `window.py`;
`app/i18n/en.ts`, `sr_Latn.ts` and generated JSON/QM/embedded resources.
Tests: new `tests/test_task018.py`, updated Task012 display-label assertion.
Tools: `tools/capture_task018.py`, `review_task018.py`. Documentation: both
READMEs, ARCHITECTURE, LOCALIZATION, TESTING, CHANGELOG, QT_TEXT_INVENTORY,
this record/artifacts, `.gitignore` evidence allowlist. Local ignored
`task/Task018.md` records status; its existing ignore policy is retained.

This is focused Task018 acceptance, not Task023 or complete repository/release
certification. Not run: native Linux, physical monitor DPI transitions, screen
readers, real drives/photo libraries, valid RAW assets, power-loss or external
OS viewers. The painted per-card action is keyboard accessible through the
group's Enter activation and the native toolbar Review control; it is not a
separate native child button. Review state is intentionally not persisted, and
no new global category/review filter is claimed. Filesystem/move verification,
explicit approval, no-overwrite and recovery authority remain in existing services.
