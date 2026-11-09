"""Capture real Task008 widgets/workers with generated images and an isolated home."""
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
from PySide6.QtWidgets import QApplication

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
        'method': 'Real Qt workers/services and synthetic PNG/JPEG fixtures. Preview error is injected '
                  'at the view for compact-state inspection. All plans rejected; no moves.'}

    def capture(name: str, widget) -> None:
        app.processEvents()
        QTest.qWait(100)
        path = output / (name + '.png')
        assert widget.grab().save(str(path))
        manifest['captures'].append(path.name)
        print(name, flush=True)

    with tempfile.TemporaryDirectory(prefix='photoagent-task008-') as temporary:
        sandbox = Path(temporary)
        for key in ('HOME', 'USERPROFILE', 'TMP', 'TEMP', 'TMPDIR'):
            os.environ[key] = str(sandbox)
        photos = sandbox / 'photos'
        generate(photos)
        originals = {path.name: path.read_bytes() for path in photos.iterdir()}
        window = MainWindow(sandbox / 'home')
        window.resize(1280, 800)
        window.show()
        try:
            pump(lambda: bool(window.settings) and not window.controller.busy)
            window.navigate(Route.DUPLICATES)
            capture('no-session', window)
            window.roots = [str(photos)]
            window.start_scan()
            pump(lambda: window.session and not window.controller.busy, timeout=120)
            for theme in ('dark', 'light'):
                window.theme.apply(theme)
                for width, height in ((1280, 800), (853, 480)):
                    prefix = f'{theme}-{width}'
                    window.resize(width, height)
                    window.duplicates_flow.show_comparison(False)
                    window.update_shell()
                    window.duplicates.mode.setCurrentIndex(0)
                    window.duplicates.groups.scrollTo(window.duplicates.groups.model().index(1))
                    pump(lambda: bool(window.duplicates.groups.groups_model.images), timeout=90)
                    capture(prefix + '-grid', window)
                    window.duplicates.mode.setCurrentIndex(1)
                    capture(prefix + '-list', window)
                    group = next(i + 1 for i, row in enumerate(window.group_rows) if row.kind == 'EXACT')
                    window.activate_group(window.duplicates.groups.model().index(group))
                    pump(lambda: window.duplicates_flow.comparing and not window.controller.busy)
                    pump(lambda: window.comparison.left.state == 'preview_ready', timeout=60)
                    app.processEvents()
                    manifest.setdefault('comparison_geometry', []).append({
                        'theme': theme, 'viewport': [width, height],
                        'horizontal_scroll': window.duplicates_flow.comparison.horizontalScrollBar().maximum(),
                        'card_min_width': window.comparison.left.minimumSizeHint().width(),
                    })
                    capture(prefix + '-comparison', window)
                    window.choose_keeper(False)
                    window.prepare_selected()
                    pump(lambda: window.plan_dialog is not None)
                    capture(prefix + '-confirmation', window.plan_dialog)
                    window.plan_dialog.reject()
                    window.comparison.left.set_image(None, 'synthetic preview failure')
                    capture(prefix + '-unavailable', window)
                    window.keep_both()
                    window.back_to_duplicates()
            assert originals == {path.name: path.read_bytes() for path in photos.iterdir()}
        finally:
            window.close()
            pump(lambda: window.finished)
    (output / 'manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    run(parser.parse_args().output)
