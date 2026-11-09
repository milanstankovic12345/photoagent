"""Real Qt event loops and synthetic photographs only. Set QT_QPA_PLATFORM=offscreen for CI."""
from dataclasses import replace
from pathlib import Path
import os
import platform
import threading
import time

import pytest

pytest.importorskip('PySide6')
from PySide6.QtCore import QModelIndex, QTimer, Qt
from PySide6.QtGui import QColor, QFont, QFontDatabase
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from app.core.models import Approval, Cancelled, Kind, Plan, SafetyError
from app.core.queries import MatchQuery
from app.services.application import Application
from app.services.preview import PreviewService
from app.ui.qt.components import PlanDialog
from app.ui.qt.navigation import Route
from app.ui.qt.strings import tr
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
    # Windows offscreen may expose no installed fonts until registered. Match
    # capture tools so rendered geometry and Serbian glyph checks use real fonts.
    if platform.system() == 'Windows' and application.platformName() == 'offscreen':
        for name in ('segoeui.ttf', 'segoeuib.ttf'):
            assert QFontDatabase.addApplicationFont(str(Path(os.environ['WINDIR']) / 'Fonts' / name)) >= 0
        application.setFont(QFont('Segoe UI', 10))
    yield application


@pytest.fixture
def desktop(qtapp, tmp_path, monkeypatch):
    errors = []
    original_error = MainWindow.error

    def record_error(self, action, detail):
        errors.append((action, detail))
        if action in ('scan', 'sources'):
            original_error(self, action, detail)

    monkeypatch.setattr(MainWindow, 'error', record_error)
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
    pump(lambda: window.session and not window.controller.busy, timeout=90)


def assert_toolbar_available(window, toolbar):
    QApplication.processEvents()
    assert toolbar.isVisible()
    controls = [toolbar.actions.itemAt(i).widget() for i in range(toolbar.actions.count())]
    for control in controls:
        position = control.mapTo(window, control.rect().topLeft())
        assert window.rect().contains(position)
        assert window.rect().contains(position + control.rect().bottomRight())
        assert control.isVisible()
    assert sum(control.property('variant') in ('primary', 'danger') for control in controls) <= 1
    for i, control in enumerate(controls):
        assert all(not control.geometry().intersects(other.geometry()) for other in controls[i + 1:])


def test_five_destinations_scan_compare_query_and_theme_restart(desktop, collection):
    window, errors = desktop
    assert window.stack.count() == 5
    assert tuple(window.navigation.buttons) == tuple(Route)
    for route in Route:
        window.navigate(route)
        QApplication.processEvents()
        assert window.stack.currentWidget() is window.pages[route]
        assert window.header.title.text() == tr('dashboard_title' if route == Route.DASHBOARD else 'scan_photos' if route == Route.SCAN else 'duplicate_photos' if route == Route.DUPLICATES else route.value)
    scan(window, collection)
    assert not errors
    assert window.duplicates.model.rowCount() == 1
    window.navigate(Route.DUPLICATES)
    screenshot = window.home / 'qt-duplicates.png'
    assert window.grab().save(str(screenshot))
    print(f'Qt synthetic screenshot: {screenshot}')
    assert list((window.home / 'PhotoAgentReports').glob('*.csv'))
    window.duplicates.table.selectRow(0)
    window.compare()
    assert window.route == Route.DUPLICATES and window.duplicates_flow.comparing
    pump(lambda: len(window.comparison.left.scene.items()) > 0)
    assert not errors
    window.comparison.left.zoom(1.25)
    window.comparison.left.fit()
    window.back_to_duplicates()
    assert not window.duplicates_flow.comparing
    assert [window.duplicates.kind.itemData(i) for i in range(window.duplicates.kind.count())] == ['', 'EXACT', 'VISUAL']
    window.duplicates.kind.setCurrentIndex(2)
    pump(lambda: window.query.kind == 'VISUAL' and not window.controller.busy)
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


def test_compare_back_preserves_group_query_pages_selection_without_requests(desktop, collection):
    import shutil
    from PIL import Image

    window, errors = desktop
    shutil.copy2(collection / 'a.png', collection / 'c.png')
    with Image.new('RGB', (80, 60), '#7a3020') as image:
        image.save(collection / 'd.png')
    for name in ('e.png', 'f.png'):
        shutil.copy2(collection / 'd.png', collection / name)
    scan(window, collection)
    window.navigate(Route.DUPLICATES)
    window.duplicates.search.setText('.png')
    window.duplicates.kind.setCurrentIndex(window.duplicates.kind.findData('EXACT'))
    pump(lambda: window.query.text == '.png' and window.query.kind == 'EXACT' and not window.controller.busy)
    window.query = replace(window.query, limit=1)
    window.request_groups()
    pump(lambda: not window.controller.busy)
    assert window.group_total == 2
    window.groups_page(1)
    pump(lambda: not window.controller.busy)
    assert window.group_offset == 1
    window.duplicates.groups.setCurrentRow(1)
    pump(lambda: not window.controller.busy)
    window.sort(3)
    pump(lambda: not window.controller.busy)
    window.sort(3)
    pump(lambda: not window.controller.busy)
    window.change_page(1)
    pump(lambda: not window.controller.busy)
    assert window.query.offset == 1 and window.query.descending and window.query.keeper_id
    window.duplicates.table.selectRow(0)
    pump(lambda: window.comparison.left.state == 'preview_ready')
    state = (window.query, window.group_offset, window.selected_id, window.duplicates.groups.currentRow(),
             window.duplicates.table.currentIndex(), window.duplicates_flow.listing.verticalScrollBar().value())
    requests, previews = [], []
    window.controller.dispatch.connect(lambda *args: requests.append(args))
    window.controller.preview_dispatch.connect(lambda *args: previews.append(args))
    window.activateWindow()
    window.duplicates.table.setFocus()
    QTest.keyClick(window.duplicates.table, Qt.Key_Return)
    assert window.duplicates_flow.comparing and window.comparison.back.hasFocus()
    assert window.header.title.text() == tr('compare')
    for width, height in ((1280, 720), (853, 480)):
        window.resize(width, height)
        assert_toolbar_available(window, window.comparison.toolbar)
    window.navigate(Route.SETTINGS)
    window.navigate(Route.DUPLICATES)
    assert window.duplicates_flow.comparing
    QTest.keyClick(window, Qt.Key_Left, Qt.AltModifier)
    assert not window.duplicates_flow.comparing and window.duplicates.table.hasFocus()
    assert state == (window.query, window.group_offset, window.selected_id, window.duplicates.groups.currentRow(),
                     window.duplicates.table.currentIndex(), window.duplicates_flow.listing.verticalScrollBar().value())
    assert window.duplicates.search.text() == '.png'
    assert window.duplicates.kind.currentData() == 'EXACT'
    assert not requests and not previews and not errors


@pytest.mark.parametrize('viewport', [(1280, 720), (853, 480)])
def test_sidebar_keyboard_and_context_actions_at_small_viewport(desktop, viewport):
    window, _ = desktop
    window.resize(*viewport)  # 853x480 is the logical space of 1280x720 at 150%.
    window.activateWindow()
    QApplication.processEvents()
    assert 190 <= window.navigation.width() <= 220
    buttons = window.navigation.buttons
    assert len({control.icon().cacheKey() for control in buttons.values()}) == 5
    dashboard, scanning = buttons[Route.DASHBOARD], buttons[Route.SCAN]
    dashboard.setFocus()
    QTest.qWait(10)
    assert dashboard.hasFocus(), QApplication.focusWidget()
    QTest.keyClick(dashboard, Qt.Key_Tab)
    assert scanning.hasFocus(), QApplication.focusWidget()
    QTest.keyClick(scanning, Qt.Key_Tab, Qt.ShiftModifier)
    assert dashboard.hasFocus()
    QTest.keyClick(dashboard, Qt.Key_Tab)
    QTest.keyClick(scanning, Qt.Key_Return)
    assert window.route == Route.SCAN
    assert buttons[Route.SCAN].isChecked()
    buttons[Route.SETTINGS].setFocus()
    QTest.keyClick(buttons[Route.SETTINGS], Qt.Key_Tab)
    first_action = next(window.scan.toolbar.actions.itemAt(i).widget()
                        for i in range(window.scan.toolbar.actions.count())
                        if window.scan.toolbar.actions.itemAt(i).widget().isEnabled())
    assert first_action.hasFocus()
    QTest.keyClick(first_action, Qt.Key_Tab, Qt.ShiftModifier)
    assert buttons[Route.SETTINGS].hasFocus()
    for route in Route:
        window.navigate(route)
        QApplication.processEvents()
        assert_toolbar_available(window, window.screens[route].toolbar)
    assert buttons[Route.SETTINGS].geometry().top() > buttons[Route.QUARANTINE].geometry().bottom()


def test_navigation_rejects_pending_plan_and_dialog_returns_focus(desktop, collection, monkeypatch):
    window, errors = desktop
    scan(window, collection)
    window.navigate(Route.DUPLICATES)
    window.duplicates.table.selectRow(0)
    window.compare()
    window.choose_keeper(False)
    window.activateWindow()
    window.comparison.prepare.setFocus()
    QTest.qWait(10)
    assert window.comparison.prepare.hasFocus()
    window.prepare_selected()
    pump(lambda: window.plan_dialog is not None)
    dialog = window.plan_dialog
    assert dialog.approval is None
    dialog.reject()
    pump(lambda: window.comparison.prepare.hasFocus())
    window.prepare_selected()
    pump(lambda: window.plan_dialog is not None)
    dialog = window.plan_dialog
    preview_id = window.controller.preview_id
    window.duplicates.table.setCurrentIndex(QModelIndex())
    assert window.plan_dialog is None and dialog.approval is None
    assert window.selected_id is None and window.controller.selection is None
    assert window.controller.preview_id > preview_id
    assert not window.comparison.prepare.isEnabled()
    window.duplicates.table.selectRow(0)
    window.choose_keeper(False)
    window.prepare_selected()
    pump(lambda: window.plan_dialog is not None)
    dialog = window.plan_dialog
    window.navigate(Route.SETTINGS)
    assert window.plan_dialog is None and dialog.approval is None
    assert (collection / 'b.png').exists()
    original = Application.prepare
    entered, release = threading.Event(), threading.Event()

    def delayed(self, pairs, cancel, **kwargs):
        entered.set()
        while not release.wait(.01):
            if cancel.is_set():
                raise Cancelled()
        return original(self, pairs, cancel, **kwargs)

    monkeypatch.setattr(Application, 'prepare', delayed)
    window.navigate(Route.DUPLICATES)
    window.prepare_selected()
    pump(entered.is_set)
    window.back_to_duplicates()
    release.set()
    pump(lambda: not window.controller.busy)
    assert window.plan_dialog is None and not window.pending_prepare
    assert (collection / 'a.png').exists() and (collection / 'b.png').exists()
    assert not list(collection.rglob('_photoagent_quarantine')) and not errors


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
        assert window.scan.progress.minimum() == window.scan.progress.maximum() == 0
        assert window.scan.cancel.isEnabled() and not window.scan.add.isEnabled()
        QTest.qWait(350)
        window.cancel()
        pump(lambda: window.session and not window.controller.busy)
        assert window.status == 'cancelled'
        assert tr('state_cancelled') in window.scan.status.text()
        assert not window.scan.timer.isActive() and window.scan.progress.maximum() == 1
        assert not window.duplicates.bulk.isEnabled()
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
    window.comparison.left.keep_photo.click()
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
    window.comparison.left.keep_photo.click()
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
    window.choose_keeper(True)
    release.set()
    pump(lambda: not window.controller.busy)
    assert window.plan_dialog is None and (collection / 'b.png').exists()
    window.keep_both()
    window.comparison.left.keep_photo.click()  # Unselect, then explicitly retain left.
    window.comparison.left.keep_photo.click()
    window.comparison.right.keep_photo.click()  # Release the other retained copy.
    release.clear()
    entered.clear()
    window.prepare_selected()
    pump(entered.is_set)
    window.cancel()
    pump(lambda: not window.controller.busy)
    assert window.plan_dialog is None and all(p.exists() for p in (collection / 'a.png', collection / 'b.png'))
    assert not errors and not window.pending_prepare
    assert window.controller.selection is None and window.selected_id is None
    assert not window.duplicates.table.currentIndex().isValid()
    window.duplicates.table.selectRow(0)
    assert window.controller.selection is not None and window.selected_id is not None


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


def test_dashboard_to_scan_to_review_with_actual_thumbnails(desktop, collection, monkeypatch):
    from PySide6.QtWidgets import QFileDialog
    window, errors = desktop
    assert window.dashboard.empty.isVisible() and not window.dashboard.recent.isVisible()
    assert window.dashboard.scan.text() == tr('first_scan')
    assert not window.dashboard.review.isEnabled() and not window.scan.start.isEnabled()
    window.dashboard.scan.click()
    assert window.route == Route.SCAN
    assert not window.scan.advanced.toggle.isChecked() and not window.scan.error_section.toggle.isChecked()
    monkeypatch.setattr(QFileDialog, 'getExistingDirectory', lambda *args, **kwargs: str(collection))
    window.scan.add.click()
    pump(lambda: not window.controller.busy)
    assert window.roots == [str(collection)] and window.scan.start.isEnabled()
    assert tr('available') in window.scan.source_labels[str(collection)].text()
    window.resize(853, 480)
    window.scan.start.click()
    QApplication.processEvents()
    viewport = window.pages[Route.SCAN].viewport()
    for control in (window.scan.status, window.scan.elapsed):
        assert viewport.rect().contains(control.mapTo(viewport, control.rect().topLeft()))
        assert viewport.rect().contains(control.mapTo(viewport, control.rect().bottomRight()))
    pump(lambda: window.session and not window.controller.busy, timeout=90)
    assert window.status == 'complete' and not errors
    assert window.scan.status.text() == tr('scan_result_summary', tr('state_complete'), 2, 1, 0, 0)
    assert window.scan.report.text() and window.scan.review.isEnabled()
    assert window.scan.layout().itemAt(0).widget() is window.scan.progress_card
    assert not window.scan.timer.isActive()
    window.scan.review.click()
    assert window.route == Route.DUPLICATES and window.duplicates.model.rowCount() == 1
    window.navigate(Route.DASHBOARD)
    assert not window.dashboard.empty.isVisible() and window.dashboard.recent.isVisible()
    assert [card.value.text() for card in window.dashboard.stat_cards[:3]] == ['2', '1', '0']
    card = window.dashboard.cards[0]
    window.pages[Route.DASHBOARD].ensureWidgetVisible(card)
    pump(lambda: card.loaded, timeout=30)
    assert not card.image.pixmap().isNull()
    from app.core.queries import PageResult
    thumbnail_generation = window.controller.thumbnail_id
    # A late refresh of the hidden gallery must not cancel the visible page's work.
    window.result('groups', PageResult(window.group_rows, window.group_total))
    assert window.controller.thumbnail_id == thumbnail_generation
    card.findChildren(type(window.scan.start))[0].click()
    pump(lambda: not window.controller.busy)
    assert window.route == Route.DUPLICATES and window.query.keeper_id == card.row.keeper_id
    assert window.selected_id == card.row.id and window.controller.selection is not None
    assert all((collection / name).exists() for name in ('a.png', 'b.png'))


def test_report_failure_does_not_change_scan_result_and_no_matches_is_distinct(desktop, collection, monkeypatch):
    window, errors = desktop
    original = Application.scan_with_report

    def failed_report(*args):
        raise OSError('synthetic report failure')

    def with_failed_report(self, folders, updates, cancel, **kwargs):
        return original(self, folders, updates, cancel, report_writer=failed_report, **kwargs)

    monkeypatch.setattr(Application, 'scan_with_report', with_failed_report)
    (collection / 'b.png').unlink()
    scan(window, collection)
    assert not errors and window.status == 'complete'
    assert window.scan.report.text().endswith(tr('report_error'))
    assert 'synthetic report failure' in window.scan.errors.toPlainText()
    assert window.dashboard.no_matches.isVisible() and not window.dashboard.empty.isVisible()
    assert not window.dashboard.cards and not window.scan.review.isEnabled()
    assert not window.scan.error_section.toggle.isChecked()
    window.refresh()
    pump(lambda: not window.controller.busy)
    assert window.status == 'complete' and window.scan.report.text().endswith(tr('report_error'))
    assert 'synthetic report failure' in window.scan.errors.toPlainText()


def test_failed_scan_keeps_details_disables_moves_and_can_retry(desktop, collection, monkeypatch):
    import app.services.indexing as indexing
    window, errors = desktop
    original = indexing.match_index

    def failed_match(*args):
        raise SafetyError('synthetic matching failure')

    monkeypatch.setattr(indexing, 'match_index', failed_match)
    scan(window, collection)
    assert errors and window.status == 'failed'
    assert tr('state_failed') in window.scan.status.text()
    assert 'synthetic matching failure' in window.scan.errors.toPlainText()
    assert window.scan.error_summary.text() == tr('scan_failure_help')
    assert not window.scan.error_section.toggle.isChecked()
    assert not window.scan.timer.isActive() and window.scan.progress.maximum() == 1
    assert not window.scan.review.isEnabled() and not window.duplicates.bulk.isEnabled()
    assert not window.dashboard.empty.isVisible() and not window.dashboard.no_matches.isVisible()
    monkeypatch.setattr(indexing, 'match_index', original)
    previous = window.session
    window.start_scan()
    pump(lambda: window.session != previous and not window.controller.busy, timeout=90)
    assert window.status == 'complete' and not window.scan.failure_detail
    assert not window.scan.errors.toPlainText()
    assert (collection / 'a.png').read_bytes() == (collection / 'b.png').read_bytes()


def test_dashboard_thumbnail_visibility_bound_and_stale_response(desktop, collection, monkeypatch):
    import shutil
    from PySide6.QtGui import QImage
    window, errors = desktop
    for i in range(4):
        shutil.copy2(collection / 'a.png', collection / f'copy-{i}.png')
    window.resize(853, 480)
    calls, requests, accepted = [], [], []
    entered = threading.Event()
    release = threading.Event()

    def delayed(self, photo, cancel, size=2048):
        calls.append((photo.path, size, threading.get_ident()))
        entered.set()
        while not release.wait(.01) and not cancel.is_set():
            pass
        return QImage(16, 12, QImage.Format_RGB32)

    monkeypatch.setattr(PreviewService, 'get', delayed)
    window.controller.thumbnail_dispatch.connect(lambda request, photos, cancel: requests.append((request, photos, cancel)))
    window.controller.thumbnails_ready.connect(accepted.append)
    window.navigate(Route.SCAN)
    scan(window, collection)
    assert len(window.dashboard.cards) == 3 and not calls
    window.navigate(Route.DASHBOARD)
    window.pages[Route.DASHBOARD].ensureWidgetVisible(window.dashboard.cards[-1])
    pump(entered.is_set)
    assert requests and 1 <= len(requests[-1][1]) <= 3
    viewport = window.pages[Route.DASHBOARD].viewport()
    for photo in requests[-1][1]:
        card = next(card for card in window.dashboard.cards if card.row.match.dup == photo)
        assert viewport.rect().intersects(card.rect().translated(card.mapTo(viewport, card.rect().topLeft())))
    request = requests[-1][0]
    pending_cancel = requests[-1][2]
    window.navigate(Route.SCAN)
    release.set()
    assert pending_cancel.is_set()
    QTest.qWait(150)
    window.controller._thumbnails(request, ((requests[-1][1][0], QImage(), ''),))
    assert not accepted and not any(card.loaded for card in window.dashboard.cards)
    assert all(size == 320 and owner != threading.get_ident() for _, size, owner in calls)
    assert not errors


def test_scan_failure_before_new_session_preserves_failed_attempt(desktop, collection, monkeypatch):
    window, errors = desktop
    scan(window, collection)
    previous = window.session

    def fail_before_session(*args, **kwargs):
        raise SafetyError('synthetic pre-session failure')

    monkeypatch.setattr(Application, 'scan', fail_before_session)
    window.start_scan()
    pump(lambda: bool(errors) and not window.controller.busy)
    assert window.session == previous and window.status == 'failed'
    assert window.scan.status.text() == tr('scan_failed')
    assert 'synthetic pre-session failure' in window.scan.errors.toPlainText()
    assert not window.scan.timer.isActive() and not window.duplicates.bulk.isEnabled()
    window.refresh()
    pump(lambda: not window.controller.busy)
    assert window.status == 'failed' and window.scan.status.text() == tr('scan_failed')


def test_source_availability_order_removal_and_collapsed_priority(desktop, tmp_path):
    window, errors = desktop
    first, second, offline = (tmp_path / name for name in ('one', 'two', 'offline'))
    first.mkdir()
    second.mkdir()
    window.roots = [str(first), str(second), str(offline)]
    window.render_roots()
    window.controller.request('settings', {'roots': window.roots.copy()})
    pump(lambda: not window.controller.busy)
    assert window.scan.start.isEnabled() and not window.scan.advanced.toggle.isChecked()
    assert list(window.scan.source_labels) == window.roots
    assert tr('unavailable') in window.scan.source_labels[str(offline)].text()
    window.scan.roots.setCurrentRow(1)
    window.reorder_root(-1)
    pump(lambda: not window.controller.busy)
    assert window.roots == [str(second), str(first), str(offline)]
    window.scan.remove_buttons[0].click()
    pump(lambda: not window.controller.busy)
    assert window.roots == [str(first), str(offline)]
    window.scan.remove_buttons[0].click()
    pump(lambda: not window.controller.busy)
    assert window.roots == [str(offline)] and not window.scan.start.isEnabled()
    assert not errors
