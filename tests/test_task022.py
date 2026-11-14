"""Task022 wording and live EN/SR state preservation; synthetic files only."""
from dataclasses import replace
import json
from pathlib import Path

import pytest

from app.i18n import STRINGS
# Import Windows asyncio helpers before conftest's subprocess confinement guard.
from tests.test_task012 import choose_language


def test_text_inventory_matches_authoritative_catalog():
    from tools.build_translations import source_catalogs
    root = Path(__file__).resolve().parents[1]
    inventory = json.loads((root / 'docs/design/QT_TEXT_INVENTORY.json').read_text(encoding='utf-8'))
    assert inventory['english_intents'] == source_catalogs(root / 'app/i18n')['en']


@pytest.mark.parametrize('language,expected', [
    ('en', ('Add Folder', 'Start Scan', 'Review Duplicates', 'Keep This Photo',
            'Keep Both', 'Move to Quarantine', 'Open in Default Viewer',
            'Show Details', 'Hide Details', 'Restore Photo', 'View Scan Errors')),
    ('sr_Latn', ('Dodaj folder', 'Pokreni skeniranje', 'Pregledaj duplikate',
                 'Zadrži ovu fotografiju', 'Zadrži obe', 'Premesti u karantin',
                 'Otvori u podrazumevanom pregledniku', 'Prikaži detalje',
                 'Sakrij detalje', 'Vrati fotografiju', 'Prikaži greške skeniranja'))])
def test_consistent_action_vocabulary(language, expected):
    catalog = STRINGS[language]
    keys = ('add_folder', 'start', 'review_duplicates', 'keep_photo', 'keep_both',
            'move_copy', 'open_default_viewer', 'show_details', 'hide_details', 'restore', 'errors')
    assert tuple(catalog[key] for key in keys) == expected
    assert catalog['add'] == catalog['add_folder']
    assert catalog['review_results'] == catalog['review_duplicates']
    assert catalog['restore_operation'] == catalog['restore']


# The pure catalog tests above remain runnable without Qt.
@pytest.fixture
def desktop(qtapp, tmp_path, monkeypatch):
    from tests.test_qt import desktop as fixture
    yield from fixture.__wrapped__(qtapp, tmp_path, monkeypatch)


@pytest.fixture
def qtapp():
    pytest.importorskip('PySide6')
    from tests.test_qt import qtapp as fixture
    from app.ui.qt.localization import language_manager
    yield from fixture.__wrapped__()
    language_manager().set_language('en')


@pytest.mark.parametrize('theme', ['dark', 'light'])
def test_live_comparison_and_collapsed_sidebar_keep_context_and_focus(desktop, collection, theme):
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication
    from app.ui.qt.localization import language_manager
    from app.ui.qt.navigation import Route
    from app.ui.qt.strings import tr
    from tests.test_qt import scan
    from tests.test_task020 import open_review
    window, errors = desktop
    scan(window, collection)
    open_review(window)
    window.theme.apply(theme)
    window.navigation.set_collapsed(True, animate=False)
    window.choose_keeper(False)
    left = window.comparison.left
    left.zoom(1.25)
    before = (window.selected_id, window.query, window.controller.selection,
              window.pending_pairs(), window.operation_epoch, left.view.transform())
    original = {p: p.read_bytes() for p in collection.iterdir()}
    for language in ('sr_Latn', 'en'):
        window.activateWindow()
        left.details.toggle.setFocus()
        choose_language(window, language)
        QApplication.processEvents()
        assert QApplication.focusWidget() is left.details.toggle
        assert (window.selected_id, window.query, window.controller.selection,
                window.pending_pairs(), window.operation_epoch, left.view.transform()) == before
        assert left.details.toggle.text() == left.details.toggle.accessibleName() == tr('show_details')
        QTest.keyClick(left.details.toggle, Qt.Key_Space)
        assert left.details.toggle.text() == left.details.toggle.accessibleName() == tr('hide_details')
        # The expanded state and action label also survive retranslation.
        language_manager().set_language('en' if language == 'sr_Latn' else 'sr_Latn')
        assert left.details.toggle.isChecked() and left.details.toggle.text() == tr('hide_details')
        language_manager().set_language(language)
        QTest.keyClick(left.details.toggle, Qt.Key_Space)
        assert window.comparison.prepare.toolTip() == tr('quarantine_description_action')
        assert window.comparison.both.accessibleDescription() == tr('keep_both_description')
        for route, control in window.navigation.buttons.items():
            assert control.text() == ''
            assert control.toolTip() == control.accessibleName() == tr(route.value)
        assert window.navigation.buttons[Route.DUPLICATES].isChecked()
        assert not window.plan_dialog
    assert {p: p.read_bytes() for p in collection.iterdir()} == original
    assert not errors


def test_confirmation_language_changes_preserve_raw_legacy_consent_and_focus(desktop, scanned):
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication
    from app.safety.operations import make_plan
    from app.ui.qt.strings import tr
    from tests.test_qt import pump
    window, errors = desktop
    base = make_plan(scanned.pairs)
    # Presentation-only RAW/legacy flags; this plan is never approved or executed.
    plan = replace(base, moves=(replace(base.moves[0], raw=True, legacy=True),))
    original = {Path(p.path): Path(p.path).read_bytes() for p in scanned.photos}
    dispatches = []
    window.controller.dispatch.connect(lambda _id, action, *_: dispatches.append(action))
    window.confirm(plan)
    dialog = window.plan_dialog
    QTest.qWait(30)  # Allow the initial safe Cancel focus to settle.
    dialog.raw.setText('RAW')
    dialog.legacy.setChecked(True)
    dialog.raw.setFocus()
    for language in ('sr_Latn', 'en'):
        choose_language(window, language)
        QApplication.processEvents()
        assert QApplication.focusWidget() is dialog.raw
        assert window.plan_dialog is dialog and dialog.plan is plan
        assert dialog.approval is None and dialog.confirm.isEnabled()
        assert dialog.raw.text() == 'RAW' and dialog.legacy.isChecked()
        assert dialog.confirm.text() == tr('approve')
        assert dialog.confirm.accessibleDescription() == dialog.confirm.toolTip() == tr('confirm_plan_help')
        assert 'RAW' in dialog.raw.placeholderText()
        assert tr('raw_warning') in dialog.warnings.text()
        assert tr('legacy_warning') in dialog.warnings.text()
        assert 'execute' not in dispatches
    dialog.reject()
    pump(lambda: not window.controller.busy)
    assert {path: path.read_bytes() for path in original} == original
    assert not errors


def test_restore_plan_and_results_describe_the_actual_action(desktop, collection):
    from PySide6.QtWidgets import QLabel, QPlainTextEdit
    from app.ui.qt.strings import tr
    from tests.test_qt import scan, pump
    window, errors = desktop
    original = {p: p.read_bytes() for p in collection.iterdir()}
    scan(window, collection)
    window.prepare_bulk()
    pump(lambda: window.plan_dialog is not None)
    window.plan_dialog.approve()
    pump(lambda: not window.controller.busy)
    assert window.statusBar().currentMessage() == tr('operation_count', 1)
    window.restore_context()
    pump(lambda: window.plan_dialog is not None)
    dialog = window.plan_dialog
    plan = dialog.plan
    for language in ('sr_Latn', 'en'):
        choose_language(window, language)
        assert dialog.plan is plan and dialog.approval is None
        assert any(label.text() == tr('restore_plan_summary', 1) for label in dialog.findChildren(QLabel))
        move = plan.moves[0]
        assert dialog.findChildren(QPlainTextEdit)[0].toPlainText() == tr(
            'restore_move_summary', move.source, move.destination)
    dialog.approve()
    pump(lambda: not window.controller.busy)
    assert window.statusBar().currentMessage() == tr('restore_count', 1)
    choose_language(window, 'sr_Latn')
    assert window.statusBar().currentMessage() == tr('restore_count', 1)
    assert {p: p.read_bytes() for p in collection.iterdir() if p.is_file()} == original
    assert not errors


def test_external_open_error_translates_without_losing_details_or_focus(desktop):
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication, QMessageBox, QTextEdit
    from app.ui.qt.strings import tr
    window, errors = desktop
    literal = 'photo_launch_failed: C:/synthetic/čćžšđ/照片.nef · SHA-256: 0123456789'
    window.show_error(literal)
    dialog = window.findChild(QMessageBox)
    QTest.qWait(30)
    toggle = next(b for b in dialog.buttons() if dialog.buttonRole(b) == QMessageBox.ActionRole)
    toggle.click()
    toggle.setFocus()
    for language in ('sr_Latn', 'en'):
        choose_language(window, language)
        QApplication.processEvents()
        assert dialog.informativeText() == tr('photo_launch_failed')
        assert dialog.detailedText() == literal
        assert any(editor.isVisible() for editor in dialog.findChildren(QTextEdit))
        assert toggle.text() == toggle.accessibleName() == tr('hide_details')
        assert QApplication.focusWidget() is toggle
        assert not window.pending_pairs() and window.plan_dialog is None
    dialog.close()
    assert not errors
