"""Task018 group semantics and query/review interactions; synthetic fixtures only."""
from dataclasses import replace
import shutil
from threading import Event

import pytest

pytest.importorskip('PySide6')
from PySide6.QtCore import Qt
from PySide6.QtGui import QDesktopServices
from PySide6.QtTest import QTest

from app.core.queries import GroupRow, PageResult
from app.services.application import Application
from app.ui.qt.gallery import GroupDelegate, GroupModel, pair_formats
from app.ui.qt.localization import language_manager
from app.ui.qt.navigation import Route
from app.ui.qt.strings import tr
from app.ui.qt.window import MainWindow
from tests.test_qt import desktop, qtapp, pump, scan, assert_toolbar_available

_real_window_error = MainWindow.error


@pytest.mark.parametrize('language', ['en', 'sr_Latn'])
@pytest.mark.parametrize('theme', ['dark', 'light'])
def test_group_states_controls_and_keyboard(desktop, collection, language, theme):
    window, errors = desktop
    manager = language_manager()
    manager.set_language(language)
    window.theme.apply(theme)
    screen = window.duplicates
    try:
        window.navigate(Route.DUPLICATES)
        assert screen.empty.text() == tr('no_session') and screen.results_panel.isHidden()
        shutil.copy2(collection / 'a.png', collection / 'c.png')
        scan(window, collection)
        assert window.group_rows[0].members == 3
        assert screen.group_heading.text() == tr('groups_count', 1)
        assert [screen.kind.itemData(i) for i in range(screen.kind.count())] == ['', 'EXACT', 'VISUAL']
        assert screen.kind.itemText(1) == tr('filter_EXACT')
        assert screen.kind.itemText(2) == tr('filter_VISUAL')
        for width, height in ((853, 480), (1440, 900)):
            window.resize(width, height)
            assert_toolbar_available(window, screen.toolbar)
            assert_toolbar_available(window, screen.filters)
            assert window.duplicates_flow.listing.horizontalScrollBar().maximum() == 0
        window.activateWindow()
        screen.search.setFocus()
        QTest.keyClick(screen.search, Qt.Key_Tab)
        assert screen.kind.hasFocus()
        QTest.keyClick(screen.kind, Qt.Key_Tab)
        assert screen.sort_order.hasFocus()
        screen.search.setText('no-such-photo')
        assert screen.empty.text() == tr('query_loading')
        assert screen.results_panel.isHidden() and not screen.compare.isEnabled()
        pump(lambda: window.query.text == 'no-such-photo' and not window.controller.busy)
        assert screen.empty.text() == tr('empty') and screen.results_panel.isHidden()
        screen.search.clear()
        pump(lambda: window.query.text == '' and not window.controller.busy)
        screen.groups.setFocus()
        QTest.keyClick(screen.groups, Qt.Key_Return)
        pump(lambda: window.duplicates_flow.comparing and not window.controller.busy)
        assert window.comparison.back.hasFocus()
        QTest.keyClick(window, Qt.Key_Left, Qt.AltModifier)
        assert not window.duplicates_flow.comparing and screen.groups.hasFocus()
        assert not errors
    finally:
        manager.set_language('en')


def test_review_labels_are_session_local_and_raw_jpeg_only_describes_samples(qtapp, scanned):
    a, b = scanned.photos
    model = GroupModel()
    raw = replace(a, is_raw=True, ext='.nef', image_format='')
    jpeg = replace(b, ext='.jpg', image_format='JPEG')
    group = GroupRow(42, 'VISUAL', a.path, 4, (raw, jpeg))
    model.replace((group,))
    assert pair_formats(group) == tr('sample_raw_jpeg')
    assert not pair_formats(replace(group, samples=(raw, replace(jpeg, image_format=''))))
    assert not pair_formats(replace(group, samples=(a, jpeg)))
    assert model.review_text(group) == tr('needs_review', 0)
    model.review[(42, 'VISUAL')] = {100}
    assert model.review_text(group) == tr('review_progress', 1)
    model.review[(42, 'VISUAL')].update((101, 102))
    assert model.review_text(group) == tr('reviewed', 3)
    text = model.index(1).data(Qt.AccessibleTextRole)
    assert tr('group_summary', 4, tr('filter_VISUAL')) in text
    assert tr('sample_raw_jpeg') in text and tr('classification_VISUAL') in text
    assert tr('group_space', '') not in text
    assert GroupModel().review_text(group) == tr('needs_review', 0)


@pytest.mark.parametrize('grid', [True, False])
def test_photo_double_click_is_separate_from_group_review(desktop, collection, monkeypatch, grid):
    window, errors = desktop
    shutil.copy2(collection / 'a.png', collection / 'c.png')
    scan(window, collection)
    window.navigate(Route.DUPLICATES)
    screen, gallery = window.duplicates, window.duplicates.groups
    screen.mode.setCurrentIndex(0 if grid else 1)
    launches = []
    monkeypatch.setattr(QDesktopServices, 'openUrl', lambda url: launches.append(url) or True)
    pump(lambda: gallery.visualRect(gallery.model().index(1)).isValid())
    index = gallery.model().index(1)
    photo = GroupDelegate.photo_rect(gallery.visualRect(index), grid)
    QTest.mouseDClick(gallery.viewport(), Qt.LeftButton, pos=photo.center())
    pump(lambda: not window.controller.busy)
    assert not window.duplicates_flow.comparing and not launches
    action = GroupDelegate.review_rect(gallery.visualRect(index), grid)
    QTest.mouseClick(gallery.viewport(), Qt.LeftButton, pos=action.center())
    pump(lambda: window.duplicates_flow.comparing and not window.controller.busy)
    assert len(window.duplicates.model.rows) == 2 and not window.pending_pairs()
    window.back_to_duplicates()
    screen.compare.click()
    pump(lambda: window.duplicates_flow.comparing and not window.controller.busy)
    assert not launches and not errors


@pytest.mark.parametrize('entry', ['pair', 'group'])
def test_back_restores_pair_identity_when_review_used_same_rows(desktop, collection, entry):
    window, errors = desktop
    for i in range(8):
        shutil.copy2(collection / 'a.png', collection / f'copy-{i}.png')
    scan(window, collection)
    window.navigate(Route.DUPLICATES)
    screen = window.duplicates
    screen.groups.setCurrentRow(1)
    pump(lambda: not window.controller.busy)
    window.resize(853, 480)
    screen.table.selectRow(0)
    screen.table.setFocus()
    screen.table.verticalScrollBar().setValue(2)
    saved = (window.query, window.group_offset, window.selected_id,
             screen.table.verticalScrollBar().value(), screen.groups.verticalScrollBar().value())
    if entry == 'group':
        window.activate_group(screen.groups.model().index(1))
    else:
        window.compare()
    window.comparison.members.selectRow(4)
    assert window.selected_id != saved[2]
    window.back_to_duplicates()
    assert saved == (window.query, window.group_offset, window.selected_id,
                     screen.table.verticalScrollBar().value(), screen.groups.verticalScrollBar().value())
    assert window.controller.selection.id == saved[2]
    assert screen.table.hasFocus() and not errors


def test_debounce_rejects_old_query_and_query_error_cannot_resurrect_results(desktop, collection, monkeypatch):
    window, errors = desktop
    scan(window, collection)
    window.navigate(Route.DUPLICATES)
    screen = window.duplicates
    screen.table.selectRow(0)
    original = Application.query_groups
    entered, release = Event(), Event()

    def delayed(self, *args):
        entered.set()
        assert release.wait(15)
        return original(self, *args)

    monkeypatch.setattr(Application, 'query_groups', delayed)
    try:
        window.request_groups()
        pump(entered.is_set)
        screen.search.setText('absent-photo')
        assert window.controller.selection is None
        assert screen.results_panel.isHidden() and not screen.compare.isEnabled()
        pump(lambda: window.query.text == 'absent-photo')
        release.set()
        pump(lambda: not window.controller.busy)
        assert not window.group_rows and not screen.model.rows
        assert screen.empty.text() == tr('empty') and screen.results_panel.isHidden()
        window.request_matches()
        request = window.controller.latest['matches']
        _real_window_error(window, 'groups', 'synthetic-query-error')
        window.controller._result(request, 'matches', PageResult((), 0))
        assert screen.empty.text() == tr('query_error') and screen.results_panel.isHidden()
        assert not window.listing_pending and not errors
    finally:
        release.set()


def test_cancelled_query_hides_results_and_invalidates_sibling(desktop, collection):
    window, errors = desktop
    scan(window, collection)
    window.navigate(Route.DUPLICATES)
    window.request_matches()
    window.request_groups()
    sibling = window.controller.latest['matches']
    window.result('cancelled', 'groups')
    window.controller._result(sibling, 'matches', PageResult((), 0))
    assert not window.listing_pending and not window.open_group
    assert window.duplicates.empty.text() == tr('action_cancelled')
    assert window.duplicates.results_panel.isHidden()
    assert window.controller.selection is None and not errors
