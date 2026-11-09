"""Bounded model/view group gallery; thumbnails never become operation evidence."""
from __future__ import annotations

from collections import OrderedDict
from pathlib import Path
from typing import Callable

from PySide6.QtCore import QAbstractListModel, QModelIndex, QRect, QSize, QTimer, Qt
from PySide6.QtGui import QImage, QPalette, QPixmap
from PySide6.QtWidgets import QListView, QStyle, QStyledItemDelegate

from app.core.queries import GroupRow
from app.ui.qt.dashboard_scan import size_text
from app.ui.qt.strings import tr


class GroupModel(QAbstractListModel):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.rows: tuple[GroupRow, ...] = ()
        self.images: OrderedDict = OrderedDict()
        self.review: dict[tuple[int, str], set[int]] = {}

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
            return '\n'.join((row.keeper_path, tr('group_summary', row.members, tr('classification_' + row.kind)),
                self.review_text(row), tr('review_session_only'), tr('estimate'), *failures))
        if role == Qt.UserRole:
            return row

    def review_text(self, row: GroupRow) -> str:
        count = len(self.review.get((row.keeper_id, row.kind), set()))
        return tr('reviewed' if count >= row.members - 1 else 'review_progress' if count else 'needs_review', count)


class GroupDelegate(QStyledItemDelegate):
    def sizeHint(self, option, index) -> QSize:
        return QSize(248, 224) if self.parent().viewMode() == QListView.IconMode else QSize(248, 116)

    def paint(self, painter, option, index) -> None:
        painter.save()
        selected = bool(option.state & QStyle.State_Selected)
        palette = option.palette
        rect = option.rect.adjusted(4, 4, -4, -4)
        painter.setPen(palette.color(QPalette.Mid))
        painter.setBrush(palette.color(QPalette.Highlight if selected else QPalette.Base))
        painter.drawRoundedRect(rect, 8, 8)
        painter.setPen(palette.color(QPalette.HighlightedText if selected else QPalette.Text))
        row = index.data(Qt.UserRole)
        if row is None:
            painter.drawText(rect.adjusted(12, 8, -12, -8), Qt.AlignCenter, tr('all_groups'))
            painter.restore()
            return
        model = index.model()
        grid = self.parent().viewMode() == QListView.IconMode
        image_rect = QRect(rect.x() + 10, rect.y() + 10, rect.width() - 20 if grid else 150, 86)
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
        text_rect = rect.adjusted(12, 106, -12, -8) if grid else rect.adjusted(174, 8, -12, -8)
        title = tr('selected_group', Path(row.keeper_path).name) if selected else Path(row.keeper_path).name
        lines = [title, tr('group_summary', row.members, tr('classification_' + row.kind)),
                 model.review_text(row)]
        if row.potential_bytes is not None:
            lines.append(tr('group_space', size_text(row.potential_bytes)))
        for line in lines:
            painter.drawText(QRect(text_rect.x(), text_rect.y(), text_rect.width(), 24),
                             Qt.AlignLeft | Qt.AlignVCenter,
                             option.fontMetrics.elidedText(line, Qt.ElideMiddle, text_rect.width()))
            text_rect.translate(0, 24)
        if option.state & QStyle.State_HasFocus:
            painter.setPen(palette.color(QPalette.Link))
            painter.setBrush(Qt.NoBrush)  # Focus outline must not cover the card contents.
            painter.drawRect(rect.adjusted(2, 2, -2, -2))
        painter.restore()


class GroupView(QListView):
    """One active batch of <=3, <=48 rendered thumbnails, <=24 group rows."""
    def __init__(self, thumbnails: Callable) -> None:
        super().__init__()
        self.groups_model = GroupModel(self)
        self.setModel(self.groups_model)
        self.setItemDelegate(GroupDelegate(self))
        self.setRowHidden(0, True)  # All groups is a separate action, never a photo card.
        self.setAccessibleName(tr('groups'))
        self.setAccessibleDescription(tr('keyboard_groups'))
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
        self.setGridSize(QSize(248, 224) if grid else QSize())
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
        return 224 if self.viewMode() == QListView.IconMode else 116

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


