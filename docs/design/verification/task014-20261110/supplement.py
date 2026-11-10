"""Additional Task014 identity, disclosure and empty-result audit evidence.

Run from the repository root with the same Python as capture.py. Reuses the
existing synthetic generator and environment guards. Never launches an OS viewer.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT))
os.environ['QT_QPA_PLATFORM'] = 'offscreen'
os.environ['QT_SCALE_FACTOR'] = '1'

from PySide6.QtCore import QCoreApplication, QEvent, Qt
from PySide6.QtGui import QFont, QFontDatabase, QDesktopServices
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QFileDialog
from unittest.mock import patch

from app.ui.qt.navigation import Route
from app.ui.qt.window import MainWindow
from tools.capture_task011 import isolated_environment, inspect_layout
from tools.capture_task012 import isolated_framework_settings
from tools.capture_ux_audit import generate, pump


def run(output: Path) -> None:
    output.mkdir(exist_ok=False)
    app = QApplication([])
    app.setStyle('Fusion')
    app.setQuitOnLastWindowClosed(False)
    if sys.platform == 'win32':
        for font in ('segoeui.ttf', 'segoeuib.ttf'):
            assert QFontDatabase.addApplicationFont(str(Path(os.environ['WINDIR']) / 'Fonts' / font)) >= 0
        app.setFont(QFont('Segoe UI', 10))
    manifest = {'synthetic': True, 'finished': False, 'captures': [], 'checks': [],
                'method': 'Real Qt widgets/workers; QWidget.grab; offscreen Fusion, DPR 1. '
                          'QTest double-click with mocked OS adapter. No moves in this supplement.'}

    def settle() -> None:
        pump(lambda: bool(window.settings) and not window.controller.busy, timeout=120)

    def capture(name: str, widget=None, *, fixture='real') -> None:
        app.processEvents()
        QTest.qWait(80)
        widget = widget or window
        shot = widget.grab()
        target = output / (name + '.png')
        assert shot.save(str(target))
        manifest['captures'].append({'file': target.name, 'fixture': fixture,
            'language': window.preferences.language.currentData(), 'theme': window.theme.active,
            'pixel_size': [shot.width(), shot.height()], 'dpr': shot.devicePixelRatio(),
            'sha256': hashlib.sha256(target.read_bytes()).hexdigest(),
            'layout': inspect_layout(window), 'visually_reviewed': False})
        print(name, flush=True)

    def reveal_bottom(scroll) -> None:
        # Disclosures relayout asynchronously; wait before choosing the viewport.
        # The first run exposed this capture-only timing issue during visual review.
        for _ in range(3):
            app.processEvents()
            QTest.qWait(150)
            scroll.verticalScrollBar().setValue(scroll.verticalScrollBar().maximum())

    with tempfile.TemporaryDirectory(prefix='photoagent-task014-', dir=Path(os.environ['WINDIR']) / 'Temp'
                                     if sys.platform == 'win32' else None) as private:
        sandbox = Path(private)
        with isolated_environment(sandbox), isolated_framework_settings(sandbox):
            photos = sandbox / 'synthetic-photos'
            generate(photos)
            original = {p.name: p.read_bytes() for p in photos.iterdir()}
            window = MainWindow(sandbox / 'home')
            window.resize(1280, 720)
            window.show()
            try:
                settle()
                window.navigate(Route.DUPLICATES)
                window.duplicates_flow.show_comparison(True)
                window.update_shell()
                capture('01-compare-no-selection')
                window.duplicates_flow.show_comparison(False)
                window.navigate(Route.SCAN)
                window.add_root()
                picker = window.findChild(QFileDialog)
                assert picker and picker.isVisible()
                capture('02-add-folder', picker)
                # Use the same selected-folder handler as the picker; only generated photos.
                picker.reject()
                window.add_selected_root(str(photos))
                settle()
                window.scan.advanced.set_expanded(True)
                capture('03-scan-advanced')
                window.start_scan()
                settle()
                assert window.status == 'complete'
                window.navigate(Route.DASHBOARD)
                area = window.pages[Route.DASHBOARD]
                area.ensureWidgetVisible(window.dashboard.cards[0], 0, 0)
                pump(lambda: window.dashboard.cards[0].loaded)
                capture('04-dashboard-candidates')
                window.navigate(Route.DUPLICATES)
                group = next(i + 1 for i, row in enumerate(window.group_rows) if row.kind == 'EXACT')
                window.activate_group(window.duplicates.groups.model().index(group))
                settle()
                pump(lambda: window.comparison.left.state == window.comparison.right.state == 'preview_ready')
                window.comparison.member_section.set_expanded(True)
                reveal_bottom(window.duplicates_flow.comparison)
                capture('05-exact-members-expanded')
                manifest['displayed_pairs'] = [asdict(row) for row in window.duplicates.model.rows]
                before = (window.selected_id, window.operation_epoch, window.pending_pairs())
                with patch.object(QDesktopServices, 'openUrl', return_value=True) as launch:
                    QTest.mouseDClick(window.comparison.left.view.viewport(), Qt.LeftButton)
                    assert launch.call_count == 0
                assert before == (window.selected_id, window.operation_epoch, window.pending_pairs())
                assert window.comparison.left.enlarged is None
                manifest['checks'].append('Current preview double-click: no OS launch, keeper change, plan or enlarged viewer')
                window.comparison.left.show_enlarged()
                capture('06-internal-enlarged-preview', window.comparison.left.enlarged)
                window.comparison.left.enlarged.close()
                window.comparison.member_section.set_expanded(False)
                window.comparison.right.details.set_expanded(True)
                reveal_bottom(window.duplicates_flow.comparison)
                capture('07-actual-photo-details')
                window.preferences.language.setCurrentIndex(window.preferences.language.findData('sr_Latn'))
                settle()
                window.duplicates_flow.comparison.verticalScrollBar().setValue(0)
                capture('08-sr-review')
                window.navigate(Route.SETTINGS)
                window.preferences.advanced.set_expanded(True)
                reveal_bottom(window.pages[Route.SETTINGS])
                capture('09-sr-settings-advanced')
                window.preferences.error_details.set_detail('synthetic settings storage diagnostic')
                window.preferences.error_details.set_expanded(True)
                reveal_bottom(window.pages[Route.SETTINGS])
                capture('10-settings-diagnostic', fixture='presentation only: injected diagnostic, no failed write')
                window.preferences.language.setCurrentIndex(window.preferences.language.findData('en'))
                settle()
                # A separate source with one generated photo gives a true no-match scan.
                single = sandbox / 'one-photo'
                single.mkdir()
                (single / 'one.png').write_bytes((photos / 'e-other.png').read_bytes())
                window.roots = [str(single)]
                window.render_roots()
                window.start_scan()
                settle()
                assert window.status == 'complete' and not window.total and not window.group_total
                window.navigate(Route.DUPLICATES)
                window.duplicates_flow.show_comparison(False)
                window.update_shell()
                window.duplicates.kind.setCurrentIndex(1)
                settle()
                pump(lambda: not window.search_timer.isActive() and not window.controller.busy)
                window.duplicates.kind.setCurrentIndex(0)
                pump(lambda: not window.search_timer.isActive() and not window.controller.busy)
                capture('11-duplicates-no-matches')
                window.navigate(Route.DASHBOARD)
                capture('12-dashboard-no-matches')
                (single / 'bad.nef').write_bytes(b'synthetic undecodable RAW')
                window.roots.append(str(sandbox / 'offline-source'))
                window.render_roots()
                window.start_scan()
                settle()
                assert window.status == 'incomplete'
                window.navigate(Route.SCAN)
                window.scan.error_section.set_expanded(True)
                reveal_bottom(window.pages[Route.SCAN])
                capture('13-scan-actual-error-details')
                window.navigate(Route.SETTINGS)
                window.pages[Route.SETTINGS].verticalScrollBar().setValue(0)
                capture('14-settings-current-sources')
                assert original == {p.name: p.read_bytes() for p in photos.iterdir()}
                manifest['checks'].append('All five generated original files remain byte-identical; no quarantine operations')
            finally:
                window.close()
                pump(lambda: window.finished)
                window.deleteLater()
                QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
    manifest['finished'] = True
    (output / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(f'Completed {len(manifest["captures"])} supplemental captures; temporary state removed.', flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=Path(__file__).parent / 'supplement')
    run(parser.parse_args().output)
