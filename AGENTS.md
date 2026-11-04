
# PhotoAgent - Repository Instructions for Codex

## 1. Project identity

Name: PhotoAgent
Current baseline: v1 prototype
Target milestone: v2
Language: Python 3.12+
Platforms: Windows 10/11 and Linux
Primary development environment: VS Code with Codex

PhotoAgent is a fully local desktop application for discovering,
reviewing, and safely managing duplicate photographs across
multiple folders, internal drives, and removable storage.

The application must work offline. Do not add cloud services,
telemetry, online accounts, or external AI APIs.

## 2. Source of truth

Inspect the actual repository before making assumptions.

The original prototype is expected to contain:

- photo_agent.py: scanning, hashing, RAW decoding, GUI,
  reporting, quarantine, and restoration
- requirements.txt: Python dependencies
- napravi_demo.py: synthetic sample collection
- start_windows.bat and start_linux.sh: launch scripts
- README_SR.md: Serbian instructions

The actual repository may differ from this description.

Never report a feature as implemented merely because it is
described in this file or in a planning document.

## 3. Existing functionality to preserve

- Recursive scanning of multiple selected folders.
- Exact-file detection using SHA-256.
- Visual similarity detection using pHash and dHash.
- RAW image support through rawpy / LibRaw.
- Preview of two candidate photographs.
- Heuristic recommendation of which file to keep.
- CSV reports.
- Explicitly approved moves into quarantine.
- Restoration of previously quarantined files.
- Offline operation.

Treat every existing behavior as unverified until tested.

## 4. Non-negotiable data safety

User photographs may be irreplaceable.

Rules:

1. Never permanently delete original photographs.
2. Never overwrite an existing photograph.
3. Never perform an unapproved bulk file operation.
4. Never use real photo libraries in automated tests.
5. Use synthetic fixtures in isolated temporary directories.
6. Require explicit confirmation before quarantine operations.
7. Verify file identity and state immediately before moving.
8. Do not treat visual similarity as proof of duplication.
9. Keep RAW originals by default.
10. Preserve edited derivatives and important metadata.
11. Never automatically remove XMP sidecar files.
12. Protect deliberate backup copies on separate drives.
13. Do not follow directory symlinks or junctions outside
    the selected roots.
14. Avoid reprocessing quarantine directories.
15. Support safe cancellation without corrupting state.
16. Log file operations and failures.
17. Make restoration reliable across application restarts.
18. Use a dry-run or preview step before destructive actions.

Quarantine is reversible file movement, not deletion.

Before any move, check the source, the retained candidate,
path containment, current metadata, and relevant hashes.

Do not substitute a weaker verification method for an
existing stronger safety guarantee.

Never run tests that modify actual user photographs.

## 5. Photograph matching rules

Separate these concepts explicitly:

EXACT:
Files with identical binary content confirmed by SHA-256.

VISUAL:
Images with similar visual content according to image hashes
or other image matching algorithms.

DERIVATIVE:
Different representations of potentially the same source,
including RAW+JPEG, exports, edits, and resized images.

SIMILAR_CAPTURE:
Different photographs of similar scenes or burst sequences.

Only EXACT may be considered for optional bulk quarantine,
and only after the user explicitly approves the operation.

VISUAL, DERIVATIVE, and SIMILAR_CAPTURE require review.

Never use a transitive similarity chain to conclude that all
images in a group represent the same original photograph.

## 6. Quality assessment rules

Image quality is multidimensional.

Consider, where available:

- Original versus derivative status
- RAW versus rendered format
- Dimensions and effective resolution
- Compression and image artifacts
- Focus and sharpness
- Noise
- Bit depth
- EXIF information
- Metadata and editing history
- Availability of the original source

RAW is not automatically a replacement for an edited JPEG.

A larger file is not automatically a higher-quality image.

Distinguish objective measurements from heuristics.
Expose uncertainty to the user.

Quality scores may inform recommendations but must never
silently authorize deletion.

## 7. Target v2 architecture

Prefer a modular architecture with clear boundaries:

- app/core: photo metadata, domain models, matching rules
- app/scanning: traversal, file inspection, image extraction
- app/matching: exact and visual duplicate detection
- app/storage: SQLite index and schema migrations
- app/safety: quarantine, verification, recovery, audit log
- app/services: application use cases and coordination
- app/ui: desktop interface and view models/controllers
- app/i18n: localization resources
- app/config: application settings
- tests: automated tests and synthetic fixtures

This is a target organization, not permission for a
large untested rewrite.

Migrate incrementally after assessing the current design.

Keep all file-system and image-processing logic outside
the UI layer.

## 8. Preferred v2 technology

Core:
- Python 3.12+
- Pillow
- ImageHash
- rawpy / LibRaw
- Standard-library sqlite3
- pytest

Desktop UI preference:
- PySide6 / Qt 6

For PySide6, use Qt-native translation resources where
practical and a maintainable theme system.

Before committing to UI migration, verify compatibility,
packaging requirements, and distribution licensing.

Avoid introducing a web frontend, backend server,
Electron, cloud API, or local LLM without a clear need.

## 9. Phase 2 priorities

Priority order:

P0: Prevent data loss and fix critical correctness defects.
P1: Establish automated tests and modular core boundaries.
P2: Implement SQLite-backed incremental indexing.
P3: Improve duplicate grouping and quality recommendations.
P4: Modernize UI with PySide6 and configurable themes.
P5: Add Serbian and English UI localization.
P6: Perform regression testing and packaging validation.

Keep each change independently reviewable.

Do not implement every priority in one uncontrolled edit.

## 10. SQLite requirements

SQLite is a local cache and operation-history store.

- Add versioned schema migrations.
- Keep schema changes backward compatible when possible.
- Use parameterized SQL.
- Use transactions for related database operations.
- Never store binary image data without justification.
- Index fields used by common queries.
- Detect added, changed, moved, and missing files.
- Treat cached fingerprints as potentially stale.
- Revalidate candidates before quarantine.
- Handle missing and disconnected drives safely.
- Never interpret an offline drive as authorization
  to delete its indexed records.
- Ensure concurrent workers do not corrupt the database.

Do not store the only recovery information in a fragile
or non-atomic in-memory structure.

## 11. UI and UX requirements

Target a modern, accessible desktop application.

Required experience:

- Scan sources / folder selection
- Dashboard and scan progress
- Duplicate groups and filtering
- Side-by-side photograph comparison
- Metadata and quality indicators
- Quarantine and restore history
- Settings
- Theme selection: Dark, Light, System
- Language selection: Serbian (Latin), English

Use background workers for scanning and hashing.
The UI must remain responsive.

Support cancellation, error reporting, and clear status
messages. Never update GUI widgets from worker threads.

Make protected or risky operations visually explicit.

Keyboard navigation, readable contrast, scaling,
and responsive layouts are important.

## 12. Localization

Initial languages:

- sr_Latn: Serbian Latin
- en: English

Use stable translation keys or Qt translation mechanisms.

Do not hardcode user-facing strings inside business logic.

Translate menus, buttons, dialogs, tooltips, status text,
errors, confirmations, and accessibility labels.

Allow changing languages in Settings.

Persist the language preference.
Provide a fallback for missing translations.

Keep technical identifiers, database values, and paths
independent from displayed translated labels.

## 13. Coding standards

- Prefer readable, idiomatic Python.
- Use type hints for new or substantially changed code.
- Use pathlib for filesystem paths when practical.
- Use dataclasses or typed models for domain objects.
- Separate pure logic from file operations and UI code.
- Avoid unnecessary dependencies.
- Use structured logging.
- Catch specific exceptions where possible.
- Do not silently suppress errors.
- Keep functions focused and testable.
- Preserve Windows and Linux compatibility.
- Avoid global mutable application state where possible.
- Document non-obvious safety decisions.

Do not add abstractions that solve hypothetical problems.

## 14. Testing requirements

Use pytest and temporary synthetic photo collections.

Cover at least:

- Exact duplicates with different names
- Different folders and drives (simulated)
- JPEG/PNG/WebP visual similarity
- Different photos with similar visual appearance
- Resolution and compression variants
- RAW files when suitable test assets are available
- Undecodable RAW files
- Duplicate groups containing more than two files
- Same path included through overlapping scan roots
- Corrupted or unreadable files
- Missing or disconnected storage
- Symlinks and path traversal
- Interrupted scans
- Stale SQLite cache entries
- Confirmation and quarantine behavior
- Restore without overwriting existing files
- Interrupted moves and recovery
- Language switching and missing translations
- Theme preference persistence

Never simulate a successful test run.

Report exactly which checks ran and which were skipped.

## 15. Development workflow

For unfamiliar or high-impact work:

1. Inspect relevant source code and tests.
2. Explain the current behavior and risks.
3. Propose a limited implementation plan.
4. Identify the files expected to change.
5. Implement the approved scope.
6. Run focused tests, then relevant regression tests.
7. Review the diff for safety and unrelated edits.
8. Summarize results and remaining limitations.

For small, well-scoped changes, avoid unnecessary process.

Do not create commits, push code, install system packages,
or modify external files without appropriate permission.

Do not overwrite uncommitted user changes.

## 16. Project documentation

Maintain these documents when relevant:

- README.md: installation, usage, supported formats
- docs/ARCHITECTURE.md: actual component structure
- docs/REVERSE_ENGINEERING.md: initial source audit
- docs/ROADMAP.md: prioritized phases
- docs/SECURITY.md: data safety and recovery
- docs/TESTING.md: commands and verification
- docs/CHANGELOG.md: notable completed changes

These are planned documents, not guaranteed existing files.

Keep documentation aligned with implemented behavior.

## 17. Definition of done

A feature is not done until:

- The code implements its stated requirements.
- Relevant tests pass.
- Existing safety guarantees remain intact.
- Failure and cancellation paths were considered.
- User-facing text is localized where appropriate.
- Documentation is updated when necessary.
- The final response lists changed files, tests run,
  known limitations, and any remaining risks.

Do not declare implementation complete based only on
successful syntax checking or a generated UI screenshot.

## 18. Communication with the owner

The owner uses Serbian for discussion and English for
technical prompts and source-code terminology.

Explain important decisions in clear, beginner-friendly
Serbian when communicating directly with the owner.

Ask before making irreversible decisions or changing
explicit product requirements.

Avoid overengineering. Prefer reliable and verifiable
changes over large speculative redesigns.
