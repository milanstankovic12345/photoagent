"""Task010: keyboard journeys, safe messages and real rendered accessibility states.

All photographs, journals, settings and operations are isolated synthetic fixtures.
Offscreen Qt checks do not substitute for a screen-reader/native DPI review.
"""
from dataclasses import replace
import json
from pathlib import Path

import pytest

pytest.importorskip('PySide6')
from PySide6.QtCore import Qt
from PySide6.QtGui import QAccessible, QColor, QImage, QPixmap
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QFileDialog, QMessageBox, QPushButton

from app.i18n import STRINGS, tr as shared_tr
from app.core.models import Kind, Plan
from app.core.queries import GroupRow, MatchRow
from app.safety.operations import make_plan
from app.ui.qt.components import PhotoView, PlanDialog
from app.ui.qt.navigation import Route
from app.ui.qt.gallery import GroupView
from app.ui.qt.strings import SR, error_text, tr
from app.ui.qt.window import MainWindow
from app.ui.qt.themes import ThemeManager
from tests.test_qt import desktop, pump, qtapp

_real_error = MainWindow.error


def tab_to(target, *, backwards=False):
    """Reach a control through the actual focus chain, failing on a cycle/trap."""
    seen = []
    for _ in range(100):
        QApplication.processEvents()
        if target.hasFocus():
            return
        current = QApplication.focusWidget()
        assert current is not None
        seen.append((type(current).__name__, current.accessibleName()))
        QTest.keyClick(current, Qt.Key_Tab, Qt.ShiftModifier if backwards else Qt.NoModifier)
    pytest.fail(f'Unreachable keyboard target: {target.accessibleName()}, '
                f'enabled={target.isEnabled()}, visible={target.isVisible()}, chain={seen[:25]}')


def test_catalog_inventory_safe_fallback_and_existing_language(monkeypatch):
    inventory = json.loads((Path(__file__).parents[1] / 'docs/design/QT_TEXT_INVENTORY.json').read_text(encoding='utf-8'))
    assert set(inventory['english_intents']) == set(SR) | set(STRINGS['sr_Latn'])
    assert all(text.strip() for text in inventory['english_intents'].values())
    assert shared_tr('history_error', language='en') == STRINGS['en']['history_error']
    assert tr('history_error') == STRINGS['sr_Latn']['history_error']
    assert tr('missing_internal_key') == tr('message_unavailable')
    assert 'missing_internal_key' not in tr('missing_internal_key')
    assert tr('metadata') == tr('message_unavailable')  # Missing format arguments.
    assert error_text('OSError: <private path>') == tr('error')
    assert error_text('destination_occupied: <private path>') == tr('destination_occupied')
    monkeypatch.delitem(SR, 'xmp_warning', raising=False)
    assert tr('xmp_warning') == STRINGS['sr_Latn']['xmp_warning']


def test_empty_plan_message_is_nonblocking_and_cannot_approve(desktop):
    window, _ = desktop
    window.confirm(Plan('synthetic-empty', ()))
    assert window.plan_dialog is None and window.executing_plan is None
    message = next(box for box in window.findChildren(QMessageBox) if box.isVisible())
    assert message.text() == tr('no_plan') and message.textFormat() == Qt.PlainText
    close = message.button(QMessageBox.Close)
    assert close.text() == tr('close')
    QTest.keyClick(close, Qt.Key_Space)
    assert not message.isVisible()


@pytest.mark.parametrize('theme', ['dark', 'light'])
def test_keyboard_sources_filters_group_compare_confirmation_restore_settings(desktop, collection, monkeypatch, theme):
    window, errors = desktop
    window.theme.apply(theme)
    window.activateWindow()
    window.navigate(Route.SCAN)
    monkeypatch.setattr(QFileDialog, 'getExistingDirectory', lambda *a, **kw: str(collection))
    tab_to(window.scan.add)
    QTest.keyClick(window.scan.add, Qt.Key_Space)
    pump(lambda: window.scan.start.isEnabled() and not window.controller.busy)
    assert window.roots == [str(collection)]
    tab_to(window.scan.roots)
    QTest.keyClick(window.scan.roots, Qt.Key_Down)
    assert str(collection) in window.scan.roots.currentItem().data(Qt.AccessibleTextRole)
    tab_to(window.scan.advanced.toggle)
    QTest.keyClick(window.scan.advanced.toggle, Qt.Key_Space)
    tab_to(window.scan.up)
    tab_to(window.scan.start)
    QTest.keyClick(window.scan.start, Qt.Key_Space)
    pump(lambda: window.session and not window.controller.busy, timeout=90)
    assert window.status == 'complete'
    window.navigate(Route.DUPLICATES)
    tab_to(window.duplicates.search)
    QTest.keyClicks(window.duplicates.search, '.png')
    pump(lambda: window.query.text == '.png' and not window.controller.busy)
    QTest.keyClick(window.duplicates.search, Qt.Key_Tab)
    assert window.duplicates.kind.hasFocus()
    QTest.keyClick(window.duplicates.kind, Qt.Key_Down)
    pump(lambda: window.query.kind == 'EXACT' and not window.controller.busy)
    tab_to(window.duplicates.groups)
    QTest.keyClick(window.duplicates.groups, Qt.Key_Down)
    QTest.keyClick(window.duplicates.groups, Qt.Key_Return)
    pump(lambda: window.duplicates_flow.comparing and not window.controller.busy)
    assert window.comparison.back.hasFocus()
    tab_to(window.comparison.left.keep_photo)
    QTest.keyClick(window.comparison.left.keep_photo, Qt.Key_Space)
    assert len(window.pending_pairs()) == 1
    tab_to(window.comparison.both)
    QTest.keyClick(window.comparison.both, Qt.Key_Space)
    assert not window.pending_pairs()
    # Uncheck one of the two explicitly retained photographs.
    tab_to(window.comparison.right.keep_photo, backwards=True)
    QTest.keyClick(window.comparison.right.keep_photo, Qt.Key_Space)
    assert window.comparison.prepare.isEnabled()
    tab_to(window.comparison.prepare)
    QTest.keyClick(window.comparison.prepare, Qt.Key_Space)
    pump(lambda: window.plan_dialog is not None)
    dialog = window.plan_dialog
    pump(lambda: dialog.cancel.hasFocus())
    QTest.keyClick(dialog.cancel, Qt.Key_Escape)
    pump(lambda: window.plan_dialog is None and window.comparison.prepare.hasFocus())
    assert len(list(collection.glob('*.png'))) == 2
    # Explicit Space activation approves only this displayed synthetic plan.
    QTest.keyClick(window.comparison.prepare, Qt.Key_Space)
    pump(lambda: window.plan_dialog is not None)
    dialog = window.plan_dialog
    tab_to(dialog.confirm)
    QTest.keyClick(dialog.confirm, Qt.Key_Return)
    assert dialog.approval is None
    QTest.keyClick(dialog.confirm, Qt.Key_Space)
    pump(lambda: window.plan_dialog is None and not window.controller.busy)
    assert len(list(collection.glob('*.png'))) == 1
    window.navigate(Route.QUARANTINE)
    tab_to(window.history.table)
    QTest.keyClick(window.history.table, Qt.Key_Down)
    pump(lambda: window.history.restore.isEnabled())
    tab_to(window.history.restore, backwards=True)
    QTest.keyClick(window.history.restore, Qt.Key_Space)
    pump(lambda: window.plan_dialog is not None)
    dialog = window.plan_dialog
    tab_to(dialog.confirm)
    QTest.keyClick(dialog.confirm, Qt.Key_Space)
    pump(lambda: not window.controller.busy and window.plan_dialog is None)
    assert (collection / 'a.png').read_bytes() == (collection / 'b.png').read_bytes()
    window.navigate(Route.SETTINGS)
    tab_to(window.preferences.theme)
    tab_to(window.preferences.preset)
    QTest.keyClick(window.preferences.preset, Qt.Key_End)
    tab_to(window.preferences.phash)
    QTest.keyClick(window.preferences.phash, Qt.Key_Up)
    tab_to(window.preferences.save)
    QTest.keyClick(window.preferences.save, Qt.Key_Space)
    pump(lambda: not window.controller.busy)
    assert window.settings['phash_max'] == 5 and window.settings['language'] == 'sr_Latn'
    assert not errors


def test_consent_warnings_stay_visible_and_enter_never_approves(qtapp, scanned):
    plan = make_plan(scanned.pairs)
    move = replace(plan.moves[0], raw=True, legacy=True, kind=Kind.VISUAL,
                   xmp=('synthetic-sidecar.xmp',))
    dialog = PlanDialog(replace(plan, moves=(move,)))
    dialog.show()
    dialog.activateWindow()
    QApplication.processEvents()
    try:
        assert dialog.warnings.isVisible() and dialog.raw.isVisible() and dialog.legacy.isVisible()
        for key in ('raw_warning', 'legacy_warning', 'xmp_warning', 'visual_warning'):
            assert tr(key) in dialog.warnings.text()
        assert not dialog.details.body.isVisible() and not dialog.confirm.isEnabled()
        dialog.raw.setFocus()
        QTest.keyClicks(dialog.raw, 'RAW')
        assert not dialog.confirm.isEnabled()
        tab_to(dialog.legacy)
        QTest.keyClick(dialog.legacy, Qt.Key_Space)
        assert dialog.confirm.isEnabled()
        tab_to(dialog.confirm)
        QTest.keyClick(dialog.confirm, Qt.Key_Return)
        assert dialog.approval is None
        QTest.keyClick(dialog.confirm, Qt.Key_Enter)
        assert dialog.approval is None
        QTest.keyClick(dialog.confirm, Qt.Key_Escape)
        assert dialog.approval is None and not dialog.isVisible()
    finally:
        dialog.close()


def test_errors_are_plain_short_and_details_are_keyboard_reachable(desktop, collection):
    window, _ = desktop
    raw = 'unmapped_internal_code: <b>private diagnostic</b>'
    for route, action, details, summary in (
        (Route.SETTINGS, 'storage', window.preferences.error_details, window.preferences.index),
        (Route.QUARANTINE, 'history', window.history.error_details, window.history.message),
        (Route.DUPLICATES, 'matches', window.duplicates.error_details, window.duplicates.empty),
    ):
        window.navigate(route)
        _real_error(window, action, raw)
        assert raw not in summary.text() and 'unmapped_internal_code' not in summary.text()
        assert details.text.toPlainText() == raw and details.body.isHidden()
        for box in window.findChildren(QMessageBox):
            assert box.textFormat() == Qt.PlainText
            assert 'unmapped_internal_code' not in box.informativeText()
            for action in box.buttons():
                if box.buttonRole(action) == QMessageBox.ActionRole:
                    assert action.text() == tr('technical_details')
                    QTest.keyClick(action, Qt.Key_Space)
                    assert action.text() == tr('hide_details')
            box.close()
        window.activateWindow()
        window.navigation.buttons[route].setFocus()
        tab_to(details.toggle)
        QTest.keyClick(details.toggle, Qt.Key_Space)
        assert details.body.isVisible()
        QTest.keyClick(details.toggle, Qt.Key_Tab)
        assert details.text.hasFocus()
        QTest.keyClick(details.text, Qt.Key_Tab)  # Read-only diagnostics cannot trap Tab.
        assert not details.text.hasFocus()


@pytest.mark.parametrize('theme', ['dark', 'light'])
def test_rendered_focus_selection_long_paths_and_accessible_names(desktop, collection, scanned, theme):
    window, _ = desktop
    # Layout assertions need real decoded previews, not another indexed scan.
    # The complete real-service scan/move/restore journey is exercised above.
    window.status = 'complete'
    window.duplicates.model.replace((MatchRow(1, 1, scanned.pairs[0]),))
    window.theme.apply(theme)
    window.resize(853, 480)
    long_path = str(collection / ('čćžšđ-fotografija-' * 35 + '.png'))
    window.scan.set_sources([long_path], {long_path: 'unavailable'})
    window.preferences.show_roots([long_path])
    window.navigate(Route.DUPLICATES)
    window.duplicates.table.selectRow(0)
    window.compare()
    left = window.comparison.left
    pump(lambda: left.state == 'preview_ready')
    left.set_photo(replace(window.controller.selection.match.keep, path=long_path))
    left.set_image(None, 'decoder_internal_exception')
    assert left.placeholder.text() == tr('preview_error')
    assert left.error_details.text.toPlainText() == 'decoder_internal_exception'
    assert left.metadata.toolTip() == long_path and long_path in left.full_metadata.text()
    window.activateWindow()
    left.keep_photo.setFocus()
    QApplication.processEvents()
    focused = left.keep_photo.grab().toImage()
    assert QAccessible.queryAccessibleInterface(left.keep_photo).text(QAccessible.Name)
    assert long_path in left.keep_photo.accessibleName()
    QTest.keyClick(left.keep_photo, Qt.Key_Space)
    assert left.keep_photo.isChecked() and left.keep_photo.text() == tr('keep_chosen')
    selected = left.keep_photo.grab().toImage()
    assert selected != focused
    QTest.keyClick(left.keep_photo, Qt.Key_Tab)
    QApplication.processEvents()
    assert selected != left.keep_photo.grab().toImage()
    assert left.details.toggle.hasFocus()
    QTest.keyClick(left.details.toggle, Qt.Key_Space)
    QTest.keyClick(left.details.toggle, Qt.Key_Tab)
    assert left.full_metadata.hasFocus()
    assert window.comparison.left.view.accessibleName() != window.comparison.right.view.accessibleName()
    assert window.duplicates.kind.accessibleName() == tr('category_filter')
    assert all(left.metadata.fontMetrics().inFontUcs4(ord(char)) for char in 'čćžšđČĆŽŠĐ'), left.metadata.font().family()
    for route in Route:
        window.navigate(route)
        QApplication.processEvents()
        page = window.pages[route]
        if route == Route.DUPLICATES:
            page = window.duplicates_flow.comparison
        assert page.horizontalScrollBar().maximum() == 0, (route, window.comparison.split.orientation(),
            page.viewport().width(), window.comparison.width(), window.comparison.minimumSizeHint().width(),
            [(type(w).__name__, w.width(), w.minimumSizeHint().width())
             for w in window.comparison.findChildren(QPushButton)])
    for control in left.preview_buttons:
        assert control.height() >= 36 and control.width() >= 36
    # Approximate longer future translations without adding a runtime language.
    for photo in (window.comparison.left, window.comparison.right):
        photo.keep_photo.setText(tr('keep_photo') + ' · ' + tr('photo_retained'))
    window.navigate(Route.DUPLICATES)
    QApplication.processEvents()
    assert window.duplicates_flow.comparison.horizontalScrollBar().maximum() == 0


def test_enlarged_preview_keyboard_close_returns_focus(qtapp, scanned):
    view = PhotoView()
    view.set_photo(scanned.photos[0])
    image = QImage(32, 24, QImage.Format_RGB32)
    image.fill(Qt.gray)
    view.set_image(image, '')
    view.show()
    view.activateWindow()
    view.enlarge.setFocus()
    QApplication.processEvents()
    try:
        QTest.keyClick(view.enlarge, Qt.Key_Space)
        pump(lambda: view.enlarged is not None)
        dialog = view.enlarged
        close = next(button for button in dialog.findChildren(QPushButton) if button.text() == tr('close_preview'))
        tab_to(close)
        QTest.keyClick(close, Qt.Key_Space)
        pump(lambda: view.enlarged is None and view.enlarge.hasFocus())
    finally:
        if view.enlarged:
            view.enlarged.close()
        view.close()


@pytest.mark.parametrize('theme', ['dark', 'light'])
def test_focused_group_keeps_thumbnail_and_text_visible(qtapp, scanned, theme):
    manager = ThemeManager(qtapp)
    manager.apply(theme)
    group = GroupView(lambda photos: None)
    photo = scanned.photos[0]
    group.replace((GroupRow(1, 'EXACT', photo.path, 2, (photo,), photo.size),))
    thumbnail = QPixmap(64, 64)
    thumbnail.fill(QColor('#ed168b'))
    group.groups_model.images[photo] = thumbnail
    group.resize(550, 300)
    group.show()
    group.activateWindow()
    group.setFocus()
    QApplication.processEvents()
    try:
        assert group.hasFocus() and group.currentRow() == 1
        pixels = group.viewport().grab().toImage()
        assert any(pixels.pixelColor(x, y) == QColor('#ed168b')
                   for x in range(0, pixels.width(), 4) for y in range(0, pixels.height(), 4))
        assert photo.path in group.currentIndex().data(Qt.AccessibleTextRole)
    finally:
        group.close()
        manager.deleteLater()
