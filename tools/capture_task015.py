"""Task015 presentation evidence; no photo I/O, application home or services.

Run python -B -m tools.capture_task015 --output <new workspace directory>.
Confirmation is a synthetic presentation fixture, rejected without approval.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import platform

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from PySide6.QtCore import QPoint, Qt, qVersion
from PySide6.QtGui import QFontDatabase
from PySide6.QtTest import QTest
from PySide6.QtWidgets import (QApplication, QGridLayout, QHBoxLayout, QMenu,
                              QPushButton, QToolTip, QVBoxLayout, QWidget)

from app.core.models import Identity, Kind, Move, Photo, Plan, Snapshot
from app.ui.qt.components import PlanDialog, ThemeSelector, style_button, text_label
from app.ui.qt.icons import ICON_NAMES, icon, set_icon
from app.ui.qt.localization import language_manager
from app.ui.qt.navigation import Route, Sidebar
from app.ui.qt.screens import DuplicatesScreen
from app.ui.qt.strings import tr
from app.ui.qt.themes import ThemeManager
from tools.capture_design_system import gallery


def icon_gallery() -> QWidget:
    host = QWidget()
    layout = QHBoxLayout(host)
    sidebar = Sidebar()
    sidebar.select(Route.DUPLICATES)
    layout.addWidget(sidebar)
    grid = QGridLayout()
    layout.addLayout(grid)
    for row, name in enumerate(ICON_NAMES):
        grid.addWidget(text_label(name), row, 0)
        for column, (variant, enabled) in enumerate((('secondary', True), ('primary', True),
                                                    ('danger', True), ('primary', False)), 1):
            control = QPushButton(tr('ready'))
            style_button(control, variant)
            set_icon(control, name)
            control.setEnabled(enabled)
            grid.addWidget(control, row, column)
    host.resize(1100, 900)
    host.show()
    return host


def confirmation() -> Plan:
    identity = Identity(0, 0)
    snapshot = Snapshot(identity, 0, 0, 0, '0' * 64)
    keeper = Photo('synthetic/photos/keeper.png', 'synthetic/photos', snapshot, identity)
    move = Move('presentation-only', 'synthetic/photos/copy.nef',
                'synthetic/photos/.photo_agent_quarantine/copy.nef', 'synthetic/photos',
                identity, snapshot, keeper, Kind.VISUAL, raw=True,
                xmp=('synthetic/photos/copy.xmp',))
    return Plan('task015-presentation-only', (move,))


def run(output: Path) -> None:
    output.mkdir(parents=True, exist_ok=False)
    app = QApplication.instance() or QApplication([])
    app.setStyle('Fusion')
    app.setQuitOnLastWindowClosed(False)
    if platform.system() == 'Windows' and app.platformName() == 'offscreen':
        for name in ('segoeui.ttf', 'segoeuib.ttf'):
            if QFontDatabase.addApplicationFont(str(Path(os.environ['WINDIR']) / 'Fonts' / name)) < 0:
                raise RuntimeError('Installed capture font unavailable')
    theme = ThemeManager(app)
    language = language_manager()
    language.set_language('en')
    manifest = {'qt': qVersion(), 'platform': platform.platform(), 'plugin': app.platformName(),
                'font': app.font().family(), 'synthetic': True,
                'scope': 'Task015 shared presentation only. No application services, home, '
                         'photo reads, moves or approvals. Confirmation paths are invented.',
                'screenshots': [], 'checks': []}

    def capture(name: str, widget: QWidget) -> None:
        QTest.qWait(50)
        app.processEvents()
        pixmap = widget.grab()
        path = output / (name + '.png')
        if not pixmap.save(str(path)):
            raise OSError(path)
        manifest['screenshots'].append({'file': path.name, 'width': pixmap.width(),
            'height': pixmap.height(), 'dpr': pixmap.devicePixelRatio(),
            'language': language.language, 'preference': theme.preference, 'active': theme.active,
            'sha256': hashlib.sha256(path.read_bytes()).hexdigest()})
        print('Captured ' + name, flush=True)

    for name in ('dark', 'light'):
        theme.apply(name)
        host = gallery()
        capture(name + '-components', host)
        glyphs = icon_gallery()
        capture(name + '-icons', glyphs)
        glyphs.close()
        dialog = PlanDialog(confirmation(), host)
        dialog.show()
        capture(name + '-confirmation', dialog)
        assert not dialog.confirm.isEnabled() and dialog.approval is None
        dialog.reject()
        assert dialog.approval is None
        menu = QMenu(host)
        for key, glyph in (('settings', 'settings'), ('restore', 'restore'), ('cancel', 'collapse')):
            menu.addAction(icon(glyph), tr(key))
        menu.actions()[1].setEnabled(False)
        menu.popup(host.mapToGlobal(QPoint(80, 80)))
        menu.setActiveAction(menu.actions()[0])
        capture(name + '-menu', menu)
        menu.close()
        QToolTip.showText(host.mapToGlobal(QPoint(100, 100)), tr('preview_note'), host)
        app.processEvents()
        tips = [w for w in app.topLevelWidgets() if w.inherits('QTipLabel') and w.isVisible()]
        assert len(tips) == 1
        capture(name + '-tooltip', tips[0])
        QToolTip.hideText()
        QTest.qWait(350)
        noop = lambda *args: None
        filters = DuplicatesScreen(*([noop] * 10))
        filters.resize(1000, 400)
        filters.show()
        capture(name + '-filters', filters)
        filters.close()
        language.set_language('sr_Latn')
        capture(name + '-components-sr', host)
        language.set_language('en')
        host.close()
        host.deleteLater()

    # Keep the same controls alive through actual System callbacks.
    host = icon_gallery()
    selector = ThemeSelector()
    host.layout().addWidget(selector)
    selector.setCurrentIndex(selector.findData('system'))
    sidebar = host.findChild(Sidebar)
    for scheme, name in ((Qt.ColorScheme.Light, 'light'), (Qt.ColorScheme.Dark, 'dark'),
                         (Qt.ColorScheme.Unknown, 'fallback')):
        if name == 'light':
            theme.apply('system', scheme)
        else:
            theme.system_changed(scheme)
        assert theme.preference == 'system' and selector.currentData() == 'system'
        assert sidebar.buttons[Route.DUPLICATES].isChecked()
        capture('system-' + name, host)
    manifest['checks'] = ['Synthetic confirmation rejected in both themes; no Approval created.',
                          'System callbacks preserve theme choice and selected navigation route.']
    host.close()
    (output / 'manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    run(parser.parse_args().output)
