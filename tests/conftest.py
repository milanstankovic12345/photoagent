"""All application state and photographs are synthetic and confined to tmp_path."""
from __future__ import annotations

from pathlib import Path
import shutil
import sys

from PIL import Image, ImageDraw
import pytest


@pytest.fixture(autouse=True)
def isolated(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    monkeypatch.setenv("TMP", str(tmp_path))
    monkeypatch.setenv("TEMP", str(tmp_path))
    monkeypatch.setenv("TMPDIR", str(tmp_path))
    monkeypatch.setenv("PYTHONDONTWRITEBYTECODE", "1")
    import app.safety.paths as paths
    import app.scanning.scanner as scanner
    original = paths.absolute

    def confined(path):
        result = original(path)
        if not result.is_relative_to(tmp_path):
            raise AssertionError(f"Application I/O outside synthetic sandbox: {result}")
        return result

    monkeypatch.setattr(paths, "absolute", confined)
    monkeypatch.setattr(scanner, "absolute", confined)
    import app.scanning.decoder as decoder
    popen = decoder.subprocess.Popen

    def confined_popen(args, *a, **kw):
        if "--worker" in args or "--index-worker" in args:
            flag = '--worker' if '--worker' in args else '--index-worker'
            assert Path(args[args.index(flag) + 1]).is_relative_to(tmp_path)
        return popen(args, *a, **kw)

    monkeypatch.setattr(decoder.subprocess, "Popen", confined_popen)
    # QFileDialog otherwise keeps framework history in the Windows registry (or
    # the user's QtProject settings). Redirect both scopes to this synthetic home.
    qt_core = sys.modules.get('PySide6.QtCore')
    previous_qt = None
    if qt_core is not None:
        settings = qt_core.QSettings
        previous_qt = settings.defaultFormat()
        scopes = (settings.UserScope, settings.SystemScope)
        previous_paths = {scope: Path(settings(settings.IniFormat, scope, 'PhotoAgent', 'path-probe').fileName()).parent.parent
                          for scope in scopes}
        settings.setDefaultFormat(settings.IniFormat)
        for scope in scopes:
            settings.setPath(settings.IniFormat, scope, str(tmp_path / 'qt-settings'))
    try:
        yield
    finally:
        if previous_qt is not None:
            if qt_core.QCoreApplication.instance():
                qt_core.QCoreApplication.sendPostedEvents(None, qt_core.QEvent.DeferredDelete)
            for scope, previous_path in previous_paths.items():
                settings.setPath(settings.IniFormat, scope, str(previous_path))
            settings.setDefaultFormat(previous_qt)


@pytest.fixture
def collection(tmp_path):
    root = tmp_path / "photos"
    root.mkdir()
    image = Image.new("RGB", (128, 96), "#b4c8e0")
    draw = ImageDraw.Draw(image)
    draw.rectangle((7, 9, 72, 65), fill="red")
    draw.ellipse((62, 37, 119, 92), fill="green")
    image.save(root / "a.png")
    image.close()
    shutil.copy2(root / "a.png", root / "b.png")
    return root


@pytest.fixture
def scanned(collection):
    from app.scanning.scanner import scan
    from queue import Queue
    from threading import Event
    result = scan([str(collection)], Queue(), Event())
    assert result.complete, "\n".join(result.errors)
    assert len(result.pairs) == 1
    return result


@pytest.fixture
def operations(tmp_path):
    from app.safety.journal import Journal
    from app.safety.operations import Operations
    journal = Journal(tmp_path / "state" / "operations")
    assert journal.writable, journal.error
    try:
        yield Operations(journal)
    finally:
        journal.close()
