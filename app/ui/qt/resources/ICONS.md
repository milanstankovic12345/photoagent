# Local icon provenance

`check.svg`, `expand.svg` and `collapse.svg` were drawn for PhotoAgent Task005
using elementary paths, without third-party artwork, packages or fonts.
These three new icons are dedicated to the public domain under CC0-1.0;
no attribution is required. They are bundled by `resources.qrc`, never fetched.
The pre-existing `photoagent.svg` is unchanged and is not covered by this notice.

## Task015 line family — 2026-11-10

`dashboard`, `scan`, `duplicates`, `quarantine`, `settings`, `search`, `filter`,
`sort`, `theme`, `language`, `open_external`, `restore`, `folder`, `expand` and
`collapse` SVGs are original elementary geometric drawings made for PhotoAgent
Task015. The last two replace the Task005 arrows. No third-party artwork,
icon package, font, tracing or network download was used. These fifteen drawings
are dedicated to the public domain under **CC0-1.0**, with no attribution required.

All use a 24 × 24 viewBox, 1.75-unit round strokes/joins and a 20 logical-pixel
display size. `icons.py` colors `currentColor` from the live application palette
and semantic foreground tokens, including primary, danger, disabled and selected
states. It renders directly at the requested device pixel ratio. Do not load these
SVGs as bare QIcons: use `icon()`, `set_icon()` or `set_combo_icon()` so colors follow
Dark/Light/System changes. Names are technical identifiers, never displayed copy.
The `check.svg` checkbox mark and brand artwork remain unchanged.

Resources are embedded offline in `app/ui/qt/resources_rc.py`. Regenerate with:

```powershell
.\.venv\Scripts\pyside6-rcc.exe app/ui/qt/resources/resources.qrc -o app/ui/qt/resources_rc.py
```

`open_external` currently marks existing reports/quarantine folder actions. It does
not add a photograph-opening feature; that behavior belongs to Task021.
