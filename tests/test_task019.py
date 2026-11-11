"""Recovery presentation uses stable IDs; synthetic workers retain all safety checks."""
from dataclasses import replace
import json
from pathlib import Path

import pytest

pytest.importorskip('PySide6')
from PySide6.QtCore import Qt
from PySide6.QtGui import QImage
from PySide6.QtWidgets import QApplication, QMessageBox

from app.core.queries import HistoryEntry, PageResult
from app.services.application import Application
from app.ui.qt.localization import language_manager
from app.ui.qt.navigation import Route
from app.ui.qt.quarantine_settings import HistoryScreen, MATCHING_PRESETS
from app.ui.qt.strings import tr
from app.ui.qt.window import MainWindow
from tests.test_qt import desktop, pump, qtapp, scan, assert_toolbar_available


_real_error = MainWindow.error


def entry(**patch):
    return replace(HistoryEntry('stable-id', '2026-11-11T10:00:00+00:00',
        '/synthetic/original/photo.png', '/synthetic/quarantine/moved.png',
        'complete', '', True, '2026-11-11T10:00:00+00:00', 1536), **patch)


@pytest.mark.parametrize('language', ['en', 'sr_Latn'])
@pytest.mark.parametrize('state,action,restored,problem,status', [
    ('complete', 'quarantine', False, '', 'history_quarantined'),
    ('complete', 'restore', False, '', 'history_restored'),
    ('complete', 'quarantine', True, '', 'state_restored'),
    ('blocked', 'restore', False, 'destination_occupied', 'state_blocked'),
    ('intent', 'quarantine', False, '', 'state_intent'),
    ('failed', 'quarantine', False, 'root_or_volume_changed', 'state_failed'),
])
def test_history_states_details_and_live_translation(qtapp, language, state, action, restored, problem, status):
    manager = language_manager()
    manager.set_language(language)
    screen = HistoryScreen(lambda: None, lambda _: None, lambda: None)
    screen.selection_changed.connect(screen.selection_details)
    item = entry(state=state, action=action, restored=restored, error=problem,
                 restorable=state == 'complete' and action == 'quarantine' and not restored)
    try:
        screen.show_page(PageResult((item,), 1))
        screen.table.selectRow(0)
        assert screen.table.columnCount() == 3
        assert screen.selected_entry.id == item.id
        assert tr(status) in screen.table.item(0, 2).text()
        assert item.id not in screen.selected_name.text()
        assert item.id in screen.details.text() and not screen.record_details.toggle.isChecked()
        assert item.destination in screen.details.text()
        assert tr('history_location_note') in screen.details.text()
        if problem:
            assert tr(problem) in screen.notice.text()
            assert tr(problem) in screen.table.item(0, 2).toolTip()
        if state in ('intent', 'blocked'):
            assert tr('recovery_required') in screen.notice.text()
        manager.set_language('sr_Latn' if language == 'en' else 'en')
        assert tr(status) in screen.selected_status.text()
        assert tr(status) in screen.table.item(0, 2).text()
        assert screen.selected_entry.id == item.id
        assert item.id in screen.details.text() and tr('history_location_note') in screen.details.text()
    finally:
        screen.deleteLater()
        QApplication.processEvents()
        manager.set_language('en')


def test_optional_preview_and_refresh_preserve_restore_target_and_visible_conflict(desktop, monkeypatch):
    window, errors = desktop
    window.navigate(Route.QUARANTINE)
    requests = []
    monkeypatch.setattr(window.controller, 'request', lambda action, payload=None: requests.append((action, payload)))
    items = (entry(), entry(id='other-id', source='/synthetic/other.png'))
    window.result('history', PageResult(items, 2))
    window.history.table.selectRow(0)
    _real_error(window, 'history_preview', 'root_or_volume_changed')
    assert window.history.restore.isEnabled()
    assert tr('root_or_volume_changed') in window.history.notice.text()
    window.restore()
    assert requests[-1] == ('restore', items[0].id)
    window.history.show_operation_error('destination_occupied')
    window.result('history', PageResult(tuple(reversed(items)), 2))
    assert window.history.selected_entry.id == items[0].id
    assert window.history.message.isVisible()
    assert window.history.message.text() == tr('destination_occupied')
    image = QImage(8, 8, QImage.Format_RGB32)
    window.result('history_preview', ('other-id', image))
    assert window.history.thumbnail.pixmap().isNull()
    assert window.history.selected_entry.id == items[0].id and not errors


@pytest.mark.parametrize('problem', ['conflict', 'offline'])
def test_real_restore_failure_after_restart_keeps_history_and_files(desktop, collection, problem):
    window, _ = desktop
    scan(window, collection)
    window.prepare_bulk()
    pump(lambda: window.plan_dialog is not None)
    plan = window.plan_dialog.plan
    moved = plan.moves[0]
    expected = Path(moved.source).read_bytes()
    window.plan_dialog.approve()
    pump(lambda: not window.controller.busy)
    window.close()
    pump(lambda: window.finished)
    if problem == 'conflict':
        Path(moved.source).write_bytes(b'synthetic occupied destination')
        quarantine_path = Path(moved.destination)
    else:
        offline = collection.with_name('synthetic-disconnected-drive')
        collection.rename(offline)
        quarantine_path = offline / Path(moved.destination).relative_to(collection)
    other = MainWindow(window.home)
    other.show()
    # The shared fixture records errors; connect the real presentation as well.
    other.controller.error.connect(lambda action, detail: _real_error(other, action, detail))
    try:
        pump(lambda: other.settings and not other.controller.busy)
        other.navigate(Route.QUARANTINE)
        other.history.table.selectRow(0)
        pump(lambda: 'history_preview' not in other.controller.latest or
             other.history.thumbnail.text() != tr('preview_loading'), timeout=60)
        other.restore()
        pump(lambda: other.history.operation_error and not other.controller.busy)
        assert other.plan_dialog is None  # Failed preparation cannot authorize a move.
        assert other.history.selected_entry.id == moved.id
        assert other.history.message.isVisible()
        if problem == 'conflict':
            assert other.history.message.text() == tr('destination_occupied')
            assert Path(moved.source).read_bytes() == b'synthetic occupied destination'
        else:
            assert not collection.exists()
            assert other.history.message.text() == tr('history_file_unavailable')
        assert quarantine_path.read_bytes() == expected
        assert other.history_rows and other.history.operation_error
    finally:
        for dialog in other.findChildren(QMessageBox):
            dialog.close()
        other.close()
        pump(lambda: other.finished)


@pytest.mark.parametrize('language', ['en', 'sr_Latn'])
@pytest.mark.parametrize('theme', ['dark', 'light'])
def test_five_settings_groups_small_layouts_and_custom_values(desktop, language, theme):
    window, errors = desktop
    manager = language_manager()
    manager.set_language(language)
    window.theme.apply(theme)
    preferences = window.preferences
    assert tuple(preferences.sections) == ('settings_appearance', 'settings_language',
        'settings_scanning', 'settings_safety', 'settings_storage')
    assert preferences.sections['settings_scanning'].isAncestorOf(preferences.preset)
    assert not preferences.safety_details.toggle.isChecked()
    assert not preferences.storage_details.toggle.isChecked()
    preferences.load_matching(13, 17)
    assert preferences.preset.currentData() == 'custom' and preferences.advanced.toggle.isChecked()
    for key, values in MATCHING_PRESETS.items():
        preferences.preset.setCurrentIndex(preferences.preset.findData(key))
        assert (preferences.phash.value(), preferences.dhash.value()) == (values.phash_max, values.dhash_max)
    preferences.preset.setCurrentIndex(preferences.preset.findData('custom'))
    assert preferences.advanced.toggle.isChecked()
    preferences.load_matching(13, 17)
    manager.set_language('sr_Latn' if language == 'en' else 'en')
    assert (preferences.phash.value(), preferences.dhash.value()) == (13, 17)
    try:
        for size in ((853, 480), (1440, 900)):
            window.resize(*size)
            for route in (Route.SETTINGS, Route.QUARANTINE):
                window.navigate(route)
                QApplication.processEvents()
                assert window.pages[route].horizontalScrollBar().maximum() == 0
                assert_toolbar_available(window, window.screens[route].toolbar)
    finally:
        manager.set_language('en')
    assert not errors


def test_failed_theme_save_rolls_back_to_latest_successful_queued_write(desktop, monkeypatch):
    window, errors = desktop
    window.navigate(Route.SETTINGS)
    original_update = Application.update_settings

    def fail_light(self, patch):
        if patch.get('theme') == 'light':
            raise OSError('synthetic settings disk failure')
        return original_update(self, patch)

    monkeypatch.setattr(Application, 'update_settings', fail_light)
    window.controller.error.connect(lambda action, detail: _real_error(window, action, detail))
    window.set_theme('system')
    window.set_theme('light')
    pump(lambda: not window.controller.busy and window.preferences.message.isVisible())
    stored = json.loads((window.home / '.photo_agent_state.json').read_text(encoding='utf-8'))
    assert stored['theme'] == window.settings['theme'] == 'system'
    assert window.theme.preference == 'system'
    assert window.preferences.theme.currentData() == window.dashboard.theme.currentData() == 'system'
    assert window.preferences.message.text() == tr('settings_save_failed')
    assert 'synthetic settings disk failure' in window.preferences.error_details.text.toPlainText()
    assert errors == [('settings', 'synthetic settings disk failure')]
    for dialog in window.findChildren(QMessageBox):
        dialog.close()
    window.set_theme('dark')
    pump(lambda: not window.controller.busy)
    assert window.preferences.message.isHidden()
    assert window.settings['theme'] == 'dark'
