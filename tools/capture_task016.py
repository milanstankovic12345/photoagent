"""Task016 real-window evidence using disposable synthetic photographs only.

Run in a fresh process per QT_SCALE_FACTOR. The output directory must be new.
No quarantine approval, user library, user settings or persistent home is used.
"""
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
from PySide6.QtCore import QAbstractAnimation, qVersion
from PySide6.QtGui import QFont, QFontDatabase
from PySide6.QtWidgets import QApplication

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
    manifest = {'qt': qVersion(), 'platform': platform.system(), 'plugin': app.platformName(),
                'scale': os.environ.get('QT_SCALE_FACTOR', '1'), 'synthetic': True,
                'scope': 'Real application, disposable home/photos, no approvals or moves.',
                'captures': []}
    with tempfile.TemporaryDirectory(prefix='synthetic-', dir=output) as directory:
        sandbox = Path(directory)
        with isolated_environment(sandbox), isolated_framework_settings(sandbox):
            photos = sandbox / 'photos'
            photos.mkdir()
            with Image.new('RGB', (160, 120), '#9cbfe3') as image:
                draw = ImageDraw.Draw(image)
                draw.rectangle((10, 10, 95, 60), fill='#b64030')
                draw.ellipse((70, 45, 150, 110), fill='#307840')
                image.save(photos / 'original.png')
            shutil.copy2(photos / 'original.png', photos / 'copy.png')
            before = {p.name: p.read_bytes() for p in photos.iterdir()}
            window = MainWindow(sandbox / 'home')
            window.show()
            try:
                pump(lambda: window.settings and not window.controller.busy)
                window.roots = [str(photos)]
                window.render_roots()
                window.start_scan()
                pump(lambda: window.session and not window.controller.busy, timeout=90)
                assert window.status == 'complete'
                window.resize(853, 480)

                def capture(name: str) -> None:
                    app.processEvents()
                    layout = inspect_layout(window)
                    assert not layout['toolbar_outside'] and not layout['toolbar_overlaps'], layout
                    assert not layout['page_horizontal_max'], layout
                    for control in (window.navigation.toggle, *window.navigation.buttons.values()):
                        assert window.navigation.rect().contains(control.geometry())
                    path = output / (name + '.png')
                    pixmap = window.grab()
                    assert pixmap.save(str(path))
                    manifest['captures'].append({'file': path.name,
                        'sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
                        'logical': [window.width(), window.height()],
                        'physical': [pixmap.width(), pixmap.height()],
                        'dpr': pixmap.devicePixelRatio(), 'layout': layout})

                for language, theme in (('en', 'dark'), ('sr_Latn', 'light')):
                    language_manager().set_language(language)
                    window.theme.apply(theme)
                    routes = tuple(Route) if language == 'en' else (Route.SCAN,)
                    for route in routes:
                        window.navigate(route)
                        for collapsed in (True, False):
                            window.navigation.set_collapsed(collapsed)
                            pump(lambda: window.navigation.animation.state() == QAbstractAnimation.Stopped)
                            capture(f'{language}-{theme}-{route.value}-' + ('compact' if collapsed else 'expanded'))
                    window.navigate(Route.DUPLICATES)
                    window.duplicates.table.selectRow(0)
                    window.compare()
                    pump(lambda: window.comparison.left.state == window.comparison.right.state == 'preview_ready')
                    for collapsed in (True, False):
                        window.navigation.set_collapsed(collapsed)
                        pump(lambda: window.navigation.animation.state() == QAbstractAnimation.Stopped)
                        capture(f'{language}-{theme}-compare-' + ('compact' if collapsed else 'expanded'))
                    window.back_to_duplicates()
                assert {p.name: p.read_bytes() for p in photos.iterdir()} == before
            finally:
                window.close()
                pump(lambda: window.finished)
    (output / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(f'{len(manifest["captures"])} captures; synthetic originals unchanged; no approvals')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    run(parser.parse_args().output)
