# Task003: Qt runtime and distribution

Task013 update (2026-11-09): the owner selected a **source ZIP + offline wheelhouse**.
The local Windows AMD64 / CPython 3.12 candidate keeps Python external and creates
an isolated `.runtime` using hash-locked wheels, with both JSON catalogs and compiled
SVG resources. Complete Qt wheels/notices remain included, including unused
transitive Addons/Pdf/WebEngine components. See [RELEASE.md](RELEASE.md) for the
current artifact inventory, official license sources, offline installation and
unresolved redistribution obligations. The historical Task003 assessment below
is not a frozen-build or clean-machine acceptance result. No application license
has been selected. Public release, Linux and clean target OS acceptance remain open.

Tested Windows runtime, 2026-11-08: Python 3.12.10 x64, PySide6/Qt 6.12.0,
shiboken6 6.12.0, Pillow 13.0.0, ImageHash 4.3.2, rawpy 0.28.0,
pillow-heif 1.8.1. Other allowed PySide6 versions (>=6.8,<7) and Linux are untested.

The adapter uses QtCore, QtGui, QtWidgets, SVG icon rendering and QtTest for tests.
It uses no WebEngine, network modules or remote resources. The PySide6 metapackage
may install unused modules; they are not application features.

Qt for Python offers LGPLv3/GPLv3 and commercial licensing. Modules and third-party
components carry individual notices. Before redistributing, inventory the included
modules, select an applicable license, retain notices, supply required source or
offers where applicable, and preserve replacement/relinking rights for LGPL libraries.
Distribution format and the application's license still need review before release;
this milestone does not certify an installer. Consult the official
[license inventory](https://doc.qt.io/qtforpython-6/licenses.html) and
[licensing guidance](https://doc.qt.io/qt-6/licensing.html).

Delivery remains a Python environment. Prepare wheels on an online machine with
matching OS, architecture and Python ABI; use a separate wheelhouse per target:

```text
python -m pip download --dest wheelhouse -r requirements-dev.txt
python -m pip install --no-index --find-links wheelhouse -r requirements-dev.txt
python -B -m app.services.preflight --ui qt
python -B photo_agent.py --ui qt
```

Use requirements.txt for runtime only. Task003 did not run wheelhouse creation or
offline installation; Task013's actual candidate checks are recorded in TESTING.md.
Repository development launchers still attempt pip installation if preflight fails;
the packaged offline launchers do not. Use the latter after explicit offline install.

Frozen packaging must include Qt platform plugins (qwindows/xcb/wayland as applicable),
used SVG/image plugins, Qt libraries/notices, LibRaw/HEIF native dependencies and a
working decoder subprocess. Current decoding invokes `python -m app.scanning.decoder`;
freezing requires explicit child dispatch and native-code tests. The official
[pyside6-deploy reference](https://doc.qt.io/qtforpython-6/deployment/deployment-pyside6-deploy.html)
is a future assessment reference, not a validated packaging recipe.

System theme detection uses QStyleHints.colorSchemeChanged. Unknown falls back to
dark without changing the system preference. Native platform support varies; see
[QStyleHints](https://doc.qt.io/qt-6/qstylehints.html).

resources_rc.py is checked in; regenerating the local SVG resource uses:

```text
.venv\Scripts\pyside6-rcc.exe app/ui/qt/resources/resources.qrc -o app/ui/qt/resources_rc.py
```

## Localization resources (Task012)

Source launches load `app/i18n/en.json` and `sr_Latn.json` alongside the Python
package. Task013's source ZIP includes both UTF-8 JSON files; a future frozen build
must include them as package data too. Used Qt framework strings map to the catalogs through the
Python QTranslator adapter; no external translation download or new dependency is
required. Frozen packaging is not the chosen Task013 format; native Linux release
validation remains open.
