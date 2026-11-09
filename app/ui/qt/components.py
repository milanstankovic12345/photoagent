from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence, QPixmap, QShortcut
from PySide6.QtWidgets import (QCheckBox, QDialog, QDialogButtonBox, QGraphicsScene,
    QGraphicsView, QHBoxLayout, QLabel, QLineEdit, QPlainTextEdit, QPushButton, QVBoxLayout, QWidget, QApplication)
from app.core.models import Approval, Kind
from app.core.models import Photo, Plan
from typing import Callable
from PySide6.QtGui import QImage
from app.ui.qt.strings import tr


def button(key: str, callback: Callable, layout) -> QPushButton:
    widget = QPushButton(tr(key))
    if key in ('selected_move', 'bulk_move', 'restore'):
        widget.setProperty('operation', True)
    widget.clicked.connect(callback)
    layout.addWidget(widget)
    return widget


class PhotoView(QWidget):
    def __init__(self) -> None:
        super().__init__()
        layout = QVBoxLayout(self)
        self.metadata = QLabel(tr('select_pair'))
        self.metadata.setWordWrap(True)
        self.metadata.setTextInteractionFlags(Qt.TextSelectableByMouse)
        layout.addWidget(self.metadata)
        self.scene = QGraphicsScene(self)
        self.view = QGraphicsView(self.scene)
        self.view.setDragMode(QGraphicsView.ScrollHandDrag)
        self.view.setFocusPolicy(Qt.StrongFocus)
        self.view.setAccessibleName(tr('compare'))
        layout.addWidget(self.view, 1)
        controls = QHBoxLayout()
        layout.addLayout(controls)
        for key, callback, shortcut in (('zoom_in', lambda: self.zoom(1.25), '+'),
                                        ('zoom_out', lambda: self.zoom(.8), '-'), ('fit', self.fit, 'F')):
            button(key, callback, controls)
            binding = QShortcut(QKeySequence(shortcut), self)
            binding.setContext(Qt.WidgetWithChildrenShortcut)
            binding.activated.connect(callback)
        self.zoom_label = QLabel('100%')
        controls.addWidget(self.zoom_label)

    def set_photo(self, photo: Photo) -> None:
        self.scene.clear()
        self.metadata.setText(tr('metadata', photo.path, photo.image_format or photo.ext,
            photo.width, photo.height, photo.size, photo.sha256, tr('yes' if photo.is_raw else 'no')))

    def set_image(self, image: QImage | None, error: str) -> None:
        self.scene.clear()
        if image is None:
            text = self.scene.addText(tr('preview_error', error))
            text.setDefaultTextColor(QApplication.palette().windowText().color())
        else:
            self.scene.addPixmap(QPixmap.fromImage(image))
        self.scene.setSceneRect(self.scene.itemsBoundingRect())
        self.fit()

    def fit(self) -> None:
        if not self.scene.items():
            return
        self.view.fitInView(self.scene.sceneRect(), Qt.KeepAspectRatio)
        self.zoom_label.setText(f'{self.view.transform().m11() * 100:.0f}%')

    def zoom(self, factor: float) -> None:
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
        self.confirm.setAutoDefault(False)
        cancel = buttons.addButton(tr('cancel'), QDialogButtonBox.RejectRole)
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
