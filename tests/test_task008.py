"""Task008: explicit decisions, bounded galleries and real synthetic recovery."""
from dataclasses import replace
from pathlib import Path
import shutil
from threading import Event
import threading

import pytest

pytest.importorskip('PySide6')
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtGui import QImage
from PySide6.QtWidgets import QLabel

from app.core.models import Approval, Kind, Match, SafetyError
from app.core.queries import DashboardSummary, MatchQuery, MatchRow
from app.services.application import Application
from app.services.preview import PreviewService
from app.ui.qt.components import PlanDialog
from app.ui.qt.navigation import Route
from app.ui.qt.strings import tr
from app.ui.qt.window import MainWindow
from tests.test_qt import desktop, pump, qtapp, scan

_real_window_error = MainWindow.error


def test_gallery_group_open_images_modes_back_and_explicit_decision(desktop, collection):
    window, errors = desktop
    shutil.copy2(collection / 'a.png', collection / 'c.png')
    scan(window, collection)
    window.navigate(Route.DUPLICATES)
    gallery = window.duplicates.groups
    pump(lambda: len(gallery.groups_model.images) == 2, timeout=60)
    assert len(window.group_rows) == 1 and window.group_rows[0].members == 3
    assert all(not image.isNull() for image in gallery.groups_model.images.values())
    window.duplicates.mode.setCurrentIndex(1)
    gallery.setCurrentRow(1)
    pump(lambda: not window.controller.busy)
    state = (window.query, window.group_offset)
    window.activate_group(gallery.model().index(1))
    pump(lambda: window.duplicates_flow.comparing and not window.controller.busy)
    pump(lambda: window.comparison.left.state == 'preview_ready')
    assert not window.comparison.prepare.isEnabled()
    assert not window.comparison.left.details.toggle.isChecked()
    window.comparison.left.enlarge.click()
    assert window.comparison.left.enlarged is not None
    assert any(label.text() == tr('preview_note') for label in window.comparison.left.enlarged.findChildren(QLabel))
    window.comparison.left.enlarged.close()
    window.comparison.left.keep_photo.click()
    assert len(window.pending_pairs()) == 1 and window.comparison.prepare.isEnabled()
    window.comparison.both.click()
    assert not window.pending_pairs() and not window.comparison.prepare.isEnabled()
    assert all((collection / name).exists() for name in ('a.png', 'b.png', 'c.png'))
    window.back_to_duplicates()
    assert state == (window.query, window.group_offset)
    assert window.duplicates.mode.currentIndex() == 1 and not errors


def test_exact_multiple_keepers_pagination_and_no_default_move(desktop, collection):
    window, errors = desktop
    for name in ('c.png', 'd.png'):
        shutil.copy2(collection / 'a.png', collection / name)
    scan(window, collection)
    window.query = replace(window.query, limit=1)
    window.request_matches()
    pump(lambda: not window.controller.busy)
    window.duplicates.table.selectRow(0)
    window.comparison.right.keep_photo.click()  # b remains; a is proposed to move.
    first_keeper = window.controller.selection.match.dup.path
    window.change_page(1)
    pump(lambda: not window.controller.busy)
    window.duplicates.table.selectRow(0)
    window.comparison.right.keep_photo.click()  # c also remains.
    assert len(window.retained) == 2 and len(window.pending_pairs()) == 1
    assert window.pending_pairs()[0].keep.path == first_keeper
    window.prepare_selected()
    pump(lambda: window.plan_dialog is not None)
    assert len(window.plan_dialog.plan.moves) == 1
    assert window.plan_dialog.plan.moves[0].keeper.path == first_keeper
    window.keep_both()  # Rejects the open frozen plan, zero moves.
    assert window.plan_dialog is None and not window.pending_pairs()
    assert len(list(collection.glob('*.png'))) == 4 and not errors


def test_visual_selection_never_reanchors_a_chain(desktop, scanned):
    window, _ = desktop
    a, b = scanned.photos
    c = replace(b, path=str(Path(b.path).with_name('c.png')))
    rows = (MatchRow(101, 11, Match(Kind.VISUAL, a, b)),
            MatchRow(102, 12, Match(Kind.VISUAL, b, c)))
    window.duplicates.model.replace(rows)
    window.duplicates.table.selectRow(0)
    window.choose_keeper(False)
    assert window.pending_pairs() == (rows[0].match,)
    window.duplicates.table.selectRow(1)
    assert not window.pending_pairs()
    window.choose_keeper(True)
    assert window.pending_pairs() == (Match(Kind.VISUAL, c, b),)
    assert all(p.keep.path != a.path for p in window.pending_pairs())
    window.keep_both()
    assert not window.pending_pairs()


def test_confirmation_enter_is_not_approval_and_details_start_collapsed(qtapp, scanned):
    from app.safety.operations import make_plan
    plan = make_plan(scanned.pairs)
    dialog = PlanDialog(plan)
    dialog.show()
    try:
        assert not dialog.details.toggle.isChecked()
        for control in (dialog, dialog.confirm, dialog.raw):
            control.setFocus()
            QTest.keyClick(control, Qt.Key_Return)
            assert dialog.approval is None
        dialog.reject()
        assert dialog.approval is None
    finally:
        dialog.close()


def test_context_restore_targets_completed_operation_and_conflict_survives_restart(desktop, collection):
    window, errors = desktop
    scan(window, collection)
    window.duplicates.table.selectRow(0)
    window.compare()
    window.choose_keeper(False)
    window.prepare_selected()
    pump(lambda: window.plan_dialog is not None)
    operation = window.plan_dialog.plan.moves[0]
    window.plan_dialog.approve()
    pump(lambda: not window.controller.busy)
    assert window.restore_id == operation.id
    assert window.comparison.context_restore.isVisible()
    window.restore_context()
    pump(lambda: window.plan_dialog is not None)
    assert window.plan_dialog.plan.moves[0].restores == operation.id
    window.plan_dialog.reject()
    window.close()
    pump(lambda: window.finished)
    service = Application(window.home)
    service.initialize()
    try:
        source = Path(operation.source)
        source.write_bytes(b'occupied synthetic destination')
        with pytest.raises(SafetyError, match='destination_occupied'):
            service.restore_plan(Event(), operation_id=operation.id)
        assert source.read_bytes() == b'occupied synthetic destination'
        source.unlink()  # Only this test's collision fixture.
        plan = service.restore_plan(Event(), operation_id=operation.id)
        service.execute(plan, Approval(plan), Event())
        assert source.read_bytes() == (collection / 'a.png').read_bytes()
    finally:
        service.close()
    assert not errors


def test_group_samples_estimate_and_global_search_are_read_only(tmp_path, collection):
    service = Application(tmp_path / 'home')
    service.initialize()
    try:
        for name in ('c.png', 'd.png'):
            shutil.copy2(collection / 'a.png', collection / name)
        result = service.scan([str(collection)], None, Event())
        group = service.query_groups(result.session_id, MatchQuery(text='d.png', limit=1)).items[0]
        assert group.members == 4 and len(group.samples) == 2
        assert group.potential_bytes == (collection / 'a.png').stat().st_size * 3
        assert service.query_matches(result.session_id, MatchQuery(text='d.png')).total == 1
        assert len(list(collection.glob('*.png'))) == 4
    finally:
        service.close()


def test_preview_and_thumbnail_requests_coalesce_and_reject_stale(desktop, scanned, monkeypatch):
    window, _ = desktop
    entered, release = threading.Event(), threading.Event()

    def delayed(self, photo, cancel, size=2048):
        entered.set()
        release.wait(2)
        return QImage(16, 12, QImage.Format_RGB32)

    monkeypatch.setattr(PreviewService, 'get', delayed)
    thumbnail_requests, preview_requests, results = [], [], []
    window.controller.thumbnail_dispatch.connect(lambda *args: thumbnail_requests.append(args))
    window.controller.preview_dispatch.connect(lambda *args: preview_requests.append(args))
    window.controller.preview_ready.connect(results.append)
    row = MatchRow(1, 1, scanned.pairs[0])
    window.controller.thumbnails((row.match.keep,))
    pump(entered.is_set)
    for _ in range(50):
        window.controller.thumbnails((row.match.dup,))
        window.controller.preview(row)
    assert len(thumbnail_requests) == len(preview_requests) == 1
    assert window.controller.thumbnail_pending is not None
    assert window.controller.preview_pending is not None
    window.controller.preview(None)
    window.controller.thumbnails(())
    release.set()
    pump(lambda: not window.controller.thumbnail_active and not window.controller.preview_active)
    assert not results and len(thumbnail_requests) == len(preview_requests) == 1


def test_comparison_expands_group_beyond_search_and_back_restores_listing(desktop, collection):
    window, errors = desktop
    shutil.copy2(collection / 'a.png', collection / 'c.png')
    scan(window, collection)
    window.navigate(Route.DUPLICATES)
    window.duplicates.search.setText('b.png')
    pump(lambda: window.query.text == 'b.png' and not window.controller.busy)
    assert window.total == 1
    window.duplicates.table.selectRow(0)
    original = (window.query, window.selected_id, window.duplicates.model.rows)
    window.compare()
    pump(lambda: not window.controller.busy)
    assert window.total == 2 and window.query.keeper_id is not None
    assert len(window.duplicates.model.rows) == 2
    window.comparison.members.selectRow(1)
    window.choose_keeper(False)
    window.back_to_duplicates()
    assert original == (window.query, window.selected_id, window.duplicates.model.rows)
    assert window.duplicates.search.text() == 'b.png' and not errors


def test_empty_filter_loading_query_error_and_stale_states(desktop, collection):
    window, _ = desktop
    window.navigate(Route.DUPLICATES)
    assert window.duplicates.empty.text() == tr('no_session')
    assert not window.duplicates.results_panel.isVisible()
    scan(window, collection)
    window.duplicates.search.setText('nothing-matches')
    pump(lambda: window.query.text == 'nothing-matches' and not window.controller.busy)
    assert window.duplicates.empty.text() == tr('empty')
    assert not window.duplicates.results_panel.isVisible()
    window.request_matches()
    assert window.duplicates.empty.text() == tr('query_loading')
    pump(lambda: not window.controller.busy)
    # Invoke the real handler; desktop's general error recorder intentionally
    # suppresses message boxes for unrelated worker failures in regression tests.
    _real_window_error(window, 'groups', 'synthetic query failure')
    assert window.duplicates.empty.text() == tr('query_error', 'synthetic query failure')
    assert window.controller.selection is None
    window.result('dashboard', DashboardSummary(2, session_id=window.session,
        status='complete', started=1_700_000_000, exact=1, warnings=('stale_results',)))
    assert window.duplicates.warning.text() == tr('stale_results')


def test_late_group_response_does_not_navigate_after_leaving_duplicates(desktop, collection, monkeypatch):
    window, errors = desktop
    scan(window, collection)
    window.navigate(Route.DUPLICATES)
    original = Application.query_matches
    entered, release = threading.Event(), threading.Event()

    def delayed(self, *args):
        entered.set()
        assert release.wait(10)
        return original(self, *args)

    monkeypatch.setattr(Application, 'query_matches', delayed)
    try:
        window.activate_group(window.duplicates.groups.model().index(1))
        pump(entered.is_set)
        window.navigate(Route.SETTINGS)
        release.set()
        pump(lambda: not window.controller.busy)
        assert window.route == Route.SETTINGS and not window.duplicates_flow.comparing
        assert not window.open_group and window.plan_dialog is None and not errors
        assert (collection / 'a.png').read_bytes() == (collection / 'b.png').read_bytes()
    finally:
        release.set()
