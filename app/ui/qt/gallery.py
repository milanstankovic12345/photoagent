"""Bounded model/view group gallery; thumbnails never become operation evidence."""
from __future__ import annotations

from collections import OrderedDict
from pathlib import Path
from typing import Callable

from PySide6.QtCore import QAbstractListModel, QModelIndex, QRect, QSize, QTimer, Qt, Signal
from PySide6.QtGui import QImage, QPalette, QPen, QPixmap
from PySide6.QtWidgets import QListView, QStyle, QStyledItemDelegate

from app.core.queries import GroupRow
from app.ui.qt.dashboard_scan import size_text
from app.ui.qt.localization import set_text, language_manager
from app.ui.qt.strings import tr
from app.ui.qt.themes import RADII


def pair_formats(row: GroupRow) -> str:
    """Describe only the two displayed samples, never the group's provenance."""
    raw = any(p.is_raw for p in row.samples[:2])
    jpeg = any(not p.is_raw and p.image_format.upper() == 'JPEG' for p in row.samples[:2])
    return tr('sample_raw_jpeg') if raw and jpeg else ''


class GroupModel(QAbstractListModel):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.rows: tuple[GroupRow, ...] = ()
        self.images: OrderedDict = OrderedDict()
        self.review: dict[tuple[int, str], set[int]] = {}
        language_manager().changed.connect(self.retranslate)

    def retranslate(self) -> None:
        self.dataChanged.emit(self.index(0), self.index(len(self.rows)))

    def replace(self, rows: tuple[GroupRow, ...]) -> None:
        self.beginResetModel()
        self.rows = rows
        self.images.clear()
        self.endResetModel()

    def rowCount(self, parent=QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self.rows) + 1

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid():
            return None
        if index.row() == 0:
            return tr('all_groups') if role in (Qt.DisplayRole, Qt.AccessibleTextRole) else None
        row = self.rows[index.row() - 1]
        if role == Qt.DisplayRole:
            return Path(row.keeper_path).name
        if role in (Qt.ToolTipRole, Qt.AccessibleTextRole):
            failures = [tr('preview_error') for photo in row.samples if isinstance(self.images.get(photo), str)]
            details = [row.keeper_path, tr('group_summary', row.members, tr('filter_' + row.kind)),
                self.review_text(row), tr('review_session_only'), tr('classification_' + row.kind),
                pair_formats(row), tr('review_group'), tr('keyboard_groups'), *failures]
            if row.potential_bytes is not None:
                details.extend((tr('group_space', size_text(row.potential_bytes)), tr('estimate')))
            return '\n'.join(filter(None, details))
        if role == Qt.UserRole:
            return row

    def review_text(self, row: GroupRow) -> str:
        count = len(self.review.get((row.keeper_id, row.kind), set()))
        return tr('reviewed' if count >= row.members - 1 else 'review_progress' if count else 'needs_review', count)


class GroupDelegate(QStyledItemDelegate):
    def sizeHint(self, option, index) -> QSize:
        return QSize(264, 252) if self.parent().viewMode() == QListView.IconMode else QSize(264, 148)

    @staticmethod
    def photo_rect(rect: QRect, grid: bool) -> QRect:
        return QRect(rect.x() + 14, rect.y() + 14, rect.width() - 28 if grid else 170, 104)

    @staticmethod
    def review_rect(rect: QRect, grid: bool) -> QRect:
        return QRect(rect.x() + (14 if grid else 198), rect.bottom() - 38,
                     rect.width() - (28 if grid else 212), 28)

    def paint(self, painter, option, index) -> None:
        painter.save()
        selected = bool(option.state & QStyle.State_Selected)
        palette = option.palette
        rect = option.rect.adjusted(4, 4, -4, -4)
        painter.setPen(palette.color(QPalette.Mid))
        painter.setBrush(palette.color(QPalette.Highlight if selected else QPalette.AlternateBase))
        painter.drawRoundedRect(rect, RADII['card'], RADII['card'])
        painter.setPen(palette.color(QPalette.HighlightedText if selected else QPalette.Text))
        row = index.data(Qt.UserRole)
        if row is None:
            painter.drawText(rect.adjusted(12, 8, -12, -8), Qt.AlignCenter, tr('all_groups'))
            painter.restore()
            return
        model = index.model()
        grid = self.parent().viewMode() == QListView.IconMode
        image_rect = self.photo_rect(option.rect, grid)
        for i, photo in enumerate(row.samples[:2]):
            target = QRect(image_rect.x() + i * (image_rect.width() // 2 + 2), image_rect.y(),
                           image_rect.width() // 2 - 2, image_rect.height())
            cached = model.images.get(photo)
            if isinstance(cached, QPixmap):
                size = cached.size().scaled(target.size(), Qt.KeepAspectRatio)
                fitted = QRect(target.topLeft(), size)
                fitted.moveCenter(target.center())
                painter.drawPixmap(fitted, cached)
            else:
                painter.drawText(target, Qt.AlignCenter | Qt.TextWordWrap,
                                 tr('thumbnail_unavailable') if cached else tr('preview_loading'))
        if pair_formats(row):
            badge = QRect(image_rect.x(), image_rect.bottom() - 19, image_rect.width(), 20)
            painter.fillRect(badge, palette.color(QPalette.Base))
            painter.setPen(palette.color(QPalette.Text))
            painter.drawText(badge, Qt.AlignCenter, tr('sample_raw_jpeg_short'))
            painter.setPen(palette.color(QPalette.HighlightedText if selected else QPalette.Text))
        text_rect = rect.adjusted(10, 118, -10, -8) if grid else rect.adjusted(194, 8, -10, -8)
        lines = [Path(row.keeper_path).name, tr('group_summary', row.members, tr('filter_' + row.kind)),
                 model.review_text(row)]
        for line in lines:
            painter.drawText(QRect(text_rect.x(), text_rect.y(), text_rect.width(), 24),
                             Qt.AlignLeft | Qt.AlignVCenter,
                             option.fontMetrics.elidedText(line, Qt.ElideMiddle, text_rect.width()))
            text_rect.translate(0, 24)
        action = self.review_rect(option.rect, grid)
        painter.setPen(palette.color(QPalette.HighlightedText if selected else QPalette.Link))
        painter.drawRoundedRect(action, RADII['card'], RADII['card'])
        painter.drawText(action, Qt.AlignCenter, tr('review_group'))
        if option.state & QStyle.State_HasFocus:
            painter.setPen(QPen(palette.color(QPalette.Link), 2))
            painter.setBrush(Qt.NoBrush)  # Focus outline must not cover the card contents.
            painter.drawRect(rect.adjusted(2, 2, -2, -2))
        painter.restore()


class GroupView(QListView):
    """One active batch of <=3, <=48 rendered thumbnails, <=24 group rows."""
    review_requested = Signal(QModelIndex)

    def __init__(self, thumbnails: Callable) -> None:
        super().__init__()
        self.groups_model = GroupModel(self)
        self.setModel(self.groups_model)
        self.setItemDelegate(GroupDelegate(self))
        self.setRowHidden(0, True)  # All groups is a separate action, never a photo card.
        set_text(self, tr('groups'), 'setAccessibleName')
        set_text(self, tr('keyboard_groups'), 'setAccessibleDescription')
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setTextElideMode(Qt.ElideMiddle)
        self.setMinimumHeight(250)
        self.request = thumbnails
        self.inflight: tuple = ()
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.setInterval(60)
        self.timer.timeout.connect(self.load_visible)
        self.verticalScrollBar().valueChanged.connect(lambda: self.timer.start())
        self.set_grid(True)

    def set_grid(self, grid: bool) -> None:
        self.setViewMode(QListView.IconMode if grid else QListView.ListMode)
        self.setWrapping(grid)
        self.setResizeMode(QListView.Adjust)
        self.setMovement(QListView.Static)
        self.setGridSize(QSize(264, 252) if grid else QSize())
        self.setUniformItemSizes(True)
        self.setSpacing(2)
        self.timer.start()

    def focusInEvent(self, event) -> None:
        super().focusInEvent(event)
        # Row zero represents the separate All Groups action and is hidden.
        # Qt's icon-view navigation can otherwise leave keyboard focus on it.
        if self.currentRow() <= 0 and self.groups_model.rows:
            self.setCurrentRow(1)

    def sizeHintForRow(self, row: int) -> int:
        return 252 if self.viewMode() == QListView.IconMode else 148

    def mouseReleaseEvent(self, event) -> None:
        super().mouseReleaseEvent(event)
        index = self.indexAt(event.position().toPoint())
        if event.button() == Qt.LeftButton and index.isValid() and index.row() > 0:
            action = GroupDelegate.review_rect(self.visualRect(index), self.viewMode() == QListView.IconMode)
            if action.contains(event.position().toPoint()):
                self.review_requested.emit(index)

    def mouseDoubleClickEvent(self, event) -> None:
        index = self.indexAt(event.position().toPoint())
        if index.isValid() and index.row() > 0:
            # A group thumbnail contains two concrete files. It is not a target
            # for opening an arbitrary file, nor a shortcut into group review.
            photo = GroupDelegate.photo_rect(self.visualRect(index), self.viewMode() == QListView.IconMode)
            if photo.contains(event.position().toPoint()):
                event.accept()
                return
        super().mouseDoubleClickEvent(event)

    def currentRow(self) -> int:
        return self.currentIndex().row()

    def setCurrentRow(self, row: int) -> None:
        self.setCurrentIndex(self.model().index(row))

    def replace(self, rows: tuple[GroupRow, ...]) -> None:
        if self.inflight:
            self.request(())  # A hidden gallery must not cancel Dashboard's batch.
        self.inflight = ()
        self.groups_model.replace(rows)
        self.setRowHidden(0, True)
        self.timer.start()

    def load_visible(self) -> None:
        if not self.isVisible() or self.inflight:
            return
        photos = []
        for i, row in enumerate(self.groups_model.rows, 1):
            if self.viewport().rect().intersects(self.visualRect(self.model().index(i))):
                photos.extend(p for p in row.samples if p not in self.groups_model.images and p not in photos)
        self.inflight = tuple(photos[:3])
        if self.inflight:
            self.request(self.inflight)

    def set_thumbnails(self, values: tuple) -> None:
        if not self.isVisible() or not self.inflight:
            return
        for photo, image, error in values:
            if photo not in self.inflight:
                continue
            self.groups_model.images[photo] = (QPixmap.fromImage(image) if isinstance(image, QImage)
                and not image.isNull() else error or tr('unavailable'))
        while len(self.groups_model.images) > 48:
            self.groups_model.images.popitem(last=False)
        self.inflight = ()
        self.viewport().update()
        self.timer.start()

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self.timer.start()

    def hideEvent(self, event) -> None:
        self.timer.stop()
        if self.inflight:
            self.request(())
        self.inflight = ()
        super().hideEvent(event)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self.timer.start()

    def sizeHint(self) -> QSize:
        return QSize(600, 260)


