from __future__ import annotations

from PySide6.QtCore import QObject, Qt
from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication

TOKENS = {
    'dark': {'background': '#161B22', 'surface': '#1F2630', 'text': '#EDF2F7',
             'accent': '#6EA8FE', 'border': '#8293A8', 'selection': '#29486D'},
    'light': {'background': '#F3F5F8', 'surface': '#FFFFFF', 'text': '#202938',
              'accent': '#215ECC', 'border': '#69798C', 'selection': '#DCE8FC'},
}


class ThemeManager(QObject):
    def __init__(self, application: QApplication) -> None:
        super().__init__(application)
        self.application = application
        self.preference = 'dark'
        self.active = 'dark'
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
                            (QPalette.Base, 'surface'), (QPalette.AlternateBase, 'background'),
                            (QPalette.Text, 'text'), (QPalette.Button, 'surface'),
                            (QPalette.ButtonText, 'text'), (QPalette.ToolTipBase, 'surface'),
                            (QPalette.ToolTipText, 'text'), (QPalette.Highlight, 'selection'),
                            (QPalette.HighlightedText, 'text'), (QPalette.Link, 'accent')):
            palette.setColor(role, QColor(c[color]))
            palette.setColor(QPalette.Disabled, role, QColor(c[color]))
        self.application.setPalette(palette)
        self.application.setStyleSheet('''
            QWidget { font-size: 14px; }
            QLabel[role="heading"] { font-size: 24px; font-weight: 600; padding: 8px 0; }
            QLabel[role="card"] { background: %(surface)s; border: 1px solid %(border)s; border-radius: 8px; padding: 16px; font-size: 18px; }
            QListWidget::item { padding: 8px; min-height: 24px; }
            QMainWindow, QDialog { background: %(background)s; color: %(text)s; }
            QPushButton, QLineEdit, QComboBox, QSpinBox { padding: 8px; border: 1px solid %(border)s; border-radius: 8px; }
            QPushButton { background: %(surface)s; color: %(text)s; }
            QPushButton[operation="true"] { border: 2px solid %(accent)s; font-weight: 600; }
            QPushButton:hover { border: 2px solid %(accent)s; padding: 7px; }
            QWidget:focus { outline: none; border: 2px solid %(accent)s; }
            QPushButton:disabled { color: %(text)s; border: 1px dashed %(border)s; }
            QTableView, QListWidget, QPlainTextEdit, QGraphicsView { background: %(surface)s; color: %(text)s; border: 1px solid %(border)s; border-radius: 8px; }
            QHeaderView::section { background: %(surface)s; color: %(text)s; padding: 8px; border: 0; border-bottom: 1px solid %(border)s; }
            QTableView::item:selected, QListWidget::item:selected { background: %(selection)s; color: %(text)s; }
            QProgressBar { border: 1px solid %(border)s; border-radius: 8px; text-align: center; }
            QProgressBar::chunk { background: %(accent)s; }
        ''' % c)
