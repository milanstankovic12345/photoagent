"""EN/SR localization with real Qt events and isolated synthetic state only."""
from dataclasses import replace
import ast
import json
import importlib.util
from pathlib import Path
from string import Formatter
from threading import Event

import pytest

from app.i18n import STRINGS, tr as shared_tr
from app.services.application import Application
from app.services.state import load_state, save_state, validated_settings

# Import capture/asyncio helpers before conftest replaces subprocess.Popen with
# its confinement guard; Windows asyncio subclasses the real Popen at import.
if importlib.util.find_spec('PySide6'):
    from tools.capture_task011 import RESOLUTIONS, inspect_layout


def test_catalog_parity_placeholders_and_literal_key_inventory():
    en, sr = STRINGS['en'], STRINGS['sr_Latn']
    assert set(en) == set(sr)
    for key in en:
        assert en[key].strip() and sr[key].strip()
        fields = lambda value: {field for _, field, _, _ in Formatter().parse(value) if field is not None}
        assert fields(en[key]) == fields(sr[key]), key
    root = Path(__file__).parents[1] / 'app/ui/qt'
    for path in root.glob('*.py'):
        for node in ast.walk(ast.parse(path.read_text(encoding='utf-8-sig'))):
            if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == 'tr'
                    and node.args and isinstance(node.args[0], ast.Constant)):
                assert node.args[0].value in en, (path, node.lineno)


def test_fallbacks_do_not_expose_keys_or_private_details(monkeypatch):
    assert shared_tr('ready', language='unknown') == STRINGS['en']['ready']
    monkeypatch.delitem(STRINGS['sr_Latn'], 'ready')
    assert shared_tr('ready') == STRINGS['en']['ready']
    assert shared_tr('unknown_internal_key', language='en') == STRINGS['en']['message_unavailable']
    assert shared_tr('metadata', language='en') == STRINGS['en']['message_unavailable']
    assert shared_tr('page', 1, 2, 3, language='en') == 'Rows 1–2 of 3'


def test_group_count_grammar_keeps_the_count_first():
    for count, noun in ((0, 'fotografija'), (1, 'fotografija'), (2, 'fotografije'),
                        (4, 'fotografije'), (5, 'fotografija'), (11, 'fotografija'),
                        (12, 'fotografija'), (14, 'fotografija'), (21, 'fotografija'),
                        (22, 'fotografije'), (25, 'fotografija'), (111, 'fotografija')):
        assert shared_tr('group_summary', count, 'EXACT', language='sr_Latn') == f'{count} {noun} · EXACT'
        assert shared_tr('group_summary', count, 'EXACT', language='en') == f'{count} photograph' + ('s' if count != 1 else '') + ' · EXACT'


@pytest.mark.parametrize('stored,expected', [(None, 'en'), ({}, 'sr_Latn'),
    ({'language': 'sr_Latn'}, 'sr_Latn'), ({'language': 'en'}, 'en'),
    ({'language': 'xx'}, 'en'), ({'language': None}, 'en'), ({'language': []}, 'en')])
def test_settings_migration_and_restart(tmp_path, stored, expected):
    path = tmp_path / 'settings.json'
    if stored is not None:
        save_state(path, {**stored, 'roots': ['/synthetic/library'], 'moves': [], 'extension': {'keep': 1}})
    value, warnings = validated_settings(load_state(path))
    assert value['language'] == expected
    assert bool(warnings) == (stored is not None and 'language' in stored and stored['language'] not in ('sr_Latn', 'en'))
    save_state(path, value)
    assert validated_settings(load_state(path))[0] == value
    if stored is not None:
        assert value['roots'] == ['/synthetic/library'] and value['extension'] == {'keep': 1}


# Pure catalog/settings tests above also run when Qt is unavailable.
@pytest.fixture
def desktop(qtapp, tmp_path):
    from app.ui.qt.window import MainWindow
    from tests.test_qt import pump
    from app.ui.qt.localization import language_manager
    language_manager().set_language('en')
    window = MainWindow(tmp_path / 'home')
    window.show()
    try:
        pump(lambda: window.settings and not window.controller.busy)
        yield window
    finally:
        window.close()
        pump(lambda: window.finished)
        window.deleteLater()
        qtapp.processEvents()
        language_manager().set_language('en')


@pytest.fixture
def qtapp():
    pytest.importorskip('PySide6')
    # Use the project's font setup and real event loop fixture.
    from tests.test_qt import qtapp as qt_fixture
    yield from qt_fixture.__wrapped__()


def choose_language(window, language):
    window.preferences.language.setCurrentIndex(window.preferences.language.findData(language))


def test_live_pages_filters_models_previews_and_restart(desktop, collection):
    from PySide6.QtCore import Qt
    from app.ui.qt.strings import tr
    from app.ui.qt.navigation import Route
    from app.ui.qt.window import MainWindow
    from tests.test_qt import scan, pump
    window = desktop
    assert window.settings['language'] == 'en'
    scan(window, collection)
    window.navigate(Route.DUPLICATES)
    window.duplicates.table.selectRow(0)
    window.compare()
    window.comparison.left.keep_photo.click()
    pump(lambda: bool(window.comparison.left.scene.items()))
    window.comparison.left.zoom(1.25)
    window.comparison.left.show_enlarged()
    selected, query = window.selected_id, window.query
    choice, pixmap = window.controller.selection, window.comparison.left.scene.items()[0].pixmap().cacheKey()
    window.comparison.left.details.set_expanded(True)
    for language in ('sr_Latn', 'en', 'sr_Latn'):
        choose_language(window, language)
        assert window.controller.selection == choice and window.selected_id == selected and window.query == query
        assert window.comparison.left.keep_photo.isChecked()
        assert window.comparison.left.details.toggle.isChecked()
        assert window.comparison.left.scene.items()[0].pixmap().cacheKey() == pixmap
        assert window.comparison.left.enlarged.windowTitle() == tr('enlarge_preview')
        assert window.comparison.left.keep_photo.text() == tr('keep_chosen')
        assert window.comparison.left.view.accessibleName() == tr('left_preview')
        assert window.duplicates.kind.itemText(1) == tr('filter_EXACT')
        assert window.duplicates.kind.itemData(1) == 'EXACT'
        assert window.duplicates.model.headerData(0, Qt.Horizontal) == tr('name')
        assert window.navigation.buttons[Route.SCAN].accessibleName() == tr('scan')
        assert window.scan.roots.item(0).data(Qt.AccessibleTextRole).endswith(tr('available'))
        assert tr('filter_EXACT') == window.duplicates.model.data(window.duplicates.model.index(0, 1))
        assert tr('recent_scan_summary', 0, 0, 0, 0, 0, 0).split('\n')[1].split(':')[0] in window.dashboard.session.text()
    pump(lambda: not window.controller.busy)
    assert json.loads((window.home / '.photo_agent_state.json').read_text(encoding='utf-8'))['language'] == 'sr_Latn'
    window.close()
    pump(lambda: window.finished)
    restarted = MainWindow(window.home)
    try:
        restarted.show()
        pump(lambda: restarted.settings and not restarted.controller.busy)
        assert restarted.settings['language'] == 'sr_Latn'
        assert restarted.preferences.language.currentData() == 'sr_Latn'
        assert restarted.scan.start.text() == tr('start')
    finally:
        restarted.close()
        pump(lambda: restarted.finished)


def test_open_confirmation_keeps_frozen_plan_and_raw_consents(desktop, scanned):
    from PySide6.QtWidgets import QPlainTextEdit
    from app.safety.operations import make_plan
    from app.ui.qt.strings import tr
    from tests.test_qt import pump
    window = desktop
    plan = make_plan(scanned.pairs)
    plan = replace(plan, moves=(replace(plan.moves[0], raw=True, legacy=True),))
    requests = []
    window.controller.dispatch.connect(lambda _id, action, *_: requests.append(action))
    window.confirm(plan)
    dialog = window.plan_dialog
    dialog.raw.setText('RA')
    dialog.legacy.setChecked(True)
    epoch = window.operation_epoch
    for language in ('sr_Latn', 'en'):
        choose_language(window, language)
        assert dialog is window.plan_dialog and dialog.plan is plan
        assert dialog.approval is None and not dialog.confirm.isEnabled()
        assert dialog.raw.text() == 'RA' and dialog.legacy.isChecked()
        assert dialog.raw.placeholderText() == tr('raw_prompt')
        assert tr('move_summary', plan.moves[0].source, plan.moves[0].destination, plan.moves[0].keeper.path) in dialog.findChildren(QPlainTextEdit)[0].toPlainText()
        assert window.operation_epoch == epoch and 'execute' not in requests
    dialog.raw.setText('RAW')
    assert dialog.confirm.isEnabled() and dialog.approval is None
    choose_language(window, 'sr_Latn')
    assert dialog.raw.text() == 'RAW' and dialog.confirm.isEnabled() and dialog.approval is None
    dialog.reject()
    pump(lambda: not window.controller.busy)
    assert all(Path(photo.path).exists() for photo in (scanned.pairs[0].keep, scanned.pairs[0].dup))


def test_language_switch_during_scan_is_immediate_and_does_not_cancel(desktop, collection, monkeypatch):
    import app.services.indexing as indexing
    from app.ui.qt.strings import tr
    from tests.test_qt import pump
    window = desktop
    original, entered, release = indexing.extract, Event(), Event()
    def delayed(*args, **kwargs):
        entered.set()
        assert release.wait(20)
        return original(*args, **kwargs)
    monkeypatch.setattr(indexing, 'extract', delayed)
    window.roots = [str(collection)]
    window.render_roots()
    window.start_scan()
    try:
        pump(entered.is_set)
        started = window.scan.started
        choose_language(window, 'sr_Latn')
        assert window.scan_active and window.scan.started == started
        assert window.scan.timer.isActive() and not window.controller.cancel_event.is_set()
        assert window.scan.start.text() == tr('start')
        assert window.preferences.language.currentData() == 'sr_Latn'
    finally:
        release.set()
    pump(lambda: window.session and not window.controller.busy, timeout=90)
    assert window.status == 'complete' and window.settings['language'] == 'sr_Latn'
    assert window.scan.status.text() == tr('scan_result_summary', tr('state_complete'), 2, 1, 0, 0)


def test_failed_language_save_rolls_back_without_approval(desktop, scanned, monkeypatch):
    from app.safety.operations import make_plan
    from app.services.application import Application
    from app.ui.qt.strings import tr
    from tests.test_qt import pump
    window = desktop
    window.confirm(make_plan(scanned.pairs))
    dialog = window.plan_dialog
    original = Application.update_settings
    def failed(self, patch):
        if 'language' in patch:
            raise OSError('synthetic settings disk failure')
        return original(self, patch)
    monkeypatch.setattr(Application, 'update_settings', failed)
    choose_language(window, 'sr_Latn')
    pump(lambda: not window.controller.busy)
    assert window.preferences.language.currentData() == 'en'
    assert window.settings['language'] == 'en'
    assert window.statusBar().currentMessage() == tr('language_save_failed')
    assert window.plan_dialog is dialog and dialog.approval is None
    dialog.reject()


def test_history_and_error_dialog_retranslate_in_place(desktop, collection):
    from PySide6.QtWidgets import QMessageBox
    from app.ui.qt.navigation import Route
    from app.ui.qt.strings import tr
    from tests.test_qt import scan, pump
    window = desktop
    scan(window, collection)
    window.duplicates.table.selectRow(0)
    window.comparison.left.keep_photo.click()
    window.prepare_selected()
    pump(lambda: window.plan_dialog is not None)
    window.plan_dialog.approve()
    pump(lambda: not window.controller.busy)
    window.navigate(Route.QUARANTINE)
    window.history.table.selectRow(0)
    selected = window.history.selected_entry.id
    window.show_error('destination_occupied: synthetic details')
    box = window.findChildren(QMessageBox)[0]
    choose_language(window, 'sr_Latn')
    assert window.history.selected_entry.id == selected
    assert window.history.table.item(0, 2).text() == tr('history_quarantined')
    assert window.history.table.horizontalHeaderItem(2).text() == tr('state')
    assert box.informativeText() == tr('destination_occupied')
    assert box.detailedText() == 'destination_occupied: synthetic details'
    assert box.button(QMessageBox.Close).text() == tr('close')
    box.close()
    pump(lambda: not window.controller.busy)


def test_fast_switch_failure_restores_last_successful_write(desktop, monkeypatch):
    from tests.test_qt import pump
    window = desktop
    original = Application.update_settings
    def fail_english(self, patch):
        if patch.get('language') == 'en':
            raise OSError('synthetic second write failure')
        return original(self, patch)
    monkeypatch.setattr(Application, 'update_settings', fail_english)
    choose_language(window, 'sr_Latn')
    choose_language(window, 'en')
    pump(lambda: not window.controller.busy)
    assert window.settings['language'] == window.preferences.language.currentData() == 'sr_Latn'
    assert json.loads((window.home / '.photo_agent_state.json').read_text(encoding='utf-8'))['language'] == 'sr_Latn'


def test_framework_directory_picker_and_context_menu(desktop, tmp_path):
    from PySide6.QtCore import QLocale
    from PySide6.QtWidgets import QFileDialog, QLabel, QLineEdit, QDialogButtonBox
    from app.ui.qt.strings import tr
    window = desktop
    window.add_root()
    dialog = window.findChild(QFileDialog)
    entry = dialog.findChild(QLineEdit, 'fileNameEdit')
    entry.setText('synthetic folder choice')
    try:
        for language in ('sr_Latn', 'en'):
            choose_language(window, language)
            from PySide6.QtWidgets import QApplication
            QApplication.processEvents()
            assert dialog.windowTitle() == tr('add')
            assert dialog.testOption(QFileDialog.ReadOnly)
            assert entry.text() == 'synthetic folder choice'
            assert Path(dialog.directory().absolutePath()) == window.home
            assert dialog.locale().language() == (QLocale.Serbian if language == 'sr_Latn' else QLocale.English)
            assert any(label.text() == tr('file_look_in') for label in dialog.findChildren(QLabel))
            assert any(button.text().replace('&', '') == tr('file_cancel') for button in dialog.findChild(QDialogButtonBox).buttons())
            line = QLineEdit(dialog)
            menu = line.createStandardContextMenu()
            try:
                assert any(action.text().split('\t')[0].replace('&', '') == tr('qt_paste') for action in menu.actions())
            finally:
                menu.deleteLater()
    finally:
        dialog.close()


def test_index_warning_is_localized_with_separate_technical_details(desktop):
    from app.core.queries import DashboardSummary
    from app.ui.qt.strings import tr
    window = desktop
    detail = 'index_temporary: synthetic index disk failure'
    window.dashboard.set_summary(DashboardSummary(0, warnings=(detail,)))
    choose_language(window, 'sr_Latn')
    assert window.dashboard.warning.text() == tr('index_temporary')
    assert window.dashboard.warning.toolTip() == ''
    assert window.dashboard.warning_details.text.toPlainText() == detail
    assert not window.dashboard.warning_details.toggle.isChecked()


@pytest.mark.parametrize('theme', ('dark', 'light'))
@pytest.mark.parametrize('language', ('en', 'sr_Latn'))
def test_localized_geometry_at_target_sizes(desktop, scanned, theme, language):
    import os
    from PySide6.QtWidgets import QApplication
    from app.core.queries import MatchRow
    from app.ui.qt.navigation import Route
    from tests.test_qt import pump
    window = desktop
    choose_language(window, language)
    pump(lambda: not window.controller.busy)
    window.theme.apply(theme)
    window.status = 'complete'
    window.duplicates.model.replace((MatchRow(1, 1, scanned.pairs[0]),))
    window.duplicates.set_state('', True)
    scale = float(os.environ.get('QT_SCALE_FACTOR', '1'))
    for width, height in RESOLUTIONS:
        window.resize(round(width / scale), round(height / scale))
        assert window.grab().devicePixelRatio() == pytest.approx(scale)
        for route in Route:
            window.duplicates_flow.show_comparison(False)
            window.navigate(route)
            QApplication.processEvents()
            layout = inspect_layout(window)
            assert not layout['page_horizontal_max'], (language, theme, route, width, layout)
            assert not layout['toolbar_outside'] and not layout['toolbar_overlaps'], layout
        window.navigate(Route.DUPLICATES)
        window.duplicates.table.selectRow(0)
        window.compare()
        pump(lambda: bool(window.comparison.left.scene.items()))
        QApplication.processEvents()
        layout = inspect_layout(window)
        assert not layout['page_horizontal_max'], (language, theme, width, layout)
        assert not layout['toolbar_outside'] and not layout['toolbar_overlaps'], layout
