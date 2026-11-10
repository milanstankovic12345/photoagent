"""Named destinations and a local, keyboard-accessible sidebar. No service calls."""
from enum import StrEnum

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QIcon, QKeyEvent
from PySide6.QtWidgets import (QHBoxLayout, QLabel, QPushButton,
                              QVBoxLayout, QWidget)

from app.ui.qt.components import style_button, text_label
from app.ui.qt.icons import set_icon
from app.ui.qt.localization import set_text, with_text
from app.ui.qt.strings import tr


class Route(StrEnum):
    DASHBOARD = 'dashboard'
    SCAN = 'scan'
    DUPLICATES = 'duplicates'
    QUARANTINE = 'history'
    SETTINGS = 'settings'


class Sidebar(QWidget):
    activated = Signal(object)

    def __init__(self) -> None:
        super().__init__()
        self.setFixedWidth(208)
        set_text(self, tr('navigation'), 'setAccessibleName')
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        brand = QHBoxLayout()
        logo = QLabel()
        logo.setPixmap(QIcon(':/photoagent/photoagent.svg').pixmap(32, 32))
        brand.addWidget(logo)
        brand.addWidget(text_label('PhotoAgent', 'section'), 1)
        layout.addLayout(brand)
        # Keep every destination in the Tab chain; select() owns the one checked
        # item rather than relying on radio-style QButtonGroup focus handling.
        self.buttons: dict[Route, QPushButton] = {}
        icons = ('dashboard', 'scan', 'duplicates', 'quarantine', 'settings')
        for route, icon in zip(Route, icons):
            if route == Route.SETTINGS:
                layout.addStretch(1)
            control = with_text(QPushButton(), tr(route.value))
            style_button(control)
            control.setProperty('navigation', True)
            control.setCheckable(True)
            set_icon(control, icon)
            control.clicked.connect(lambda checked=False, destination=route: self.activated.emit(destination))
            self.buttons[route] = control
            layout.addWidget(control)

    def select(self, route: Route) -> None:
        for destination, control in self.buttons.items():
            control.setChecked(destination == route)

    def keyPressEvent(self, event: QKeyEvent) -> None:
        # QPushButton uses Space by default; Enter should also activate navigation.
        if event.key() in (Qt.Key_Return, Qt.Key_Enter):
            focused = self.focusWidget()
            if focused in self.buttons.values():
                focused.click()
                event.accept()
                return
        super().keyPressEvent(event)
