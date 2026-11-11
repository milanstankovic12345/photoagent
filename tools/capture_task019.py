"""Capture recovery/settings with generated photos and isolated application data."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import tempfile

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from PIL import Image, ImageDraw
from PySide6.QtGui import QFont, QFontDatabase
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QMessageBox

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
    manifest = {'platform': platform.system(), 'plugin': app.platformName(),
        'scale': os.environ.get('QT_SCALE_FACTOR', '1'), 'synthetic': True,
        'method': 'Real Qt workers/services. Generated PNG copies; approved synthetic '
                  'quarantine/restore only. Conflict and disconnected root are synthetic.',
        'captures': []}
    with tempfile.TemporaryDirectory(prefix='synthetic-', dir=output) as directory:
        sandbox = Path(directory)
        with isolated_environment(sandbox), isolated_framework_settings(sandbox):
            photos = sandbox / 'photos'
            photos.mkdir()
            with Image.new('RGB', (240, 160), '#abcce5') as image:
                draw = ImageDraw.Draw(image)
                draw.rectangle((10, 20, 130, 100), fill='#a84130')
                draw.ellipse((110, 50, 230, 150), fill='#d7bd50')
                image.save(photos / 'scene.png')
            shutil.copy2(photos / 'scene.png', photos / 'scene-copy.png')
            originals = {path: path.read_bytes() for path in photos.iterdir()}
            window = MainWindow(sandbox / 'home')
            window.show()
            try:
                pump(lambda: window.settings and not window.controller.busy)

                def capture(name: str, route: Route, *, bottom: bool = False) -> None:
                    window.navigate(route)
                    QTest.qWait(80)
                    bar = window.pages[route].verticalScrollBar()
                    bar.setValue(bar.maximum() if bottom else 0)
                    QTest.qWait(30)
                    layout = inspect_layout(window)
                    assert not any(layout[key] for key in
                        ('toolbar_outside', 'toolbar_overlaps', 'page_horizontal_max')), layout
                    path = output / (name + '.png')
                    shot = window.grab()
                    assert shot.save(str(path))
                    manifest['captures'].append({'file': path.name, 'layout': layout,
                        'language': language_manager().language, 'theme': window.theme.active,
                        'logical': [window.width(), window.height()],
                        'physical': [shot.width(), shot.height()], 'dpr': shot.devicePixelRatio(),
                        'sha256': hashlib.sha256(path.read_bytes()).hexdigest()})

                def appearance(language: str, theme: str, width: int, height: int) -> None:
                    window.preferences.language.setCurrentIndex(window.preferences.language.findData(language))
                    pump(lambda: not window.controller.busy)
                    window.set_theme(theme)
                    pump(lambda: not window.controller.busy)
                    window.resize(width, height)

                def matrix(state: str) -> None:
                    for language, theme, width, height in (
                            ('en', 'dark', 1280, 900), ('sr_Latn', 'light', 853, 480)):
                        appearance(language, theme, width, height)
                        capture(f'{state}-{language}-{theme}', Route.QUARANTINE)

                matrix('empty')
                window.roots = [str(photos)]
                window.render_roots()
                window.start_scan()
                pump(lambda: window.session and not window.controller.busy, timeout=90)
                window.prepare_bulk()
                pump(lambda: window.plan_dialog is not None)
                move = window.plan_dialog.plan.moves[0]
                window.plan_dialog.approve()
                pump(lambda: not window.controller.busy)
                window.navigate(Route.QUARANTINE)
                window.history.table.selectRow(0)
                pump(lambda: not window.history.thumbnail.pixmap().isNull(), timeout=60)
                matrix('active')

                for language, theme, width, height in (
                        ('en', 'dark', 1280, 900), ('sr_Latn', 'light', 853, 480)):
                    appearance(language, theme, width, height)
                    capture(f'settings-{language}-{theme}', Route.SETTINGS)
                    window.preferences.storage_details.set_expanded(True)
                    capture(f'storage-{language}-{theme}', Route.SETTINGS, bottom=True)
                    window.preferences.storage_details.set_expanded(False)

                def failed_restore() -> None:
                    window.navigate(Route.QUARANTINE)
                    window.restore()
                    pump(lambda: window.history.operation_error and not window.controller.busy)
                    for dialog in window.findChildren(QMessageBox):
                        dialog.close()

                Path(move.source).write_bytes(b'synthetic occupied destination')
                failed_restore()
                matrix('conflict')
                # Remove only the synthetic collision placeholder, never a photo.
                Path(move.source).unlink()
                offline = photos.with_name('synthetic-offline')
                photos.rename(offline)
                window.history.show_operation_error('')
                failed_restore()
                matrix('offline')
                offline.rename(photos)
                window.restore()
                pump(lambda: window.plan_dialog is not None)
                assert not Path(move.source).exists()
                window.plan_dialog.approve()
                pump(lambda: not window.controller.busy)
                window.history.table.selectRow(0)
                matrix('restored')
                assert all(path.read_bytes() == content for path, content in originals.items())
            finally:
                window.close()
                pump(lambda: window.finished)
    (output / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(f'{len(manifest["captures"])} captures; synthetic originals restored byte-for-byte')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    run(parser.parse_args().output)
