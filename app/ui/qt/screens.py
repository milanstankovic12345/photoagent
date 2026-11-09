"""Qt screens contain presentation only; all filesystem work goes through the worker."""
from typing import Callable
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QAbstractItemView, QComboBox, QFormLayout, QHBoxLayout,
    QLabel, QLineEdit, QListWidget, QPlainTextEdit, QProgressBar, QPushButton,
    QSpinBox, QSplitter, QTableView, QTableWidget, QVBoxLayout, QWidget)
from app.ui.qt.components import PhotoView, button
from app.ui.qt.models import MatchModel
from app.ui.qt.strings import tr


def label(text: str, layout: QVBoxLayout) -> QLabel:
    item = QLabel(text)
    item.setWordWrap(True)
    item.setTextInteractionFlags(Qt.TextSelectableByMouse)
    layout.addWidget(item)
    return item


class DashboardScreen(QWidget):
    def __init__(self, refresh: Callable) -> None:
        super().__init__()
        layout = QVBoxLayout(self)
        heading = label(tr('dashboard'), layout)
        heading.setProperty('role', 'heading')
        self.counts = label(tr('no_session'), layout)
        self.counts.setProperty('role', 'card')
        self.session = label('', layout)
        self.session.setProperty('role', 'card')
        self.warning = label('', layout)
        self.roots = label('', layout)
        label(tr('estimate'), layout)
        button('refresh', refresh, layout)
        layout.addStretch()


class ScanScreen(QWidget):
    def __init__(self, add: Callable, remove: Callable, reorder: Callable, start: Callable,
                 cancel: Callable, reports: Callable, errors_page: Callable) -> None:
        super().__init__()
        layout = QVBoxLayout(self)
        label(tr('settings_roots'), layout)
        self.roots = QListWidget()
        self.roots.setAccessibleName(tr('source'))
        layout.addWidget(self.roots, 1)
        tools = QHBoxLayout()
        layout.addLayout(tools)
        button('add', add, tools)
        button('remove', remove, tools)
        button('up', lambda: reorder(-1), tools)
        button('down', lambda: reorder(1), tools)
        actions = QHBoxLayout()
        layout.addLayout(actions)
        self.start = button('start', start, actions)
        self.cancel = button('cancel', cancel, actions)
        self.cancel.setEnabled(False)
        button('reports', reports, actions)
        self.progress = QProgressBar()
        self.progress.setTextVisible(False)
        self.progress.setRange(0, 1)
        layout.addWidget(self.progress)
        self.status = label(tr('ready'), layout)
        label(tr('errors'), layout)
        self.errors = QPlainTextEdit()
        self.errors.setReadOnly(True)
        layout.addWidget(self.errors, 1)
        pages = QHBoxLayout()
        layout.addLayout(pages)
        button('previous', lambda: errors_page(-1), pages)
        button('next', lambda: errors_page(1), pages)


class DuplicatesScreen(QWidget):
    def __init__(self, changed: Callable, sort: Callable, page: Callable, selected: Callable,
                 compare: Callable, prepare: Callable, bulk: Callable, group_changed: Callable,
                 group_page: Callable) -> None:
        super().__init__()
        layout = QVBoxLayout(self)
        filters = QHBoxLayout()
        layout.addLayout(filters)
        self.search = QLineEdit()
        self.search.setPlaceholderText(tr('search'))
        self.search.setAccessibleName(tr('search'))
        self.search.textChanged.connect(changed)
        filters.addWidget(self.search, 1)
        self.kind = QComboBox()
        self.kind.addItem(tr('all'), '')
        for kind in ('EXACT', 'VISUAL', 'DERIVATIVE', 'SIMILAR_CAPTURE'):
            self.kind.addItem(kind, kind)
        self.kind.currentIndexChanged.connect(changed)
        filters.addWidget(self.kind)
        self.warning = label('', layout)
        splitter = QSplitter()
        layout.addWidget(splitter, 1)
        group_panel = QWidget()
        group_layout = QVBoxLayout(group_panel)
        label(tr('groups'), group_layout)
        self.groups = QListWidget()
        self.groups.currentRowChanged.connect(group_changed)
        group_layout.addWidget(self.groups)
        navigation = QHBoxLayout()
        group_layout.addLayout(navigation)
        button('previous', lambda: group_page(-1), navigation)
        button('next', lambda: group_page(1), navigation)
        splitter.addWidget(group_panel)
        self.table = QTableView()
        self.model = MatchModel(self.table)
        self.table.setModel(self.model)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.horizontalHeader().sectionClicked.connect(sort)
        self.table.selectionModel().currentRowChanged.connect(selected)
        self.table.doubleClicked.connect(compare)
        self.table.setAlternatingRowColors(True)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setAccessibleName(tr('duplicates'))
        splitter.addWidget(self.table)
        splitter.setStretchFactor(1, 3)
        self.empty = label('', layout)
        pages = QHBoxLayout()
        layout.addLayout(pages)
        button('previous', lambda: page(-1), pages)
        self.page = QLabel()
        pages.addWidget(self.page, 1)
        button('next', lambda: page(1), pages)
        actions = QHBoxLayout()
        layout.addLayout(actions)
        button('compare', compare, actions)
        self.prepare = button('selected_move', prepare, actions)
        self.bulk = button('bulk_move', bulk, actions)


class CompareScreen(QWidget):
    def __init__(self, prepare: Callable) -> None:
        super().__init__()
        layout = QVBoxLayout(self)
        self.warning = label(tr('heuristic'), layout)
        label(tr('preview_note'), layout)
        split = QSplitter()
        self.left, self.right = PhotoView(), PhotoView()
        split.addWidget(self.left)
        split.addWidget(self.right)
        layout.addWidget(split, 1)
        controls = QHBoxLayout()
        layout.addLayout(controls)
        self.keep = QComboBox()
        self.keep.addItem(tr('keep_left'), False)
        self.keep.addItem(tr('keep_right'), True)
        controls.addWidget(self.keep)
        self.prepare = button('selected_move', prepare, controls)


class HistoryScreen(QWidget):
    def __init__(self, restore: Callable, page: Callable) -> None:
        super().__init__()
        layout = QVBoxLayout(self)
        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels([tr(k) for k in ('time', 'source', 'destination', 'state', 'detail', 'restore')])
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.table, 1)
        actions = QHBoxLayout()
        layout.addLayout(actions)
        button('previous', lambda: page(-1), actions)
        self.page = QLabel()
        actions.addWidget(self.page, 1)
        button('next', lambda: page(1), actions)
        self.restore = button('restore', restore, layout)


class SettingsScreen(QWidget):
    def __init__(self, save: Callable, theme_changed: Callable) -> None:
        super().__init__()
        layout = QVBoxLayout(self)
        form = QFormLayout()
        layout.addLayout(form)
        self.theme = QComboBox()
        for theme in ('dark', 'light', 'system'):
            self.theme.addItem(tr(theme), theme)
        self.theme.currentIndexChanged.connect(theme_changed)
        form.addRow(tr('theme'), self.theme)
        language = QComboBox()
        language.addItem(tr('language'))
        language.setEnabled(False)
        language.setToolTip(tr('language_later'))
        form.addRow(tr('language'), language)
        label(tr('language_later'), layout)
        label(tr('sensitivity'), layout)
        matching = QFormLayout()
        layout.addLayout(matching)
        self.phash, self.dhash = QSpinBox(), QSpinBox()
        for item in (self.phash, self.dhash):
            item.setRange(0, 64)
        matching.addRow(tr('phash'), self.phash)
        matching.addRow(tr('dhash'), self.dhash)
        label(tr('settings_roots'), layout)
        label(tr('locked'), layout)
        self.index = label('', layout)
        button('save', save, layout)
        layout.addStretch()
