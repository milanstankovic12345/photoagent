"""Real Qt event loops and synthetic photographs only. Set QT_QPA_PLATFORM=offscreen for CI."""
from dataclasses import replace
from pathlib import Path
import threading
import time

import pytest

pytest.importorskip('PySide6')
from PySide6.QtCore import QTimer, Qt
from PySide6.QtGui import QColor
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from app.core.models import Approval, Cancelled, Kind, Plan, SafetyError
from app.core.queries import MatchQuery
from app.services.application import Application
from app.services.preview import PreviewService
from app.ui.qt.components import PlanDialog
from app.ui.qt.themes import ThemeManager, TOKENS
from app.ui.qt.window import MainWindow


def pump(predicate, timeout=30):
    deadline = time.monotonic() + timeout
    while not predicate():
        if time.monotonic() > deadline:
            raise AssertionError('Qt worker timeout')
        QTest.qWait(5)
    QApplication.processEvents()


@pytest.fixture(scope='module')
def qtapp():
    application = QApplication.instance() or QApplication([])
    application.setStyle('Fusion')
    application.setQuitOnLastWindowClosed(False)
    yield application


@pytest.fixture
def desktop(qtapp, tmp_path, monkeypatch):
    errors = []
    monkeypatch.setattr(MainWindow, 'error', lambda self, action, detail: errors.append((action, detail)))
    window = MainWindow(tmp_path / 'home')
    window.show()
    try:
        pump(lambda: window.settings and not window.controller.busy)
        yield window, errors
    finally:
        window.close()
        pump(lambda: window.finished)
        window.deleteLater()
        QApplication.processEvents()


def scan(window, collection):
    window.roots = [str(collection)]
    window.render_roots()
    window.start_scan()
    pump(lambda: window.session and not window.controller.busy)


def test_six_screens_scan_compare_query_and_theme_restart(desktop, collection):
    window, errors = desktop
    assert window.stack.count() == 6
    for i in range(6):
        window.navigation.setCurrentRow(i)
        QApplication.processEvents()
        assert window.stack.currentIndex() == i
    scan(window, collection)
    assert not errors
    assert window.duplicates.model.rowCount() == 1
    window.navigation.setCurrentRow(2)
    screenshot = window.home / 'qt-duplicates.png'
    assert window.grab().save(str(screenshot))
    print(f'Qt synthetic screenshot: {screenshot}')
    assert list((window.home / 'PhotoAgentReports').glob('*.csv'))
    window.duplicates.table.selectRow(0)
    pump(lambda: len(window.comparison.left.scene.items()) > 0)
    assert not errors
    window.comparison.left.zoom(1.25)
    window.comparison.left.fit()
    window.duplicates.kind.setCurrentIndex(3)
    pump(lambda: window.query.kind == 'DERIVATIVE' and not window.controller.busy)
    assert not window.duplicates.model.rows
    window.preferences.theme.setCurrentIndex(1)
    pump(lambda: not window.controller.busy)
    assert window.settings['theme'] == 'light' and window.theme.active == 'light'
    window.close()
    pump(lambda: window.finished)
    other = MainWindow(window.home)
    other.show()
    try:
        pump(lambda: bool(other.settings) and not other.controller.busy)
        assert other.theme.active == 'light' and other.session == window.session
    finally:
        other.close()
        pump(lambda: other.finished)


def test_thread_ownership_heartbeat_cancel_and_close(desktop, collection, monkeypatch):
    window, errors = desktop
    import app.scanning.inspection as inspection
    import app.services.indexing as indexing
    original = indexing.extract
    main = threading.get_ident()
    owners = []

    def slow(*args):
        owners.append(threading.get_ident())
        cancel = args[-1]
        for _ in range(100):
            if cancel.wait(.01):
                raise Cancelled()
        return original(*args)

    monkeypatch.setattr(indexing, 'extract', slow)
    beats = []
    timer = QTimer()
    timer.setInterval(20)
    timer.timeout.connect(lambda: beats.append(time.monotonic()))
    timer.start()
    try:
        window.roots = [str(collection)]
        window.start_scan()
        pump(lambda: owners)
        QTest.qWait(350)
        window.cancel()
        pump(lambda: window.session and not window.controller.busy)
        assert window.status == 'cancelled'
        assert not errors and all(owner != main for owner in owners)
        assert len(beats) >= 8
        assert max(b - a for a, b in zip(beats, beats[1:])) < .250
        window.start_scan()
        pump(lambda: len(owners) >= 2)
        window.close()
        pump(lambda: window.finished)
        assert not any(thread.isRunning() for thread in window.controller.threads)
    finally:
        timer.stop()


def test_plan_rejection_close_and_explicit_execution(desktop, collection):
    window, errors = desktop
    scan(window, collection)
    window.duplicates.table.selectRow(0)
    window.prepare_selected()
    pump(lambda: window.plan_dialog is not None)
    assert window.plan_dialog.approval is None
    window.plan_dialog.reject()
    assert (collection / 'b.png').exists()
    assert not list(collection.rglob('_photoagent_quarantine'))
    window.prepare_selected()
    pump(lambda: window.plan_dialog is not None)
    window.plan_dialog.approve()
    pump(lambda: not window.controller.busy)
    assert not errors and not (collection / 'b.png').exists()
    assert window.history_rows and window.history_rows[0].restorable
    window.history.table.selectRow(0)
    window.restore()
    pump(lambda: window.plan_dialog is not None)
    window.close()
    pump(lambda: window.finished)
    assert not (collection / 'b.png').exists()


def test_stale_preview_request_is_discarded(desktop, scanned, monkeypatch):
    window, errors = desktop
    from app.core.queries import MatchRow
    from PySide6.QtGui import QImage
    started = threading.Event()

    def slow(self, photo, cancel, size=2048):
        started.set()
        cancel.wait(.4)
        return QImage(8, 8, QImage.Format_RGB32)

    monkeypatch.setattr(PreviewService, 'get', slow)
    received = []
    window.controller.preview_ready.connect(received.append)
    window.controller.preview(MatchRow(1, 1, scanned.pairs[0]))
    pump(started.is_set)
    window.controller.preview(None)
    QTest.qWait(500)
    assert not received


def test_preview_source_changes_orientation_cache_and_corrupt_raw(qtapp, collection, scanned, tmp_path, monkeypatch):
    from PIL import Image
    from queue import Queue
    from threading import Event
    from app.scanning.scanner import scan as reference_scan
    from app.scanning.decoder import decode
    service = PreviewService(limit=128 * 96 * 4)
    photo = scanned.pairs[0].keep
    image = service.get(photo, Event())
    assert (image.width(), image.height()) == (128, 96)
    service.get(scanned.pairs[0].dup, Event())
    assert service.bytes <= service.limit and len(service.cache) <= 1
    import app.services.preview as preview
    # A cancellation during cache-hit validation must not corrupt byte accounting.
    with monkeypatch.context() as interrupted:
        fresh_snapshot = preview.snapshot
        calls = 0

        def cancelled_snapshot(path, cancel):
            nonlocal calls
            calls += 1
            if calls == 2:
                raise Cancelled()
            return fresh_snapshot(path, cancel)

        interrupted.setattr(preview, 'snapshot', cancelled_snapshot)
        with pytest.raises(Cancelled):
            service.get(scanned.pairs[0].dup, Event())
        assert service.bytes == sum(im.sizeInBytes() for im in service.cache.values())
    original = preview.decode

    def changed(*args, **kwargs):
        result = original(*args, **kwargs)
        Path(args[0]).write_bytes(b'changed')
        return result

    service.cache.clear()
    service.bytes = 0
    monkeypatch.setattr(preview, 'decode', changed)
    with pytest.raises(SafetyError, match='candidate_changed_review_again'):
        service.get(photo, Event())
    monkeypatch.setattr(preview, 'decode', original)
    oriented = tmp_path / 'orientation'
    oriented.mkdir()
    with Image.new('RGB', (2400, 1200), 'red') as im:
        exif = Image.Exif()
        exif[0x0112] = 6
        im.save(oriented / 'a.jpg', exif=exif)
    result = decode(oriented / 'a.jpg', preview_size=2048)
    assert (result['width'], result['height']) == (1200, 2400)
    import base64
    from PySide6.QtGui import QImage
    rendered = QImage.fromData(base64.b64decode(result['preview']), 'PNG')
    assert (rendered.width(), rendered.height()) == (1024, 2048)
    small = decode(oriented / 'a.jpg')
    assert (small['phash'], small['dhash']) == (result['phash'], result['dhash'])
    raw = oriented / 'bad.nef'
    raw.write_bytes(b'not raw')
    with pytest.raises(SafetyError):
        decode(raw, preview_size=2048)


def test_themes_system_fallback_and_text_contrast(qtapp):
    theme = ThemeManager(qtapp)
    theme.apply('system', Qt.ColorScheme.Light)
    assert theme.active == 'light' and theme.preference == 'system'
    theme.system_changed(Qt.ColorScheme.Dark)
    assert theme.active == 'dark'
    theme.system_changed(Qt.ColorScheme.Unknown)
    assert theme.active == 'dark' and theme.preference == 'system'
    theme.apply('light')
    theme.system_changed(Qt.ColorScheme.Dark)
    assert theme.active == 'light'

    def luminance(hex_value):
        c = QColor(hex_value)
        values = [v / 12.92 if v <= .04045 else ((v + .055) / 1.055) ** 2.4
                  for v in (c.redF(), c.greenF(), c.blueF())]
        return sum(a * b for a, b in zip(values, (.2126, .7152, .0722)))

    for colors in TOKENS.values():
        for surface in ('surface', 'background', 'selection'):
            a, b = sorted((luminance(colors['text']), luminance(colors[surface])))
            assert (b + .05) / (a + .05) >= 4.5


def test_raw_legacy_confirmation_requires_both(qtapp, scanned):
    from app.safety.operations import make_plan
    plan = make_plan(list(scanned.pairs))
    plan = replace(plan, moves=(replace(plan.moves[0], raw=True, legacy=True),))
    dialog = PlanDialog(plan)
    try:
        assert not dialog.confirm.isEnabled() and dialog.approval is None
        dialog.raw.setText('RAW')
        assert not dialog.confirm.isEnabled()
        dialog.legacy.setChecked(True)
        assert dialog.confirm.isEnabled()
        dialog.approve()
        assert dialog.approval == Approval(plan, raw=True, legacy=True)
    finally:
        dialog.close()


def test_preparation_cancel_and_keeper_change_invalidate_plan(desktop, collection, monkeypatch):
    window, errors = desktop
    scan(window, collection)
    window.duplicates.table.selectRow(0)
    original = Application.prepare
    entered = threading.Event()
    release = threading.Event()

    def delayed(self, pairs, cancel, **kwargs):
        entered.set()
        while not release.wait(.01):
            if cancel.is_set():
                raise Cancelled()
        return original(self, pairs, cancel, **kwargs)

    monkeypatch.setattr(Application, 'prepare', delayed)
    window.prepare_selected()
    pump(entered.is_set)
    window.comparison.keep.setCurrentIndex(1)
    release.set()
    pump(lambda: not window.controller.busy)
    assert window.plan_dialog is None and (collection / 'b.png').exists()
    release.clear()
    entered.clear()
    window.prepare_selected()
    pump(entered.is_set)
    window.cancel()
    pump(lambda: not window.controller.busy)
    assert window.plan_dialog is None and all(p.exists() for p in (collection / 'a.png', collection / 'b.png'))
    assert not errors and not window.pending_prepare


def test_mid_decode_cancellation(qtapp, collection):
    from app.scanning.decoder import decode
    cancel = threading.Event()
    timer = threading.Timer(.05, cancel.set)
    timer.start()
    try:
        with pytest.raises(Cancelled):
            decode(collection / 'a.png', cancel, preview_size=2048)
    finally:
        timer.join()


def test_preflight_checks_only_selected_toolkit(monkeypatch):
    import app.services.preflight as preflight
    original = preflight.importlib.import_module

    def no_tk(name):
        if name == 'tkinter':
            raise AssertionError('Qt mode must not import Tkinter')
        return original(name)

    monkeypatch.setattr(preflight.importlib, 'import_module', no_tk)
    preflight.check()
    preflight.check('qt')

    def no_qt(name):
        if name.startswith('PySide6'):
            raise AssertionError('Tk mode must not import Qt')
        return original(name)

    monkeypatch.setattr(preflight.importlib, 'import_module', no_qt)
    preflight.check('tk')
