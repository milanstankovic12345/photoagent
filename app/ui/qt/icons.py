"""Local line icons, colored at paint time so System/theme changes stay live."""
from __future__ import annotations

from PySide6.QtCore import QFile, QIODevice, QRect, QRectF, QSize, Qt
from PySide6.QtGui import QIcon, QIconEngine, QPainter, QPaintEvent, QPalette, QPixmap
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import QAbstractButton, QApplication, QComboBox, QWidget

from app.ui.qt import resources_rc  # Register embedded SVGs without a MainWindow.
from app.ui.qt.themes import TOKENS

ICON_SIZE = 20
ICON_NAMES = ('dashboard', 'scan', 'duplicates', 'quarantine', 'settings',
              'search', 'filter', 'sort', 'theme', 'language', 'open_external',
              'restore', 'expand', 'collapse', 'folder')


class _LineIconEngine(QIconEngine):
    def __init__(self, name: str, variant: str) -> None:
        super().__init__()
        self.name, self.variant = name, variant
        source = QFile(f':/photoagent/{name}.svg')
        if not source.open(QIODevice.ReadOnly):
            raise ValueError(f'Missing bundled icon: {name}')
        self.svg = bytes(source.readAll())
        source.close()

    def clone(self) -> QIconEngine:
        return _LineIconEngine(self.name, self.variant)

    def key(self) -> str:
        return 'PhotoAgentLineIcon'

    def paint(self, painter: QPainter, rect: QRect | QRectF, mode: QIcon.Mode,
              state: QIcon.State) -> None:
        palette = QApplication.palette()
        colors = TOKENS['light' if palette.color(QPalette.Window).lightness() > 128 else 'dark']
        token = ('disabled_text' if mode == QIcon.Disabled else
                 'on_primary' if self.variant == 'primary' else
                 'on_danger' if self.variant == 'danger' else 'text')
        renderer = QSvgRenderer(self.svg.replace(b'currentColor', colors[token].encode('ascii')))
        # A square viewport preserves optical size even in a non-square target.
        target = QRectF(0, 0, min(rect.width(), rect.height()), min(rect.width(), rect.height()))
        target.moveCenter(QRectF(rect).center())
        painter.save()
        renderer.render(painter, target)
        painter.restore()

    def pixmap(self, size: QSize, mode: QIcon.Mode, state: QIcon.State) -> QPixmap:
        return self.scaledPixmap(size, mode, state, 1.0)

    def scaledPixmap(self, size: QSize, mode: QIcon.Mode, state: QIcon.State,
                     scale: float) -> QPixmap:
        pixmap = QPixmap(size * scale)
        pixmap.setDevicePixelRatio(scale)
        pixmap.fill(Qt.transparent)
        painter = QPainter(pixmap)
        self.paint(painter, QRectF(0, 0, size.width(), size.height()), mode, state)
        painter.end()
        return pixmap


def icon(name: str, variant: str = 'secondary') -> QIcon:
    if name not in ICON_NAMES or variant not in ('primary', 'secondary', 'danger'):
        raise ValueError((name, variant))
    return QIcon(_LineIconEngine(name, variant))


def set_icon(control: QAbstractButton, name: str) -> None:
    """Keep existing text/accessibility; icons supplement the named action."""
    control.setProperty('icon_role', name)
    control.setIcon(icon(name, control.property('variant') or 'secondary'))
    control.setIconSize(QSize(ICON_SIZE, ICON_SIZE))


def set_combo_icon(control: QComboBox, name: str) -> None:
    control.setProperty('icon_role', name)
    control.setIconSize(QSize(ICON_SIZE, ICON_SIZE))
    for index in range(control.count()):
        control.setItemIcon(index, icon(name))


class IconLabel(QWidget):
    """Decorative source glyph; repaint from the current application palette."""
    def __init__(self, name: str) -> None:
        super().__init__()
        self.glyph = icon(name)
        self.setProperty('icon_role', name)
        self.setFixedSize(ICON_SIZE, ICON_SIZE)

    def paintEvent(self, event: QPaintEvent) -> None:
        painter = QPainter(self)
        self.glyph.paint(painter, self.rect(), Qt.AlignCenter,
                         QIcon.Normal if self.isEnabled() else QIcon.Disabled)
        painter.end()
