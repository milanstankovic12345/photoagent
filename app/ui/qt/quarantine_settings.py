"""Quarantine and Settings presentation; all file inspection stays in services."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import (QAbstractItemView, QComboBox, QFormLayout, QHBoxLayout,
    QHeaderView, QLabel, QSpinBox, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget)

from app import __version__
from app.core.queries import HistoryEntry, MatchingOptions, PageResult, StorageSummary
from app.ui.qt.components import (Card, CollapsibleSection, ContextToolbar, EmptyState,
                                  TechnicalDetails, ThemeSelector, button, path_label, text_label)
from app.ui.qt.localization import set_text, text_of, add_item, language_manager
from app.ui.qt.strings import tr, join_text

# Search breadth choices, not calibrated image-quality or duplicate confidence.
MATCHING_PRESETS = {'strict': MatchingOptions(2, 3), 'balanced': MatchingOptions(),
                    'broader': MatchingOptions(8, 10)}


def move_date(value: str | None) -> str:
    if value is None:
        return tr('not_available')
    try:
        parsed = datetime.fromisoformat(value)
        if parsed.tzinfo is None:
            return tr('not_available')
        return parsed.astimezone(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')
    except ValueError:
        return tr('not_available')


class HistoryScreen(QWidget):
    selection_changed = Signal()

    def __init__(self, restore: Callable, page: Callable, open_folder: Callable) -> None:
        super().__init__()
        self.entries: dict[str, HistoryEntry] = {}
        layout = QVBoxLayout(self)
        self.toolbar = ContextToolbar()
        self.restore = button('restore', restore, self.toolbar.actions, variant='primary')
        self.open_folder = button('open_quarantine_folder', open_folder, self.toolbar.actions)
        layout.addWidget(text_label(tr('quarantine_description'), 'metadata'))
        self.message = text_label('')
        layout.addWidget(self.message)
        self.empty = EmptyState('quarantine_empty', 'quarantine_empty_detail')
        layout.addWidget(self.empty)
        self.table = QTableWidget(0, 6)
        set_text(self.table, [tr(k) for k in
            ('name', 'original_location', 'moved_at', 'size', 'state', 'kind')], 'setHorizontalHeaderLabels')
        set_text(self.table, tr('history'), 'setAccessibleName')
        set_text(self.table, tr('keyboard_history'), 'setAccessibleDescription')
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setTabKeyNavigation(False)  # Arrows browse cells; Tab leaves the table.
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setAlternatingRowColors(True)
        self.table.setWordWrap(False)
        self.table.setTextElideMode(Qt.ElideMiddle)
        header = self.table.horizontalHeader()
        header.setStretchLastSection(False)
        header.setMinimumSectionSize(110)
        header.setSectionResizeMode(QHeaderView.ResizeToContents)
        header.setSectionResizeMode(0, QHeaderView.Interactive)
        header.resizeSection(0, 160)
        header.setSectionResizeMode(1, QHeaderView.Stretch)
        self.table.setMinimumHeight(220)
        self.table.itemSelectionChanged.connect(self.selection_changed)
        layout.addWidget(self.table, 1)
        self.pager = QWidget()
        actions = QHBoxLayout(self.pager)
        self.previous = button('previous', lambda: page(-1), actions)
        self.page = QLabel()
        actions.addWidget(self.page, 1)
        self.next = button('next', lambda: page(1), actions)
        layout.addWidget(self.pager)
        self.detail_card = Card()
        detail_layout = self.detail_card.content
        self.thumbnail = text_label(tr('thumbnail_unavailable'), 'metadata')
        self.thumbnail.setAlignment(Qt.AlignCenter)
        self.thumbnail.setFixedHeight(120)
        detail_layout.addWidget(self.thumbnail)
        self.details = path_label()
        detail_layout.addWidget(self.details)
        layout.addWidget(self.detail_card)
        self.error_details = TechnicalDetails()
        layout.addWidget(self.error_details)
        self.empty_space = QWidget()
        layout.addWidget(self.empty_space, 1)
        self.show_page(PageResult((), 0))
        language_manager().changed.connect(self.retranslate_rows)

    def retranslate_rows(self) -> None:
        # Update cells in place: no selection signal, preview job or plan change.
        for row in range(self.table.rowCount()):
            entry = self.entries[self.table.item(row, 0).data(Qt.UserRole)]
            status = 'state_restored' if entry.restored and entry.state == 'complete' else 'state_' + entry.state
            for column, value in ((2, move_date(entry.moved_at)),
                                  (3, str(entry.size) if entry.size is not None else tr('not_available')),
                                  (4, tr(status)), (5, tr('action_' + entry.action))):
                item = self.table.item(row, column)
                item.setText(value)
                item.setToolTip(value)

    @property
    def selected_entry(self) -> HistoryEntry | None:
        row = self.table.currentRow()
        item = self.table.item(row, 0)
        # Never interpret a previous row position as a new operation ID.
        return self.entries.get(item.data(Qt.UserRole)) if item and self.table.selectedItems() else None

    def clear_selection(self) -> None:
        self.table.clearSelection()
        self.table.setCurrentCell(-1, -1)

    def show_page(self, value: PageResult[HistoryEntry]) -> None:
        selected = self.selected_entry
        selected_id = selected.id if selected else None
        self.table.blockSignals(True)
        self.table.clearSelection()
        self.table.setCurrentCell(-1, -1)
        self.entries = {entry.id: entry for entry in value.items}
        self.table.setRowCount(len(value.items))
        for i, entry in enumerate(value.items):
            original = entry.source if entry.action == 'quarantine' else entry.destination
            status = ('state_restored' if entry.restored and entry.state == 'complete' else 'state_' + entry.state)
            columns = (Path(original).name, original, move_date(entry.moved_at),
                       str(entry.size) if entry.size is not None else tr('not_available'),
                       tr(status), tr('action_' + entry.action))
            for j, text in enumerate(columns):
                item = QTableWidgetItem(text)
                item.setData(Qt.UserRole, entry.id)
                item.setToolTip(text)
                self.table.setItem(i, j, item)
            if entry.id == selected_id:
                self.table.selectRow(i)
        self.table.blockSignals(False)
        set_text(self.message, '')
        self.message.hide()
        self.error_details.set_detail('')
        self.empty.setVisible(value.total == 0)
        self.empty_space.setVisible(not value.items)
        self.table.setVisible(bool(value.items))
        self.pager.setVisible(value.total > 0)
        self.previous.setEnabled(value.offset > 0)
        self.next.setEnabled(value.offset + len(value.items) < value.total)
        set_text(self.page, tr('page', value.offset + bool(value.items), value.offset + len(value.items), value.total))
        self.selection_changed.emit()

    def selection_details(self) -> None:
        entry = self.selected_entry
        self.detail_card.setVisible(entry is not None)
        self.thumbnail.clear()
        set_text(self.thumbnail, tr('preview_loading') if entry and entry.restorable else tr('thumbnail_unavailable'))
        set_text(self.thumbnail, text_of(self.thumbnail), 'setAccessibleName')
        self.error_details.set_detail(entry.error if entry else '')
        if entry:
            set_text(self.details, tr('history_selection', entry.id, entry.source, entry.destination,
                                    tr('yes' if entry.restorable else 'no')))

    def show_preview(self, operation_id: str, image: QImage) -> None:
        entry = self.selected_entry
        if entry and entry.id == operation_id:
            set_text(self.thumbnail, '')
            self.thumbnail.setPixmap(QPixmap.fromImage(image).scaled(200, 120, Qt.KeepAspectRatio, Qt.SmoothTransformation))
            set_text(self.thumbnail, tr('thumbnail_for', Path(entry.source).name), 'setAccessibleName')

    def fail(self, detail: str) -> None:
        self.show_page(PageResult((), 0))
        self.empty.hide()
        set_text(self.message, tr('history_load_failed'))
        self.error_details.set_detail(detail)
        self.message.show()


class SettingsScreen(QWidget):
    def __init__(self, save: Callable, theme_changed: Callable, edit_sources: Callable,
                 language_changed: Callable) -> None:
        super().__init__()
        layout = QVBoxLayout(self)
        self.toolbar = ContextToolbar()
        self.save = button('save', save, self.toolbar.actions)

        def section(key: str, description: str) -> QVBoxLayout:
            card = Card()
            card.content.addWidget(text_label(tr(key), 'section'))
            card.content.addWidget(text_label(tr(description), 'metadata'))
            layout.addWidget(card)
            return card.content

        appearance = section('settings_appearance', 'settings_appearance_detail')
        self.theme = ThemeSelector()
        self.theme.currentIndexChanged.connect(theme_changed)
        appearance.addWidget(self.theme)
        language = section('settings_language', 'language_later')
        self.language = QComboBox()
        set_text(self.language, tr('settings_language'), 'setAccessibleName')
        add_item(self.language, tr('language_english'), 'en')
        add_item(self.language, tr('language_serbian'), 'sr_Latn')
        self.language.currentIndexChanged.connect(language_changed)
        language.addWidget(self.language)
        scanning = section('settings_scanning', 'settings_roots')
        self.roots = path_label()
        scanning.addWidget(self.roots)
        self.edit_sources = button('edit_sources', edit_sources, scanning)
        matching = section('settings_similarity', 'matching_explanation')
        self.preset = QComboBox()
        set_text(self.preset, tr('settings_similarity'), 'setAccessibleName')
        for key in (*MATCHING_PRESETS, 'custom'):
            add_item(self.preset, tr('matching_' + key), key)
        matching.addWidget(self.preset)
        self.preset_detail = text_label('')
        matching.addWidget(self.preset_detail)
        self.advanced = CollapsibleSection('sensitivity')
        matching.addWidget(self.advanced)
        form = QFormLayout()
        self.advanced.body_layout.addLayout(form)
        self.phash, self.dhash = QSpinBox(), QSpinBox()
        for key, item in (('phash', self.phash), ('dhash', self.dhash)):
            item.setRange(0, 64)
            set_text(item, tr(key), 'setAccessibleName')
            form.addRow(text_label(tr(key)), item)
            item.valueChanged.connect(self.matching_edited)
        self.preset.currentIndexChanged.connect(self.preset_changed)
        self.load_matching(4, 6)
        safety = section('settings_safety', 'settings_safety_detail')
        safety.addWidget(text_label(tr('locked')))
        storage = section('settings_storage', 'preview_cache_detail')
        self.index = path_label(tr('storage_loading'))
        storage.addWidget(self.index)
        self.error_details = TechnicalDetails()
        storage.addWidget(self.error_details)
        about = section('settings_about', 'offline_detail')
        about.addWidget(text_label(tr('app_version', __version__)))
        layout.addStretch()

    def load_matching(self, phash: int, dhash: int) -> None:
        for control, value in ((self.phash, phash), (self.dhash, dhash)):
            control.blockSignals(True)
            control.setValue(value)
            control.blockSignals(False)
        self.matching_edited()

    def matching_edited(self) -> None:
        options = MatchingOptions(self.phash.value(), self.dhash.value())
        key = next((k for k, v in MATCHING_PRESETS.items() if v == options), 'custom')
        self.preset.blockSignals(True)
        self.preset.setCurrentIndex(self.preset.findData(key))
        self.preset.blockSignals(False)
        set_text(self.preset_detail, tr('matching_' + key + '_detail'))
        if key == 'custom':
            self.advanced.toggle.setChecked(True)

    def preset_changed(self) -> None:
        key = self.preset.currentData()
        if key in MATCHING_PRESETS:
            options = MATCHING_PRESETS[key]
            self.load_matching(options.phash_max, options.dhash_max)
        else:
            set_text(self.preset_detail, tr('matching_custom_detail'))
            self.advanced.toggle.setChecked(True)

    def show_roots(self, roots: list[str]) -> None:
        set_text(self.roots, join_text(tr('settings_source', i + 1, root) for i, root in enumerate(roots))
                           or tr('empty_sources'))

    def show_storage(self, value: StorageSummary) -> None:
        self.error_details.set_detail('')
        set_text(self.index, tr('storage_info', value.index_path, value.indexed))
