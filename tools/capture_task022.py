"""Capture Task022 EN/SR wording on real Qt widgets with isolated synthetic data.

No OS viewer is launched and no photograph is moved. Run once per output folder
and scale factor; the folder must not exist. Offscreen captures are not native
display, accessibility or physical DPI acceptance.
"""
from __future__ import annotations

import argparse
from dataclasses import replace
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import tempfile
from threading import Event
from unittest.mock import patch

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from PIL import Image, ImageDraw
from PySide6.QtCore import QSignalBlocker, Qt
from PySide6.QtGui import QFont, QFontDatabase
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QMessageBox, QToolTip

import app.services.indexing as indexing
from app.ui.qt.localization import language_manager
from app.ui.qt.navigation import Route
from app.ui.qt.window import MainWindow
from tools.capture_task011 import inspect_layout, isolated_environment
from tools.capture_task012 import isolated_framework_settings
from tools.capture_ux_audit import pump


def run(output: Path) -> None:
    output = output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    app = QApplication([])
    app.setStyle('Fusion')
    app.setQuitOnLastWindowClosed(False)
    if platform.system() == 'Windows':
        for name in ('segoeui.ttf', 'segoeuib.ttf'):
            assert QFontDatabase.addApplicationFont(str(Path(os.environ['WINDIR']) / 'Fonts' / name)) >= 0
        app.setFont(QFont('Segoe UI', 10))
    manifest = {'platform': platform.system(), 'qt_platform': app.platformName(),
                'scale': os.environ.get('QT_SCALE_FACTOR', '1'), 'synthetic': True,
                'moved_files': 0, 'os_launches': 0, 'captures': []}
    with tempfile.TemporaryDirectory(prefix='synthetic-', dir=output) as directory:
        sandbox = Path(directory)
        with isolated_environment(sandbox), isolated_framework_settings(sandbox):
            photos = sandbox / 'Fotografije-čćžšđ-照片'
            photos.mkdir()
            with Image.new('RGB', (900, 600), '#accde6') as image:
                draw = ImageDraw.Draw(image)
                draw.rectangle((35, 80, 490, 410), fill='#a84130')
                draw.ellipse((430, 190, 850, 550), fill='#d7bd50')
                image.save(photos / 'Izvornik-đ.png')
            shutil.copy2(photos / 'Izvornik-đ.png', photos / 'Kopija-ć-照片.png')
            originals = {p: p.read_bytes() for p in photos.iterdir()}
            window = MainWindow(sandbox / 'home')
            window.show()

            def capture(name: str, widget=None, *, layout_check: bool = True) -> None:
                QTest.qWait(80)
                app.processEvents()
                layout = inspect_layout(window)
                if layout_check:
                    assert not any(layout[k] for k in
                        ('toolbar_outside', 'toolbar_overlaps', 'page_horizontal_max')), layout
                widget = widget or window
                shot = widget.grab()
                path = output / (name + '.png')
                assert shot.save(str(path))
                manifest['captures'].append({'file': path.name, 'layout': layout,
                    'language': language_manager().language, 'theme': window.theme.active,
                    'logical': [widget.width(), widget.height()], 'physical': [shot.width(), shot.height()],
                    'dpr': shot.devicePixelRatio(), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()})

            def languages_and_themes():
                for language in ('en', 'sr_Latn'):
                    window.preferences.language.setCurrentIndex(window.preferences.language.findData(language))
                    for theme in ('dark', 'light'):
                        window.theme.apply(theme)
                        for combo in (window.preferences.theme, window.dashboard.theme):
                            with QSignalBlocker(combo):
                                combo.setCurrentIndex(combo.findData(theme))
                        yield f'{language}-{theme}'

            try:
                pump(lambda: window.settings and not window.controller.busy)
                window.resize(853, 480)
                window.navigation.set_collapsed(True, animate=False)
                window.roots = [str(photos)]
                window.render_roots()
                original_extract, entered, release = indexing.extract, Event(), Event()

                def delayed(*args, **kwargs):
                    entered.set()
                    assert release.wait(90)
                    return original_extract(*args, **kwargs)

                with patch.object(indexing, 'extract', delayed):
                    window.navigate(Route.SCAN)
                    window.start_scan()
                    try:
                        pump(entered.is_set)
                        for suffix in languages_and_themes():
                            assert window.scan_active and not window.controller.cancel_event.is_set()
                            capture('scan-running-' + suffix)
                    finally:
                        release.set()
                    pump(lambda: window.session and not window.controller.busy, timeout=90)
                window.navigate(Route.DUPLICATES)
                window.duplicates.table.selectRow(0)
                window.compare()
                pump(lambda: not window.controller.busy and window.comparison.left.state == 'preview_ready')
                window.choose_keeper(False)
                chosen = window.pending_pairs()
                for suffix in languages_and_themes():
                    for width, height in ((1440, 900), (853, 480)):
                        window.resize(width, height)
                        scroll = window.duplicates_flow.comparison
                        scroll.verticalScrollBar().setValue(0)
                        capture(f'comparison-{suffix}-{width}')
                        window.comparison.left.details.set_expanded(True)
                        window.comparison.right.details.set_expanded(True)
                        # Expansion changes the scroll range on the next layout pass.
                        app.processEvents()
                        QTest.qWait(100)
                        scroll.ensureWidgetVisible(window.comparison.right.details.toggle)
                        capture(f'details-{suffix}-{width}')
                        window.comparison.left.details.set_expanded(False)
                        window.comparison.right.details.set_expanded(False)
                    assert window.pending_pairs() == chosen and not window.plan_dialog
                    control = window.comparison.prepare
                    QToolTip.showText(control.mapToGlobal(control.rect().center()), control.toolTip(), control)
                    app.processEvents()
                    tooltip = next(w for w in app.topLevelWidgets() if w.isVisible() and w.windowType() == Qt.ToolTip)
                    capture('quarantine-tooltip-' + suffix, tooltip)
                    QToolTip.hideText()
                window.prepare_selected()
                pump(lambda: window.plan_dialog is not None)
                # Preview extra-consent wording without approving an invented RAW.
                plan = window.plan_dialog.plan
                window.plan_dialog.reject()
                consent_plan = replace(plan, moves=(replace(plan.moves[0], raw=True, legacy=True),))
                window.confirm(consent_plan)
                dialog = window.plan_dialog
                dialog.raw.setText('RAW')
                dialog.legacy.setChecked(True)
                for suffix in languages_and_themes():
                    assert dialog.plan is consent_plan and dialog.approval is None
                    assert dialog.raw.text() == 'RAW' and dialog.legacy.isChecked()
                    capture('confirmation-' + suffix, dialog)
                dialog.reject()
                window.show_error('photo_launch_failed: synthetic association failure · čćžšđ/照片.nef')
                error = window.findChild(QMessageBox)
                for suffix in languages_and_themes():
                    capture('external-open-error-' + suffix, error)
                error.close()
                window.back_to_duplicates()
                for route in (Route.DASHBOARD, Route.SCAN, Route.DUPLICATES, Route.QUARANTINE, Route.SETTINGS):
                    window.navigate(route)
                    for suffix in languages_and_themes():
                        capture(f'{route.value}-' + suffix)
                pump(lambda: not window.controller.busy)
                assert {p: p.read_bytes() for p in photos.iterdir() if p.is_file()} == originals
                manifest['original_bytes_preserved'] = True
            finally:
                window.close()
                pump(lambda: window.finished)
    (output / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(f"Captured {len(manifest['captures'])} states in {output}; synthetic originals unchanged")


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True, type=Path)
    run(parser.parse_args().output)
