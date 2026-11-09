"""Render localized Qt screens using only disposable generated photographs.

Run in a fresh process per QT_SCALE_FACTOR. Output must not already exist.
Captures and contact sheets are evidence, not native platform acceptance.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import platform
import tempfile

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from PIL import Image, ImageDraw
from PySide6.QtCore import QCoreApplication, QEvent, QSettings, qVersion
from PySide6.QtGui import QFont, QFontDatabase
from PySide6.QtWidgets import QApplication, QFileDialog

from app.ui.qt.navigation import Route
from app.ui.qt.window import MainWindow
from tools.capture_task011 import inspect_layout, isolated_environment
from tools.capture_ux_audit import generate, pump


@contextmanager
def isolated_framework_settings(sandbox: Path):
    previous = QSettings.defaultFormat()
    scopes = (QSettings.UserScope, QSettings.SystemScope)
    paths = {scope: Path(QSettings(QSettings.IniFormat, scope, 'PhotoAgent', 'path-probe').fileName()).parent.parent
             for scope in scopes}
    QSettings.setDefaultFormat(QSettings.IniFormat)
    for scope in scopes:
        QSettings.setPath(QSettings.IniFormat, scope, str(sandbox / 'qt-settings'))
    try:
        yield
    finally:
        for scope, path in paths.items():
            QSettings.setPath(QSettings.IniFormat, scope, str(path))
        QSettings.setDefaultFormat(previous)


def run(output: Path, width: int, height: int) -> None:
    output = output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    application = QApplication([])
    application.setStyle('Fusion')
    application.setQuitOnLastWindowClosed(False)
    if platform.system() == 'Windows':
        for name in ('segoeui.ttf', 'segoeuib.ttf'):
            if QFontDatabase.addApplicationFont(str(Path(os.environ['WINDIR']) / 'Fonts' / name)) < 0:
                raise RuntimeError('Offscreen font unavailable')
        application.setFont(QFont('Segoe UI', 10))
    scale = float(os.environ.get('QT_SCALE_FACTOR', '1'))
    manifest = {'synthetic': True, 'finished': False, 'qt': qVersion(),
                'python': platform.python_version(), 'platform': platform.system(),
                'qt_platform': application.platformName(), 'scale': scale,
                'requested_physical': [width, height], 'captures': []}

    def capture(name, widget, window, *, check_layout=True):
        application.processEvents()
        layout = inspect_layout(window) if check_layout else None
        if layout and (layout['page_horizontal_max'] or layout['toolbar_outside'] or layout['toolbar_overlaps']):
            raise AssertionError((name, layout))
        pixmap = widget.grab()
        assert pixmap.devicePixelRatio() == scale
        path = output / (name + '.png')
        if not pixmap.save(str(path)):
            raise OSError('Capture failed')
        manifest['captures'].append({'file': path.name, 'sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
            'logical': [widget.width(), widget.height()], 'physical': [pixmap.width(), pixmap.height()],
            'dpr': pixmap.devicePixelRatio(), 'layout': layout})

    shared_temp = Path(os.environ['WINDIR']) / 'Temp' if platform.system() == 'Windows' else None
    with tempfile.TemporaryDirectory(prefix='photoagent-language-', dir=shared_temp) as directory:
        sandbox = Path(directory)
        with isolated_environment(sandbox), isolated_framework_settings(sandbox):
            photos = sandbox / 'fotografije-čćžšđ'
            generate(photos)
            original = {path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in photos.iterdir()}
            window = MainWindow(sandbox / 'home')
            window.show()
            try:
                pump(lambda: window.settings and not window.controller.busy)
                window.roots = [str(photos)]
                window.render_roots()
                window.start_scan()
                pump(lambda: window.session and not window.controller.busy, timeout=90)
                assert window.status == 'complete'
                window.resize(round(width / scale), round(height / scale))
                for language in ('en', 'sr_Latn'):
                    window.preferences.language.setCurrentIndex(window.preferences.language.findData(language))
                    pump(lambda: not window.controller.busy)
                    for theme in ('dark', 'light'):
                        window.set_theme(theme)
                        pump(lambda: not window.controller.busy)
                        prefix = language + '-' + theme
                        for route in Route:
                            window.duplicates_flow.show_comparison(False)
                            window.navigate(route)
                            capture(prefix + '-' + route.value, window, window)
                        window.navigate(Route.DUPLICATES)
                        window.duplicates.table.selectRow(0)
                        window.compare()
                        pump(lambda: bool(window.comparison.left.scene.items()) and bool(window.comparison.right.scene.items()))
                        window.comparison.left.keep_photo.setChecked(True)
                        window.choose_keeper(False)
                        capture(prefix + '-compare', window, window)
                        window.prepare_selected()
                        pump(lambda: window.plan_dialog is not None)
                        assert window.plan_dialog.approval is None
                        capture(prefix + '-confirmation', window.plan_dialog, window, check_layout=False)
                        window.plan_dialog.reject()
                        window.add_root()
                        picker = window.findChild(QFileDialog)
                        capture(prefix + '-folder', picker, window, check_layout=False)
                        picker.reject()
                        QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
                assert original == {path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in photos.iterdir()}
                assert not list(photos.rglob('_photoagent_quarantine'))
                manifest['original_bytes_preserved'] = True
            finally:
                window.close()
                pump(lambda: window.finished)
                window.deleteLater()
                QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
    for language in ('en', 'sr_Latn'):
        for theme in ('dark', 'light'):
            prefix = language + '-' + theme
            entries = [entry for entry in manifest['captures'] if entry['file'].startswith(prefix)]
            sheet = Image.new('RGB', (1200, 4 * 380), '#d6d9df')
            draw = ImageDraw.Draw(sheet)
            for i, entry in enumerate(entries):
                with Image.open(output / entry['file']) as screenshot:
                    screenshot.thumbnail((590, 346))
                    x, y = (i % 2) * 600, (i // 2) * 380
                    sheet.paste(screenshot, (x, y + 25))
                    draw.text((x + 5, y + 5), entry['file'], fill='black')
            sheet.save(output / (prefix + '-review.jpg'), quality=90)
    manifest['finished'] = True
    (output / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(f'Completed {len(manifest["captures"])} localized captures; synthetic state removed.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--width', type=int, default=1280)
    parser.add_argument('--height', type=int, default=720)
    args = parser.parse_args()
    run(args.output, args.width, args.height)
