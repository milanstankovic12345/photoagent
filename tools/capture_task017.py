"""Task017 real Qt windows, disposable state and generated photographs only."""
from __future__ import annotations

import argparse
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
from PySide6.QtGui import QFont, QFontDatabase
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from app.core.models import SafetyError
from app.services.application import Application
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
        'method': 'Real workers and services. A delayed extraction captures running/cancelled states; '
                  'an injected pre-session exception captures failure. No approvals or moves.',
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
            originals = {p: p.read_bytes() for p in photos.iterdir()}
            window = MainWindow(sandbox / 'home')
            window.show()
            try:
                pump(lambda: window.settings and not window.controller.busy)

                def capture(name: str, route: Route) -> None:
                    window.navigate(route)
                    window.pages[route].verticalScrollBar().setValue(0)
                    QTest.qWait(70)
                    layout = inspect_layout(window)
                    assert not any(layout[key] for key in
                        ('toolbar_outside', 'toolbar_overlaps', 'page_horizontal_max')), layout
                    path = output / (name + '-' + route.value + '.png')
                    shot = window.grab()
                    assert shot.save(str(path))
                    manifest['captures'].append({'file': path.name, 'layout': layout,
                        'language': language_manager().language, 'theme': window.theme.active,
                        'scan_state': window.scan.state,
                        'logical': [window.width(), window.height()],
                        'physical': [shot.width(), shot.height()], 'dpr': shot.devicePixelRatio(),
                        'sha256': hashlib.sha256(path.read_bytes()).hexdigest()})

                def matrix(state: str) -> None:
                    for language in ('en', 'sr_Latn'):
                        language_manager().set_language(language)
                        for theme in ('dark', 'light'):
                            window.set_theme(theme)
                            pump(lambda: not window.controller.busy)
                            for width, height in ((853, 480), (1440, 900)):
                                window.resize(width, height)
                                for route in (Route.DASHBOARD, Route.SCAN):
                                    capture(f'{state}-{language}-{theme}-{width}', route)

                def scan_sources(roots: list[str]) -> None:
                    previous = window.session
                    window.roots = roots
                    window.render_roots()
                    window.start_scan()
                    pump(lambda: window.session != previous and not window.controller.busy, timeout=90)

                matrix('empty')
                scan_sources([str(photos)])
                assert window.scan.state == 'complete'
                matrix('complete')
                language_manager().set_language('en')
                window.set_theme('dark')
                pump(lambda: not window.controller.busy)
                window.resize(853, 480)
                one = sandbox / 'single'
                one.mkdir()
                shutil.copy2(photos / 'original.png', one / 'single.png')
                scan_sources([str(one)])
                assert window.scan.state == 'complete' and not window.scan.review.isEnabled()
                capture('no-matches', Route.SCAN)
                capture('no-matches', Route.DASHBOARD)
                (one / 'broken.jpg').write_bytes(b'synthetic undecodable image')
                scan_sources([str(one), str(sandbox / 'offline')])
                assert window.scan.state == 'incomplete'
                capture('errors-offline', Route.SCAN)
                window.scan.error_section.set_expanded(True)
                QTest.qWait(70)  # Let the expanded body enter the scroll layout.
                window.pages[Route.SCAN].ensureWidgetVisible(window.scan.errors)
                QTest.qWait(70)
                # Capture details separately without resetting the page scroll.
                assert window.scan.errors.toPlainText()
                assert window.grab().save(str(output / 'errors-expanded.png'))
                window.scan.error_section.set_expanded(False)
                window.roots = [str(photos)]
                window.render_roots()
                entered, release = Event(), Event()
                import app.services.indexing as indexing
                extract = indexing.extract

                def delayed(*args, **kwargs):
                    entered.set()
                    assert release.wait(30)
                    return extract(*args, **kwargs)

                # A new pipeline version ensures extraction rather than a cache hit.
                version = indexing.pipeline_version()
                with patch.object(indexing, 'extract', delayed), patch.object(
                        indexing, 'pipeline_version', return_value=version + '-capture'):
                    window.start_scan()
                    try:
                        pump(entered.is_set)
                        capture('running', Route.SCAN)
                        capture('running', Route.DASHBOARD)
                        window.cancel()
                    finally:
                        release.set()
                    pump(lambda: not window.controller.busy, timeout=90)
                assert window.scan.state == 'cancelled'
                capture('cancelled', Route.SCAN)
                with patch.object(Application, 'scan_with_report', side_effect=SafetyError('synthetic failure')):
                    window.start_scan()
                    pump(lambda: not window.controller.busy)
                assert window.scan.state == 'failed'
                capture('failed', Route.SCAN)
                assert {p: p.read_bytes() for p in photos.iterdir()} == originals
            finally:
                window.close()
                pump(lambda: window.finished)
    (output / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(f'{len(manifest["captures"])} captures plus expanded errors; originals unchanged; no approvals')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    run(parser.parse_args().output)
