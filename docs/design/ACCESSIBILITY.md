# Task010 accessibility and translation preparation

This milestone retains the Serbian Latin Qt interface. It does not implement
English defaults or language switching. `state.py` language validation and the
shared SR/EN resources are unchanged. The complete key inventory and English
editorial intentions are in [QT_TEXT_INVENTORY.json](QT_TEXT_INVENTORY.json);
Serbian wording remains in `app/ui/qt/strings.py` and `app/i18n/__init__.py`.
The inventory is documentation and is never loaded at runtime.

The inventory includes navigation, page headings/purposes, actions, dialogs,
empty/loading/error/success states, classifications/statuses, tooltips, accessible
names/descriptions and Settings explanations. Technical identifiers (EXACT, VISUAL,
RAW, hashes, paths, operation IDs, schema values and the literal RAW consent token)
remain independent of translated labels. New UI copy belongs in the existing
catalog. The inventory test checks every Qt/shared Serbian key has an English intent.

Unknown Qt translation keys and invalid format arguments use a readable Serbian
fallback. Shared known keys retain their Serbian/English resource fallback.
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
acceptance belongs to Task011; full localization belongs to Task012.
