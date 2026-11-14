"""Final refinement evidence on real Qt widgets, exclusively synthetic local data.

Run in a fresh process per QT_SCALE_FACTOR. Refuse existing output directories.
Widget captures and simulated System signals never establish native acceptance.
No external viewer is launched. One displayed synthetic move/restore is approved.
"""
from __future__ import annotations

import argparse
from dataclasses import replace
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import tempfile
from threading import Event
from unittest.mock import patch

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from PySide6.QtCore import QCoreApplication, QEvent, QSignalBlocker, Qt, qVersion
from PySide6.QtGui import QDesktopServices, QFont, QFontDatabase
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QFileDialog, QMessageBox

import app.services.indexing as indexing
from app.core.models import Kind, Match
from app.core.queries import MatchRow
from app.ui.qt.localization import language_manager
from app.ui.qt.navigation import Route
from app.ui.qt.strings import tr
from app.ui.qt.window import MainWindow
from tools.capture_task011 import inspect_layout, isolated_environment
from tools.capture_task012 import isolated_framework_settings
from tools.capture_ux_audit import generate, pump


def run(output: Path, history_only: bool = False) -> None:
    output = output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    app = QApplication([])
    app.setStyle('Fusion')
    app.setQuitOnLastWindowClosed(False)
    if platform.system() == 'Windows' and app.platformName() == 'offscreen':
        for name in ('segoeui.ttf', 'segoeuib.ttf'):
            assert QFontDatabase.addApplicationFont(str(Path(os.environ['WINDIR']) / 'Fonts' / name)) >= 0
        app.setFont(QFont('Segoe UI', 10))
    screen = app.primaryScreen()
    manifest = {
        'finished': False, 'synthetic': True, 'scope': 'loaded-history-supplement' if history_only else 'full',
        'started_utc': datetime.now(timezone.utc).isoformat(),
        'environment': {'platform': platform.platform(), 'python': platform.python_version(),
            'qt': qVersion(), 'qt_platform': app.platformName(), 'style': app.style().objectName(),
            'font': app.font().family(), 'scale': os.environ.get('QT_SCALE_FACTOR', '1'),
            'screen_geometry': screen.geometry().getRect(),
            'screen_available': screen.availableGeometry().getRect(),
            'screen_logical_dpi': screen.logicalDotsPerInch(),
            'screen_physical_dpi': screen.physicalDotsPerInch(),
            'screen_dpr': screen.devicePixelRatio(),
            'versions': {key: importlib.metadata.version(key) for key in ('PySide6', 'Pillow', 'rawpy', 'ImageHash')}},
        'method': 'QWidget.grab with real event loop, workers and services. '
            'Programmatic controls and QTest keys; no native mouse/display acceptance. '
            'Offscreen screen dimensions/DPI are virtual. RAW warnings are presentation fixtures.',
        'os_launches': 0, 'checks': [], 'captures': [],
        'not_verified': ['Native Windows/Linux viewer display and associations',
            'Physical screen/DPI changes and assistive technology', 'Valid RAW decoding/display',
            'Physical removable media and power loss', 'Packaging/Task013 release gates'],
    }
    if platform.system() == 'Windows':
        import ctypes
        user32 = ctypes.windll.user32
        manifest['environment']['native_session_reported'] = {
            'primary_pixels': [user32.GetSystemMetrics(0), user32.GetSystemMetrics(1)],
            'system_dpi': user32.GetDpiForSystem(),
            'note': 'Read-only host API values, not an observed display/DPI transition test',
        }

    def save() -> None:
        (output / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')

    def no_launch(_):
        raise AssertionError('OS launches are forbidden during synthetic captures')

    windows: list[MainWindow] = []

    def create(home: Path) -> MainWindow:
        window = MainWindow(home)
        windows.append(window)
        window.resize(1280, 720)
        window.show()
        pump(lambda: window.settings and not window.controller.busy, timeout=120)
        return window

    def close(window: MainWindow) -> None:
        window.close()
        pump(lambda: window.finished)
        assert all(not thread.isRunning() for thread in window.controller.threads)
        windows.remove(window)
        window.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)

    def capture(name: str, window: MainWindow, widget=None, *, fixture: str = 'real') -> None:
        if history_only and name not in ('quarantine-active-en-dark-compact-1280',
                                        'quarantine-after-restart', 'restore-conflict-en-dark-compact-1280'):
            return
        app.processEvents()
        QTest.qWait(90)
        if window.route == Route.DASHBOARD:
            dashboard = window.dashboard
            visible = [card for card in dashboard.cards if dashboard.viewport.rect().intersects(
                card.rect().translated(card.mapTo(dashboard.viewport, card.rect().topLeft())))]
            pump(lambda: all(card.loaded for card in visible), timeout=120)
        gallery = window.duplicates.groups
        if window.route == Route.DUPLICATES and gallery.isVisible():
            visible_photos = [photo for i, row in enumerate(gallery.groups_model.rows, 1)
                if gallery.viewport().rect().intersects(gallery.visualRect(gallery.model().index(i)))
                for photo in row.samples]
            pump(lambda: all(photo in gallery.groups_model.images for photo in visible_photos), timeout=120)
        if window.route == Route.QUARANTINE and window.history.selected_entry:
            pump(lambda: window.history.thumbnail.text() != tr('preview_loading'), timeout=120)
            if name in ('quarantine-active-en-dark-compact-1280', 'quarantine-after-restart',
                        'restore-conflict-en-dark-compact-1280'):
                assert not window.history.thumbnail.pixmap().isNull(), name
        layout = inspect_layout(window)
        assert not any(layout[key] for key in ('page_horizontal_max', 'toolbar_outside', 'toolbar_overlaps')), (name, layout)
        widget = widget or window
        shot = widget.grab()
        path = output / (name + '.png')
        assert not path.exists() and shot.save(str(path))
        entry = {'file': path.name, 'sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
            'logical': [widget.width(), widget.height()], 'physical': [shot.width(), shot.height()],
            'dpr': shot.devicePixelRatio(), 'language': language_manager().language,
            'theme': window.theme.active, 'theme_preference': window.theme.preference,
            'sidebar_collapsed': window.navigation.collapsed, 'route': window.route.value,
            'layout': layout, 'fixture': fixture, 'visually_reviewed': False}
        if widget is window and window.route == Route.DUPLICATES and window.duplicates_flow.comparing:
            for control in (window.comparison.both, window.comparison.prepare):
                origin = control.mapTo(window, control.rect().topLeft())
                assert window.rect().contains(origin) and window.rect().contains(origin + control.rect().bottomRight())
        manifest['captures'].append(entry)
        save()
        print(name, flush=True)

    def presentation(window: MainWindow, language: str, theme: str) -> None:
        language_manager().set_language(language)
        window.theme.apply(theme)
        # Match the displayed selection without queuing persistence behind a held scan.
        for combo, value in ((window.preferences.language, language),
                             (window.preferences.theme, theme), (window.dashboard.theme, theme)):
            with QSignalBlocker(combo):
                combo.setCurrentIndex(combo.findData(value))

    def variants(window: MainWindow, name: str, *, matrix: bool = False) -> None:
        if history_only:
            if name in ('quarantine-active', 'restore-conflict'):
                presentation(window, 'en', 'dark')
                window.navigation.set_collapsed(True, animate=False)
                window.resize(1280, 720)
                capture(name + '-en-dark-compact-1280', window)
            return
        for language in ('en', 'sr_Latn'):
            for theme in ('dark', 'light'):
                presentation(window, language, theme)
                for collapsed in ((True, False) if matrix else (True,)):
                    window.navigation.set_collapsed(collapsed, animate=False)
                    for width, height in (((1280, 720), (853, 480)) if matrix else ((1280, 720),)):
                        window.resize(width, height)
                        capture(f'{name}-{language}-{theme}-{"compact" if collapsed else "expanded"}-{width}', window)

    save()
    with tempfile.TemporaryDirectory(prefix='synthetic-', dir=output) as directory:
        sandbox = Path(directory)
        with isolated_environment(sandbox), isolated_framework_settings(sandbox), patch.object(QDesktopServices, 'openUrl', no_launch):
            window = create(sandbox / 'home')
            try:
                for route in Route:
                    window.navigate(route)
                    variants(window, 'empty-' + route.value)
                photos = sandbox / 'fotografije-čćžšđ'
                generate(photos)
                originals = {p: p.read_bytes() for p in photos.iterdir()}
                window.navigate(Route.SCAN)
                window.scan.add.click()
                chooser = window.findChild(QFileDialog)
                assert chooser is not None and chooser.testOption(QFileDialog.ReadOnly)
                capture('folder-chooser', window, chooser)
                chooser.fileSelected.emit(str(photos))
                chooser.close()
                pump(lambda: not window.controller.busy)
                manifest['checks'].append('Read-only Qt folder chooser result adds only the synthetic root')

                extract, entered, release = indexing.extract, Event(), Event()

                def delayed(*args, **kwargs):
                    entered.set()
                    assert release.wait(120)
                    return extract(*args, **kwargs)

                with patch.object(indexing, 'extract', delayed):
                    window.scan.start.click()
                    try:
                        pump(entered.is_set)
                        heartbeats = []
                        for language, theme, route in (('en', 'dark', Route.SCAN), ('sr_Latn', 'light', Route.SETTINGS),
                                                       ('sr_Latn', 'dark', Route.DASHBOARD), ('en', 'light', Route.SCAN)):
                            presentation(window, language, theme)
                            window.navigate(route)
                            QTest.qWait(20)
                            heartbeats.append(window.scan_active and not window.controller.cancel_event.is_set())
                            capture('running-' + route.value + '-' + language + '-' + theme, window)
                        assert all(heartbeats)
                    finally:
                        release.set()
                    pump(lambda: window.session and not window.controller.busy, timeout=120)
                manifest['checks'].append('GUI event loop, navigation and theme/language changes while extraction is held on worker')
                assert window.status == 'complete'
                for route in (Route.DASHBOARD, Route.SCAN, Route.DUPLICATES, Route.SETTINGS):
                    window.navigate(route)
                    variants(window, 'populated-' + route.value, matrix=True)

                window.review_results()
                window.duplicates.kind.setCurrentIndex(window.duplicates.kind.findData('EXACT'))
                pump(lambda: not window.controller.busy and window.query.kind == 'EXACT' and bool(window.duplicates.model.rows))
                window.duplicates.table.selectRow(0)
                window.compare()
                pump(lambda: not window.controller.busy and window.comparison.right.state == 'preview_ready')
                assert window.total == 2  # Three members, represented by two direct links.
                window.choose_keeper(False)
                variants(window, 'compare-exact', matrix=True)
                window.keep_both()
                assert not window.pending_pairs()
                capture('compare-keep-both', window)
                window.comparison.right.keep_photo.click()
                window.prepare_selected()
                pump(lambda: window.plan_dialog is not None)
                assert len(window.plan_dialog.plan.moves) == 1
                capture('quarantine-confirm-cancel', window, window.plan_dialog)
                QTest.keyClick(window.plan_dialog, Qt.Key_Escape)
                pump(lambda: window.plan_dialog is None)
                assert all(p.read_bytes() == data for p, data in originals.items())
                manifest['checks'].append('Keep Both and Escape/cancel preserve every synthetic original; unseen member has no move')
                window.prepare_selected()
                pump(lambda: window.plan_dialog is not None)
                move = window.plan_dialog.plan.moves[0]
                window.plan_dialog.approve()
                pump(lambda: not window.controller.busy)
                assert not Path(move.source).exists() and Path(move.destination).read_bytes() == originals[Path(move.source)]
                window.navigate(Route.QUARANTINE)
                window.history.table.selectRow(0)
                pump(lambda: not window.controller.busy)
                variants(window, 'quarantine-active', matrix=True)
                home = window.home
                close(window)
                window = create(home)
                window.navigate(Route.QUARANTINE)
                window.history.table.selectRow(next(i for i, item in enumerate(window.history_rows) if item.id == move.id))
                pump(lambda: not window.controller.busy)
                capture('quarantine-after-restart', window)
                conflict = b'synthetic occupied restore destination'
                Path(move.source).write_bytes(conflict)
                window.restore()
                pump(lambda: bool(window.history.operation_error) and not window.controller.busy)
                assert not window.plan_dialog and Path(move.source).read_bytes() == conflict
                assert Path(move.destination).read_bytes() == originals[Path(move.source)]
                variants(window, 'restore-conflict')
                error = next(box for box in window.findChildren(QMessageBox) if box.isVisible())
                capture('restore-conflict-dialog', window, error)
                error.close()
                conflict_path = sandbox / 'preserved-conflict.bin'
                Path(move.source).rename(conflict_path)
                window.restore()
                pump(lambda: window.plan_dialog is not None)
                capture('restore-confirm', window, window.plan_dialog)
                window.plan_dialog.approve()
                pump(lambda: not window.controller.busy)
                assert all(p.read_bytes() == data for p, data in originals.items())
                assert conflict_path.read_bytes() == conflict
                capture('restore-complete', window)
                manifest['checks'].append('One explicit quarantine; restart journal target; conflict refused; explicit restore preserves all original and conflict bytes')

                # Refresh scan after restore so VISUAL review uses current file identities.
                window.start_scan()
                pump(lambda: not window.controller.busy and window.status == 'complete', timeout=120)
                window.review_results()
                window.duplicates.kind.setCurrentIndex(window.duplicates.kind.findData('VISUAL'))
                pump(lambda: not window.controller.busy and window.query.kind == 'VISUAL' and bool(window.duplicates.model.rows))
                window.duplicates.table.selectRow(0)
                window.compare()
                pump(lambda: not window.controller.busy and window.comparison.left.state == 'preview_ready')
                variants(window, 'compare-visual')
                row = window.controller.selection
                raw = replace(row.match.keep, is_raw=True, ext='.nef', image_format='')
                backup = replace(row.match.dup, root=str(sandbox / 'backup-drive'))
                window.duplicates.model.replace((MatchRow(9001, 9001, Match(Kind.VISUAL, raw, backup)),))
                window.duplicates.table.selectRow(0)
                for language in ('en', 'sr_Latn'):
                    language_manager().set_language(language)
                    window.resize(1280, 720)
                    capture('raw-backup-warning-' + language, window, fixture='RAW/backup presentation only; never approved')
                window.show_error('photo_launch_failed: synthetic association failure')
                error = window.findChild(QMessageBox)
                capture('external-open-error', window, error, fixture='Synthetic error; no OS request sent')
                error.close()

                # A missing file is refused by the real worker, before OS dispatch.
                target = row.match.dup
                parked = sandbox / 'temporarily-disconnected-photo.jpg'
                Path(target.path).rename(parked)
                try:
                    window.open_photo(target)
                    pump(lambda: not window.controller.busy and any(
                        box.isVisible() for box in window.findChildren(QMessageBox)))
                    error = next(box for box in window.findChildren(QMessageBox) if box.isVisible())
                    for language in ('en', 'sr_Latn'):
                        language_manager().set_language(language)
                        capture('missing-photo-error-' + language, window, error)
                    error.close()
                finally:
                    parked.rename(target.path)
                manifest['checks'].append('Missing photograph refused by real validation worker before OS launch')

                # Simulate a platform signal, preserving selection and unsaved choice.
                state = (window.query, window.selected_id, window.pending_pairs())
                window.theme.apply('system', Qt.ColorScheme.Dark)
                window.theme.system_changed(Qt.ColorScheme.Light)
                assert window.theme.active == 'light' and window.theme.preference == 'system'
                assert state == (window.query, window.selected_id, window.pending_pairs())
                capture('system-light-signal', window, fixture='Simulated System colorSchemeChanged, not OS setting change')
                window.theme.system_changed(Qt.ColorScheme.Dark)
                assert window.theme.active == 'dark'
                manifest['checks'].append('System dark/light signal tracking preserves query, selection and pending choices')
                assert all(p.read_bytes() == data for p, data in originals.items())
                manifest['original_bytes_restored'] = True
                manifest['confirmed_quarantine_count'] = manifest['confirmed_restore_count'] = 1
            finally:
                for active in windows:
                    for box in active.findChildren(QMessageBox):
                        box.close()
                for active in list(windows):
                    close(active)
                language_manager().set_language('en')
                save()
    manifest['finished'] = True
    save()
    print(f"Finished: {len(manifest['captures'])} captures; all synthetic original bytes restored", flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--history-only', action='store_true',
                        help='Capture three loaded history repairs; still verify the synthetic safety journey')
    arguments = parser.parse_args()
    run(arguments.output, arguments.history_only)
