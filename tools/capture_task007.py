"""Capture Task007 with real workers and synthetic photos in a disposable home.

Only the failed matching case injects a fault; its persisted failed session and
rendering use the real service/Qt error path. No photograph operations are invoked.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict
import hashlib
import json
import os
from pathlib import Path
import platform
import tempfile
from unittest.mock import patch

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from PySide6.QtGui import QFont, QFontDatabase
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from app.core.models import SafetyError
from app.services.application import Application
from app.ui.qt.navigation import Route
from app.ui.qt.window import MainWindow
from tools.capture_ux_audit import generate, pump


def run(output: Path, width: int, height: int) -> None:
    output = output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    app = QApplication.instance() or QApplication([])
    app.setStyle('Fusion')
    app.setQuitOnLastWindowClosed(False)
    if platform.system() == 'Windows' and app.platformName() == 'offscreen':
        for name in ('segoeui.ttf', 'segoeuib.ttf'):
            if QFontDatabase.addApplicationFont(str(Path(os.environ['WINDIR']) / 'Fonts' / name)) < 0:
                raise RuntimeError('Cannot load installed font for capture')
        app.setFont(QFont('Segoe UI', 10))
    manifest = {'platform': platform.platform(), 'qt': app.platformName(),
        'viewport': [width, height], 'scale_factor': os.environ.get('QT_SCALE_FACTOR', '1'),
        'method': 'Real workers/services and generated PNG/JPEG/invalid RAW; only failed-match '
                  'capture injects a matching exception. No physical DPI/native display tested.',
        'screenshots': [], 'summaries': [], 'checks': []}

    def capture(window: MainWindow, name: str, state: str) -> None:
        # Progress is delivered in a signal callback. Flush queued layout requests
        # before grabbing, so a newly wrapped label gets its final height.
        app.processEvents()
        QTest.qWait(50)
        pixmap = window.grab()
        path = output / (name + '.png')
        if not pixmap.save(str(path)):
            raise OSError(str(path))
        manifest['screenshots'].append({'file': path.name, 'state': state,
            'width': pixmap.width(), 'height': pixmap.height(), 'dpr': pixmap.devicePixelRatio(),
            'sha256': hashlib.sha256(path.read_bytes()).hexdigest()})
        print(name, flush=True)

    with tempfile.TemporaryDirectory(prefix='photoagent-task007-') as temporary:
        sandbox = Path(temporary)
        for key in ('HOME', 'USERPROFILE', 'TMP', 'TEMP', 'TMPDIR'):
            os.environ[key] = str(sandbox)
        photos = sandbox / 'photos'
        generate(photos)
        original = {p.name: p.read_bytes() for p in photos.iterdir()}
        for theme in ('dark', 'light'):
            (photos / 'bad.nef').unlink(missing_ok=True)  # Only the generated fixture in this temp home.
            home = sandbox / theme
            service = Application(home)
            service.initialize()
            service.update_settings({'theme': theme})
            service.close()
            window = MainWindow(home)
            window.resize(width, height)
            window.show()

            def settled() -> None:
                pump(lambda: bool(window.settings) and not window.controller.busy, timeout=120)

            try:
                settled()
                capture(window, theme + '-dashboard-empty', 'No session')
                window.dashboard.scan.click()
                capture(window, theme + '-scan-empty', 'No sources; advanced/errors collapsed')
                window.roots = [str(photos)]
                window.render_roots()
                window.controller.request('settings', {'roots': window.roots.copy()})
                settled()
                capture(window, theme + '-scan-sources', 'Available source; one primary start action')
                active = []

                def progress(value) -> None:
                    if value.phase == 'scan' and value.processed and not active:
                        active.append(True)
                        assert window.scan.progress.maximum() == 0
                        capture(window, theme + '-scan-active', 'Actual processed-file progress, unknown denominator')

                window.controller.progress.connect(progress)
                window.start_scan()
                settled()
                window.controller.progress.disconnect(progress)
                assert active and window.status == 'complete'
                capture(window, theme + '-scan-complete', 'Five photos, one EXACT group, direct VISUAL links')
                window.navigate(Route.DASHBOARD)
                app.processEvents()
                first = window.dashboard.cards[0]
                window.pages[Route.DASHBOARD].ensureWidgetVisible(first)
                pump(lambda: first.loaded, timeout=60)
                capture(window, theme + '-dashboard-complete', 'Actual candidates with asynchronously loaded visible thumbnails')
                window.pages[Route.DASHBOARD].verticalScrollBar().setValue(0)
                app.processEvents()
                capture(window, theme + '-dashboard-metrics', 'Whole index and last-session metrics')
                manifest['checks'].append(theme + ': actual scan and visible preview completed')

                (photos / 'bad.nef').write_bytes(b'synthetic invalid raw')
                window.roots.append(str(sandbox / 'offline-drive'))
                window.render_roots()
                window.navigate(Route.SCAN)
                window.start_scan()
                settled()
                assert window.status == 'incomplete' and not window.duplicates.bulk.isEnabled()
                capture(window, theme + '-scan-incomplete', 'Actual invalid RAW and offline source; errors collapsed')
                window.scan.error_section.set_expanded(True)
                window.pages[Route.SCAN].ensureWidgetVisible(window.scan.errors)
                app.processEvents()
                capture(window, theme + '-scan-error-details', 'Actual error details on demand')

                window.pages[Route.SCAN].verticalScrollBar().setValue(0)
                window.roots = [str(photos)]
                window.render_roots()
                with patch('app.services.indexing.match_index', side_effect=SafetyError('synthetic_matching_failure')):
                    window.start_scan()
                    settled()
                assert window.status == 'failed'
                assert 'synthetic_matching_failure' in window.scan.errors.toPlainText()
                assert not window.duplicates.bulk.isEnabled()
                capture(window, theme + '-scan-failed', 'Injected matching fault; real persisted failed session')
                window.navigate(Route.DASHBOARD)
                app.processEvents()
                capture(window, theme + '-dashboard-failed', 'Real failed session, review-only warning, no candidates')
                window.controller.result.connect(lambda action, value: manifest['summaries'].append(asdict(value))
                    if action == 'dashboard' else None)
                window.refresh()
                settled()
                assert all((photos / name).read_bytes() == data for name, data in original.items())
                manifest['checks'].append(theme + ': incomplete/failed sessions prohibit bulk; all original bytes preserved')
            finally:
                window.close()
                pump(lambda: window.finished)
                assert not any(thread.isRunning() for thread in window.controller.threads)
                window.deleteLater()
                app.processEvents()
        manifest['checks'].append('All workers stopped before sandbox cleanup')
        rendered = json.dumps(manifest, ensure_ascii=False, indent=2)
        rendered = rendered.replace(str(sandbox).replace('\\', '\\\\'), '<private-temp>')
        (output / 'manifest.json').write_text(rendered + '\n', encoding='utf-8')
    print(f'Completed {len(manifest["screenshots"])} screenshots', flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--width', type=int, default=1280)
    parser.add_argument('--height', type=int, default=800)
    args = parser.parse_args()
    run(args.output, args.width, args.height)
