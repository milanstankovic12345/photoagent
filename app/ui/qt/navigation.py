"""Named destinations and a local, keyboard-accessible sidebar. No service calls."""
from enum import StrEnum

from PySide6.QtCore import QAbstractAnimation, QEasingCurve, Qt, Signal, QVariantAnimation
from PySide6.QtGui import QIcon, QKeyEvent, QPainter, QPaintEvent, QPalette
from PySide6.QtWidgets import (QHBoxLayout, QLabel, QPushButton,
                              QSizePolicy, QVBoxLayout, QWidget)

from app.ui.qt.components import style_button, text_label
from app.ui.qt.icons import set_icon
from app.ui.qt.localization import set_text
from app.ui.qt.strings import tr


class Route(StrEnum):
    DASHBOARD = 'dashboard'
    SCAN = 'scan'
    DUPLICATES = 'duplicates'
    QUARANTINE = 'history'
    SETTINGS = 'settings'


class NavigationButton(QPushButton):
    """Native checkable semantics plus a shape cue independent of surface color."""

    def paintEvent(self, event: QPaintEvent) -> None:
        super().paintEvent(event)
        if self.isChecked():
            painter = QPainter(self)
            painter.fillRect(3, 12, 3, self.height() - 24,
                             self.palette().color(QPalette.ButtonText))
            painter.end()


class Sidebar(QWidget):
    activated = Signal(object)
    COMPACT_WIDTH = 64
    EXPANDED_WIDTH = 208

    def __init__(self) -> None:
        super().__init__()
        self.collapsed = True
        self.setFixedWidth(self.COMPACT_WIDTH)
        set_text(self, tr('navigation'), 'setAccessibleName')
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        brand = QHBoxLayout()
        brand.setContentsMargins(16, 0, 0, 0)
        logo = QLabel()
        logo.setAccessibleName('PhotoAgent')
        logo.setFixedSize(32, 40)
        logo.setPixmap(QIcon(':/photoagent/photoagent.svg').pixmap(32, 32))
        brand.addWidget(logo)
        self.brand_name = text_label('PhotoAgent', 'section')
        self.brand_name.setWordWrap(False)
        brand.addWidget(self.brand_name, 1)
        brand.addStretch()
        layout.addLayout(brand)
        self.toggle = QPushButton()
        style_button(self.toggle)
        self.toggle.setProperty('disclosure', True)
        self.toggle.setProperty('compact', True)
        self.toggle.setCheckable(True)  # Checked means expanded in the native API.
        self.toggle.setFixedHeight(44)
        self.toggle.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Fixed)
        self.toggle.toggled.connect(lambda expanded: self.set_collapsed(not expanded))
        layout.addWidget(self.toggle)
        # Keep every destination in the Tab chain; select() owns the one checked
        # item rather than relying on radio-style QButtonGroup focus handling.
        self.buttons: dict[Route, QPushButton] = {}
        icons = ('dashboard', 'scan', 'duplicates', 'quarantine', 'settings')
        for route, icon in zip(Route, icons):
            if route == Route.SETTINGS:
                layout.addStretch(1)
            control = NavigationButton()
            style_button(control)
            set_text(control, tr(route.value), 'setAccessibleName')
            set_text(control, tr(route.value), 'setToolTip')
            control.setProperty('navigation', True)
            control.setCheckable(True)
            control.setFixedHeight(44)
            control.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Fixed)
            set_icon(control, icon)
            control.clicked.connect(lambda checked=False, destination=route: self.activated.emit(destination))
            self.buttons[route] = control
            layout.addWidget(control)

        self.animation = QVariantAnimation(self)
        self.animation.setDuration(160)
        self.animation.setEasingCurve(QEasingCurve.InOutCubic)
        self.animation.valueChanged.connect(self.setFixedWidth)
        self.animation.finished.connect(self._update_presentation)
        self._update_presentation()

    def set_collapsed(self, collapsed: bool, *, animate: bool = True) -> None:
        """Resize this widget only; do not navigate, request data or change focus."""
        if self.collapsed == collapsed:
            return
        self.collapsed = collapsed
        self.animation.stop()
        self.toggle.setChecked(not collapsed)
        target = self.COMPACT_WIDTH if collapsed else self.EXPANDED_WIDTH
        if animate and self.isVisible():
            self.animation.setStartValue(self.width())
            self.animation.setEndValue(target)
            self.animation.start()
        else:
            self.setFixedWidth(target)
        self._update_presentation()

    def _update_presentation(self) -> None:
        # Hide labels while changing width, so text is never clipped mid-animation.
        labels = not self.collapsed and self.animation.state() != QAbstractAnimation.Running
        self.brand_name.setVisible(labels)
        for route, control in self.buttons.items():
            set_text(control, tr(route.value) if labels else '')
            control.setProperty('compact', not labels)
            control.style().unpolish(control)
            control.style().polish(control)
            control.update()
        key = 'navigation_expand' if self.collapsed else 'navigation_collapse'
        set_text(self.toggle, tr(key), 'setAccessibleName')
        set_text(self.toggle, tr(key), 'setToolTip')
        set_text(self.toggle, tr('section_collapsed' if self.collapsed else 'section_expanded'),
                 'setAccessibleDescription')
        set_icon(self.toggle, 'expand' if self.collapsed else 'collapse')

    def select(self, route: Route) -> None:
        for destination, control in self.buttons.items():
            control.setChecked(destination == route)

    def keyPressEvent(self, event: QKeyEvent) -> None:
        # QPushButton uses Space by default; Enter should also activate navigation.
        if event.key() in (Qt.Key_Return, Qt.Key_Enter):
            focused = self.focusWidget()
            if focused is self.toggle or focused in self.buttons.values():
                focused.click()
                event.accept()
                return
        super().keyPressEvent(event)
