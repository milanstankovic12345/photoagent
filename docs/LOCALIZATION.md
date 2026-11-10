# PhotoAgent v2.5 localization

## Sources and build

The editable sources are `app/i18n/en.ts` and `app/i18n/sr_Latn.ts`, UTF-8 Qt
Linguist TS 2.1 files. Context `PhotoAgent` uses stable keys as `<source>` values;
the English catalog contains the English prose in `<translation>`. Edit translation
elements with Qt Linguist or a UTF-8 editor. Do not rename keys, translate arguments,
or change `{0}` / `%1` placeholders. The separate `group_summary_one/few/other`
keys implement Serbian 1/2–4/other grammar including the 11–14 exception.

From the repository, using the environment containing PySide6:

```text
python -B -m tools.build_translations
python -B -m tools.build_translations --check
```

On Windows use `.venv/Scripts/python.exe`; on Linux use `.venv/bin/python`.
The first command validates key parity, complete translations and placeholders,
generates the non-Qt JSON fallback catalogs, invokes Qt `lrelease` for `.qm`, then
`rcc` to embed them in `app/i18n/resources_rc.py`. It never installs or downloads.
The equivalent Qt tool commands after JSON generation are:

```text
pyside6-lrelease app/i18n/en.ts -qm app/i18n/en.qm
pyside6-lrelease app/i18n/sr_Latn.ts -qm app/i18n/sr_Latn.qm
pyside6-rcc app/i18n/translations.qrc -o app/i18n/resources_rc.py
```

This follows Qt's [TS → QM and resource embedding workflow](https://doc.qt.io/qtforpython-6/tutorials/basictutorial/translations.html).
Commit TS, generated JSON/QM, QRC and the generated Python resource together.
`--check` validates TS/JSON parity without PySide6; the compiled-resource test
compares every embedded translation against JSON to detect stale QM/resources.
Do not edit generated JSON or `resources_rc.py` independently. When adding keys,
update `docs/design/QT_TEXT_INVENTORY.json` and both TS files, then rebuild.

## Runtime behavior

`LanguageManager` loads embedded `:/photoagent/i18n/{language}.qm` catalogs through
`QTranslator`. `QtMessage` preserves the stable key and original arguments for live
bindings. The framework translator maps QFileDialog, context menu and standard
button source strings to those same catalog keys. Qt `LanguageChange` updates
standard dialogs; bound widgets and models update in place, preserving selections,
preview images, zoom and frozen operation plans. No translated label is used as a
database identifier, sorting field, file identity or confirmation token.

Both languages currently contain **434/434 finished messages (100%)**, with no
missing explicit SafetyError codes or untranslated application safety warnings.
Translation coverage means catalog/key/placeholder and rendered workflow coverage;
it is not certification of every OS/Qt-provided string or linguistic proofreading.

Fallback order is selected compiled entry → selected JSON entry → English JSON
entry → localized readable unavailable-message text for an unknown key or invalid
format arguments. A missing QM catalog leaves the JSON fallback operational.
Unknown language identifiers normalize to English. Missing keys and formatting
failures are logged. Raw exception details remain available separately under
Technical details and retain original wording, paths and hashes.

Fresh installations start in English. Existing state without a language keeps
Serbian Latin. The service saves `en`/`sr_Latn` atomically in settings; switching
is immediate while persistence queues behind active work. Save failure restores
the last successful choice. No approval, matching, recovery or database format is
changed by switching. Settings chooses display locale `en_US` or `sr_Latn_RS`;
binary size units and technical format names stay stable, decimals/grouping and
dates change for display only. History dates remain UTC with the UTC suffix.
Other technical metadata/CSV fields retain their stable formatting.

## Packaging and extending

The source ZIP includes TS/QM/JSON/QRC, the embedded Python resource, build tool,
English/Serbian README and this guide. A frozen build must include the imported
`app.i18n.resources_rc` module and both JSON fallback files under `app/i18n`;
no working-directory lookup or system-installed translations are needed. A frozen
executable configuration is not currently provided by PhotoAgent. The packaging
test loads the resource from an extracted Unicode path in a separate isolated
Python process, without importing the development source. The installed-runtime
release smoke also checks all compiled entries in both languages.

To add a language: add a matching complete TS, add its stable identifier to
`app.i18n.LANGUAGES`, the build tool, settings validation and Settings selector,
add the locale mapping in localization (shared by formatting) and its plural rule where
needed, extend QRC and tests, then regenerate all resources. Persistence always
uses the stable identifier. Translations and safety logic remain separate.

The retained Tk UI is Serbian only. OS error details and OS-owned dialogs outside
PhotoAgent (including an external file manager) follow their own language. Future
Qt versions can introduce framework strings outside the explicit adapter map;
review these when upgrading. Linux native display, physical DPI, screen reader
and valid RAW acceptance remain separate platform checks.

## Serbian maintainer notes

Izvori prevoda su `.ts` datoteke; `.json`, `.qm` i Python resurs su generisani izlazi.
Promenite oba izvora, sačuvajte parametre i pokrenite `tools.build_translations`.
Pre pakovanja pokrenite proveru kataloga i lokalizacione testove. Izbor jezika se
čuva automatski; potvrda karantina ili vraćanja ostaje zasebna izričita radnja.
Putanje, nazivi fotografija, heševi i token `RAW` uvek ostaju nepromenjeni.
