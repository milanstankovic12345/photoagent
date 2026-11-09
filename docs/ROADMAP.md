# PhotoAgent v2 implementation roadmap

Task013 (2026-11-09): local source ZIP/offline-wheelhouse tooling is implemented
for the owner's selected format, with hash verification and synthetic installed
runtime rehearsal. [RELEASE.md](RELEASE.md) documents actual contents, dependency
and license inventory, installation/recovery and open gates; [TESTING.md](TESTING.md)
records executed checks. R1/M7 remains open: a host-local fresh venv is not clean
Windows 10/11 or Linux acceptance, valid RAW/platform/DPI gates remain required,
and the 1k/10k benchmark/budgets and redistribution license decisions are unresolved.
No release-ready/publication claim or safety-policy waiver is made.

Planning baseline: `569e2a1`, 2026-11-04. The task table and gate definitions below
originated as a proposal; their present status is assessed here and in
[TESTING.md](TESTING.md). T1, S1-S4, B1-B5 and I1-I2 have implementations with
Windows synthetic regression coverage. I1/I2 use a schema-versioned SQLite cache,
full-content validation, disk-backed matching and paged Tkinter results. The JSON
operation journal remains authoritative. Warm cache hits still read full SHA-256.
Neither M2 nor M3 has a completed cross-platform gate: Linux was not run, and the
1k/10k M3 benchmark stopped before its first scenario completed. Quality calibration,
Task003 adds PySide6 and themes (now the default at the owner's request); manual acceptance,
Tk localization, native platform acceptance and packaging remain open. Qt localization
and runtime switching are implemented by Task012 with synthetic coverage. Priorities follow
[AGENTS.md](../AGENTS.md); finding IDs refer to [the audit](REVERSE_ENGINEERING.md).
Each change must remain independently reviewable and preserve stronger existing checks.

Task010 adds Qt accessibility fixes and a 291-key translation-intent inventory,
with isolated keyboard journeys and offscreen Dark/Light scaling evidence. See
[accessibility contracts](design/ACCESSIBILITY.md) and [executed checks](TESTING.md).
It does not close the native assistive-technology/platform gate, Task011's complete
redesign review, or L1/Task012's full localization and runtime language switching.

Task011 implements Stage H's repeatable synthetic capture/geometry and regression
workflow. [The verification report](design/TASK011_VERIFICATION.md) records current
offscreen results and reviewed images across four sizes and three actual Qt DPRs.
Native Windows/Linux DPI, monitor changes and assistive-technology checks remain
open, so Prompt 6.1 is not declared fully accepted. L1/Task012 localization and
Task013 release/package validation remain separate workstreams. Task012 is now implemented
for Qt; the historical Stage H checks below do not verify it. No matcher,
schema, recovery format or safety guarantee is changed by this stage.

## Prioritized backlog and dependencies

Task012 implements L1 for the Qt interface: EN/SR catalogs, immediate switching,
persistent preferences, legacy migration and safe fallback. See [TESTING.md](TESTING.md)
for executed regression and scaling checks. Tk remains Serbian; native Linux,
physical monitor/assistive-technology checks and packaging remain open gates.

Dependencies are task IDs. T1's initial harness precedes safety changes; its broader
fixture coverage grows with each milestone rather than delaying urgent P0 fixes.

| Task | Priority / milestone | Scope and finding coverage | Depends on |
|---|---|---|---|
| T1 | P1 enabling / M0 | pytest harness, isolated synthetic fixtures, turn the 17 probes into durable regression cases, safe demo and corrected README (H14, D6). | None |
| S1 | P0 / M1 | Shared no-overwrite move/restore/rollback primitive; reject same-file candidates (H1, H6). | T1 |
| S2 | P0 / M1 | Stable source/keeper identity, hashes, approved snapshots, source/destination/parent containment, junction/volume policy and quarantine exclusion (H3-H6). | T1, S1 |
| S3 | P0 / M1 | Durable operation intent, restart reconciliation, validated legacy state, multi-instance coordination, retained audit history (H2, H3, H7, D4). | S1, S2 |
| S4 | P0 / M1 | Reviewable action plans, protected backup roots, explicit per-operation approval; keep RAW and edited derivatives protected by default; non-exact never bulk (H8). | S2, S3 |
| B1 | P1 / M2 | Typed models and service boundaries; move I/O out of UI; stable category/error identifiers (D1). | S1-S4 |
| B2 | P1 / M2 | Worker lifecycle, bounded cancellation, asynchronous previews/actions, source availability, invalidate all keeper-dependent results (H9, H11, H13). | B1 |
| B3 | P1 / M2 | Polling survives report failure; unique reports and structured persistent diagnostics (H10, D4, D5). | B1, S3 |
| B4 | P1 / M2 | Decoder/resource policy, malformed/multiframe/EXIF/sidecar tests and metadata extraction status (H12, D6). | T1, B1 |
| B5 | P1 / M2 | Reproducible environments, separately reviewed removal of tracked venv, version/capability preflight, offline install instructions (D2, D3). | T1 |
| I1 | P2 / M3 | SQLite schema/migrations, source/file identity, scan generations, stale-cache detection and transactional operation-store integration. | B1-B4, S3 |
| I2 | P2 / M3 | Incremental scanning, bounded memory/results, controlled writer concurrency and archive benchmarks. | I1, B2 |
| Q1 | P3 / M4 | Explicit groups and keeper dependencies; EXACT/VISUAL/DERIVATIVE/SIMILAR_CAPTURE; explained quality and metadata-aware recommendations (H8, H9, D6). | B1, B4, I1 |
| Q2 | P3 / M4 | Calibrate visual thresholds and test false positives, bursts, edits and non-transitive relationships. | Q1, T1 |
| U1 | P4 / M5 | PySide6 compatibility/licensing/package gate, then desktop UI and Dark/Light/System themes. | B2, B3, B5, Q1 |
| L1 | P5 / M6 | en/sr_Latn resources, runtime switching, persistent preference and missing-translation fallback. | U1, B1 |
| R1 | P6 / M7 | Full regression, offline packages, migration/recovery rehearsal and release evidence. | I2, Q2, U1, L1 |

Coverage check: H1-H14 and D1-D6 each have a P0/P1 task above. H8/H9/D6
receive immediate protection or regression coverage before later P3 enhancements.
Performance improvements must not replace existing full SHA verification with a
weaker size/mtime-only shortcut.

## Milestones and measurable gates

Safety, backend modernization, UI migration and localization are separate workstreams.
Acceptance criteria below are targets, not results. Required safety cases must pass
on Windows and Linux; a platform skip does not satisfy the corresponding gate.

### Task002 evidence review for M2 and M3 (Windows, 2026-11-08)

| Gate criterion | Status and evidence |
|---|---|
| M2 GUI-free backend imports and compatible results | Windows synthetic import and matcher-equivalence tests pass. Large 1k/10k pair-identity comparison remains unmeasured. |
| M2 report failure, offline roots, keeper invalidation | Covered by passing UI, scanning and indexing regressions in TESTING.md. |
| M2 cancellation, decoder limits and shutdown | Covered by passing synthetic regressions; OS calls still have no hard cancellation deadline. |
| M2 slow-I/O heartbeat under 250 ms | Met on this Windows host: six complete 20-photo scans, worst gap 84.746 ms, 50 ms worker-read delay and 25 ms tick. Raw gaps in `.benchmarks/task002-ui-final-20261108/results.json`. |
| M2 clean launch on Windows and Linux | Windows environment and UI tests pass. Native Linux launch remains untested. **M2 cross-platform gate open.** |
| M3 unchanged warm scan: zero decodes with full SHA reads | Small synthetic tests cover cache reuse and full-content validation. A 10-file tool smoke check measured 0 warm decodes and 10 SHA reads. Required 1k/10k measured counts remain open. |
| M3 changed/moved/replaced/offline outcomes and move-time verification | Passing synthetic index and operation tests cover these states. Physical drive unplug/replug remains untested. |
| M3 migrations, crash recovery and writer concurrency | Passing synthetic migration, process-crash and competing-writer tests; physical power-loss behavior remains unverified. |
| M3 1k/10k cold/warm/changed metrics, pair comparison and 125% budgets | Index attempt stopped during its first 1k cold scan; no completed scenario or valid budget. Baseline attempt is also incomplete. The tool now records a pair-identity digest for future completed runs. **M3 benchmark and cross-platform gate open.** |

### M0 — Executable baseline and synthetic test harness

- Deliver T1's initial harness, safe fixtures and corrected demo instructions.
- Acceptance: the 17 historical checks have named reproducible tests; actual file
  tests use temporary roots; home state/reports are redirected; demo repeat runs
  cannot overwrite an existing collection. Known failures have explicit issue IDs
  and strict expected-failure status, never misleading green acceptance.
- Rollback: revert harness/demo changes independently. Keep recorded findings;
  no real library or persisted application schema should have changed.

### M1 — Safe operations and recovery (safety gate)

- Deliver S1-S4 using the existing UI; only minimal extraction needed for safety.
- Acceptance: all S1-S4 regression cases pass; denied/expired approval performs
  zero moves; occupied targets retain original bytes; source/keeper changes,
  same-file aliases and path escapes are rejected. Every injected crash boundary
  yields an intact source or verified quarantine file with durable recovery data.
  Restart recovery is idempotent; offline drives remain pending; two instances
  cannot lose operation records. RAW/XMP/backup protections are exercised.
- Rollback: disable new moves and enter recovery/read-only mode on regression.
  Keep operation journals and quarantine intact. Do not fall back to unsafe v1
  writes or restore an old history snapshot over operations performed afterward.

### M2 — Modular backend and responsive existing UI

- Deliver B1-B5; keep Tkinter presentation while moving I/O into services.
- Acceptance: core/matching/safety imports require no GUI instance; equivalent
  baseline inputs produce documented equivalent results except intentional fixes.
  Report failure cannot stop polling; offline roots are explicit; moved keepers
  invalidate every dependent result. Cancellation is checked each hash chunk and
  between decode/tasks. A controlled slow-I/O fixture keeps UI heartbeat gaps
  below 250 ms on the recorded reference host. Decoder limits and shutdown are tested.
  Clean environments start on both OS families without the tracked Windows venv.
- Rollback: restore the last safe service/UI adapter, preserving M1 storage and
  recovery readers. Revert modules separately; do not reinstall a tracked venv or
  delete the user's active environment as part of rollback.

### M3 — SQLite incremental index (backend modernization)

- Deliver I1/I2; record the selected transaction/writer policy and schema versions.
- Acceptance: unchanged warm scan performs zero image decodes on a controlled
  unchanged fixture; changed metadata invalidates entries; moves and replacements
  have explicit outcomes; incomplete/offline scans never mark an entire source
  missing or remove records. All schema upgrades are transactional/recoverable;
  crash and concurrent-worker tests pass. Benchmark 1k/10k synthetic records with
  cold/warm time, read/decode counts and peak RAM; set hardware-specific budgets.
  Move-time full verification remains mandatory even on a cache hit.
- Rollback: preserve a consistent pre-migration backup and all subsequent operation
  history. Rebuild only the disposable index. If an older binary cannot read newer
  history, refuse mutation and use the compatible recovery reader; no blind down-migration.

### M4 — Explainable grouping and recommendations

- Deliver Q1/Q2 independently from the UI framework migration.
- Acceptance: labeled fixtures cover all four categories, 3+ exact members,
  RAW/rendered edits, bursts and A-B-C chains; no non-exact bulk candidates.
  Every recommendation exposes evidence/uncertainty; regression-set errors are
  recorded as a confusion matrix. Unknown provenance remains uncertain rather
  than being asserted as a derivative. No calibrated thresholds ship without review.
- Rollback: select the previous matcher version and invalidate only derived match
  results. Preserve photo records, approvals/history and M1 protection policies;
  never apply old approvals to recomputed plans.

### M5 — Desktop UI migration and themes

- Deliver U1 only after a written Python/Qt/native-codec compatibility, packaging
  and distribution-license assessment. Task003 records the source-runtime assessment
  in QT_DISTRIBUTION.md; frozen packaging and native manual/scaling acceptance remain open.
- Acceptance: scan sources, progress/cancel, group filters, comparison, metadata,
  quarantine/restore history and settings work through the same services. Keyboard
  flows and 100/150/200% scaling pass manual checks; Dark/Light/System persist
  across restart. No worker writes widgets. Run the same safety scenarios through Qt.
- Rollback: retain the tested Tkinter adapter for the same service/schema version;
  preference fallback must not alter operation history or weaken confirmations.

### M6 — Localization

- Deliver L1 separately from UI restructuring; Qt resources preferred where practical.
- Acceptance: all inventoried menus, buttons, dialogs, confirmations, status/error
  messages, tooltips and accessibility labels have en and sr_Latn entries. Runtime
  switching and restart persistence pass; injected missing keys use the agreed
  fallback. Paths, enum values and stored records remain unchanged by locale.
- Rollback: use the last complete resource set or fallback language; preserve the
  selected preference and history; never migrate technical identifiers as translations.

### M7 — Release and recovery rehearsal

- Deliver R1 with test results, exact skip reasons, dependency versions and packages.
- Acceptance: packaged smoke/safety checks pass on Windows 10/11 and the declared
  Linux distribution/filesystem matrix; offline launch performs no network access.
  Rehearse legacy import, upgrade, crash recovery and rollback on synthetic collections.
  No open critical/high data-loss defect or skipped required safety case is accepted.
- Rollback: distribute the last compatible safe package or recovery-only build.
  Keep new-format readers and journals available; never delete quarantine during uninstall.

## Decisions and assumptions to resolve

| ID | Decision / proposed starting point | Deadline / evidence required |
|---|---|---|
| A1 | Versioned manifest journal vs minimal SQLite operation store before the index. Prefer one authoritative writer/history. | Before S3: compare crash durability, corruption handling and migration complexity. |
| A2 | Atomic no-overwrite and stable file/volume identity on supported filesystems; same-volume operation only initially. | Before S1/S2: Windows/Linux integration proof; explicit refusal for unsupported cases. |
| A3 | Network shares, removable formats and mount points in the supported matrix. | M1 scope gate: test plan and user-visible unsupported-state behavior. |
| A4 | Definition/configuration of protected backup roots and uncertain edited derivatives. | Before S4: reviewable defaults; confirmation remains explicit. |
| A5 | Redistributable RAW fixtures and decoder limits/process isolation. | Before B4: asset provenance and resource measurements; no borrowed personal library. |
| A6 | SQLite journal mode, writer topology, schema versions and legacy import policy. | Before I1: recovery/concurrency tests; preserve legacy file and mark unverifiable records. |
| A7 | Windows i5-1335U UI reference measured in Task002; 250 ms UI target met on that host. 1k/10k index/baseline measurements and budgets remain open. | Complete interrupted benchmark work in a separate performance task; then derive per-scenario 125% time/RAM budgets. |
| A8 | Qt distribution/license obligations, packaging tool and theme behavior. | Before U1 implementation; no licensing conclusion in this plan. |
| A9 | Translation workflow and fallback language (proposed: English). | Before L1; stable internal identifiers begin in B1. |

Recommended implementation order: M0 baseline, M1 safety, M2 modular backend,
M3 index, M4 matching, M5 UI, M6 localization, M7 release. Each milestone requires
its own scope review, focused tests, relevant regression, diff review and updated docs.

