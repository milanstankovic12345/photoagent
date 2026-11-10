# Qt accessibility and localization

Task016 (2026-11-10) adds session-local compact/expanded navigation. The default
64 logical-pixel rail retains the application logo and five destinations; the
208 logical-pixel expanded rail shows localized labels. Settings stays at the
bottom. A 44-pixel checkable toggle precedes the destinations in Tab order;
Space/Enter/Return activate it without moving focus. Its checked state means
expanded, with a localized action name, tooltip and state description. Every
destination retains a localized accessible name and tooltip in either mode,
and native checked semantics. A persistent foreground marker identifies the
active destination without relying on color alone. Selection has a subtle
surface and no decorative contour; keyboard focus retains its own outline.

The 160 ms event-loop animation resizes only Sidebar. Pages, queries, selections,
scroll widgets, workers and confirmation dialogs remain alive. Repeated toggles
reverse from the current width. Labels appear after expansion to avoid clipping.
An open modal confirmation continues to block pointer access to the sidebar;
programmatic resizing neither rejects it nor supplies consent. The mode lasts
for the current window session and is not a new saved preference.
See [Task016 evidence](verification/task016-20261110/README.md) for executed
interaction, rendering, regression and scaled-layout checks and their limits.

Task015 (2026-11-10) refines shared presentation with 1 px control outlines,
discreet card separators and a local line icon family. Navigation, disclosure and
embedded preview/source containers keep a visible keyboard focus without nested
decorative boxes. Task016 replaces the checked navigation contour with a persistent
marker; focus has its own contrasting outline on the selected destination.
Checkbox and item focus outlines stay 2 px. Border widths, content rectangles and
layout geometry remain stable across hover/focus/selection.

Icons supplement existing translated labels and accessible names. Disabled icons
use readable semantic foregrounds; primary/danger icons use their action's text
color. System changes repaint the same icon objects, preserving filter, route,
language and theme choices. No photograph-opening behavior is added. New rendered
contrast/HiDPI/keyboard/choice tests and inspected captures are documented in
[Task015 evidence](verification/task015-20261110/README.md). Native accessibility,
screen readers and physical high-DPI remain unverified.

Task010 established the accessibility behavior below; Task012 adds English and
Serbian Latin runtime switching. v2.5 authoritative catalogs live in `app/i18n/`
as UTF-8 Qt TS sources, compiled to embedded QM with generated JSON fallback.
See [build and editing instructions](../LOCALIZATION.md).
[QT_TEXT_INVENTORY.json](QT_TEXT_INVENTORY.json) documents their
current keys and is never loaded at runtime. Native Qt framework messages used by
the app map into the same catalogs through a small QTranslator adapter.

The inventory includes navigation, page headings/purposes, actions, dialogs,
empty/loading/error/success states, classifications/statuses, tooltips, accessible
names/descriptions and Settings explanations. Technical identifiers (EXACT, VISUAL,
RAW, hashes, paths, operation IDs, schema values and the literal RAW consent token)
remain independent of translated labels. New UI copy belongs in the existing
catalog. Tests check key and placeholder parity and literal Qt translation keys.

Missing translations and unknown languages fall back to English. Unknown keys or
invalid format arguments show a readable message in the active/fallback language.
Exception text and unrecognized error codes appear only in selectable plain-text
technical details, initially collapsed. A short actionable message remains visible.
Scan/report failures retain their diagnostics in the existing Errors section.
Preview errors do not authorize moving files or change eligibility checks.
The empty-plan message opens without a nested blocking dialog loop and offers a
localized Close action, with no approval or movement. Hidden gallery/dashboard
refreshes cancel only their own thumbnail batches.

Keyboard behavior:

- Tab/Shift+Tab traverse sidebar, active page actions and page content in visual
  order. Read-only tables use arrows within the table and Tab to leave it.
  Hidden/disabled controls are skipped. Source rows expose their path and
  availability to accessibility APIs. Arrows select sources, groups, pairs and
  history entries. Enter opens a group/pair comparison.
- Entering the gallery selects its first visible group if focus would otherwise
  remain on the hidden All Groups row. All Groups remains a separate button.
- Comparison opens with Back focused; Back/Alt+Left returns to the selected pair.
  Left/right preview names differ; retaining controls name the full photograph.
  Retained/proposed/selected states have text, including a label on selected groups.
- Confirmation starts on Cancel. Enter/Return never approves a plan. Space on the
  explicit approval button or a deliberate pointer click can approve only after
  required RAW/legacy consents. Escape rejects. Critical warnings remain outside
  collapsed technical details. Cancel returns focus to the invoker when still
  available, otherwise the current navigation entry.
- Read-only diagnostic editors allow Tab to leave. Enlarged previews have a named
  view and explicit Close action; closing returns to their invoking enlarge control.

Long paths wrap within the available width and are available in full tooltips,
selectable metadata or diagnostic/plan editors. Compact photo names are elided in
the summary, while full values stay in details and accessible control names.
Preview actions wrap. Narrow comparison layouts stack the two photographs below
640 logical pixels or when the two cards' actual minimum widths need more room,
instead of shrinking their controls. Source availability remains on its own line
beside an elided path. Gallery focus is an unfilled outline that preserves the
thumbnail and text underneath. Existing theme tokens
preserve readable disabled states and focus outlines in Dark and Light.

For executed commands, actual results and reviewed renders see
[TESTING.md](../TESTING.md). Offscreen rendering and `QAccessible` queries do not
prove assistive-technology usability. Manual NVDA/Narrator, native Windows/Linux
high-DPI and physical-display keyboard testing remain unverified. Full redesign
acceptance belongs to Task011. Task012 covers the Qt interface; Tk remains Serbian.
