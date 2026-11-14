"""Windows native viewer probe using generated photos and the actual Qt launch adapter.

Requires an unlocked interactive Windows desktop with a PNG association.
Output must be new. May leave the viewer open; never closes an existing OS window.
Title-matched OS screenshots need visual inspection: OS acceptance is not display proof.
Linux native verification remains a separate manual gate.
"""
from __future__ import annotations

import argparse
import ctypes
from ctypes import wintypes
import hashlib
import json
import os
from pathlib import Path
import platform
import time
from uuid import uuid4

if platform.system() == 'Windows':
    os.environ['QT_QPA_PLATFORM'] = 'windows'

from PIL import ImageGrab
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QMessageBox

from app.ui.qt.navigation import Route
from app.ui.qt.window import MainWindow
from tools.capture_task011 import isolated_environment
from tools.capture_task012 import isolated_framework_settings
from tools.capture_ux_audit import generate, pump


def run(output: Path) -> None:
    if platform.system() != 'Windows':
        raise RuntimeError('Use the documented native Linux checklist on a Linux desktop')
    output = output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    user32 = ctypes.WinDLL('user32', use_last_error=True)
    callback_type = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    user32.EnumWindows.argtypes = [callback_type, wintypes.LPARAM]
    user32.GetWindowTextLengthW.argtypes = [wintypes.HWND]
    user32.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
    user32.IsWindowVisible.argtypes = [wintypes.HWND]
    user32.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
    app = QApplication([])
    app.setQuitOnLastWindowClosed(False)
    token = 'Task023-' + uuid4().hex[:10]
    report = {'platform': platform.platform(), 'qt_platform': app.platformName(),
        'synthetic': True, 'finished': False, 'method': 'Native Qt, real worker/service/adapter and OS association; QTest events, not manual mouse input',
        'session_pixels': [user32.GetSystemMetrics(0), user32.GetSystemMetrics(1)],
        'system_dpi': user32.GetDpiForSystem(), 'launches': [], 'screenshots': [],
        'limits': ['Viewer title detection may fail even if an app opened',
            'Screenshot requires visual inspection before display acceptance',
            'No Linux, valid RAW, physical DPI or assistive technology verification']}

    def save() -> None:
        (output / 'manifest.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')

    def viewer_capture(name: str) -> None:
        found = []

        @callback_type
        def collect(hwnd, _):
            length = user32.GetWindowTextLengthW(hwnd)
            text = ctypes.create_unicode_buffer(length + 1)
            user32.GetWindowTextW(hwnd, text, len(text))
            if user32.IsWindowVisible(hwnd) and token in text.value:
                found.append(hwnd)
            return True

        deadline = time.monotonic() + 20
        while not found and time.monotonic() < deadline:
            user32.EnumWindows(collect, 0)
            QTest.qWait(200)
        if not found:
            report['screenshots'].append({'state': name, 'captured': False,
                'reason': 'No visible window title containing synthetic filename token; display unverified'})
        else:
            hwnd = found[0]
            QTest.qWait(1500)
            rect = wintypes.RECT()
            assert user32.GetWindowRect(hwnd, ctypes.byref(rect))
            path = output / (name + '.png')
            # A desktop rectangle can show another app if Windows refuses focus.
            # Capture the title-matched HWND itself; never substitute screen pixels.
            try:
                with ImageGrab.grab(window=hwnd) as image:
                    image.save(path)
                    report['screenshots'].append({'state': name, 'file': path.name, 'captured': True,
                        'pixels': list(image.size), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
                        'capture_method': 'Pillow ImageGrab(window=HWND), not desktop rectangle',
                        'visually_reviewed': False})
            except (OSError, TypeError) as exc:
                # Older supported Pillow versions may lack HWND capture. A clear
                # limitation is preferable to substituting another window's pixels.
                report['screenshots'].append({'state': name, 'captured': False,
                    'reason': 'Target HWND capture unavailable; display needs human observation',
                    'detail': str(exc)})
        save()

    save()
    with isolated_environment(output), isolated_framework_settings(output):
        photos = output / 'synthetic-photos'
        generate(photos)
        for index, path in enumerate(sorted(photos.iterdir())):
            path.rename(path.with_name(f'{token}-{index}-čćžšđ' + path.suffix))
        original = {p: p.read_bytes() for p in photos.iterdir()}
        window = MainWindow(output / 'synthetic-home')
        real_open = window.desktop_viewer.open_photo

        def record_open(path: str) -> bool:
            assert Path(path).resolve().is_relative_to(photos)
            accepted = real_open(path)
            report['launches'].append({'file': Path(path).name, 'accepted': accepted})
            save()
            return accepted

        window.desktop_viewer.open_photo = record_open
        window.show()
        try:
            pump(lambda: window.settings and not window.controller.busy, timeout=120)
            window.add_selected_root(str(photos))
            pump(lambda: not window.controller.busy)
            window.start_scan()
            pump(lambda: window.session and not window.controller.busy, timeout=120)
            window.navigate(Route.DUPLICATES)
            window.duplicates.table.selectRow(0)
            window.compare()
            pump(lambda: not window.controller.busy and window.comparison.left.state == 'preview_ready')
            view = window.comparison.left.view.viewport()
            QTest.mouseClick(view, Qt.LeftButton)
            QTest.qWait(500)
            assert not report['launches']
            report['single_click_no_launch'] = True
            QTest.mouseDClick(view, Qt.LeftButton)
            QTest.mouseRelease(view, Qt.LeftButton)
            pump(lambda: len(report['launches']) == 1, timeout=90)
            assert len(report['launches']) == 1
            viewer_capture('double-click-viewer')
            # Use the explicit action on the same immutable concrete photo.
            window.comparison.left.open_default.click()
            pump(lambda: len(report['launches']) == 2, timeout=90)
            assert len(report['launches']) == 2
            viewer_capture('explicit-action-viewer')
            report['original_bytes_preserved'] = all(p.read_bytes() == data for p, data in original.items())
        finally:
            for box in window.findChildren(QMessageBox):
                box.close()
            window.close()
            pump(lambda: window.finished)
            assert all(not thread.isRunning() for thread in window.controller.threads)
            save()
    report['finished'] = True
    save()
    print(json.dumps({'output': str(output), 'launches': report['launches'], 'screenshots': report['screenshots']}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    run(parser.parse_args().output)
