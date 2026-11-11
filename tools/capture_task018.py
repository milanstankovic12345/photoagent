"""Capture Task018 with real Qt workers, temporary state and generated photos."""
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
    manifest = {'platform': platform.system(), 'plugin': app.platformName(),
        'scale': os.environ.get('QT_SCALE_FACTOR', '1'), 'synthetic': True,
        'method': 'Real Qt windows, workers and services. Generated PNG/JPEG fixtures. '
                  'Loading captured synchronously after editing the query. No approvals or moves.',
        'captures': []}
    with tempfile.TemporaryDirectory(prefix='synthetic-', dir=output) as directory:
        sandbox = Path(directory)
        with isolated_environment(sandbox), isolated_framework_settings(sandbox):
            photos = sandbox / 'photos'
            photos.mkdir()
            for number, color in enumerate(('#a84130', '#3b8659')):
                with Image.new('RGB', (240, 160), '#abcce5') as image:
                    draw = ImageDraw.Draw(image)
                    draw.rectangle((10, 20, 130, 100), fill=color)
                    draw.ellipse((110, 50, 230, 150), fill='#d7bd50')
                    image.save(photos / f'scene-{number}.png')
                    if number == 0:
                        image.save(photos / 'rendered.jpg', quality=90)
                for copy in range(number + 1):
                    shutil.copy2(photos / f'scene-{number}.png', photos / f'scene-{number}-copy-{copy}.png')
            originals = {p: p.read_bytes() for p in photos.iterdir()}
            window = MainWindow(sandbox / 'home')
            window.show()
            try:
                pump(lambda: window.settings and not window.controller.busy)
                window.navigate(Route.DUPLICATES)

                def capture(name: str) -> None:
                    QTest.qWait(70)
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
                        'groups': window.group_total,
                        'members': [r.members for r in window.group_rows],
                        'kinds': [r.kind for r in window.group_rows],
                        'sha256': hashlib.sha256(path.read_bytes()).hexdigest()})

                def matrix(state: str) -> None:
                    for language in ('en', 'sr_Latn'):
                        language_manager().set_language(language)
                        for theme in ('dark', 'light'):
                            window.theme.apply(theme)
                            for width, height in ((853, 480), (1440, 900)):
                                window.resize(width, height)
                                capture(f'{state}-{language}-{theme}-{width}')

                matrix('empty')
                window.roots = [str(photos)]
                window.render_roots()
                window.start_scan()
                pump(lambda: window.session and not window.controller.busy, timeout=90)
                assert {r.kind for r in window.group_rows} == {'EXACT', 'VISUAL'}
                assert {2, 3}.issubset({r.members for r in window.group_rows})
                pump(lambda: bool(window.duplicates.groups.groups_model.images))
                matrix('grid')
                window.duplicates.mode.setCurrentIndex(1)
                matrix('list')
                window.duplicates.search.setText('absent-photo')
                # Keep debounce pending during capture without changing app logic.
                window.search_timer.setInterval(5000)
                window.search_timer.start()
                capture('loading-sr_Latn-light-1440')
                window.search_timer.stop()
                window.filter_changed()
                pump(lambda: not window.controller.busy)
                matrix('filtered')
                assert {p: p.read_bytes() for p in photos.iterdir()} == originals
            finally:
                window.close()
                pump(lambda: window.finished)
    (output / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(f'{len(manifest["captures"])} captures; originals unchanged; no approvals')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    run(parser.parse_args().output)
