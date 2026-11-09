from __future__ import annotations

from PySide6 import QtSvg  # Load SVG runtime before icon-engine DLLs on Windows.
from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon, QKeySequence, QPixmap, QShortcut
from PySide6.QtWidgets import (QCheckBox, QDialog, QDialogButtonBox, QGraphicsScene,
    QGraphicsView, QHBoxLayout, QLabel, QLineEdit, QPlainTextEdit, QPushButton,
    QVBoxLayout, QWidget, QFrame, QLayout, QStackedLayout)
from app.core.models import Approval, Kind
from app.core.models import Photo, Plan
from typing import Callable
from PySide6.QtGui import QImage
from app.ui.qt.strings import tr
from app.ui.qt.themes import SPACING
from app.ui.qt import resources_rc  # Register icons even when used without MainWindow.


def text_label(text: str, role: str = 'body') -> QLabel:
    label = QLabel(text)
    label.setTextFormat(Qt.PlainText)
    label.setWordWrap(True)
    label.setProperty('role', role)
    return label


def style_button(widget: QPushButton, variant: str = 'secondary') -> None:
    if variant not in ('primary', 'secondary', 'danger'):
        raise ValueError(variant)
    widget.setProperty('variant', variant)
    widget.setAccessibleName(widget.text())
    widget.setFocusPolicy(Qt.StrongFocus)


class PageHeader(QWidget):
    def __init__(self, title_key: str, subtitle_key: str | None = None) -> None:
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, SPACING[1])
        layout.setSpacing(SPACING[1])
        self.title = text_label(tr(title_key), 'heading')
        layout.addWidget(self.title)
        if subtitle_key:
            layout.addWidget(text_label(tr(subtitle_key), 'metadata'))


class Card(QFrame):
    def __init__(self) -> None:
        super().__init__()
        self.setProperty('role', 'card')
        self.content = QVBoxLayout(self)
        self.content.setContentsMargins(*([SPACING[3]] * 4))
        self.content.setSpacing(SPACING[2])


class StatCard(Card):
    """Values are supplied by callers; an absent measurement stays absent."""
    def __init__(self, title_key: str, value: str = '—', detail_key: str | None = None) -> None:
        super().__init__()
        self.content.addWidget(text_label(tr(title_key), 'metadata'))
        self.value = text_label(value, 'stat')
        self.content.addWidget(self.value)
        if detail_key:
            self.content.addWidget(text_label(tr(detail_key), 'small'))


class EmptyState(Card):
    def __init__(self, title_key: str = 'empty', detail_key: str | None = None) -> None:
        super().__init__()
        self.content.addWidget(text_label(tr(title_key), 'section'))
        if detail_key:
            self.content.addWidget(text_label(tr(detail_key), 'metadata'))


class StatusBadge(QLabel):
    def __init__(self, key: str, tone: str = 'neutral') -> None:
        super().__init__()
        if tone not in ('neutral', 'success', 'warning', 'danger'):
            raise ValueError(tone)
        self.setTextFormat(Qt.PlainText)
        self.setText(tr(key))  # Meaning is always present as text, independent of color.
        self.setAccessibleName(tr(key))
        self.setProperty('role', 'badge')
        self.setProperty('tone', tone)


class CollapsibleSection(Card):
    def __init__(self, title_key: str, expanded: bool = False) -> None:
        super().__init__()
        self.toggle = QPushButton(tr(title_key))
        style_button(self.toggle)
        self.toggle.setCheckable(True)
        self.toggle.setChecked(expanded)
        self.content.addWidget(self.toggle)
        self.body = QWidget()
        self.body_layout = QVBoxLayout(self.body)
        self.body_layout.setContentsMargins(0, 0, 0, 0)
        self.body_layout.setSpacing(SPACING[1])
        self.content.addWidget(self.body)
        self.toggle.toggled.connect(self.set_expanded)
        self.set_expanded(expanded)

    def set_expanded(self, expanded: bool) -> None:
        self.toggle.setChecked(expanded)
        self.body.setVisible(expanded)
        self.toggle.setIcon(QIcon(':/photoagent/' + ('collapse.svg' if expanded else 'expand.svg')))
        self.toggle.setAccessibleDescription(tr('section_expanded' if expanded else 'section_collapsed'))


def button(key: str, callback: Callable, layout: QLayout, *, variant: str | None = None) -> QPushButton:
    widget = QPushButton(tr(key))
    variant = variant or ('danger' if key in ('selected_move', 'bulk_move', 'approve')
                          else 'primary' if key in ('start', 'save', 'compare') else 'secondary')
    style_button(widget, variant)
    if key in ('selected_move', 'bulk_move', 'restore'):
        widget.setProperty('operation', True)
    widget.clicked.connect(callback)
    layout.addWidget(widget)
    return widget


class PhotoView(Card):
    def __init__(self) -> None:
        super().__init__()
        layout = self.content
        self.metadata = text_label(tr('select_pair'), 'metadata')
        self.metadata.setTextInteractionFlags(Qt.TextSelectableByMouse)
        layout.addWidget(self.metadata)
        self.scene = QGraphicsScene(self)
        self.view = QGraphicsView(self.scene)
        self.view.setDragMode(QGraphicsView.ScrollHandDrag)
        self.view.setFocusPolicy(Qt.StrongFocus)
        self.view.setAccessibleName(tr('compare'))
        self.preview = QStackedLayout()
        self.placeholder = text_label(tr('select_pair'), 'metadata')
        self.placeholder.setAlignment(Qt.AlignCenter)
        self.placeholder.setMinimumHeight(160)
        self.preview.addWidget(self.placeholder)
        self.preview.addWidget(self.view)
        layout.addLayout(self.preview, 1)
        controls = QHBoxLayout()
        layout.addLayout(controls)
        self.preview_buttons = []
        for key, callback, shortcut in (('zoom_in', lambda: self.zoom(1.25), '+'),
                                        ('zoom_out', lambda: self.zoom(.8), '-'), ('fit', self.fit, 'F')):
            self.preview_buttons.append(button(key, callback, controls))
            binding = QShortcut(QKeySequence(shortcut), self)
            binding.setContext(Qt.WidgetWithChildrenShortcut)
            binding.activated.connect(callback)
        self.zoom_label = QLabel('100%')
        self.zoom_label.setProperty('role', 'small')
        controls.addWidget(self.zoom_label)
        self.reset()

    def show_state(self, key: str, *args: str) -> None:
        self.scene.clear()
        self.state = key
        self.placeholder.setText(tr(key, *args))
        self.placeholder.setAccessibleName(self.placeholder.text())
        self.preview.setCurrentWidget(self.placeholder)
        self.zoom_label.setText('—')
        for control in self.preview_buttons:
            control.setEnabled(False)

    def reset(self) -> None:
        self.metadata.setText(tr('select_pair'))
        self.show_state('select_pair')

    def set_photo(self, photo: Photo) -> None:
        self.show_state('preview_loading')
        self.metadata.setText(tr('metadata', photo.path, photo.image_format or photo.ext,
            photo.width, photo.height, photo.size, photo.sha256, tr('yes' if photo.is_raw else 'no')))

    def set_image(self, image: QImage | None, error: str) -> None:
        self.scene.clear()
        if image is None or image.isNull():
            self.show_state('preview_error', error or tr('unavailable'))
        else:
            self.state = 'preview_ready'
            self.scene.addPixmap(QPixmap.fromImage(image))
            self.preview.setCurrentWidget(self.view)
            for control in self.preview_buttons:
                control.setEnabled(True)
        self.scene.setSceneRect(self.scene.itemsBoundingRect())
        self.fit()

    def fit(self) -> None:
        if not self.scene.items():
            return
        self.view.fitInView(self.scene.sceneRect(), Qt.KeepAspectRatio)
        self.zoom_label.setText(f'{self.view.transform().m11() * 100:.0f}%')

    def zoom(self, factor: float) -> None:
        if self.state != 'preview_ready':
            return
        scale = self.view.transform().m11() * factor
        if .01 <= scale <= 32:
            self.view.scale(factor, factor)
            self.zoom_label.setText(f'{scale * 100:.0f}%')


class PlanDialog(QDialog):
    """No Approval exists until the explicit button validates every extra consent."""
    def __init__(self, plan: Plan, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.plan = plan
        self.approval = None
        self.setWindowTitle(tr('plan'))
        self.resize(900, 620)
        layout = QVBoxLayout(self)
        text = QPlainTextEdit()
        text.setReadOnly(True)
        lines = [tr('plan_count', plan.id, len(plan.moves))]
        for move in plan.moves:
            if move.kind != Kind.EXACT:
                lines.append(tr('visual_warning'))
            if move.keeper and move.keeper.root != move.root:
                lines.append(tr('cross_roots'))
            if move.raw or move.keeper and move.keeper.is_raw:
                lines.append(tr('raw_warning'))
            if move.xmp:
                lines.extend([tr('xmp_warning'), *move.xmp])
            if move.legacy:
                lines.append(tr('legacy_warning'))
            lines.extend([tr('heuristic'), tr('plan_move', move.action, move.kind.value, move.source,
                move.destination, move.expected.sha256, move.expected.identity)])
            if move.keeper:
                lines.append(tr('plan_keeper', move.keeper.path, move.keeper.sha256))
            lines.append('')
        text.setPlainText('\n'.join(lines))
        layout.addWidget(text)
        self.raw = QLineEdit()
        self.raw.setPlaceholderText(tr('raw_prompt'))
        self.raw.setAccessibleName(tr('raw_prompt'))
        self.raw.setVisible(any(m.raw for m in plan.moves))
        layout.addWidget(self.raw)
        self.legacy = QCheckBox(tr('legacy_confirm'))
        self.legacy.setVisible(any(m.legacy for m in plan.moves))
        layout.addWidget(self.legacy)
        buttons = QDialogButtonBox()
        self.confirm = buttons.addButton(tr('approve'), QDialogButtonBox.AcceptRole)
        style_button(self.confirm, 'danger')
        self.confirm.setAutoDefault(False)
        cancel = buttons.addButton(tr('cancel'), QDialogButtonBox.RejectRole)
        style_button(cancel)
        cancel.setDefault(True)
        cancel.setFocus()
        buttons.rejected.connect(self.reject)
        self.confirm.clicked.connect(self.approve)
        self.raw.textChanged.connect(self.validate)
        self.legacy.toggled.connect(self.validate)
        layout.addWidget(buttons)
        self.validate()

    def validate(self) -> None:
        self.confirm.setEnabled((not any(m.raw for m in self.plan.moves) or self.raw.text() == 'RAW')
            and (not any(m.legacy for m in self.plan.moves) or self.legacy.isChecked()))

    def approve(self) -> None:
        self.validate()
        if self.confirm.isEnabled() and self.plan.moves:
            self.approval = Approval(self.plan, raw=any(m.raw for m in self.plan.moves),
                                     legacy=any(m.legacy for m in self.plan.moves))
            self.accept()
