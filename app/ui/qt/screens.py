"""Qt screens contain presentation only; all filesystem work goes through the worker."""
from typing import Callable
from PySide6.QtCore import QEvent, Qt
from PySide6.QtWidgets import (QAbstractItemView, QComboBox, QHBoxLayout,
    QLabel, QLineEdit,
    QScrollArea, QSplitter, QStackedWidget, QTableView,
    QVBoxLayout, QWidget)
from app.ui.qt.components import CollapsibleSection, ContextToolbar, PhotoView, TechnicalDetails, button, text_label
from app.ui.qt.dashboard_scan import DashboardScreen, ScanScreen
from app.ui.qt.models import MatchModel
from app.ui.qt.gallery import GroupView
from app.ui.qt.strings import tr
from app.ui.qt.quarantine_settings import HistoryScreen, SettingsScreen


def label(text: str, layout: QVBoxLayout) -> QLabel:
    item = QLabel(text)
    item.setTextFormat(Qt.PlainText)
    item.setWordWrap(True)
    item.setTextInteractionFlags(Qt.TextSelectableByMouse)
    layout.addWidget(item)
    return item


def scroll_page(screen: QWidget) -> QScrollArea:
    scroll = QScrollArea()
    scroll.setWidgetResizable(True)
    scroll.setFrameShape(QScrollArea.NoFrame)
    scroll.setFocusPolicy(Qt.NoFocus)
    scroll.setWidget(screen)
    if isinstance(screen, CompareScreen):
        scroll.viewport().installEventFilter(screen)
    return scroll


class DuplicatesFlow(QStackedWidget):
    """Both views stay alive, preserving queries, selection and scroll positions."""
    def __init__(self, listing: QWidget, comparison: QWidget) -> None:
        super().__init__()
        self.listing = scroll_page(listing)
        self.comparison = scroll_page(comparison)
        self.addWidget(self.listing)
        self.addWidget(self.comparison)
        self.listing_scroll = (0, 0)

    @property
    def comparing(self) -> bool:
        return self.currentWidget() is self.comparison

    def show_comparison(self, comparing: bool) -> None:
        if comparing and not self.comparing:
            self.listing_scroll = (self.listing.horizontalScrollBar().value(), self.listing.verticalScrollBar().value())
        self.setCurrentWidget(self.comparison if comparing else self.listing)

    def restore_listing_scroll(self) -> None:
        for bar, value in zip((self.listing.horizontalScrollBar(), self.listing.verticalScrollBar()), self.listing_scroll):
            bar.setValue(value)


class DuplicatesScreen(QWidget):
    def __init__(self, changed: Callable, sort: Callable, page: Callable, selected: Callable,
                 compare: Callable, prepare: Callable, bulk: Callable, group_changed: Callable,
                 group_page: Callable, thumbnails: Callable) -> None:
        super().__init__()
        layout = QVBoxLayout(self)
        self.toolbar = ContextToolbar()
        self.compare = button('compare', compare, self.toolbar.actions)
        self.compare.setEnabled(False)
        self.bulk = button('bulk_move', bulk, self.toolbar.actions, variant='secondary')
        filters = QVBoxLayout()
        layout.addLayout(filters)
        self.search = QLineEdit()
        self.search.setPlaceholderText(tr('search'))
        self.search.setAccessibleName(tr('search'))
        self.search.textChanged.connect(changed)
        filters.addWidget(self.search, 1)
        options = ContextToolbar()
        filters.addWidget(options)
        self.kind = QComboBox()
        self.kind.setAccessibleName(tr('category_filter'))
        self.kind.addItem(tr('all'), '')
        for kind in ('EXACT', 'VISUAL'):
            self.kind.addItem(tr('filter_' + kind), kind)
        self.kind.currentIndexChanged.connect(changed)
        options.actions.addWidget(self.kind)
        self.sort_order = QComboBox()
        for key in MatchModel.columns:
            self.sort_order.addItem(tr(key), key)
        self.sort_order.setAccessibleName(tr('sort'))
        self.sort_order.currentIndexChanged.connect(sort)
        options.actions.addWidget(self.sort_order)
        self.direction = button('sort_asc', lambda: sort(self.sort_order.currentIndex()), options.actions)
        self.direction.setAccessibleDescription(tr('sort_direction'))
        self.mode = QComboBox()
        self.mode.addItems([tr('grid'), tr('list')])
        self.mode.setAccessibleName(tr('view_mode'))
        options.actions.addWidget(self.mode)
        self.warning = label('', layout)
        splitter = QSplitter(Qt.Vertical)
        self.results_panel = splitter
        layout.addWidget(splitter, 1)
        group_panel = QWidget()
        group_layout = QVBoxLayout(group_panel)
        group_heading = QHBoxLayout()
        group_layout.addLayout(group_heading)
        group_heading.addWidget(text_label(tr('groups')), 1)
        self.all_groups = button('all_groups', lambda: self.groups.setCurrentRow(0), group_heading)
        self.groups = GroupView(thumbnails)
        self.groups.selectionModel().currentChanged.connect(lambda current, _: group_changed(current.row()))
        self.mode.currentIndexChanged.connect(lambda index: self.groups.set_grid(index == 0))
        group_layout.addWidget(self.groups)
        navigation = QHBoxLayout()
        group_layout.addLayout(navigation)
        self.group_previous = button('previous', lambda: group_page(-1), navigation)
        self.group_page = QLabel()
        navigation.addWidget(self.group_page, 1)
        self.group_next = button('next', lambda: group_page(1), navigation)
        splitter.addWidget(group_panel)
        self.table = QTableView()
        self.table.setTabKeyNavigation(False)
        self.model = MatchModel(self.table)
        self.table.setModel(self.model)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.horizontalHeader().sectionClicked.connect(sort)
        self.table.selectionModel().currentRowChanged.connect(selected)
        self.table.activated.connect(compare)
        self.table.setAlternatingRowColors(True)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setAccessibleName(tr('duplicates'))
        self.table.setAccessibleDescription(tr('keyboard_pairs'))
        self.table.setTextElideMode(Qt.ElideMiddle)
        self.table.setMinimumHeight(100)
        splitter.addWidget(self.table)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 1)
        self.empty = label('', layout)
        self.pager = QWidget()
        pages = QHBoxLayout(self.pager)
        layout.addWidget(self.pager)
        self.previous = button('previous', lambda: page(-1), pages)
        self.page = QLabel()
        pages.addWidget(self.page, 1)
        self.next = button('next', lambda: page(1), pages)
        self.error_details = TechnicalDetails()
        layout.addWidget(self.error_details)
        self.set_state(tr('no_session'), False)

    def set_state(self, message: str, show_results: bool) -> None:
        self.error_details.set_detail('')
        self.empty.setText(message)
        self.empty.setVisible(bool(message))
        self.results_panel.setVisible(show_results)
        self.pager.setVisible(show_results)


class CompareScreen(QWidget):
    def __init__(self, prepare: Callable, back: Callable, keep_both: Callable, page: Callable) -> None:
        super().__init__()
        layout = QVBoxLayout(self)
        self.toolbar = ContextToolbar()
        self.back = button('back_to_group', back, self.toolbar.actions)
        self.warning = label(tr('review_advice'), layout)
        self.split = split = QSplitter()
        self.left, self.right = PhotoView(), PhotoView()
        self.left.view.setAccessibleName(tr('left_preview'))
        self.right.view.setAccessibleName(tr('right_preview'))
        split.addWidget(self.left)
        split.addWidget(self.right)
        split.setChildrenCollapsible(False)
        layout.addWidget(split, 1)
        self.decision = label(tr('choose_keeper'), layout)
        footer = ContextToolbar()
        layout.addWidget(footer)
        self.both = button('keep_both', keep_both, footer.actions)
        self.prepare = button('move_copy', prepare, footer.actions, variant='danger')
        self.context_restore = button('restore_operation', lambda: None, footer.actions)
        self.context_restore.hide()
        self.member_section = CollapsibleSection('direct_members')
        layout.addWidget(self.member_section)
        self.member_page = QLabel()
        navigation = QHBoxLayout()
        self.member_section.body_layout.addLayout(navigation)
        self.previous = button('previous', lambda: page(-1), navigation)
        navigation.addWidget(self.member_page, 1)
        self.next = button('next', lambda: page(1), navigation)
        self.members = QTableView()
        self.members.setTabKeyNavigation(False)
        self.members.setAccessibleName(tr('direct_members'))
        self.members.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.members.setSelectionMode(QAbstractItemView.SingleSelection)
        self.members.setMinimumHeight(96)
        self.members.setMaximumHeight(140)
        self.members.horizontalHeader().setStretchLastSection(True)
        self.member_section.body_layout.addWidget(self.members)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        # Keep full-size controls at narrow logical widths, including high DPI.
        # The widget itself may already be wider than the scroll viewport due
        # to the two-column minimum size. Use the available viewport width.
        available = min(self.width(), self.parentWidget().width()) if self.parentWidget() else self.width()
        self.adapt_width(available)

    def eventFilter(self, watched, event) -> bool:
        if event.type() == QEvent.Resize:
            self.adapt_width(event.size().width())
        return super().eventFilter(watched, event)

    def adapt_width(self, available: int) -> None:
        margins = self.layout().contentsMargins()
        required = (self.left.minimumSizeHint().width() + self.right.minimumSizeHint().width()
                    + self.split.handleWidth() + margins.left() + margins.right())
        orientation = Qt.Vertical if available < max(640, required) else Qt.Horizontal
        if self.split.orientation() != orientation:
            self.split.setOrientation(orientation)
            self.layout().invalidate()
            self.updateGeometry()
