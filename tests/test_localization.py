"""v2.5 translation sources, compiled resources, formatting and Unicode workflows."""
import ast
import json
from pathlib import Path
import shutil
import subprocess
import sys
from zipfile import ZipFile

import pytest

from app.i18n import STRINGS
from tools.build_translations import build as check_translations, source_catalogs
from tests.test_task012 import desktop, qtapp, choose_language
from tests.test_task013 import bundle_inputs

ROOT = Path(__file__).resolve().parents[1]


def test_editable_sources_match_runtime_catalogs_and_all_explicit_safety_errors():
    assert source_catalogs(ROOT / 'app/i18n') == STRINGS
    assert check_translations(check=True) == {language: len(catalog) for language, catalog in STRINGS.items()}
    # A new explicit safety error must have a readable translation in both languages.
    for path in (ROOT / 'app').rglob('*.py'):
        if 'ui' in path.parts:
            continue
        for node in ast.walk(ast.parse(path.read_text(encoding='utf-8-sig'))):
            if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                    and node.func.id == 'SafetyError' and node.args
                    and isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str)):
                key = node.args[0].value.split(':', 1)[0]
                assert all(key in catalog for catalog in STRINGS.values()), (path, key)


@pytest.mark.parametrize('defect', ('unfinished', 'placeholder', 'missing', 'json'))
def test_build_rejects_incomplete_or_stale_resources(tmp_path, defect):
    import xml.etree.ElementTree as ET
    for extension in ('ts', 'json'):
        for language in STRINGS:
            shutil.copyfile(ROOT / f'app/i18n/{language}.{extension}', tmp_path / f'{language}.{extension}')
    path = tmp_path / 'sr_Latn.ts'
    tree = ET.parse(path)
    context = tree.getroot().find('context')
    message = context.find('message')
    if defect == 'unfinished':
        message.find('translation').set('type', 'unfinished')
    elif defect == 'placeholder':
        message.find('translation').text += ' {99}'
    elif defect == 'missing':
        context.remove(message)
    else:
        (tmp_path / 'en.json').write_text('{}', encoding='utf-8')
    tree.write(path, encoding='utf-8', xml_declaration=True)
    with pytest.raises(ValueError):
        check_translations(tmp_path, check=True)


def test_compiled_qt_catalog_coverage_and_missing_resource_fallback(qtapp, monkeypatch):
    from PySide6.QtCore import QCoreApplication
    from app.ui.qt.localization import language_manager
    from app.ui.qt.qt_translations import QT_KEYS
    from app.ui.qt.strings import tr
    manager = language_manager()
    for language, expected in STRINGS.items():
        manager.set_language(language)
        catalog = manager.catalogs[language]
        assert all(catalog.translate('PhotoAgent', key) == value for key, value in expected.items())
        assert QCoreApplication.translate('PhotoAgent', 'ready') == expected['ready']
        for context, mapping in QT_KEYS.items():
            for source, key in mapping.items():
                assert QCoreApplication.translate(context, source) == expected[key]
    # Missing compiled resource and missing compiled key both use the JSON fallback.
    monkeypatch.delitem(manager.catalogs, 'sr_Latn')
    manager.set_language('sr_Latn')
    assert tr('xmp_warning') == STRINGS['sr_Latn']['xmp_warning']
    assert tr('unknown_internal_key') == STRINGS['sr_Latn']['message_unavailable']
    manager.set_language('en')


def test_locale_values_reformat_open_widgets_and_preserve_literals(desktop):
    from PySide6.QtWidgets import QLabel
    from app.core.queries import DashboardSummary
    from app.ui.qt.formatting import date_text, number_text, size_text
    from app.ui.qt.localization import set_text
    from app.ui.qt.strings import tr
    window = desktop
    literal = 'C:/Fotografije/čćžšđ/ready/Фото/照片.png'
    label = QLabel(window)
    set_text(label, tr('photo_summary', literal, 'PNG', 128, 96, size_text(1536)))
    summary = DashboardSummary(1234, 'synthetic', 'complete', 1794222000,
                               potential_bytes=1536, exact_groups=1234)
    window.dashboard.set_summary(summary)
    for language, amount, count in (('sr_Latn', '1,5 KiB', '1.234'), ('en', '1.5 KiB', '1,234')):
        choose_language(window, language)
        assert amount in label.text() and literal in label.text()
        assert window.dashboard.stat_cards[0].value.text() == count
        assert window.dashboard.stat_cards[3].value.text() == count
        assert date_text(summary.started) in window.dashboard.session.text()
        assert str(number_text(1234)) == count
        assert summary.indexed == 1234 and summary.potential_bytes == 1536


def test_history_date_formats_supported_iso_values_in_utc(qtapp):
    from app.ui.qt.quarantine_settings import move_date
    from app.ui.qt.localization import language_manager
    # Accept the same ISO variants as before; presentation must retain UTC.
    for language in STRINGS:
        language_manager().set_language(language)
        expected = move_date('2026-11-09T12:30:00.123456+00:00')
        assert expected.endswith('12:30:00 UTC')
        assert move_date('2026-11-09 13:30:00.123456+01:00') == expected
        assert move_date('2026-11-09T12:30:00') == STRINGS[language]['not_available']
        assert move_date('invalid') == STRINGS[language]['not_available']
    language_manager().set_language('en')


def test_unicode_scan_confirmation_quarantine_and_restore(desktop, collection):
    from PySide6.QtWidgets import QPlainTextEdit
    from app.ui.qt.strings import tr
    from tests.test_qt import pump, scan
    window = desktop
    unicode_root = collection.with_name('Fotografije-čćžšđ-照片')
    collection.rename(unicode_root)
    (unicode_root / 'a.png').rename(unicode_root / 'Izvornik-đ-Фото.png')
    (unicode_root / 'b.png').rename(unicode_root / 'Kopija-ć-照片.png')
    before = {path: path.read_bytes() for path in unicode_root.iterdir()}
    scan(window, unicode_root)
    window.duplicates.table.selectRow(0)
    window.comparison.left.keep_photo.click()
    window.prepare_selected()
    pump(lambda: window.plan_dialog is not None)
    dialog = window.plan_dialog
    plan = dialog.plan
    for language in ('sr_Latn', 'en'):
        choose_language(window, language)
        assert dialog.plan is plan and dialog.approval is None
        assert all(path.exists() for path in before)
        assert str(unicode_root) in dialog.findChildren(QPlainTextEdit)[0].toPlainText()
        assert dialog.cancel.text() == tr('cancel')
        assert tr('xmp_warning') not in dialog.warnings.text()
    dialog.approve()
    pump(lambda: not window.controller.busy)
    moved = plan.moves[0]
    assert Path(moved.destination).read_bytes() == before[Path(moved.source)]
    window.restore_context()
    pump(lambda: window.plan_dialog is not None)
    restore_dialog = window.plan_dialog
    assert restore_dialog.plan.moves[0].keeper is None
    choose_language(window, 'sr_Latn')
    assert restore_dialog.approval is None
    assert tr('restore_original') in restore_dialog.findChildren(QPlainTextEdit)[0].toPlainText()
    restore_dialog.approve()
    pump(lambda: not window.controller.busy)
    assert all(path.read_bytes() == data for path, data in before.items())
    assert json.loads((window.home / '.photo_agent_state.json').read_text(encoding='utf-8'))['language'] == 'sr_Latn'
    assert window.preferences.language.currentData() == 'sr_Latn'


def test_embedded_translations_load_from_isolated_packaged_tree(bundle_inputs, tmp_path):
    pytest.importorskip('PySide6')
    from tools.build_release import build
    source, lock, wheels = bundle_inputs
    for original in (ROOT / 'app/i18n').iterdir():
        if original.is_file():
            shutil.copyfile(original, source / 'app/i18n' / original.name)
    archive_path = tmp_path / 'local-candidate.zip'
    build(wheels, lock, archive_path, source=source)
    extracted = tmp_path / 'paket-čćž-照片'
    with ZipFile(archive_path) as archive:
        for language in STRINGS:
            assert f'app/i18n/{language}.ts' in archive.namelist()
            assert f'app/i18n/{language}.qm' in archive.namelist()
        archive.extractall(extracted)  # This test's own allowlisted synthetic archive.
    # Isolated Python cannot find the repository; it imports only the packaged resource.
    code = '''
import importlib.util, json, pathlib, sys
from PySide6.QtCore import QCoreApplication, QTranslator
application = QCoreApplication([])
root = pathlib.Path(sys.argv[1]) / 'app/i18n'
spec = importlib.util.spec_from_file_location('bundle_translations', root / 'resources_rc.py')
resource = importlib.util.module_from_spec(spec)
spec.loader.exec_module(resource)
for language in ('en', 'sr_Latn'):
    catalog = QTranslator()
    assert catalog.load(':/photoagent/i18n/' + language + '.qm')
    expected = json.loads((root / (language + '.json')).read_text(encoding='utf-8'))
    assert all(catalog.translate('PhotoAgent', key) == value for key, value in expected.items())
print('Isolated packaged EN/SR resources verified')
'''
    result = subprocess.run([sys.executable, '-I', '-B', '-c', code, str(extracted)],
                            cwd=tmp_path, capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr
    assert 'verified' in result.stdout
