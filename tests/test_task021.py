"""System opening: synthetic files, real Qt events, and mocked OS launches only."""
from dataclasses import replace
from pathlib import Path
from threading import Event, get_ident

import pytest

pytest.importorskip('PySide6')
from PySide6.QtCore import QTimer, Qt
from PySide6.QtGui import QContextMenuEvent, QDesktopServices
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QGraphicsView, QMenu, QMessageBox

from app.core.models import Approval, Cancelled, Photo, SafetyError
from app.core.queries import GroupRow
from app.i18n import STRINGS
from app.safety.paths import identity, snapshot
from app.services.application import Application
from app.services.open_photo import resolve_photo
from app.ui.qt.desktop_viewer import DesktopViewer
from app.ui.qt.components import PhotoLabel, PhotoView
from app.ui.qt.gallery import GroupDelegate, GroupView
from app.ui.qt.localization import language_manager
from app.ui.qt.navigation import Route
from app.ui.qt.strings import tr
from app.ui.qt.window import MainWindow
from tests.test_qt import desktop, pump, qtapp, scan
from tests.test_task020 import open_review


_adapter_open = DesktopViewer.open_photo
_window_error = MainWindow.error


@pytest.fixture(autouse=True)
def launches(monkeypatch):
    calls = []
    monkeypatch.setattr(DesktopViewer, 'open_photo', lambda self, path: calls.append(path) or True)
    # Defense in depth: no test in this module may start a real application.
    monkeypatch.setattr(QDesktopServices, 'openUrl', lambda url: pytest.fail('unmocked OS launch'))
    return calls


@pytest.fixture
def literal_photo(tmp_path):
    root = tmp_path / 'synthetic čć ž photographs'
    root.mkdir()
    path = root / 'photo #1 %20 & $ (copy).nef'
    path.write_bytes(b'synthetic RAW bytes; no decoding required')
    return Photo(str(path), str(root), snapshot(path), identity(root), is_raw=True, ext='.nef')


def double_click(widget, pos=None):
    if pos is None:
        pos = widget.rect().center()
    QTest.mouseDClick(widget, Qt.LeftButton, pos=pos)
    QTest.mouseRelease(widget, Qt.LeftButton, pos=pos)


def test_adapter_keeps_literal_local_path(literal_photo, monkeypatch):
    urls = []
    monkeypatch.setattr(QDesktopServices, 'openUrl', lambda url: urls.append(url) or True)
    assert _adapter_open(DesktopViewer(), literal_photo.path)
    assert len(urls) == 1 and urls[0].isLocalFile()
    assert Path(urls[0].toLocalFile()) == Path(literal_photo.path)
    assert not urls[0].hasQuery() and not urls[0].hasFragment()


def test_raw_resolution_does_not_decode_or_require_association(literal_photo, monkeypatch):
    monkeypatch.setattr('app.scanning.decoder.decode', lambda *a, **k: pytest.fail('unexpected decode'))
    assert resolve_photo(None, literal_photo, Event()) == literal_photo.path
    cancel = Event()
    cancel.set()
    with pytest.raises(Cancelled):
        resolve_photo(None, literal_photo, cancel)


def test_placeholders_do_not_open_but_raw_has_explicit_keyboard_action(qtapp, literal_photo):
    label = PhotoLabel('thumbnail_unavailable')
    view = PhotoView()
    targets = []
    label.open_requested.connect(targets.append)
    view.open_requested.connect(targets.append)
    try:
        label.target = literal_photo
        label.show()
        view.show()
        double_click(label)
        assert not targets
        view.set_photo(literal_photo)
        view.set_image(None, 'decoder_failed')
        double_click(view.placeholder)
        assert not targets and view.open_default.isEnabled()
        view.activateWindow()
        view.open_default.setFocus()
        QTest.keyClick(view.open_default, Qt.Key_Space)
        assert targets == [literal_photo]
        view.reset()
        assert not view.open_default.isEnabled()
    finally:
        label.close()
        view.close()
        label.deleteLater()
        view.deleteLater()


@pytest.mark.parametrize('defect', ['missing', 'offline', 'changed', 'replacement', 'outside', 'root_identity'])
def test_fresh_identity_content_and_containment(literal_photo, tmp_path, defect):
    photo = literal_photo
    path = Path(photo.path)
    if defect == 'missing':
        path.unlink()
    elif defect == 'offline':
        Path(photo.root).rename(tmp_path / 'synthetic-disconnected-drive')
    elif defect == 'changed':
        # Even unchanged length and mtime must not bypass full content hashing.
        import os
        info = path.stat()
        path.write_bytes(b'X' * photo.size)
        os.utime(path, ns=(info.st_atime_ns, info.st_mtime_ns))
    elif defect == 'replacement':
        path.rename(path.with_suffix('.old'))
        path.write_bytes(b'synthetic RAW bytes; no decoding required')
    elif defect == 'outside':
        photo = replace(photo, path=str(tmp_path / 'other.nef'))
        Path(photo.path).write_bytes(b'synthetic')
    else:
        photo = replace(photo, root_identity=replace(photo.root_identity, inode=photo.root_identity.inode + 1))
    with pytest.raises((OSError, SafetyError)):
        resolve_photo(None, photo, Event())


def test_redirected_path_is_rejected(literal_photo, tmp_path):
    link = Path(literal_photo.root) / 'link.nef'
    try:
        link.symlink_to(literal_photo.path)
    except OSError as exc:
        pytest.skip(f'Creating synthetic symlinks unavailable: {exc}')
    with pytest.raises(SafetyError, match='redirected_path'):
        resolve_photo(None, replace(literal_photo, path=str(link)), Event())


@pytest.mark.parametrize('keyboard', [False, True])
def test_gallery_context_menu_names_and_opens_its_concrete_sample(qtapp, literal_photo, keyboard):
    other = replace(literal_photo, path=str(Path(literal_photo.path).with_name('other.nef')))
    gallery = GroupView(lambda photos: None)
    targets = []
    gallery.open_requested.connect(targets.append)
    gallery.replace((GroupRow(1, 'EXACT', literal_photo.path, 2, (literal_photo, other)),
                     GroupRow(2, 'EXACT', other.path, 2, (other, literal_photo))))
    gallery.resize(700, 400)
    gallery.show()
    gallery.setCurrentRow(2 if keyboard else 1)
    QApplication.processEvents()
    point = gallery.visualRect(gallery.model().index(2)).center()
    menus = []

    def choose_action():
        menu = QApplication.activePopupWidget()
        if isinstance(menu, QMenu):
            menus.append(menu.actions()[0].text())
            menu.actions()[0].trigger()
            menu.close()

    # Keep a bad menu implementation from hanging the test's nested event loop.
    guard = QTimer(gallery)
    guard.setSingleShot(True)
    guard.timeout.connect(lambda: QApplication.activePopupWidget().close()
        if QApplication.activePopupWidget() else None)
    guard.start(1000)
    QTimer.singleShot(0, choose_action)
    event = QContextMenuEvent(QContextMenuEvent.Keyboard if keyboard else QContextMenuEvent.Mouse,
        point, gallery.viewport().mapToGlobal(point))
    try:
        QApplication.sendEvent(gallery.viewport(), event)
        assert menus == [tr('open_named_photo', other.path)]
        assert targets == [other] and gallery.currentRow() == 2
    finally:
        guard.stop()
        gallery.close()
        gallery.deleteLater()


def test_quarantine_rechecks_manifest_across_restart_and_restore(tmp_path, scanned):
    app = Application(tmp_path / 'home')
    app.initialize()
    try:
        plan = app.prepare(scanned.pairs, Event())
        app.execute(plan, Approval(plan), Event())
        move = plan.moves[0]
    finally:
        app.close()
    app = Application(tmp_path / 'home')
    app.initialize()
    try:
        assert app.resolve_photo(move.id, Event()) == move.destination
        with pytest.raises(FileNotFoundError):
            app.resolve_photo(scanned.pairs[0].dup, Event())
        Path(move.destination).write_bytes(b'changed quarantine contents')
        with pytest.raises(SafetyError, match='quarantine_content_changed'):
            app.resolve_photo(move.id, Event())
    finally:
        app.close()


def test_restored_operation_never_opens_stale_or_unrelated_path(tmp_path, scanned):
    app = Application(tmp_path / 'home')
    app.initialize()
    try:
        plan = app.prepare(scanned.pairs, Event())
        app.execute(plan, Approval(plan), Event())
        move = plan.moves[0]
        restored = app.restore_plan(Event(), operation_id=move.id)
        app.execute(restored, Approval(restored), Event())
        # A different file at the former quarantine location must never open.
        Path(move.destination).write_bytes(b'unrelated synthetic photograph')
        for operation_id in (move.id, restored.moves[0].id, 'unknown-id'):
            with pytest.raises(SafetyError, match='quarantine_preview_unavailable'):
                app.resolve_photo(operation_id, Event())
        assert Path(move.source).exists()
    finally:
        app.close()
    app = Application(tmp_path / 'home')
    app.initialize()
    try:
        with pytest.raises(SafetyError, match='quarantine_preview_unavailable'):
            app.resolve_photo(move.id, Event())
    finally:
        app.close()


@pytest.mark.parametrize('side', ['left', 'right'])
def test_comparison_single_double_and_keyboard_do_not_choose_keeper(desktop, collection, launches, side):
    window, errors = desktop
    scan(window, collection)
    open_review(window)
    view = getattr(window.comparison, side)
    photo = view.photo
    index = window.duplicates.table.currentIndex()
    QTest.mouseClick(view.view.viewport(), Qt.LeftButton, pos=view.view.viewport().rect().center())
    QApplication.processEvents()
    assert not launches and window.duplicates.table.currentIndex() == index
    double_click(view.view.viewport())
    pump(lambda: len(launches) == 1)
    assert launches == [photo.path] and view.enlarged is None
    assert not window.pending_pairs() and window.plan_dialog is None
    window.activateWindow()
    view.open_default.setFocus()
    QTest.keyClick(view.open_default, Qt.Key_Space)
    pump(lambda: len(launches) == 2)
    assert launches == [photo.path] * 2 and not errors


@pytest.mark.parametrize('grid', [True, False])
@pytest.mark.parametrize('slot', [0, 1])
def test_group_slots_open_their_file_and_preserve_group_selection(desktop, collection, launches, grid, slot):
    window, errors = desktop
    scan(window, collection)
    window.navigate(Route.DUPLICATES)
    gallery = window.duplicates.groups
    window.duplicates.mode.setCurrentIndex(0 if grid else 1)
    gallery.setCurrentRow(1)
    pump(lambda: not window.controller.busy and len(gallery.groups_model.images) == 2)
    index = gallery.model().index(1)
    photo = index.data(Qt.UserRole).samples[slot]
    rect = GroupDelegate.sample_rect(gallery.visualRect(index), grid, slot)
    QTest.mouseClick(gallery.viewport(), Qt.LeftButton, pos=rect.center())
    QApplication.processEvents()
    assert not launches and gallery.currentRow() == 1
    double_click(gallery.viewport(), rect.center())
    pump(lambda: len(launches) == 1)
    assert launches == [photo.path] and gallery.currentRow() == 1
    assert not window.duplicates_flow.comparing and not window.pending_pairs()
    assert gallery.open_actions[slot].text() == tr('open_named_photo', photo.path)
    window.activateWindow()
    gallery.setFocus()
    modifiers = Qt.AltModifier | (Qt.ShiftModifier if slot else Qt.NoModifier)
    QTest.keyClick(gallery, Qt.Key_O, modifiers)
    pump(lambda: len(launches) == 2)
    assert launches == [photo.path] * 2 and not errors


def test_dashboard_opens_duplicate_sample_without_review(desktop, collection, launches):
    window, errors = desktop
    scan(window, collection)
    window.navigate(Route.DASHBOARD)
    pump(lambda: bool(window.dashboard.cards))
    card = window.dashboard.cards[0]
    window.pages[Route.DASHBOARD].ensureWidgetVisible(card)
    pump(lambda: not card.image.pixmap().isNull())
    QTest.mouseClick(card.image, Qt.LeftButton)
    assert not launches
    double_click(card.image)
    pump(lambda: len(launches) == 1)
    assert launches == [card.row.match.dup.path]
    assert window.route == Route.DASHBOARD and not window.pending_pairs() and not errors


def test_enlarged_preview_uses_its_own_photo(desktop, collection, launches):
    window, errors = desktop
    scan(window, collection)
    open_review(window)
    photo = window.comparison.left.photo
    window.comparison.left.enlarge.click()
    dialog = window.comparison.left.enlarged
    view = dialog.findChild(QGraphicsView)
    QTest.qWait(30)
    double_click(view.viewport())
    pump(lambda: len(launches) == 1)
    assert launches == [photo.path] and not window.pending_pairs() and not errors
    dialog.close()


def test_delayed_request_stays_with_clicked_photo_on_selection_change(desktop, collection, launches, monkeypatch):
    window, errors = desktop
    scan(window, collection)
    open_review(window)
    original = Application.resolve_photo
    entered, release = Event(), Event()
    threads = []
    photo = window.comparison.left.photo

    def delayed(self, target, cancel):
        threads.append(get_ident())
        entered.set()
        assert release.wait(15)
        return original(self, target, cancel)

    monkeypatch.setattr(Application, 'resolve_photo', delayed)
    try:
        window.comparison.left.open_default.click()
        pump(entered.is_set)
        # Clear/reselect and navigate while validation is pending. Neither may
        # substitute the right photo or the new global selection into the reply.
        window.duplicates.table.clearSelection()
        window.controller.preview(None)
        window.navigate(Route.DASHBOARD)
        assert not window.controller.busy
        release.set()
        pump(lambda: len(launches) == 1)
        assert launches == [photo.path] and len(threads) == 1
        assert threads[0] != get_ident() and not errors
    finally:
        release.set()


def test_history_double_click_keeps_operation_id_during_selection_change(desktop, collection, launches, monkeypatch):
    import shutil
    window, errors = desktop
    shutil.copy2(collection / 'a.png', collection / 'c.png')
    scan(window, collection)
    window.prepare_bulk()
    pump(lambda: window.plan_dialog is not None)
    window.plan_dialog.approve()
    pump(lambda: not window.controller.busy and len(window.history_rows) == 2)
    window.navigate(Route.QUARANTINE)
    window.history.table.selectRow(0)
    pump(lambda: not window.history.thumbnail.pixmap().isNull())
    clicked = window.history.selected_entry
    entered, release = Event(), Event()
    original = Application.resolve_photo
    targets = []

    def delayed(self, target, cancel):
        targets.append(target)
        entered.set()
        assert release.wait(15)
        return original(self, target, cancel)

    monkeypatch.setattr(Application, 'resolve_photo', delayed)
    try:
        QTest.mouseClick(window.history.thumbnail, Qt.LeftButton)
        assert not launches
        double_click(window.history.thumbnail)
        pump(entered.is_set)
        window.history.table.selectRow(1)
        assert window.history.selected_entry.id != clicked.id
        release.set()
        pump(lambda: len(launches) == 1)
        assert targets == [clicked.id] and launches == [clicked.destination]
        assert not Path(clicked.source).exists() and window.plan_dialog is None and not errors
        # Restore the originally clicked photo through the normal confirmed flow.
        window.history.table.selectRow(0)
        window.restore()
        pump(lambda: window.plan_dialog is not None)
        window.plan_dialog.approve()
        pump(lambda: not window.controller.busy and Path(clicked.source).exists())
        window.open_photo(clicked.id)
        pump(lambda: bool(errors))
        assert errors[-1] == ('open_photo', 'quarantine_preview_unavailable')
        assert launches == [clicked.destination]
    finally:
        release.set()


@pytest.mark.parametrize('invalidate', ['cancel', 'execute', 'close'])
def test_cancel_move_dispatch_or_close_discards_late_open(desktop, literal_photo, launches, monkeypatch, invalidate):
    window, errors = desktop
    photo = literal_photo
    entered, release, finished = Event(), Event(), Event()
    original = Application.resolve_photo

    def delayed(self, target, cancel):
        entered.set()
        try:
            assert release.wait(15)
            return original(self, target, cancel)
        finally:
            finished.set()

    monkeypatch.setattr(Application, 'resolve_photo', delayed)
    try:
        window.open_photo(photo)
        request = window.controller.latest['open_photo']
        pump(entered.is_set)
        if invalidate == 'cancel':
            window.controller.cancel()
        elif invalidate == 'close':
            window.close()
        else:
            # Isolate dispatch invalidation without executing any file operation.
            window.controller.dispatch.disconnect(window.controller.worker.run)
            window.controller.request('execute', None)
            window.controller.pending.clear()
            window.controller.busy = False
        release.set()
        pump(finished.is_set)
        window.controller._result(request, 'open_photo', photo.path)
        QTest.qWait(30)
        assert not launches and not errors
    finally:
        release.set()


def test_new_open_supersedes_pending_target(desktop, literal_photo, launches, monkeypatch):
    window, errors = desktop
    path = Path(literal_photo.path).with_name('second synthetic.nef')
    path.write_bytes(b'second synthetic RAW')
    second = replace(literal_photo, path=str(path), snapshot=snapshot(path))
    entered, release = Event(), Event()
    original = Application.resolve_photo

    def delayed(self, target, cancel):
        if target == literal_photo:
            entered.set()
            assert release.wait(15)
        return original(self, target, cancel)

    monkeypatch.setattr(Application, 'resolve_photo', delayed)
    try:
        window.open_photo(literal_photo)
        pump(entered.is_set)
        window.open_photo(second)
        release.set()
        pump(lambda: bool(launches))
        assert launches == [second.path] and not errors
    finally:
        release.set()


def test_open_controls_status_and_error_dialog_translate_live(desktop, literal_photo, launches):
    window, errors = desktop
    manager = language_manager()
    try:
        window.comparison.left.set_photo(literal_photo)
        for language in ('en', 'sr_Latn'):
            manager.set_language(language)
            assert window.comparison.left.open_default.text() == tr('open_default_viewer')
            assert window.history.open_default.text() == tr('open_default_viewer')
            assert window.comparison.left.photo == literal_photo
        window.result('open_photo', literal_photo.path)
        assert window.statusBar().currentMessage() == tr('photo_open_requested')
        _window_error(window, 'open_photo', 'photo_launch_failed: synthetic association failure')
        dialog = window.findChild(QMessageBox)
        assert dialog.informativeText() == tr('photo_launch_failed')
        manager.set_language('en')
        assert dialog.informativeText() == STRINGS['en']['photo_launch_failed']
        assert window.statusBar().currentMessage() == STRINGS['en']['photo_open_requested']
        assert launches == [literal_photo.path] and not errors
    finally:
        manager.set_language('en')
        for dialog in window.findChildren(QMessageBox):
            dialog.close()


@pytest.mark.parametrize('language', ['en', 'sr_Latn'])
@pytest.mark.parametrize('problem,key', [('missing', 'photo_open_unavailable'),
    ('offline', 'photo_open_unavailable'), ('unreadable', 'photo_open_unavailable'),
    ('changed', 'candidate_changed_review_again'), ('rejected', 'photo_launch_failed'),
    ('association', 'photo_launch_failed')])
def test_readable_localized_failures_and_no_fallback(desktop, literal_photo, launches, monkeypatch, language, problem, key):
    window, errors = desktop
    photo = literal_photo
    shown = []
    monkeypatch.setattr(window, 'show_error', shown.append)
    window.controller.error.connect(lambda action, detail: _window_error(window, action, detail))
    manager = language_manager()
    manager.set_language(language)
    try:
        if problem == 'missing':
            Path(photo.path).unlink()
        elif problem == 'offline':
            Path(photo.root).rename(Path(photo.root).with_name('synthetic-offline'))
        elif problem == 'changed':
            Path(photo.path).write_bytes(b'changed synthetic file')
        elif problem == 'unreadable':
            monkeypatch.setattr(Application, 'resolve_photo', lambda *args: (_ for _ in ()).throw(PermissionError('synthetic denied')))
        elif problem == 'association':
            monkeypatch.setattr(DesktopViewer, 'open_photo', lambda *args: (_ for _ in ()).throw(OSError('no association')))
        else:
            monkeypatch.setattr(DesktopViewer, 'open_photo', lambda *args: False)
        window.open_photo(photo)
        pump(lambda: bool(errors))
        if problem in ('rejected', 'association'):
            # These errors originate at the GUI adapter, not the worker signal.
            _window_error(window, *errors[-1])
        assert shown and shown[-1].split(':', 1)[0] == key
        assert tr(key) == STRINGS[language][key]
        assert window.comparison.left.enlarged is None and not window.pending_pairs()
        assert not launches
    finally:
        manager.set_language('en')
