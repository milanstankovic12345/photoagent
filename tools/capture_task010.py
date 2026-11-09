"""Task010 evidence: actual Qt DPI, long paths and focus/selection in both themes.

Run each scale in a fresh process, e.g. QT_SCALE_FACTOR=1.5, then
python -B -m tools.capture_task010 --output docs/design/verification/task010/150
All state lives in TemporaryDirectory. This driver never executes a file move.
"""
from __future__ import annotations

import argparse
from dataclasses import replace
import hashlib
import json
import os
from pathlib import Path
import platform
import tempfile

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QFontDatabase
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QMessageBox

from app.core.models import Kind
from app.ui.qt.components import PlanDialog
from app.ui.qt.navigation import Route
from app.ui.qt.strings import tr
from app.ui.qt.window import MainWindow
from tools.capture_ux_audit import generate, pump


def run(output: Path) -> None:
    output.mkdir(parents=True, exist_ok=False)
    app = QApplication.instance() or QApplication([])
    app.setStyle('Fusion')
    app.setQuitOnLastWindowClosed(False)
    if platform.system() == 'Windows' and app.platformName() == 'offscreen':
        for name in ('segoeui.ttf', 'segoeuib.ttf'):
            assert QFontDatabase.addApplicationFont(str(Path(os.environ['WINDIR']) / 'Fonts' / name)) >= 0
        app.setFont(QFont('Segoe UI', 10))
    scale = float(os.environ.get('QT_SCALE_FACTOR', '1'))
    manifest = {'platform': platform.platform(), 'python': platform.python_version(),
        'qt_platform': app.platformName(), 'scale_factor': scale, 'captures': [],
        'method': 'Real Qt widgets/workers/services, generated photographs and temporary home. '
                  'No moves executed. RAW/legacy/VISUAL warnings and unavailable preview are '
                  'injected presentation fixtures; no successful RAW decode claimed. '
                  'Physical display, screen reader and native DPI behavior unverified.'}

    def capture(name: str, widget) -> None:
        app.processEvents()
        QTest.qWait(100)
        shot = widget.grab()
        target = output / (name + '.png')
        assert shot.save(str(target))
        assert abs(shot.devicePixelRatio() - scale) < .01
        manifest['captures'].append({'file': target.name,
            'logical_size': [widget.width(), widget.height()],
            'pixel_size': [shot.width(), shot.height()], 'dpr': shot.devicePixelRatio(),
            'sha256': hashlib.sha256(target.read_bytes()).hexdigest()})
        print(name, flush=True)

    with tempfile.TemporaryDirectory(prefix='photoagent-task010-') as temporary:
        sandbox = Path(temporary)
        photos = sandbox / ('čćžšđ-duga-putanja-' * 3)
        generate(photos)
        (photos / 'b-copy.png').rename(photos / ('čćžšđ-duga-fotografija-' * 4 + '.png'))
        originals = {p: p.read_bytes() for p in photos.iterdir()}
        window = MainWindow(sandbox / 'home')
        window.resize(round(1280 / scale), round(720 / scale))
        window.show()
        try:
            pump(lambda: bool(window.settings) and not window.controller.busy)
            window.roots = [str(photos)]
            window.render_roots()
            window.start_scan()
            pump(lambda: window.session and not window.controller.busy, timeout=120)
            assert window.status == 'complete'
            for theme in ('dark', 'light'):
                window.set_theme(theme)
                window.controller.request('storage')
                pump(lambda: not window.controller.busy)
                for route in Route:
                    window.navigate(route)
                    if route == Route.DUPLICATES:
                        window.duplicates_flow.show_comparison(False)
                        window.update_shell()
                        window.duplicates.groups.setCurrentRow(1)
                        window.duplicates.groups.setFocus()
                        pump(lambda: not window.controller.busy)
                        expected = {p for row in window.group_rows for p in row.samples}
                        pump(lambda: expected <= window.duplicates.groups.groups_model.images.keys())
                    elif route == Route.SETTINGS:
                        window.preferences.theme.setFocus()
                    elif route == Route.SCAN:
                        window.scan.add.setFocus()
                    app.processEvents()
                    page = (window.duplicates_flow.listing if route == Route.DUPLICATES else window.pages[route])
                    page.verticalScrollBar().setValue(0)
                    assert page.horizontalScrollBar().maximum() == 0, route
                    capture(theme + '-' + route.value, window)
                window.navigate(Route.DUPLICATES)
                window.duplicates.table.selectRow(0)
                window.compare()
                pump(lambda: window.comparison.left.state == 'preview_ready')
                window.comparison.left.keep_photo.setFocus()
                QTest.keyClick(window.comparison.left.keep_photo, Qt.Key_Space)
                app.processEvents()
                window.duplicates_flow.comparison.ensureWidgetVisible(window.comparison.left.keep_photo)
                assert window.duplicates_flow.comparison.horizontalScrollBar().maximum() == 0
                capture(theme + '-compare-selected', window)
                window.comparison.right.set_image(None, 'synthetic_decoder_failure: preview diagnostics')
                window.comparison.right.details.set_expanded(True)
                window.comparison.right.error_details.set_expanded(True)
                app.processEvents()
                window.duplicates_flow.comparison.ensureWidgetVisible(window.comparison.right.error_details.text, 0, 0)
                capture(theme + '-preview-details', window)
                window.prepare_selected()
                pump(lambda: window.plan_dialog is not None)
                plan = window.plan_dialog.plan
                capture(theme + '-confirmation', window.plan_dialog)
                window.plan_dialog.reject()
                warnings = replace(plan, moves=(replace(plan.moves[0], raw=True, legacy=True,
                    kind=Kind.VISUAL, xmp=('synthetic.xmp',)),))
                dialog = PlanDialog(warnings, window)
                dialog.show()
                dialog.raw.setFocus()
                capture(theme + '-consent-warnings', dialog)
                assert dialog.warnings.isVisible() and dialog.raw.isVisible() and dialog.legacy.isVisible()
                dialog.reject()
                window.error('storage', 'synthetic_index_failure: technical diagnostic')
                window.navigate(Route.SETTINGS)
                window.preferences.error_details.set_expanded(True)
                window.pages[Route.SETTINGS].ensureWidgetVisible(window.preferences.error_details)
                capture(theme + '-storage-error-details', window)
                window.back_to_duplicates()
                # Refresh restores real previews before the next theme.
                window.invalidate_selection()
                window.duplicates_flow.show_comparison(False)
            assert originals == {p: p.read_bytes() for p in photos.iterdir()}
        finally:
            for box in window.findChildren(QMessageBox):
                box.close()
            window.close()
            pump(lambda: window.finished)
    (output / 'manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    run(parser.parse_args().output)
