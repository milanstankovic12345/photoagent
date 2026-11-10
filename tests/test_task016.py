"""Collapsing navigation changes presentation, never session data or consent."""
from threading import Event

import pytest

pytest.importorskip('PySide6')
from PySide6.QtCore import QAbstractAnimation, QTimer, Qt
from PySide6.QtGui import QAccessible
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from app.services.application import Application
from app.ui.qt.localization import language_manager
from app.ui.qt.navigation import Route
from app.ui.qt.strings import tr
from tests.test_qt import desktop, pump, qtapp, scan, assert_toolbar_available
from tests.test_qt_design_system import painted_color
from app.ui.qt.themes import TOKENS


def settle(sidebar):
    pump(lambda: sidebar.animation.state() == QAbstractAnimation.Stopped)


@pytest.mark.parametrize('theme', ['dark', 'light'])
@pytest.mark.parametrize('language', ['en', 'sr_Latn'])
def test_routes_keyboard_accessibility_and_small_layouts(desktop, theme, language):
    window, errors = desktop
    sidebar = window.navigation
    manager = language_manager()
    manager.set_language(language)
    window.theme.apply(theme)
    window.activateWindow()
    assert sidebar.collapsed and sidebar.width() == sidebar.COMPACT_WIDTH
    try:
        for size in ((1280, 720), (853, 480)):
            window.resize(*size)
            for collapsed in (True, False):
                sidebar.set_collapsed(collapsed)
                settle(sidebar)
                assert sidebar.width() == (64 if collapsed else 208)
                assert sidebar.toggle.isChecked() == (not collapsed)
                action = tr('navigation_expand' if collapsed else 'navigation_collapse')
                assert sidebar.toggle.toolTip() == sidebar.toggle.accessibleName() == action
                interface = QAccessible.queryAccessibleInterface(sidebar.toggle)
                assert interface.state().checked == (not collapsed)
                assert interface.text(QAccessible.Description) == tr(
                    'section_collapsed' if collapsed else 'section_expanded')
                sidebar.toggle.setFocus()
                QTest.keyClick(sidebar.toggle, Qt.Key_Tab)
                assert sidebar.buttons[Route.DASHBOARD].hasFocus()
                for route, control in sidebar.buttons.items():
                    control.setFocus()
                    QTest.keyClick(control, Qt.Key_Return)
                    assert window.route == route and window.stack.currentWidget() is window.pages[route]
                    assert control.isChecked() and control.hasFocus()
                    accessible = QAccessible.queryAccessibleInterface(control)
                    assert accessible.state().checked and accessible.state().focusable
                    assert accessible.text(QAccessible.Name) == control.toolTip() == tr(route.value)
                    assert control.text() == ('' if collapsed else tr(route.value))
                    assert control.width() >= 44 and control.height() >= 44
                    assert sidebar.rect().contains(control.geometry())
                    assert painted_color(control.grab().toImage(), TOKENS[theme]['focus'])
                    if not collapsed:
                        assert control.fontMetrics().horizontalAdvance(control.text()) + 48 <= control.width()
                    assert_toolbar_available(window, window.screens[route].toolbar)
                assert sidebar.buttons[Route.SETTINGS].y() > sidebar.buttons[Route.QUARANTINE].geometry().bottom()
                sidebar.toggle.setFocus()
                QApplication.processEvents()
                selected = sidebar.buttons[Route.SETTINGS]
                image = selected.grab().toImage()
                ratio = image.devicePixelRatio()
                # The persistent three-pixel marker survives when focus leaves.
                assert image.pixelColor(int(4 * ratio), int(20 * ratio)).name().upper() == TOKENS[theme]['text']
        # Refresh bindings in both directions without resurrecting collapsed text.
        sidebar.set_collapsed(True)
        settle(sidebar)
        for current in ('sr_Latn', 'en'):
            manager.set_language(current)
            assert all(not control.text() and control.toolTip() == tr(route.value)
                       for route, control in sidebar.buttons.items())
            assert sidebar.toggle.toolTip() == tr('navigation_expand')
        # Both native Space and the existing Enter behavior toggle, keeping focus.
        for key in (Qt.Key_Space, Qt.Key_Return, Qt.Key_Enter):
            previous = sidebar.collapsed
            sidebar.toggle.setFocus()
            QTest.keyClick(sidebar.toggle, key)
            settle(sidebar)
            assert sidebar.collapsed != previous and sidebar.toggle.hasFocus()
        assert not errors
    finally:
        manager.set_language('en')


def test_collapse_preserves_compare_filters_scroll_and_open_confirmation(desktop, collection):
    window, errors = desktop
    before_files = {path: path.read_bytes() for path in collection.iterdir()}
    scan(window, collection)
    window.navigate(Route.DUPLICATES)
    window.duplicates.search.setText('.png')
    window.duplicates.kind.setCurrentIndex(window.duplicates.kind.findData('EXACT'))
    pump(lambda: window.query.text == '.png' and window.query.kind == 'EXACT' and not window.controller.busy)
    window.duplicates.table.selectRow(0)
    window.compare()
    pump(lambda: window.comparison.left.state == 'preview_ready')
    window.choose_keeper(False)
    window.resize(853, 480)
    QApplication.processEvents()
    scroll = window.duplicates_flow.comparison.verticalScrollBar()
    scroll.setValue(min(40, scroll.maximum()))
    assert scroll.value() > 0
    pages = dict(window.pages)
    screens = dict(window.screens)

    def state():
        return (window.route, window.session, window.query, window.group_offset,
                window.selected_id, window.duplicates.table.currentIndex(),
                dict(window.retained), window.choice_context, window.listing_context,
                window.duplicates_flow.listing_scroll, window.pending_pairs(),
                window.controller.preview_id, window.duplicates_flow.comparing)

    original = state()
    position = scroll.value()
    requests = []
    window.controller.dispatch.connect(lambda *args: requests.append(args))
    for _ in range(4):
        window.navigation.set_collapsed(not window.navigation.collapsed)
        settle(window.navigation)
        assert state() == original
        assert scroll.value() == position
    assert window.pages == pages and window.screens == screens and not requests

    window.prepare_selected()
    pump(lambda: window.plan_dialog is not None and not window.controller.busy)
    dialog = window.plan_dialog
    pump(lambda: dialog.cancel.hasFocus())
    plan = dialog.plan
    original = state()
    requests.clear()
    # A modal confirmation intentionally blocks pointer access to the sidebar.
    # Programmatic width changes must still preserve that dialog and its consent.
    for _ in range(4):
        window.navigation.set_collapsed(not window.navigation.collapsed)
        settle(window.navigation)
        assert state() == original and window.plan_dialog is dialog
        assert dialog.plan is plan and dialog.approval is None
        assert dialog.cancel.hasFocus() and dialog.isVisible()
    assert not requests and not errors
    assert {path: path.read_bytes() for path in collection.iterdir()} == before_files
    dialog.reject()


def test_reversing_animation_during_scan_keeps_worker_and_focus(desktop, collection, monkeypatch):
    window, errors = desktop
    entered, release = Event(), Event()
    original_scan = Application.scan

    def delayed(self, *args, **kwargs):
        entered.set()
        if not release.wait(20):
            raise AssertionError('Synthetic scan release timed out')
        return original_scan(self, *args, **kwargs)

    monkeypatch.setattr(Application, 'scan', delayed)
    window.roots = [str(collection)]
    window.render_roots()
    window.navigate(Route.SCAN)
    window.start_scan()
    timer = QTimer()
    beats = []
    timer.setInterval(10)
    timer.timeout.connect(lambda: beats.append(1))
    timer.start()
    try:
        pump(entered.is_set)
        window.activateWindow()
        sidebar = window.navigation
        sidebar.toggle.setFocus()
        for _ in range(6):
            QTest.keyClick(sidebar.toggle, Qt.Key_Space)
            QTest.qWait(30)  # Reverse before the 160 ms animation has finished.
            assert window.scan_active and window.controller.busy
            assert sidebar.toggle.hasFocus() and window.route == Route.SCAN
        settle(sidebar)
        assert sidebar.collapsed and sidebar.width() == 64 and len(beats) >= 6
        release.set()
        pump(lambda: window.session and not window.controller.busy, timeout=90)
        assert window.status == 'complete' and window.duplicates.model.rowCount() == 1
        window.navigate(Route.SETTINGS)
        assert sidebar.collapsed  # Retained for the session across route changes.
        assert not errors and all((collection / name).exists() for name in ('a.png', 'b.png'))
    finally:
        release.set()
        timer.stop()
