"""Render Task009 with real services and generated photos in a disposable home."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import platform
import tempfile

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from PySide6.QtGui import QFont, QFontDatabase
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QMessageBox

from app.ui.qt.navigation import Route
from app.ui.qt.window import MainWindow
from tools.capture_ux_audit import generate, pump


def run(output: Path) -> None:
    output.mkdir(parents=True, exist_ok=False)
    app = QApplication.instance() or QApplication([])
    app.setStyle('Fusion')
    app.setQuitOnLastWindowClosed(False)
    if platform.system() == 'Windows' and app.platformName() == 'offscreen':
        for name in ('segoeui.ttf', 'segoeuib.ttf'):
            QFontDatabase.addApplicationFont(str(Path(os.environ['WINDIR']) / 'Fonts' / name))
        app.setFont(QFont('Segoe UI', 10))
    manifest = {'platform': platform.platform(), 'qt': app.platformName(), 'captures': [],
        'method': 'Real Qt workers/services and synthetic photographs. Explicit bulk approval '
                  'moves only disposable fixtures. Restore plans rejected. Occupied destination '
                  'is a real synthetic collision; history load failure is injected into the view. '
                  'No native folder launcher or physical display tested.'}

    def capture(name: str, widget) -> None:
        app.processEvents()
        QTest.qWait(100)
        assert widget.grab().save(str(output / (name + '.png')))
        manifest['captures'].append(name + '.png')
        print(name, flush=True)

    with tempfile.TemporaryDirectory(prefix='photoagent-task009-') as temporary:
        sandbox = Path(temporary)
        photos = sandbox / 'photos'
        generate(photos)
        originals = {p.name: p.read_bytes() for p in photos.iterdir()}
        window = MainWindow(sandbox / 'home')
        window.show()
        try:
            pump(lambda: bool(window.settings) and not window.controller.busy)
            for theme in ('dark', 'light'):
                window.set_theme(theme)
                pump(lambda: not window.controller.busy)
                window.navigate(Route.QUARANTINE)
                capture(theme + '-empty', window)
            window.roots = [str(photos)]
            window.render_roots()
            window.start_scan()
            pump(lambda: bool(window.session) and not window.controller.busy, timeout=120)
            window.prepare_bulk()
            pump(lambda: window.plan_dialog is not None)
            moves = window.plan_dialog.plan.moves
            window.plan_dialog.approve()
            pump(lambda: not window.controller.busy)
            assert len(moves) == 2
            for theme in ('dark', 'light'):
                window.set_theme(theme)
                pump(lambda: not window.controller.busy)
                for width, height in ((1280, 800), (853, 480)):
                    prefix = f'{theme}-{width}'
                    window.resize(width, height)
                    window.navigate(Route.QUARANTINE)
                    window.history.table.selectRow(0)
                    pump(lambda: not window.history.thumbnail.pixmap().isNull(), timeout=60)
                    window.pages[Route.QUARANTINE].verticalScrollBar().setValue(0)
                    capture(prefix + '-history', window)
                    window.restore()
                    pump(lambda: window.plan_dialog is not None)
                    capture(prefix + '-restore-confirmation', window.plan_dialog)
                    window.plan_dialog.reject()
                    window.navigate(Route.SETTINGS)
                    window.preferences.load_matching(13, 17)
                    scroll = window.pages[Route.SETTINGS].verticalScrollBar()
                    scroll.setValue(0)
                    capture(prefix + '-settings', window)
                    scroll.setValue(scroll.maximum())
                    capture(prefix + '-settings-storage', window)
            window.resize(1280, 800)
            window.navigate(Route.QUARANTINE)
            selected = window.history.selected_entry
            Path(selected.source).write_bytes(b'synthetic occupied destination')
            window.restore()
            pump(lambda: bool(window.findChildren(QMessageBox)) and not window.controller.busy)
            box = window.findChildren(QMessageBox)[-1]
            capture('occupied-destination', box)
            box.close()
            assert Path(selected.source).read_bytes() == b'synthetic occupied destination'
            window.error('history', 'synthetic unavailable manifest')
            capture('history-unavailable', window)
            for move in moves:
                assert Path(move.destination).read_bytes() == originals[Path(move.source).name]
            assert all((photos / name).read_bytes() == content for name, content in originals.items()
                       if str(photos / name) not in {m.source for m in moves})
        finally:
            window.close()
            pump(lambda: window.finished)
    (output / 'manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    run(parser.parse_args().output)
