"""Task009: real manifests, isolated synthetic moves and Qt settings/history."""
import json
from pathlib import Path
import shutil
from threading import Event

import pytest

pytest.importorskip('PySide6')
from PySide6.QtGui import QDesktopServices, QImage
from PySide6.QtWidgets import QMessageBox

from app import __version__
from app.core.models import Approval, SafetyError
from app.core.queries import HistoryEntry, MatchQuery, MatchingOptions, PageResult
from app.services.application import Application
from app.services.quarantine import quarantine_folder, quarantine_photo
from app.services.state import load_state
from app.ui.qt.navigation import Route
from app.ui.qt.quarantine_settings import MATCHING_PRESETS
from app.ui.qt.strings import SR, tr
from app.ui.qt.window import MainWindow
from tests.test_qt import desktop, pump, qtapp, scan, assert_toolbar_available
from tests.test_task003_services import service

_real_error = MainWindow.error


def quarantine(service, collection, *, copies=2):
    for i in range(2, copies):
        shutil.copy2(collection / 'a.png', collection / f'copy-{i}.png')
    summary = service.scan([str(collection)], None, Event())
    plan = service.prepare_session(summary.session_id, Event())
    service.execute(plan, Approval(plan), Event())
    return plan


def test_manifest_date_size_are_read_only_not_last_transition(service, collection):
    move = quarantine(service, collection).moves[0]
    first = service.history().items[0]
    service.journal.transition(move.id, 'complete', 'later observation')
    manifests = {p: p.read_bytes() for p in service.journal.directory.glob('*.json')}
    entry = service.history().items[0]
    assert first.moved_at == entry.moved_at == first.at
    assert entry.at != entry.moved_at and entry.size == move.expected.size
    assert entry.id == move.id and entry.restorable
    assert manifests == {p: p.read_bytes() for p in service.journal.directory.glob('*.json')}


def test_legacy_and_reconciled_move_do_not_invent_dates(service, collection):
    summary = service.scan([str(collection)], None, Event())
    move = service.prepare_session(summary.session_id, Event()).moves[0]
    Path(move.destination).parent.mkdir(parents=True)
    service.journal.begin(move)
    Path(move.source).rename(move.destination)  # Synthetic interrupted move.
    assert service.operations.recover() == []
    entry = service.history().items[0]
    assert entry.moved_at is None and entry.size == move.expected.size
    service.journal._save({'version': 1, 'id': 'a' * 32, 'state': 'legacy',
        'entry': {'origin': str(collection / 'legacy.png'), 'dest': move.destination},
        'transitions': [{'state': 'legacy', 'at': '2026-01-01', 'detail': ''}]})
    legacy = next(e for e in service.history().items if e.state == 'legacy')
    assert legacy.moved_at is None and legacy.size is None
    with pytest.raises(SafetyError, match='quarantine_preview_unavailable'):
        quarantine_photo(service.journal, legacy.id, Event())


def test_quarantine_preview_uses_fresh_destination_and_rejects_replacement(service, collection, qtapp):
    move = quarantine(service, collection).moves[0]
    photo = quarantine_photo(service.journal, move.id, Event())
    assert photo.path == move.destination and not Path(move.source).exists()
    assert photo.snapshot.sha256 == move.expected.sha256
    assert not service.history_preview(move.id, Event()).isNull()
    saved = Path(move.destination).with_suffix('.saved')
    Path(move.destination).rename(saved)
    shutil.copy2(saved, move.destination)  # Same bytes, wrong physical identity.
    with pytest.raises(SafetyError, match='quarantine_content_changed'):
        service.history_preview(move.id, Event())
    assert service.history().items[0].id == move.id


def test_folder_is_per_record_and_storage_reports_actual_fallback(service, collection, tmp_path):
    other = tmp_path / 'other-drive'
    other.mkdir()
    shutil.copy2(collection / 'a.png', other / 'copy.png')
    result = service.scan([str(collection), str(other)], None, Event())
    pairs = [r.match for r in service.query_matches(result.session_id, MatchQuery()).items]
    plan = service.prepare(pairs, Event(), session=result.session_id)
    service.execute(plan, Approval(plan), Event())
    assert {m.root for m in plan.moves} == {str(collection), str(other)}
    for move in plan.moves:
        assert quarantine_folder(service.journal, move.id) == Path(move.destination).parent
    with pytest.raises(SafetyError, match='no_restore_candidates'):
        quarantine_folder(service.journal, 'missing')
    service.close()
    # Corrupt synthetic DB is preserved; the actual active path is temporary.
    service.index_path.write_bytes(b'corrupt synthetic index')
    service.initialize()
    storage = service.storage_summary()
    assert storage.index_path == str(service.index.path) != str(service.index_path)
    assert storage.indexed == 0


def test_restore_selected_after_restart_collision_and_invalid_id(service, collection):
    plan = quarantine(service, collection, copies=3)
    expected = {m.id: Path(m.destination).read_bytes() for m in plan.moves}
    service.close()
    service.initialize()
    selected, other = plan.moves
    Path(selected.source).write_bytes(b'occupied original')
    with pytest.raises(SafetyError, match='destination_occupied'):
        service.restore_plan(Event(), operation_id=selected.id)
    assert Path(selected.source).read_bytes() == b'occupied original'
    assert Path(other.destination).read_bytes() == expected[other.id]
    with pytest.raises(SafetyError, match='no_restore_candidates'):
        service.restore_plan(Event(), operation_id='missing')
    restore = service.restore_plan(Event(), operation_id=other.id)
    assert restore.moves[0].restores == other.id
    service.execute(restore, Approval(restore), Event())
    assert Path(other.source).read_bytes() == expected[other.id]
    with pytest.raises(SafetyError, match='quarantine_preview_unavailable'):
        quarantine_photo(service.journal, other.id, Event())


@pytest.mark.parametrize('key', ['strict', 'balanced', 'broader'])
def test_matching_presets_persist_and_preserve_custom_legacy_extensions(service, tmp_path, key):
    roots = [str(tmp_path / 'z'), str(tmp_path / 'a')]
    legacy = [{'origin': str(tmp_path / 'z' / 'old.png'),
               'dest': str(tmp_path / 'z' / '.photo_agent_quarantine' / 'old.png')}]
    service.update_settings({'roots': roots, 'moves': legacy, 'extra': {'unknown': [1, 2]},
                             'phash_max': 13, 'dhash_max': 17})
    service.update_settings({'theme': 'system'})
    state = load_state(service.home / '.photo_agent_state.json')
    assert (state['phash_max'], state['dhash_max']) == (13, 17)
    options = MATCHING_PRESETS[key]
    assert MatchingOptions(options.phash_max, options.dhash_max) == options
    assert MATCHING_PRESETS['balanced'] == MatchingOptions(4, 6)
    service.update_settings({'phash_max': options.phash_max, 'dhash_max': options.dhash_max})
    service.close()
    _, state, _ = service.initialize()
    assert (state['phash_max'], state['dhash_max']) == (options.phash_max, options.dhash_max)
    assert state['roots'] == roots and state['moves'] == legacy and state['extra'] == {'unknown': [1, 2]}
    assert state['theme'] == 'system'


def test_history_selection_refresh_page_and_stale_preview_cannot_retarget(desktop, monkeypatch):
    window, errors = desktop
    entries = tuple(HistoryEntry(str(i), 'later', f'/synthetic/{i}.png', f'/synthetic/q/{i}.png',
                                'complete', '', True, 'first', 12) for i in range(3))
    requests = []
    monkeypatch.setattr(window.controller, 'request', lambda action, payload=None: requests.append((action, payload)))
    window.result('history', PageResult(entries[:2], 3))
    assert not window.history.restore.isEnabled()
    window.history.table.selectRow(1)
    window.restore()
    assert requests[-1] == ('restore', '1')
    window.result('history', PageResult(tuple(reversed(entries[:2])), 3))
    assert window.history.selected_entry.id == '1'
    window.restore()
    assert requests[-1] == ('restore', '1')
    image = QImage(8, 8, QImage.Format_RGB32)
    window.result('history_preview', ('0', image))
    assert window.history.thumbnail.pixmap().isNull()
    window.history_total = 201
    window.history_page(1)
    assert window.history.selected_entry is None and not window.history.restore.isEnabled()
    assert requests[-1][0] == 'history'
    window.result('history', PageResult((entries[2],), 201, 200))
    window.restore()
    assert requests[-1][0] != 'restore'
    window.history.table.selectRow(0)
    window.restore()
    assert requests[-1] == ('restore', '2') and not errors
    opened = []
    monkeypatch.setattr(QDesktopServices, 'openUrl', lambda url: opened.append(url.toLocalFile()) or True)
    window.open_quarantine_folder()
    assert requests[-1] == ('quarantine_folder', '2')
    window.result('quarantine_folder', ('1', '/synthetic/wrong-folder'))
    assert not opened
    window.result('quarantine_folder', ('2', '/synthetic/selected-folder'))
    assert opened == ['/synthetic/selected-folder']
    # An optional decode failure cannot authorize a move or disable preparation.
    _real_error(window, 'history_preview', 'decoder_timeout')
    assert window.history.restore.isEnabled() and window.history.selected_entry.id == '2'
    assert window.history.thumbnail.text() == tr('thumbnail_unavailable')


def test_history_real_preview_confirmation_restart_and_empty_failure(desktop, collection):
    window, errors = desktop
    window.navigate(Route.QUARANTINE)
    assert window.history.empty.isVisible() and not window.history.restore.isEnabled()
    scan(window, collection)
    window.prepare_bulk()
    pump(lambda: window.plan_dialog is not None)
    move = window.plan_dialog.plan.moves[0]
    expected = Path(move.source).read_bytes()
    window.plan_dialog.approve()
    pump(lambda: not window.controller.busy)
    window.close()
    pump(lambda: window.finished)
    other = MainWindow(window.home)
    other.show()
    try:
        pump(lambda: other.settings and not other.controller.busy)
        other.navigate(Route.QUARANTINE)
        other.history.table.selectRow(0)
        pump(lambda: not other.history.thumbnail.pixmap().isNull(), timeout=60)
        other.resize(853, 480)
        pump(lambda: other.pages[Route.QUARANTINE].horizontalScrollBar().maximum() == 0)
        assert other.history.selected_entry.id == move.id
        other.restore()
        pump(lambda: other.plan_dialog is not None)
        assert other.plan_dialog.plan.moves[0].restores == move.id
        assert not Path(move.source).exists()  # Preparation does not move.
        other.plan_dialog.approve()
        pump(lambda: not other.controller.busy)
        assert Path(move.source).read_bytes() == expected
        other.history.table.selectRow(0)
        assert not other.history.restore.isEnabled()
        _real_error(other, 'history', 'synthetic unavailable manifest')
        assert other.history.message.isVisible() and other.history.empty.isHidden()
        assert not other.history.restore.isEnabled()
        other.controller.request('history', MatchQuery(sort='time', descending=True))
        pump(lambda: not other.controller.busy)
        assert other.history_rows
    finally:
        other.close()
        pump(lambda: other.finished)
    assert not errors


def test_settings_sections_custom_theme_and_preset_restart(desktop, tmp_path):
    window, errors = desktop
    window.navigate(Route.SETTINGS)
    preferences = window.preferences
    preferences.load_matching(13, 17)
    assert preferences.preset.currentData() == 'custom' and preferences.advanced.toggle.isChecked()
    window.save_settings()
    pump(lambda: not window.controller.busy)
    preferences.theme.setCurrentIndex(preferences.theme.findData('light'))
    pump(lambda: not window.controller.busy)
    assert (preferences.phash.value(), preferences.dhash.value()) == (13, 17)
    assert window.dashboard.theme.currentData() == 'light'
    window.close()
    pump(lambda: window.finished)
    other = MainWindow(window.home)
    other.show()
    try:
        pump(lambda: other.settings and not other.controller.busy)
        assert other.preferences.preset.currentData() == 'custom' and other.theme.active == 'light'
        assert (other.preferences.phash.value(), other.preferences.dhash.value()) == (13, 17)
        other.preferences.preset.setCurrentIndex(other.preferences.preset.findData('balanced'))
        assert (other.preferences.phash.value(), other.preferences.dhash.value()) == (4, 6)
        other.save_settings()
        pump(lambda: not other.controller.busy)
        state = json.loads((other.home / '.photo_agent_state.json').read_text(encoding='utf-8'))
        assert (state['phash_max'], state['dhash_max']) == (4, 6)
        other.preferences.edit_sources.click()
        assert other.route == Route.SCAN
        assert __version__ == '2.5' and 'app_version' in SR
    finally:
        other.close()
        pump(lambda: other.finished)
    assert not errors


@pytest.mark.parametrize('theme', ['dark', 'light'])
def test_history_settings_errors_toolbar_and_unavailable_features(desktop, theme):
    window, _ = desktop
    window.theme.apply(theme)
    window.resize(853, 480)
    window.navigate(Route.SETTINGS)
    assert_toolbar_available(window, window.preferences.toolbar)
    assert window.preferences.language.currentData() == 'en'
    assert window.preferences.language.count() == 2
    assert '64 MiB' in tr('preview_cache_detail') and 'not calibrated' in tr('matching_explanation')
    window.navigate(Route.QUARANTINE)
    assert_toolbar_available(window, window.history.toolbar)
    _real_error(window, 'restore', 'destination_occupied')
    assert window.history.message.text() == tr('destination_occupied')
    for dialog in window.findChildren(QMessageBox):
        assert dialog.informativeText() == tr('destination_occupied')
        dialog.close()
    pump(lambda: not window.controller.busy)
