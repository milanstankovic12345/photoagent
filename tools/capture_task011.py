"""Task011: repeatable Qt render/geometry evidence in a disposable synthetic home.

Run each QT_SCALE_FACTOR in a NEW process. Output must not already exist.
--scenarios adds the extended state/operation journey; the size matrix always runs.
No user settings or photographs are read. Windows uses its shared temporary
directory so public screenshots contain no real profile names or library paths.
"""
from __future__ import annotations

import argparse
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import replace
import faulthandler
import hashlib
import json
import os
from pathlib import Path
import platform
import tempfile
import threading
from unittest.mock import patch

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from PySide6.QtCore import QCoreApplication, QEvent, Qt, qVersion
from PySide6.QtGui import QFont, QFontDatabase
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QMessageBox, QWidget

from app.core.models import Cancelled, Kind
from app.ui.qt.components import PlanDialog
from app.ui.qt.navigation import Route
from app.ui.qt.window import MainWindow
from tools.capture_ux_audit import generate, pump

RESOLUTIONS = ((1280, 720), (1366, 768), (1650, 900), (1920, 1080))


@contextmanager
def isolated_environment(sandbox: Path) -> Iterator[None]:
    """Decoder subprocesses inherit only this temporary state; restore on exit."""
    keys = ('HOME', 'USERPROFILE', 'TMP', 'TEMP', 'TMPDIR')
    previous = {key: os.environ.get(key) for key in keys}
    try:
        for key in keys:
            os.environ[key] = str(sandbox)
        yield
    finally:
        for key, value in previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


def inspect_layout(window: MainWindow) -> dict:
    """Check the page viewport and real shell actions, not a resized bitmap.

    Metadata/member/history tables may scroll internally; the primary page must
    not require horizontal scrolling. Vertical scrolling is intentional.
    """
    QApplication.processEvents()
    page = window.pages[window.route]
    if window.route == Route.DUPLICATES:
        page = page.comparison if page.comparing else page.listing
    toolbar = next(toolbar for toolbar in window.toolbars if toolbar.isVisible())
    controls = [toolbar.actions.itemAt(i).widget() for i in range(toolbar.actions.count())]
    outside = []
    for control in controls:
        if control.isVisible():
            origin = control.mapTo(window, control.rect().topLeft())
            if not (window.rect().contains(origin) and
                    window.rect().contains(origin + control.rect().bottomRight())):
                outside.append(control.accessibleName() or control.text())
    overlaps = sum(a.geometry().intersects(b.geometry()) for i, a in enumerate(controls)
                   for b in controls[i + 1:] if a.isVisible() and b.isVisible())
    return {'page_horizontal_max': page.horizontalScrollBar().maximum(),
            'page_vertical_max': page.verticalScrollBar().maximum(),
            'toolbar_outside': outside, 'toolbar_overlaps': overlaps,
            'viewport': [page.viewport().width(), page.viewport().height()]}


def run(output: Path, scenarios: bool = False) -> None:
    output.mkdir(parents=True, exist_ok=False)
    app = QApplication.instance() or QApplication([])
    app.setStyle('Fusion')
    app.setQuitOnLastWindowClosed(False)
    if platform.system() == 'Windows' and app.platformName() == 'offscreen':
        for name in ('segoeui.ttf', 'segoeuib.ttf'):
            assert QFontDatabase.addApplicationFont(str(Path(os.environ['WINDIR']) / 'Fonts' / name)) >= 0
        app.setFont(QFont('Segoe UI', 10))
    scale = float(os.environ.get('QT_SCALE_FACTOR', '1'))
    manifest = {'python': platform.python_version(), 'platform': platform.system(),
        'qt_version': qVersion(), 'qt_platform': app.platformName(), 'scale_factor': scale,
        'synthetic': True, 'captures': [], 'checks': [], 'finished': False,
        'method': 'QWidget.grab, actual Qt event loop/workers/services. Physical target sizes '
                  'are divided by QT_SCALE_FACTOR to exercise constrained logical space. '
                  'No bitmap resizing used for DPI assertions. Internal metadata tables may scroll. '
                  'Loading/unavailable preview and RAW/legacy warnings are presentation fixtures. '
                  'Cancellation delays extraction but uses the real cancellation path. '
                  'All moves explicitly approved and restricted to generated temporary files.',
        'skipped': ['Native Windows/Linux display and monitor DPI transitions',
                    'NVDA/Narrator, physical media and cross-drive operations',
                    'Successful RAW decode: no redistributable RAW fixture',
                    'Full localization, release audit and packaging (Task012/013)']}
    windows = []
    requested = (1650, 900)

    def settled(window: MainWindow) -> None:
        pump(lambda: bool(window.settings) and not window.controller.busy, timeout=120)

    def create(home: Path) -> MainWindow:
        window = MainWindow(home)
        windows.append(window)
        window.resize(*(round(n / scale) for n in requested))
        window.show()
        settled(window)
        return window

    def close(window: MainWindow) -> None:
        window.close()
        pump(lambda: window.finished)
        assert not any(thread.isRunning() for thread in window.controller.threads)

    def dispose(window: MainWindow) -> None:
        """Release stopped Qt objects before creating the next service/window set."""
        close(window)
        windows.remove(window)
        window.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)

    def capture(name: str, window: MainWindow, widget: QWidget | None = None, *,
                fixture: str = 'real', matrix: bool = False) -> None:
        app.processEvents()
        QTest.qWait(60)
        widget = widget or window
        shot = widget.grab()
        target = output / (name + '.png')
        assert not target.exists() and shot.save(str(target))
        layout = inspect_layout(window)
        entry = {'file': target.name, 'theme': window.theme.active,
            'state': name, 'fixture': fixture, 'matrix': matrix,
            'target_physical': list(requested),
            'logical_size': [widget.width(), widget.height()],
            'window_logical': [window.width(), window.height()],
            'pixel_size': [shot.width(), shot.height()], 'dpr': shot.devicePixelRatio(),
            'layout': layout, 'sha256': hashlib.sha256(target.read_bytes()).hexdigest(),
            'visually_reviewed': False}
        manifest['captures'].append(entry)
        (output / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')
        assert abs(shot.devicePixelRatio() - scale) < .01, entry
        assert not layout['page_horizontal_max'] and not layout['toolbar_outside'] and not layout['toolbar_overlaps'], entry
        assert [window.width(), window.height()] == [round(n / scale) for n in requested], entry
        print(name, flush=True)

    def page(window: MainWindow, route: Route) -> None:
        window.navigate(route)
        app.processEvents()
        scroll = window.pages[route]
        if route == Route.DUPLICATES:
            scroll = scroll.comparison if scroll.comparing else scroll.listing
        scroll.verticalScrollBar().setValue(0)

    def both(window: MainWindow, name: str, route: Route | None = None,
             widget: QWidget | None = None, fixture: str = 'real') -> None:
        for theme in ('dark', 'light'):
            window.set_theme(theme)
            settled(window)
            if route is not None:
                page(window, route)
            if window.route == Route.DUPLICATES and not window.duplicates_flow.comparing:
                expected = {p for row in window.group_rows for p in row.samples}
                pump(lambda: expected <= window.duplicates.groups.groups_model.images.keys())
            capture(theme + '-' + name, window, widget, fixture=fixture)

    # Shared Windows temporary storage avoids recording a real account name.
    temp_parent = Path(os.environ['WINDIR']) / 'Temp' if platform.system() == 'Windows' else None
    with tempfile.TemporaryDirectory(prefix='photoagent-task011-', dir=temp_parent) as private:
        sandbox = Path(private)
        with isolated_environment(sandbox):
            photos = sandbox / 'synthetic-photos'
            generate(photos)
            originals = {p.name: p.read_bytes() for p in photos.iterdir()}
            window = create(sandbox / 'home')
            try:
                if scenarios:
                    both(window, 'dashboard-empty', Route.DASHBOARD)
                    both(window, 'scan-empty', Route.SCAN)
                    both(window, 'duplicates-empty', Route.DUPLICATES)
                    both(window, 'history-empty', Route.QUARANTINE)
                window.roots = [str(photos)]
                window.render_roots()
                window.controller.request('settings', {'roots': window.roots.copy()})
                settled(window)
                if scenarios:
                    both(window, 'scan-sources', Route.SCAN)
                    import app.services.indexing as indexing
                    original_extract = indexing.extract
                    started = threading.Event()

                    def delayed(*args):
                        started.set()
                        if args[-1].wait(2):
                            raise Cancelled()
                        return original_extract(*args)

                    for theme in ('dark', 'light'):
                        window.set_theme(theme)
                        settled(window)
                        with patch.object(indexing, 'extract', delayed):
                            started.clear()
                            window.start_scan()
                            pump(started.is_set)
                            capture(theme + '-scan-running', window, fixture='delayed extraction')
                            window.cancel()
                            settled(window)
                        assert window.status == 'cancelled' and not window.duplicates.bulk.isEnabled()
                        capture(theme + '-scan-cancelled', window)
                window.start_scan()
                settled(window)
                assert window.status == 'complete'
                assert any(row.kind == 'EXACT' and row.members == 3 for row in window.group_rows)
                assert any(row.kind == 'VISUAL' for row in window.group_rows)
                if scenarios:
                    both(window, 'scan-complete', Route.SCAN)
                    # Filter and list states use real query services.
                    page(window, Route.DUPLICATES)
                    window.duplicates.mode.setCurrentIndex(1)
                    both(window, 'duplicates-list')
                    window.duplicates.search.setText('no-such-synthetic-photo')
                    pump(lambda: window.query.text == 'no-such-synthetic-photo' and not window.controller.busy)
                    both(window, 'duplicates-filtered')
                    window.duplicates.search.clear()
                    pump(lambda: window.query.text == '' and not window.controller.busy)
                window.duplicates.mode.setCurrentIndex(0)
                # Broad matrix: every main page and loaded comparison in both themes.
                for requested in RESOLUTIONS:
                    window.resize(*(round(n / scale) for n in requested))
                    for theme in ('dark', 'light'):
                        window.set_theme(theme)
                        settled(window)
                        for route in Route:
                            window.duplicates_flow.show_comparison(False)
                            page(window, route)
                            if route == Route.DASHBOARD:
                                app.processEvents()
                                QTest.qWait(150)
                            if route == Route.DUPLICATES:
                                expected = {p for row in window.group_rows for p in row.samples}
                                pump(lambda: expected <= window.duplicates.groups.groups_model.images.keys())
                            capture(f'matrix-{requested[0]}-{theme}-{route.value}', window, matrix=True)
                        page(window, Route.DUPLICATES)
                        index = next(i for i, row in enumerate(window.duplicates.model.rows) if row.match.kind == Kind.EXACT)
                        window.duplicates.table.selectRow(index)
                        window.compare()
                        settled(window)  # A direct-group query may replace the selected row.
                        pump(lambda: window.comparison.left.state == window.comparison.right.state == 'preview_ready')
                        capture(f'matrix-{requested[0]}-{theme}-compare', window, matrix=True)
                        assert window.comparison.left.scene.items() and window.comparison.right.scene.items()
                        window.back_to_duplicates()
                requested = (1650, 900)
                window.resize(*(round(n / scale) for n in requested))
                if scenarios:
                    page(window, Route.DUPLICATES)
                    exact = next(i + 1 for i, row in enumerate(window.group_rows) if row.kind == 'EXACT')
                    window.duplicates.groups.setCurrentRow(exact)
                    settled(window)
                    both(window, 'exact-three-members')
                    window.duplicates.table.selectRow(0)
                    window.compare()
                    settled(window)
                    pump(lambda: window.comparison.left.state == window.comparison.right.state == 'preview_ready')
                    window.choose_keeper(False)
                    both(window, 'compare-keeper')
                    window.keep_both()
                    assert not window.pending_pairs()
                    both(window, 'compare-keep-both')
                    for theme in ('dark', 'light'):
                        window.set_theme(theme)
                        settled(window)
                        window.comparison.right.show_state('preview_loading')
                        capture(theme + '-compare-loading', window, fixture='presentation only')
                        window.comparison.right.set_image(None, 'synthetic preview unavailable')
                        capture(theme + '-compare-unavailable', window, fixture='presentation only')
                        window.comparison.right.details.set_expanded(True)
                        window.comparison.right.error_details.set_expanded(True)
                        capture(theme + '-compare-details', window, fixture='presentation only')
                    window.choose_keeper(False)
                    window.choose_keeper(True, False)
                    assert len(window.pending_pairs()) == 1
                    window.prepare_selected()
                    pump(lambda: window.plan_dialog is not None)
                    plan = window.plan_dialog.plan
                    both(window, 'confirmation', widget=window.plan_dialog)
                    window.plan_dialog.reject()
                    assert originals == {name: (photos / name).read_bytes() for name in originals}
                    both(window, 'confirmation-rejected')
                    for theme in ('dark', 'light'):
                        window.set_theme(theme)
                        settled(window)
                        warnings = replace(plan, moves=(replace(plan.moves[0], raw=True, legacy=True,
                            kind=Kind.VISUAL, xmp=('synthetic.xmp',)),))
                        dialog = PlanDialog(warnings, window)
                        dialog.show()
                        capture(theme + '-confirmation-warnings', window, dialog, fixture='presentation only; never executed')
                        assert not dialog.confirm.isEnabled()
                        dialog.reject()
                    window.prepare_selected()
                    pump(lambda: window.plan_dialog is not None)
                    move = window.plan_dialog.plan.moves[0]
                    window.plan_dialog.approve()  # Only the displayed generated temporary photograph.
                    settled(window)
                    both(window, 'history-populated', Route.QUARANTINE)
                    dispose(window)
                    window = create(sandbox / 'home')
                    page(window, Route.QUARANTINE)
                    row = next(i for i, entry in enumerate(window.history_rows) if entry.id == move.id)
                    window.history.table.selectRow(row)
                    settled(window)
                    both(window, 'history-after-restart')
                    # A real destination conflict must retain both byte sequences.
                    Path(move.source).write_bytes(b'synthetic occupied destination')
                    window.restore()
                    settled(window)
                    pump(lambda: any(box.isVisible() for box in window.findChildren(QMessageBox)))
                    box = next(box for box in window.findChildren(QMessageBox) if box.isVisible())
                    both(window, 'restore-conflict', widget=box)
                    box.close()
                    assert Path(move.source).read_bytes() == b'synthetic occupied destination'
                    assert Path(move.destination).read_bytes() == originals[Path(move.source).name]
                    # Preserve the synthetic conflicting file too; do not delete or overwrite it.
                    Path(move.source).rename(sandbox / 'preserved-conflict.bin')
                    window.history.table.selectRow(row)
                    window.restore()
                    pump(lambda: window.plan_dialog is not None)
                    both(window, 'restore-confirmation', widget=window.plan_dialog)
                    window.plan_dialog.approve()
                    settled(window)
                    both(window, 'history-restored', Route.QUARANTINE)
                    assert originals == {name: (photos / name).read_bytes() for name in originals}
                    # VISUAL remains a direct, manually reviewed pair.
                    window.review_results()
                    settled(window)
                    visual = next(i for i, row in enumerate(window.duplicates.model.rows) if row.match.kind == Kind.VISUAL)
                    window.duplicates.table.selectRow(visual)
                    window.compare()
                    settled(window)
                    pump(lambda: window.comparison.left.state == window.comparison.right.state == 'preview_ready')
                    both(window, 'visual-review')
                    window.back_to_duplicates()
                    # Actual incomplete/offline scan, not fabricated dashboard counters.
                    (photos / 'bad.nef').write_bytes(b'synthetic undecodable RAW')
                    window.roots.append(str(sandbox / 'offline-drive'))
                    window.render_roots()
                    window.start_scan()
                    settled(window)
                    assert window.status == 'incomplete' and not window.duplicates.bulk.isEnabled()
                    both(window, 'scan-errors', Route.SCAN)
                    window.scan.error_section.set_expanded(True)
                    both(window, 'scan-error-details')
                    both(window, 'dashboard-incomplete', Route.DASHBOARD)
                    window.controller.request('bulk', window.session)
                    settled(window)
                    pump(lambda: any(box.isVisible() for box in window.findChildren(QMessageBox)))
                    box = next(box for box in window.findChildren(QMessageBox) if box.isVisible())
                    both(window, 'operation-refused', widget=box)
                    box.close()
                    page(window, Route.SETTINGS)
                    window.preferences.load_matching(13, 17)
                    window.save_settings()
                    settled(window)
                    both(window, 'settings-custom')
                    scroll = window.pages[Route.SETTINGS]
                    for theme in ('dark', 'light'):
                        window.set_theme(theme)
                        settled(window)
                        for suffix, target in (('matching', window.preferences.preset),
                                               ('storage-about', window.preferences.index)):
                            scroll.ensureWidgetVisible(target, 0, 100)
                            capture(theme + '-settings-' + suffix, window)
                    dispose(window)
                    window = create(sandbox / 'home')
                    assert window.theme.active == 'light'
                    assert (window.settings['phash_max'], window.settings['dhash_max']) == (13, 17)
                    page(window, Route.SETTINGS)
                    capture('light-settings-persisted', window)
                    window.theme.apply('system', Qt.ColorScheme.Light)
                    capture('system-light', window)
                    window.theme.system_changed(Qt.ColorScheme.Dark)
                    assert window.theme.active == 'dark'
                    capture('system-dark', window)
                    window.theme.system_changed(Qt.ColorScheme.Unknown)
                    assert window.theme.active == 'dark' and window.theme.preference == 'system'
                    capture('system-fallback', window)
                    manifest['checks'].extend(['Rejected confirmation left every original byte unchanged',
                        'Approved synthetic move, fresh MainWindow restart, conflict refusal, approved restore',
                        'Restored originals byte-identical; conflicting synthetic content preserved separately',
                        'Actual incomplete scan refused bulk; RAW decode failure visible',
                        'Saved Light and custom 13/17 survived restart; injected System changes/fallback rendered'])
                manifest['checks'].append('All 48 matrix page/comparison geometries passed at this Qt DPR')
            finally:
                print('Closing synthetic windows/workers', flush=True)
                faulthandler.dump_traceback_later(30, repeat=True)
                try:
                    for existing in windows[:]:
                        for box in existing.findChildren(QMessageBox):
                            box.close()
                        dispose(existing)
                    app.processEvents()
                    (output / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')
                    print('Qt cleanup complete; removing synthetic sandbox', flush=True)
                finally:
                    faulthandler.cancel_dump_traceback_later()
    # Publish completion only after every worker and the disposable sandbox closed.
    manifest['finished'] = True
    (output / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')
    print(f'Completed {len(manifest["captures"])} captures; temporary state removed.', flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--scenarios', action='store_true')
    args = parser.parse_args()
    run(args.output, args.scenarios)
