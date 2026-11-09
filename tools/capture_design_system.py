"""Render real shared widgets without photo files, a home, index or journal.

Run: python -B -m tools.capture_design_system --output <new directory>
Offscreen evidence is not native DPI or full accessibility acceptance.
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
from PySide6.QtWidgets import (QApplication, QComboBox, QDialog, QGridLayout,
    QHBoxLayout, QLineEdit, QListWidget, QMenu, QPushButton, QTableWidget,
    QTableWidgetItem, QToolTip, QVBoxLayout, QWidget)

from app.ui.qt.components import (Card, CollapsibleSection, EmptyState, PageHeader,
    PhotoView, StatCard, StatusBadge, button, text_label)
from app.ui.qt.strings import tr
from app.ui.qt.themes import ThemeManager


def gallery() -> QWidget:
    host = QWidget()
    host.setWindowTitle(tr('design_system'))
    layout = QVBoxLayout(host)
    layout.setContentsMargins(24, 24, 24, 24)
    layout.setSpacing(16)
    layout.addWidget(PageHeader('design_system', 'design_system_note'))
    grid = QGridLayout()
    grid.setSpacing(16)
    layout.addLayout(grid)
    grid.addWidget(StatCard('dashboard', detail_key='no_session'), 0, 0)
    grid.addWidget(EmptyState('empty', 'select_pair'), 0, 1)
    actions = Card()
    row = QHBoxLayout()
    actions.content.addLayout(row)
    primary = button('start', lambda: None, row)
    button('refresh', lambda: None, row)
    disabled = button('save', lambda: None, row)
    disabled.setEnabled(False)
    button('selected_move', lambda: None, actions.content)
    badges = QHBoxLayout()
    for key, tone in (('ready', 'neutral'), ('state_complete', 'success'),
                      ('state_incomplete', 'warning'), ('state_failed', 'danger')):
        badges.addWidget(StatusBadge(key, tone))
    actions.content.addLayout(badges)
    grid.addWidget(actions, 1, 0)
    section = CollapsibleSection('detail', expanded=True)
    section.body_layout.addWidget(text_label(tr('preview_note'), 'metadata'))
    field = QLineEdit()
    field.setPlaceholderText(tr('search'))
    field.setAccessibleName(tr('search'))
    section.body_layout.addWidget(field)
    grid.addWidget(section, 1, 1)
    loading, unavailable = PhotoView(), PhotoView()
    loading.show_state('preview_loading')
    unavailable.set_image(None, tr('unavailable'))
    grid.addWidget(loading, 2, 0)
    grid.addWidget(unavailable, 2, 1)
    choices = Card()
    combo = QComboBox()
    combo.setAccessibleName(tr('theme'))
    combo.addItems([tr(key) for key in ('dark', 'light', 'system')])
    choices.content.addWidget(combo)
    listing = QListWidget()
    listing.setAccessibleName(tr('theme'))
    listing.addItems([tr(key) for key in ('dark', 'light', 'system')])
    listing.setCurrentRow(0)
    choices.content.addWidget(listing)
    grid.addWidget(choices, 3, 0)
    table = QTableWidget(3, 1)
    table.setAccessibleName(tr('theme'))
    table.setHorizontalHeaderLabels([tr('theme')])
    table.horizontalHeader().setStretchLastSection(True)
    table.setAlternatingRowColors(True)
    table.setEditTriggers(QTableWidget.NoEditTriggers)
    for row, key in enumerate(('dark', 'light', 'system')):
        table.setItem(row, 0, QTableWidgetItem(tr(key)))
    table.selectRow(1)
    grid.addWidget(table, 3, 1)
    host.resize(1280, 1000)
    host.show()
    primary.setFocus(Qt.TabFocusReason)
    return host


def run(output: Path) -> None:
    output.mkdir(parents=True, exist_ok=False)
    app = QApplication.instance() or QApplication([])
    app.setStyle('Fusion')
    app.setQuitOnLastWindowClosed(False)
    # Windows offscreen may not enumerate system fonts; load only for this process.
    if platform.system() == 'Windows' and app.platformName() == 'offscreen':
        for name in ('segoeui.ttf', 'segoeuib.ttf'):
            if QFontDatabase.addApplicationFont(str(Path(os.environ['WINDIR']) / 'Fonts' / name)) < 0:
                raise RuntimeError('Installed capture font unavailable')
    theme = ThemeManager(app)
    manifest = {'qt': qVersion(), 'platform': platform.platform(),
                'plugin': app.platformName(), 'font': app.font().family(),
                'scale_factor': os.environ.get('QT_SCALE_FACTOR', '1'),
                'scope': 'Shared Qt widgets only; no photographs or collection data.',
                'screenshots': []}

    def capture(name: str, widget: QWidget) -> None:
        app.processEvents()
        pixmap = widget.grab()
        path = output / (name + '.png')
        if not pixmap.save(str(path)):
            raise OSError(path)
        manifest['screenshots'].append({'file': path.name, 'width': pixmap.width(),
            'height': pixmap.height(), 'dpr': pixmap.devicePixelRatio(),
            'sha256': hashlib.sha256(path.read_bytes()).hexdigest()})
        print('Captured ' + name, flush=True)

    for name in ('dark', 'light'):
        theme.apply(name)
        host = gallery()
        QTest.qWait(50)
        capture(name + '-components', host)
        dialog = QDialog(host)
        dialog.setWindowTitle(tr('design_system'))
        content = QVBoxLayout(dialog)
        content.addWidget(PageHeader('design_system', 'preview_note'))
        button('approve', lambda: None, content).setEnabled(False)
        button('cancel', lambda: None, content).setFocus()
        dialog.resize(620, 230)
        dialog.show()
        capture(name + '-dialog', dialog)
        dialog.close()
        menu = QMenu(host)
        for key in ('refresh', 'settings', 'cancel'):
            menu.addAction(tr(key))
        menu.actions()[-1].setEnabled(False)
        menu.popup(host.mapToGlobal(QPoint(80, 80)))
        menu.setActiveAction(menu.actions()[0])
        capture(name + '-menu', menu)
        menu.close()
        QToolTip.showText(host.mapToGlobal(QPoint(100, 100)), tr('preview_note'), host)
        app.processEvents()
        tips = [w for w in app.topLevelWidgets() if w.inherits('QTipLabel') and w.isVisible()]
        if len(tips) != 1:
            raise RuntimeError('Expected a visible Qt tooltip')
        capture(name + '-tooltip', tips[0])
        QToolTip.hideText()
        QTest.qWait(350)  # Qt hides tooltips after a short delay; finish before the next capture.
        host.close()
        host.deleteLater()
        app.processEvents()
    (output / 'manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    run(parser.parse_args().output)
