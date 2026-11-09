"""Shared semantic tokens and application-wide Qt presentation; no settings I/O."""
from __future__ import annotations

from PySide6.QtCore import QObject, Qt
from PySide6.QtGui import QColor, QFont, QFontDatabase, QPalette
from PySide6.QtWidgets import QApplication, QToolTip

# Logical pixels: Qt handles device scaling. Geometry stays unchanged across states.
SPACING = (4, 8, 12, 16, 24, 32)
RADII = {'control': 8, 'card': 12}
CONTROL_HEIGHT = 36
TYPE = {'title': 24, 'section': 18, 'body': 14, 'metadata': 13, 'small': 12}
TOKENS = {
    'dark': {
        'background': '#0B1220', 'surface': '#172338', 'elevated': '#1E2B40',
        'border': '#2A3A52', 'control_border': '#8295B0',
        'text': '#F3F6FC', 'secondary_text': '#A7B4C9',
        'accent': '#3B82F6', 'link': '#93C5FD', 'primary': '#2563EB', 'on_primary': '#FFFFFF',
        'primary_hover': '#1D4ED8', 'hover': '#243750', 'selection': '#24466E',
        'success': '#34D399', 'warning': '#FBBF24', 'danger': '#EF6464',
        'danger_hover': '#FF9292', 'on_danger': '#0B1220',
        'disabled': '#1E2B40', 'disabled_text': '#A7B4C9', 'focus': '#93C5FD',
        'primary_focus': '#FFFFFF', 'danger_focus': '#0B1220',
    },
    'light': {
        'background': '#F2F5FA', 'surface': '#FFFFFF', 'elevated': '#E9EFF7',
        'border': '#CCD6E4', 'control_border': '#61738D',
        'text': '#172338', 'secondary_text': '#52637A',
        'accent': '#2563EB', 'link': '#1D4ED8', 'primary': '#2563EB', 'on_primary': '#FFFFFF',
        'primary_hover': '#1D4ED8', 'hover': '#E9EFF7', 'selection': '#DCE8FC',
        'success': '#13724F', 'warning': '#855000', 'danger': '#B42332',
        'danger_hover': '#921C29', 'on_danger': '#FFFFFF',
        'disabled': '#E4EAF2', 'disabled_text': '#52637A', 'focus': '#1D4ED8',
        'primary_focus': '#FFFFFF', 'danger_focus': '#FFFFFF',
    },
}


def stylesheet(colors: dict[str, str]) -> str:
    """One stylesheet for all screens, dialogs and reusable widgets."""
    return '''
        QWidget { font-size: %(body)dpx; color: %(text)s; }
        QMainWindow, QDialog, QScrollArea > QWidget > QWidget { background: %(background)s; }
        QLabel { background: transparent; }
        QLabel[role="heading"] { font-size: %(title)dpx; font-weight: 600; }
        QLabel[role="section"] { font-size: %(section)dpx; font-weight: 600; }
        QLabel[role="metadata"] { font-size: %(metadata)dpx; color: %(secondary_text)s; }
        QLabel[role="small"] { font-size: %(small)dpx; color: %(secondary_text)s; }
        QLabel[role="stat"] { font-size: %(title)dpx; font-weight: 600; }
        QFrame[role="card"], QLabel[role="card"] {
            background: %(surface)s; border: 1px solid %(border)s; border-radius: %(card_radius)dpx;
        }
        QLabel[role="card"] { padding: 16px; font-size: %(section)dpx; }
        QLabel[role="badge"] { background: %(elevated)s; border-radius: %(control_radius)dpx;
            padding: 4px 8px; font-size: %(small)dpx; font-weight: 600; }
        QLabel[tone="success"] { color: %(success)s; }
        QLabel[tone="warning"] { color: %(warning)s; }
        QLabel[tone="danger"] { color: %(danger)s; }
        QPushButton, QLineEdit, QComboBox, QSpinBox {
            min-height: %(control_content)dpx; padding: 6px 12px;
            background: %(surface)s; border: 2px solid %(control_border)s;
            border-radius: %(control_radius)dpx; selection-background-color: %(selection)s;
            selection-color: %(text)s;
        }
        QLineEdit { placeholder-text-color: %(secondary_text)s; }
        QPushButton { font-weight: 600; }
        QPushButton:hover, QPushButton:pressed { background: %(hover)s; }
        QPushButton[navigation="true"] { text-align: left; padding: 10px 8px; }
        QPushButton[navigation="true"]:checked { background: %(selection)s; color: %(text)s; }
        QPushButton[choice="true"]:checked { background: %(selection)s; color: %(text)s; }
        QPushButton[variant="primary"] { background: %(primary)s; color: %(on_primary)s; border-color: %(primary)s; }
        QPushButton[variant="primary"]:hover, QPushButton[variant="primary"]:pressed {
            background: %(primary_hover)s; border-color: %(primary_hover)s;
        }
        QPushButton[variant="danger"] { background: %(danger)s; color: %(on_danger)s; border-color: %(danger)s; }
        QPushButton[variant="danger"]:hover, QPushButton[variant="danger"]:pressed {
            background: %(danger_hover)s; border-color: %(danger_hover)s;
        }
        QPushButton[operation="true"] { font-weight: 600; }
        QPushButton:disabled, QLineEdit:disabled, QComboBox:disabled, QSpinBox:disabled {
            color: %(disabled_text)s; background: %(disabled)s; border-color: %(control_border)s;
        }
        QPushButton:focus, QLineEdit:focus, QComboBox:focus, QSpinBox:focus { border-color: %(focus)s; }
        QPushButton[variant="primary"]:focus { border-color: %(primary_focus)s; }
        QPushButton[variant="danger"]:focus { border-color: %(danger_focus)s; }
        QCheckBox { spacing: 8px; padding: 4px; border: 2px solid transparent; }
        QCheckBox:focus { border-color: %(focus)s; border-radius: %(control_radius)dpx; }
        QCheckBox::indicator { width: 16px; height: 16px; border: 2px solid %(control_border)s; background: %(surface)s; }
        QCheckBox::indicator:checked { background: %(primary)s; image: url(:/photoagent/check.svg); }
        QCheckBox:disabled { color: %(disabled_text)s; }
        QTableView, QListView, QPlainTextEdit, QGraphicsView {
            background: %(surface)s; alternate-background-color: %(elevated)s;
            border: 2px solid %(control_border)s; border-radius: %(control_radius)dpx;
            selection-background-color: %(selection)s; selection-color: %(text)s;
            gridline-color: %(border)s;
        }
        QTableView:focus, QListView:focus, QPlainTextEdit:focus, QGraphicsView:focus { border-color: %(focus)s; }
        QTableView::item, QListView::item { padding: 8px; border: 2px solid transparent; }
        QListView::item:hover { background: %(hover)s; }
        QTableView::item:selected, QListView::item:selected { background: %(selection)s; color: %(text)s; }
        QTableView::item:focus, QListView::item:focus { border-color: %(focus)s; }
        QHeaderView::section { background: %(elevated)s; padding: 8px; border: 0; border-bottom: 1px solid %(control_border)s; }
        QMenu, QComboBox QAbstractItemView { background: %(surface)s; border: 1px solid %(control_border)s; padding: 4px; }
        QMenu::item { padding: 8px 24px; }
        QMenu::item:selected { background: %(selection)s; }
        QMenu::item:disabled { color: %(disabled_text)s; }
        QMenu::separator { height: 1px; background: %(control_border)s; margin: 4px; }
        QToolTip { background: %(elevated)s; color: %(text)s; border: 1px solid %(control_border)s; padding: 8px; }
        QProgressBar { background: %(background)s; border: 1px solid %(control_border)s; border-radius: 8px; text-align: center; }
        QProgressBar::chunk { background: %(accent)s; }
        QStatusBar { background: %(background)s; }
        QSplitter::handle { background: %(border)s; }
    ''' % {**colors, **TYPE, 'card_radius': RADII['card'],
           'control_radius': RADII['control'], 'control_content': CONTROL_HEIGHT - 16}


class ThemeManager(QObject):
    def __init__(self, application: QApplication) -> None:
        super().__init__(application)
        self.application = application
        self.preference = 'dark'
        self.active = 'dark'
        # Installed platform fonts only; Qt scales logical pixels for the device.
        font = QFont(application.font())
        families = set(QFontDatabase.families())
        for family in ('Segoe UI', 'Noto Sans', 'DejaVu Sans'):
            if family in families:
                font.setFamily(family)
                break
        self.application.setFont(font)
        application.styleHints().colorSchemeChanged.connect(self.system_changed)

    def system_changed(self, scheme: Qt.ColorScheme) -> None:
        if self.preference == 'system':
            self.apply('system', scheme)

    def apply(self, preference: str, scheme: Qt.ColorScheme | None = None) -> None:
        self.preference = preference if preference in ('dark', 'light', 'system') else 'dark'
        if scheme is None:
            scheme = self.application.styleHints().colorScheme()
        self.active = ('light' if scheme == Qt.ColorScheme.Light else 'dark') if self.preference == 'system' else self.preference
        c = TOKENS[self.active]
        palette = QPalette()
        for role, color in ((QPalette.Window, 'background'), (QPalette.WindowText, 'text'),
                            (QPalette.Base, 'surface'), (QPalette.AlternateBase, 'elevated'),
                            (QPalette.Text, 'text'), (QPalette.Button, 'surface'),
                            (QPalette.ButtonText, 'text'), (QPalette.ToolTipBase, 'elevated'),
                            (QPalette.ToolTipText, 'text'), (QPalette.Highlight, 'selection'),
                            (QPalette.HighlightedText, 'text'), (QPalette.Link, 'link'),
                            (QPalette.LinkVisited, 'link'),
                            (QPalette.PlaceholderText, 'secondary_text')):
            palette.setColor(role, QColor(c[color]))
            disabled_color = 'disabled_text' if color in ('text', 'secondary_text', 'link') else color
            palette.setColor(QPalette.Disabled, role, QColor(c[disabled_color]))
        self.application.setPalette(palette)
        QToolTip.setPalette(palette)
        self.application.setStyleSheet(stylesheet(c))
