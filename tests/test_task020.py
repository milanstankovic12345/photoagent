"""Photo-first review and frozen-plan invalidation, using isolated synthetic files."""
from dataclasses import replace
from pathlib import Path
import shutil
from threading import Event

import pytest

pytest.importorskip('PySide6')
from PySide6.QtCore import Qt
from PySide6.QtGui import QImage
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from app.core.models import Kind, Match
from app.core.queries import MatchRow
from app.services.application import Application
from app.ui.qt.localization import language_manager
from app.ui.qt.navigation import Route
from app.ui.qt.strings import tr
from tests.test_qt import desktop, qtapp, pump, scan


def open_review(window):
    window.navigate(Route.DUPLICATES)
    window.duplicates.table.selectRow(0)
    window.compare()
    pump(lambda: not window.controller.busy and window.comparison.left.state == 'preview_ready')


def test_initial_compact_header_and_pair_selector_localize(desktop):
    window, errors = desktop
    manager = language_manager()
    try:
        window.duplicates_flow.show_comparison(True)
        window.navigate(Route.DUPLICATES)
        for language in ('en', 'sr_Latn'):
            manager.set_language(language)
            for width, height in ((1440, 900), (853, 480)):
                window.resize(width, height)
                QTest.qWait(80)
                title = window.header.title
                assert window.header.rect().contains(title.geometry())
                assert title.height() >= title.fontMetrics().height()
                assert window.comparison.pair_choice.accessibleName() == tr('direct_pair_choice')
        assert not errors
    finally:
        manager.set_language('en')


@pytest.mark.parametrize('language', ['en', 'sr_Latn'])
@pytest.mark.parametrize('theme', ['dark', 'light', 'system'])
def test_photos_choices_sticky_footer_and_keyboard(desktop, collection, language, theme):
    window, errors = desktop
    scan(window, collection)
    open_review(window)
    manager = language_manager()
    try:
        manager.set_language(language)
        window.theme.apply(theme)
        left, right = window.comparison.left, window.comparison.right
        assert left.recommendation.text() == tr('suggested_exact')
        assert left.choice_status.text() == right.choice_status.text() == tr('photo_undecided')
        assert not window.pending_pairs() and not window.comparison.prepare.isEnabled()
        assert not left.details.toggle.isChecked()
        photo = window.controller.selection.match.keep
        assert Path(photo.path).name in left.metadata.text()
        assert str(photo.width) in left.metadata.text() and str(photo.height) in left.metadata.text()
        assert photo.sha256 not in left.metadata.text() and photo.sha256 in left.full_metadata.text()
        for width, height in ((1440, 900), (853, 480)):
            window.resize(width, height)
            QApplication.processEvents()
            assert window.comparison.split.orientation() == (Qt.Vertical if width == 853 else Qt.Horizontal)
            scroll = window.duplicates_flow.comparison
            assert scroll.horizontalScrollBar().maximum() == 0
            for position in (0, scroll.verticalScrollBar().maximum()):
                scroll.verticalScrollBar().setValue(position)
                actions = window.comparison.footer_actions.actions
                for i in range(actions.count()):
                    control = actions.itemAt(i).widget()
                    if control.isVisible():
                        position = control.mapTo(window, control.rect().topLeft())
                        assert window.rect().contains(position)
                        assert window.rect().contains(position + control.rect().bottomRight())
            assert left.view.minimumHeight() >= 240 and right.view.minimumHeight() >= 240
        window.activateWindow()
        left.keep_photo.setFocus()
        QTest.keyClick(left.keep_photo, Qt.Key_Space)
        assert len(window.pending_pairs()) == 1
        assert left.choice_status.text() == tr('photo_retained')
        assert right.choice_status.text() == tr('photo_proposed')
        assert Path(window.pending_pairs()[0].dup.path).name in window.comparison.proposed.text()
        assert left.recommendation.text() == tr('suggested_exact')
        QTest.keyClick(window.comparison.both, Qt.Key_Space)
        assert window.comparison.both.isChecked()
        assert left.keep_photo.isChecked() and right.keep_photo.isChecked()
        assert not window.pending_pairs() and not window.comparison.prepare.isEnabled()
        assert not window.comparison.proposed.isVisible()
        assert len(list(collection.glob('*.png'))) == 2 and not errors
    finally:
        manager.set_language('en')


def test_direct_pair_navigation_paginates_without_approving_unseen_members(desktop, collection):
    window, errors = desktop
    for name in ('c.png', 'd.png'):
        shutil.copy2(collection / 'a.png', collection / name)
    scan(window, collection)
    window.query = replace(window.query, limit=1)
    window.request_matches()
    pump(lambda: not window.controller.busy)
    open_review(window)
    window.choose_keeper(False)
    original = window.pending_pairs()
    first_id = window.selected_id
    window.comparison.pair_next.click()
    pump(lambda: not window.controller.busy)
    assert window.query.offset == 1 and window.selected_id != first_id
    assert window.pending_pairs() == original
    assert window.comparison.right.choice_status.text() == tr('photo_undecided')
    assert window.comparison.pair_choice.currentData() == window.selected_id
    window.comparison.pair_previous.click()
    pump(lambda: not window.controller.busy)
    assert window.query.offset == 0 and window.selected_id == first_id
    assert window.pending_pairs() == original
    window.keep_both()
    assert not window.pending_pairs() and len(list(collection.glob('*.png'))) == 4 and not errors


def test_visual_direct_links_keep_both_and_recommendation_are_separate(desktop, scanned):
    window, errors = desktop
    a, b = scanned.photos
    c = replace(b, path=str(Path(b.path).with_name('c.png')))
    # Presentation fixture A~B, B~C. No A~C edge exists or may be inferred.
    rows = (MatchRow(101, 11, Match(Kind.VISUAL, a, b)),
            MatchRow(102, 12, Match(Kind.VISUAL, b, c)))
    window.duplicates.model.replace(rows)
    window.total = 2
    window.duplicates.table.selectRow(0)
    window.choose_keeper(True)
    assert window.pending_pairs()[0].keep == b
    assert window.comparison.left.recommendation.text() == tr('suggested_heuristic')
    window.select_pair(1)
    assert window.controller.selection == rows[1] and not window.pending_pairs()
    window.choose_keeper(True)
    assert window.pending_pairs() == (Match(Kind.VISUAL, c, b),)
    window.keep_both()
    assert not window.pending_pairs() and window.comparison.both.isChecked()
    assert all(v.keep_photo.isChecked() and v.choice_status.text() == tr('photo_retained')
               for v in (window.comparison.left, window.comparison.right))
    assert window.duplicates.model.retained_paths == {b.path, c.path}
    window.comparison.right.keep_photo.click()
    assert window.pending_pairs() == (rows[1].match,)
    assert not window.comparison.both.isChecked() and not errors


@pytest.mark.parametrize('change', ['member', 'filter', 'session', 'both'])
def test_open_and_late_plans_invalidated_by_context(desktop, collection, monkeypatch, change):
    window, errors = desktop
    shutil.copy2(collection / 'a.png', collection / 'c.png')
    scan(window, collection)
    open_review(window)
    window.choose_keeper(False)
    window.prepare_selected()
    pump(lambda: window.plan_dialog is not None)
    dialog = window.plan_dialog
    window.select_pair(1)
    assert window.plan_dialog is None and dialog.approval is None
    window.choose_keeper(False)

    original = Application.prepare
    entered, release = Event(), Event()

    def delayed(self, *args, **kwargs):
        entered.set()
        assert release.wait(10)
        return original(self, *args, **kwargs)

    monkeypatch.setattr(Application, 'prepare', delayed)
    dispatched = []
    window.controller.dispatch.connect(lambda request, action, *args: dispatched.append(action))
    try:
        window.prepare_selected()
        pump(entered.is_set)
        if change == 'member':
            window.select_pair(0)
        elif change == 'filter':
            window.duplicates.search.setText('no-such-photo')
        elif change == 'session':
            window.invalidate_selection()
            window.session = 'replacement-synthetic-session'
        else:
            window.keep_both()
        release.set()
        pump(lambda: not window.controller.busy)
        assert window.plan_dialog is None and 'execute' not in dispatched
        assert len(list(collection.glob('*.png'))) == 3 and not errors
    finally:
        release.set()


def test_late_preview_does_not_replace_new_photos_or_choice(desktop, collection):
    window, errors = desktop
    shutil.copy2(collection / 'a.png', collection / 'c.png')
    scan(window, collection)
    open_review(window)
    stale_request = window.controller.preview_id
    window.select_pair(1)
    window.choose_keeper(True)
    expected = (window.controller.selection, window.pending_pairs())
    image = QImage(10, 10, QImage.Format_RGB32)
    image.fill(Qt.magenta)
    window.controller._preview(stale_request, ((image, ''), (image, '')))
    assert expected == (window.controller.selection, window.pending_pairs())
    assert window.comparison.right.photo == expected[0].match.dup
    assert window.comparison.right.keep_photo.isChecked() and not errors


def test_raw_backup_and_derivative_warnings_visible_outside_details(desktop, scanned):
    window, errors = desktop
    a, b = scanned.photos
    raw = replace(a, is_raw=True, ext='.nef', image_format='')
    backup = replace(b, root=str(Path(b.root).parent / 'backup-drive'), ext='.jpg', image_format='JPEG')
    row = MatchRow(101, 11, Match(Kind.VISUAL, raw, backup))
    window.duplicates.model.replace((row,))
    window.duplicates.table.selectRow(0)
    for key in ('raw_warning', 'cross_roots', 'visual_warning', 'preserve_derivatives'):
        assert tr(key) in window.comparison.warning.text()
    assert any(label.text() == tr('xmp_possible') for label in
               window.comparison.left.details.body.findChildren(type(window.comparison.warning)))
    assert not window.comparison.left.details.toggle.isChecked()
    assert not window.comparison.right.details.toggle.isChecked()
    assert not window.pending_pairs() and not errors


def test_long_copy_names_do_not_displace_bottom_actions(desktop, scanned):
    window, errors = desktop
    a, b = scanned.photos
    rows = tuple(MatchRow(101 + i, 11, Match(Kind.EXACT, a,
        replace(b, path=str(Path(b.path).with_name(f'copy-{i}-' + 'čćžšđ' * 35 + '.png')))))
        for i in range(3))
    window.duplicates.model.replace(rows)
    window.total = 3
    for i in range(3):
        window.select_pair(i)
        window.choose_keeper(False)
    window.duplicates_flow.show_comparison(True)
    window.navigate(Route.DUPLICATES)
    window.resize(853, 480)
    window.navigation.set_collapsed(False, animate=False)
    QApplication.processEvents()
    assert len(window.pending_pairs()) == 3
    assert all(row.match.dup.path in window.comparison.proposed.toolTip() for row in rows)
    assert '…' in window.comparison.proposed.text()
    for control in (window.comparison.both, window.comparison.prepare):
        position = control.mapTo(window, control.rect().topLeft())
        assert window.rect().contains(position)
        assert window.rect().contains(position + control.rect().bottomRight())
    assert window.duplicates_flow.comparison.horizontalScrollBar().maximum() == 0 and not errors
