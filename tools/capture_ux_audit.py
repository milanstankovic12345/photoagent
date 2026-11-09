"""Capture the existing Qt UX using only generated files and a private temporary home.

Run from the repository root with ``python -B -m tools.capture_ux_audit --output ...``.
The output must be new. It contains PNG evidence and a manifest, never recovery data.
This drives real window slots/workers, not native mouse input or a physical display.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import shutil
import tempfile
import time
from typing import Callable

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from PIL import Image, ImageDraw
from PySide6.QtGui import QFont, QFontDatabase
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QMessageBox

from app.ui.qt.window import MainWindow


def pump(predicate: Callable[[], bool], timeout: float = 60) -> None:
    deadline = time.monotonic() + timeout
    while not predicate():
        if time.monotonic() >= deadline:
            raise TimeoutError('Audit worker did not settle')
        QTest.qWait(10)
    QApplication.processEvents()


def generate(root: Path) -> None:
    root.mkdir()
    with Image.new('RGB', (640, 480), '#b4c8e0') as image:
        draw = ImageDraw.Draw(image)
        draw.rectangle((35, 45, 360, 325), fill='#cd2838')
        draw.ellipse((310, 185, 595, 460), fill='#28723f')
        for x in range(0, 640, 32):
            draw.line((x, 0, 640 - x, 479), fill='#364e87', width=3)
        image.save(root / 'a-original.png')
        image.save(root / 'd-export.jpg', quality=94)
    for name in ('b-copy.png', 'c-copy.png'):
        shutil.copy2(root / 'a-original.png', root / name)
    with Image.new('RGB', (320, 240), '#e3cd64') as image:
        ImageDraw.Draw(image).polygon(((0, 0), (320, 200), (50, 220)), fill='#251c40')
        image.save(root / 'e-other.png')


def run(output: Path) -> None:
    output = output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    manifest: dict = {
        'environment': {
            'python': platform.python_version(), 'platform': platform.platform(),
            'qt_platform': os.environ['QT_QPA_PLATFORM'], 'style': 'Fusion',
            'viewport_logical': [1280, 800],
            'versions': {name: importlib.metadata.version(name) for name in ('PySide6', 'Pillow')},
        },
        'method': 'Real Qt widgets, event loop, workers and services; window slots drive actions. '
                  'No OS window decoration, native folder chooser, or physical display tested.',
        'screenshots': [], 'checks': [], 'dashboard': [], 'scan_summaries': [],
    }
    app = QApplication.instance() or QApplication([])
    app.setStyle('Fusion')
    app.setQuitOnLastWindowClosed(False)
    # The Windows offscreen plugin can expose no system fonts. Load installed
    # fonts for this process only; do not change application or system settings.
    loaded_fonts = []
    if platform.system() == 'Windows' and app.platformName() == 'offscreen':
        fonts = Path(os.environ['WINDIR']) / 'Fonts'
        for name in ('segoeui.ttf', 'segoeuib.ttf'):
            font_id = QFontDatabase.addApplicationFont(str(fonts / name))
            if font_id < 0:
                raise RuntimeError('Installed Segoe UI font unavailable for offscreen capture')
            loaded_fonts.extend(QFontDatabase.applicationFontFamilies(font_id))
        app.setFont(QFont('Segoe UI', 10))
    manifest['environment']['loaded_font_families'] = loaded_fonts
    manifest['environment']['font_family'] = app.font().family()
    windows: list[MainWindow] = []

    def capture(name: str, widget, state: str) -> None:
        QApplication.processEvents()
        pixmap = widget.grab()
        path = output / (name + '.png')
        if not pixmap.save(str(path)):
            raise OSError(f'Cannot save {path}')
        manifest['screenshots'].append({
            'file': path.name, 'state': state, 'width': pixmap.width(), 'height': pixmap.height(),
            'device_pixel_ratio': pixmap.devicePixelRatio(),
            'sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
        })
        print('Captured ' + name, flush=True)

    def page(window: MainWindow, index: int, name: str, state: str) -> None:
        window.navigation.setCurrentRow(index)
        QApplication.processEvents()
        capture(name, window, state)

    def settled(window: MainWindow) -> None:
        pump(lambda: bool(window.settings) and not window.controller.busy)

    def create(home: Path) -> MainWindow:
        window = MainWindow(home)
        windows.append(window)
        window.resize(1280, 800)
        window.show()

        def record(action: str, value) -> None:
            if action == 'dashboard':
                manifest['dashboard'].append(asdict(value))
            elif action == 'scan':
                manifest['scan_summaries'].append(asdict(value[0]))

        window.controller.result.connect(record)
        settled(window)
        return window

    def close(window: MainWindow) -> None:
        window.close()
        pump(lambda: window.finished)
        assert all(not thread.isRunning() for thread in window.controller.threads)

    with tempfile.TemporaryDirectory(prefix='photoagent-task004-') as private:
        sandbox = Path(private).resolve()
        # Child decoders inherit this process-only environment; the user's state is untouched.
        for key in ('HOME', 'USERPROFILE', 'TMP', 'TEMP', 'TMPDIR'):
            os.environ[key] = str(sandbox)
        home = sandbox / 'home'
        photos = sandbox / 'photos'
        generate(photos)
        original = {p.name: p.read_bytes() for p in photos.iterdir()}
        try:
            window = create(home)
            names = ('dashboard', 'scan', 'duplicates', 'compare', 'quarantine', 'settings')
            for i, name in enumerate(names):
                page(window, i, f'{i + 1:02}-{name}-initial', 'No scan; empty application home')

            window.roots = [str(photos)]
            window.render_roots()
            window.controller.request('settings', {'roots': window.roots.copy()})
            settled(window)
            page(window, 1, '07-scan-sources', 'One generated source, before scan')
            progress_captured = []

            def progress(value) -> None:
                if value.phase == 'scan' and value.processed and not progress_captured:
                    progress_captured.append(True)
                    capture('08-scan-running', window, 'Actual worker scan progress')

            window.controller.progress.connect(progress)
            window.start_scan()
            settled(window)
            window.controller.progress.disconnect(progress)
            assert progress_captured and window.status == 'complete'
            assert any(row.kind == 'EXACT' and row.members == 3 for row in window.group_rows)
            assert any(row.kind == 'VISUAL' for row in window.group_rows)
            capture('09-scan-complete', window, 'Completed real scan of five generated photos')
            page(window, 0, '10-dashboard-populated', 'Actual summary after completed scan')
            page(window, 2, '11-duplicates-populated', 'Actual direct groups and candidate pairs')
            window.duplicates.search.setText('no-such-generated-photo')
            pump(lambda: window.query.text == 'no-such-generated-photo' and not window.controller.busy)
            capture('12-duplicates-no-filter-results', window, 'No result for literal search')
            window.duplicates.search.clear()
            pump(lambda: window.query.text == '' and not window.controller.busy)
            group_index = next(i + 1 for i, row in enumerate(window.group_rows) if row.kind == 'EXACT')
            window.duplicates.groups.setCurrentRow(group_index)
            settled(window)
            capture('13-exact-three-members', window, 'Exact group: retained original plus two candidate copies')
            previews = []
            window.controller.preview_ready.connect(previews.append)
            selected = next(i for i, row in enumerate(window.duplicates.model.rows)
                            if Path(row.match.dup.path).name == 'b-copy.png')
            window.duplicates.table.selectRow(selected)
            pump(lambda: bool(previews))
            window.compare()
            QApplication.processEvents()
            window.comparison.left.fit()
            window.comparison.right.fit()
            capture('14-compare-exact', window, 'Both real generated previews loaded')

            window.prepare_selected()
            pump(lambda: window.plan_dialog is not None)
            dialog = window.plan_dialog
            assert dialog.approval is None and len(dialog.plan.moves) == 1
            capture('15-quarantine-confirmation', dialog, 'Real single-move plan; no Approval yet')
            dialog.reject()
            assert all((photos / name).read_bytes() == data for name, data in original.items())
            manifest['checks'].append('Reject confirmation: all five original byte sequences unchanged')
            window.prepare_selected()
            pump(lambda: window.plan_dialog is not None)
            operation_id = window.plan_dialog.plan.moves[0].id
            window.plan_dialog.approve()  # Only generated b-copy.png, in the private temp root.
            settled(window)
            assert not (photos / 'b-copy.png').exists()
            assert any(row.id == operation_id and row.restorable for row in window.history_rows)
            page(window, 4, '16-quarantine-populated', 'Completed synthetic quarantine; one restorable operation')
            close(window)
            window = create(home)
            assert window.roots == [str(photos)]
            page(window, 4, '17-quarantine-after-restart', 'New MainWindow and worker services; same private journal')
            row = next(i for i, entry in enumerate(window.history_rows) if entry.id == operation_id)
            window.history.table.selectRow(row)
            window.restore()
            pump(lambda: window.plan_dialog is not None)
            assert window.plan_dialog.plan.moves[0].restores == operation_id
            capture('18-restore-confirmation', window.plan_dialog, 'Restore selected operation ID after restart')
            window.plan_dialog.approve()
            settled(window)
            assert all((photos / name).read_bytes() == data for name, data in original.items())
            capture('19-quarantine-restored', window, 'Restore completed; original operation is no longer eligible')
            manifest['checks'].append('Quarantine, service restart and selected-ID restore preserve all original bytes')

            # A genuinely malformed file and an absent source produce real service/UI errors.
            (photos / 'bad.nef').write_bytes(b'synthetic invalid RAW')
            window.roots.append(str(sandbox / 'offline-drive'))
            window.render_roots()
            window.navigation.setCurrentRow(1)
            window.start_scan()
            settled(window)
            assert window.status == 'incomplete' and window.scan.errors.toPlainText()
            assert not window.duplicates.bulk.isEnabled()
            capture('20-scan-errors-offline', window, 'Incomplete scan: malformed RAW and missing synthetic drive')
            page(window, 0, '21-dashboard-incomplete', 'Actual incomplete/offline warnings; review only')
            manifest['checks'].append('Incomplete scan disables bulk quarantine')

            # A real worker rejects preparation from an incomplete session; no injected error text.
            window.controller.request('bulk', window.session)
            settled(window)
            pump(lambda: bool(window.findChildren(QMessageBox)))
            box = window.findChildren(QMessageBox)[-1]
            capture('22-operation-error', box, 'Worker rejects incomplete_scan; real error dialog')
            box.reject()
            page(window, 5, '23-settings-populated', 'Current controls and actual private index location')
            window.preferences.theme.setCurrentIndex(window.preferences.theme.findData('light'))
            settled(window)
            capture('24-settings-light', window, 'Existing Light theme after actual settings persistence')
            close(window)
            window = create(home)
            assert window.theme.active == 'light'
            manifest['checks'].append('Light theme survives service/window restart')
            manifest['checks'].append('Every worker thread stopped before temporary sandbox cleanup')
        finally:
            for window in windows:
                if not window.finished:
                    close(window)
                window.deleteLater()
            QApplication.processEvents()
        # Replace volatile private paths in the text manifest; PNGs retain actual rendered paths.
        rendered = json.dumps(manifest, ensure_ascii=False, indent=2)
        rendered = rendered.replace(str(sandbox).replace('\\', '\\\\'), '<private-temp>')
        (output / 'manifest.json').write_text(rendered + '\n', encoding='utf-8')
    print(f'Completed {len(manifest["screenshots"])} captures; private sandbox removed.', flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    run(parser.parse_args().output)
