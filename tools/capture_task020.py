"""Task020 real Qt captures and explicit synthetic quarantine/restore exercise."""
from __future__ import annotations

import argparse
from dataclasses import replace
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

from app.core.models import Kind, Match
from app.core.queries import MatchRow
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
        'method': 'Real Qt widgets/workers/services and generated PNG/JPEG photos. '
                  'One explicit synthetic quarantine and restore. RAW/backup warning is a '
                  'presentation fixture only; no fake RAW is approved or moved.', 'captures': []}
    with tempfile.TemporaryDirectory(prefix='synthetic-', dir=output) as directory:
        sandbox = Path(directory)
        with isolated_environment(sandbox), isolated_framework_settings(sandbox):
            photos = sandbox / 'photos'
            photos.mkdir()
            with Image.new('RGB', (900, 600), '#abcce5') as image:
                draw = ImageDraw.Draw(image)
                draw.rectangle((35, 80, 490, 410), fill='#a84130')
                draw.ellipse((430, 190, 850, 550), fill='#d7bd50')
                image.save(photos / 'scene.png')
                image.save(photos / 'rendered.jpg', quality=92)
            for name in ('scene-copy.png', 'scene-backup.png'):
                shutil.copy2(photos / 'scene.png', photos / name)
            originals = {p: p.read_bytes() for p in photos.iterdir()}
            window = MainWindow(sandbox / 'home')
            window.show()
            try:
                pump(lambda: window.settings and not window.controller.busy)
                window.roots = [str(photos)]
                window.render_roots()
                window.start_scan()
                pump(lambda: window.session and not window.controller.busy, timeout=90)
                window.review_results()
                window.duplicates.kind.setCurrentIndex(window.duplicates.kind.findData('EXACT'))
                pump(lambda: not window.controller.busy and window.query.kind == 'EXACT'
                     and bool(window.duplicates.model.rows))
                window.duplicates.table.selectRow(0)
                window.compare()
                pump(lambda: not window.controller.busy and window.comparison.right.state == 'preview_ready')

                def capture(name: str, *, bottom: bool = False, dialog: bool = False) -> None:
                    scroll = window.duplicates_flow.comparison
                    scroll.verticalScrollBar().setValue(scroll.verticalScrollBar().maximum() if bottom else 0)
                    QTest.qWait(80)
                    window.header.layout().activate()
                    app.processEvents()
                    assert window.header.rect().contains(window.header.title.geometry())
                    assert window.header.title.height() >= window.header.title.fontMetrics().height()
                    layout = inspect_layout(window)
                    assert not any(layout[key] for key in
                        ('toolbar_outside', 'toolbar_overlaps', 'page_horizontal_max')), layout
                    for control in (window.comparison.both, window.comparison.prepare):
                        position = control.mapTo(window, control.rect().topLeft())
                        assert window.rect().contains(position)
                        assert window.rect().contains(position + control.rect().bottomRight())
                    widget = window.plan_dialog if dialog else window
                    shot = widget.grab()
                    path = output / (name + '.png')
                    assert shot.save(str(path))
                    manifest['captures'].append({'file': path.name, 'layout': layout,
                        'language': language_manager().language, 'theme': window.theme.active,
                        'logical': [widget.width(), widget.height()],
                        'physical': [shot.width(), shot.height()], 'dpr': shot.devicePixelRatio(),
                        'sha256': hashlib.sha256(path.read_bytes()).hexdigest()})

                window.choose_keeper(False)
                for language in ('en', 'sr_Latn'):
                    language_manager().set_language(language)
                    for theme in ('dark', 'light'):
                        window.theme.apply(theme)
                        for width, height in ((1440, 900), (853, 480)):
                            window.resize(width, height)
                            capture(f'exact-{language}-{theme}-{width}')
                            if width == 853:
                                capture(f'exact-{language}-{theme}-{width}-bottom', bottom=True)
                window.keep_both()
                assert not window.pending_pairs()
                capture('keep-both-sr_Latn-light')

                # Confirm/cancel uses the real preflight; neither choice nor Cancel moves anything.
                window.choose_keeper(False)
                window.choose_keeper(True, False)
                window.prepare_selected()
                pump(lambda: window.plan_dialog is not None)
                capture('confirmation-sr_Latn-light', dialog=True)
                window.plan_dialog.reject()
                assert all(path.read_bytes() == data for path, data in originals.items())
                window.prepare_selected()
                pump(lambda: window.plan_dialog is not None)
                move = window.plan_dialog.plan.moves[0]
                window.plan_dialog.approve()
                pump(lambda: not window.controller.busy)
                assert window.restore_id == move.id and not Path(move.source).exists()
                window.restore_context()
                pump(lambda: window.plan_dialog is not None)
                window.plan_dialog.approve()
                pump(lambda: not window.controller.busy)
                assert all(path.read_bytes() == data for path, data in originals.items())

                window.duplicates.kind.setCurrentIndex(window.duplicates.kind.findData('VISUAL'))
                pump(lambda: not window.controller.busy and window.query.kind == 'VISUAL')
                window.duplicates.table.selectRow(0)
                window.compare()
                pump(lambda: not window.controller.busy and window.comparison.right.state == 'preview_ready')
                window.choose_keeper(True)
                window.resize(1440, 900)
                language_manager().set_language('en')
                window.theme.apply('dark')
                capture('visual-en-dark')
                row = window.controller.selection
                raw = replace(row.match.keep, is_raw=True, ext='.nef', image_format='')
                backup = replace(row.match.dup, root=str(sandbox / 'backup-drive'))
                window.duplicates.model.replace((MatchRow(9001, 9001, Match(Kind.VISUAL, raw, backup)),))
                window.duplicates.table.selectRow(0)
                capture('raw-backup-warning-en-dark')
                manifest['original_bytes_restored'] = all(p.read_bytes() == data for p, data in originals.items())
                manifest['confirmed_synthetic_quarantine_restore'] = True
                manifest['finished'] = True
            finally:
                window.close()
                pump(lambda: window.finished)
                language_manager().set_language('en')
    (output / 'manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    print(json.dumps({'output': str(output), 'captures': len(manifest['captures']), 'finished': True}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output', type=Path)
    run(parser.parse_args().output)
