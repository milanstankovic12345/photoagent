from __future__ import annotations

from PySide6 import QtSvg  # Load SVG runtime before icon-engine DLLs on Windows.
from PySide6.QtCore import QEvent, QRect, QSize, QTimer, Qt
from PySide6.QtGui import QIcon, QKeySequence, QPixmap, QShortcut
from PySide6.QtWidgets import (QCheckBox, QComboBox, QDialog, QGraphicsScene,
    QGraphicsView, QHBoxLayout, QLabel, QLineEdit, QPlainTextEdit, QPushButton,
    QVBoxLayout, QWidget, QFrame, QLayout, QLayoutItem, QSizePolicy, QStackedLayout)
from app.core.models import Approval, Kind
from app.core.models import Photo, Plan
from typing import Callable
from PySide6.QtGui import QImage
from app.ui.qt.localization import set_text, text_of, add_item, with_text
from app.ui.qt.strings import tr, join_text
from app.ui.qt.themes import SPACING
from app.ui.qt import resources_rc  # Register icons even when used without MainWindow.


def text_label(text: str, role: str = 'body') -> QLabel:
    label = with_text(QLabel(), text)
    label.setTextFormat(Qt.PlainText)
    label.setWordWrap(True)
    label.setProperty('role', role)
    return label


def path_label(text: str = '', role: str = 'body') -> QLabel:
    """Wrap long paths without letting their minimum width stretch the page."""
    label = text_label(text, role)
    policy = label.sizePolicy()
    policy.setHorizontalPolicy(QSizePolicy.Ignored)
    label.setSizePolicy(policy)
    label.setTextInteractionFlags(Qt.TextSelectableByMouse | Qt.TextSelectableByKeyboard)
    label.setFocusPolicy(Qt.ClickFocus)
    return label


class ElidedPathLabel(QLabel):
    """A single visible line with the complete path in tooltip/accessibility."""
    def __init__(self, value: str) -> None:
        super().__init__()
        self.value = value
        self.setTextFormat(Qt.PlainText)
        self.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        set_text(self, value, 'setToolTip')
        set_text(self, value, 'setAccessibleName')

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        set_text(self, self.fontMetrics().elidedText(self.value, Qt.ElideMiddle, self.width()))


def style_button(widget: QPushButton, variant: str = 'secondary') -> None:
    if variant not in ('primary', 'secondary', 'danger'):
        raise ValueError(variant)
    widget.setProperty('variant', variant)
    set_text(widget, text_of(widget), 'setAccessibleName')
    widget.setFocusPolicy(Qt.StrongFocus)


class ThemeSelector(QComboBox):
    """One theme control shared by Dashboard and Settings."""
    def __init__(self) -> None:
        super().__init__()
        set_text(self, tr('theme'), 'setAccessibleName')
        for theme in ('dark', 'light', 'system'):
            add_item(self, tr(theme), theme)


class PageHeader(QWidget):
    def __init__(self, title_key: str, subtitle_key: str | None = None) -> None:
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, SPACING[1])
        layout.setSpacing(SPACING[1])
        self.title = text_label(tr(title_key), 'heading')
        layout.addWidget(self.title)
        self.subtitle = text_label(tr(subtitle_key) if subtitle_key else '', 'metadata')
        self.subtitle.setVisible(bool(subtitle_key))
        layout.addWidget(self.subtitle)

    def set_page(self, title_key: str, subtitle_key: str) -> None:
        set_text(self.title, tr(title_key))
        set_text(self.subtitle, tr(subtitle_key))
        self.subtitle.show()


class WrappingLayout(QLayout):
    """Keep contextual actions reachable when the content column gets narrow."""
    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self.items: list[QLayoutItem] = []
        self.setContentsMargins(0, 0, 0, 0)
        self.setSpacing(SPACING[1])

    def addItem(self, item: QLayoutItem) -> None:
        self.items.append(item)

    def count(self) -> int:
        return len(self.items)

    def itemAt(self, index: int) -> QLayoutItem | None:
        return self.items[index] if 0 <= index < len(self.items) else None

    def takeAt(self, index: int) -> QLayoutItem | None:
        return self.items.pop(index) if 0 <= index < len(self.items) else None

    def expandingDirections(self) -> Qt.Orientations:
        return Qt.Orientations()

    def hasHeightForWidth(self) -> bool:
        return True

    def heightForWidth(self, width: int) -> int:
        return self.arrange(QRect(0, 0, width, 0), apply=False)

    def minimumSize(self) -> QSize:
        size = QSize()
        for item in self.items:
            size = size.expandedTo(item.minimumSize())
        return size

    def sizeHint(self) -> QSize:
        return self.minimumSize()

    def setGeometry(self, rect: QRect) -> None:
        super().setGeometry(rect)
        self.arrange(rect, apply=True)

    def arrange(self, rect: QRect, *, apply: bool) -> int:
        x, y, height = rect.x(), rect.y(), 0
        for item in self.items:
            size = item.sizeHint()
            if x > rect.x() and x + size.width() > rect.x() + rect.width():
                x = rect.x()
                y += height + self.spacing()
                height = 0
            if apply:
                item.setGeometry(QRect(x, y, size.width(), size.height()))
            x += size.width() + self.spacing()
            height = max(height, size.height())
        return y + height - rect.y()


class ContextToolbar(QWidget):
    def __init__(self) -> None:
        super().__init__()
        set_text(self, tr('page_actions'), 'setAccessibleName')
        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Maximum)
        self.actions = WrappingLayout(self)


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
        set_text(self, tr(key))  # Meaning is always present as text, independent of color.
        set_text(self, tr(key), 'setAccessibleName')
        self.setProperty('role', 'badge')
        self.setProperty('tone', tone)


class CollapsibleSection(Card):
    def __init__(self, title_key: str, expanded: bool = False) -> None:
        super().__init__()
        self.toggle = with_text(QPushButton(), tr(title_key))
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
        set_text(self.toggle, tr('section_expanded' if expanded else 'section_collapsed'), 'setAccessibleDescription')


class TechnicalDetails(CollapsibleSection):
    """Raw diagnostics are selectable, plain text and hidden until requested."""
    def __init__(self) -> None:
        super().__init__('technical_details')
        self.text = QPlainTextEdit()
        self.text.setReadOnly(True)
        self.text.setTabChangesFocus(True)
        set_text(self.text, tr('technical_details'), 'setAccessibleName')
        self.text.setMaximumHeight(160)
        self.body_layout.addWidget(self.text)
        self.set_detail('')

    def set_detail(self, detail: str) -> None:
        set_text(self.text, detail, 'setPlainText')
        self.set_expanded(False)
        self.setVisible(bool(detail))


def button(key: str, callback: Callable, layout: QLayout, *, variant: str | None = None) -> QPushButton:
    widget = with_text(QPushButton(), tr(key))
    variant = variant or ('danger' if key in ('selected_move', 'bulk_move', 'approve')
                          else 'primary' if key in ('start', 'save', 'compare') else 'secondary')
    style_button(widget, variant)
    if key in ('selected_move', 'bulk_move', 'restore'):
        widget.setProperty('operation', True)
    if key in ('selected_move', 'bulk_move', 'move_copy', 'approve'):
        set_text(widget, tr('quarantine_description_action'), 'setAccessibleDescription')
    elif key in ('restore', 'restore_operation'):
        set_text(widget, tr('restore_description_action'), 'setAccessibleDescription')
    widget.clicked.connect(callback)
    layout.addWidget(widget)
    return widget


class PhotoView(Card):
    def __init__(self) -> None:
        super().__init__()
        layout = self.content
        layout.setContentsMargins(12, 12, 12, 12)
        self.metadata = path_label(tr('select_pair'), 'metadata')
        layout.addWidget(self.metadata)
        self.metadata.setMaximumHeight(52)
        self.scene = QGraphicsScene(self)
        self.view = QGraphicsView(self.scene)
        self.view.setDragMode(QGraphicsView.ScrollHandDrag)
        self.view.setFocusPolicy(Qt.StrongFocus)
        set_text(self.view, tr('compare'), 'setAccessibleName')
        self.view.setMinimumSize(120, 120)
        self.view.viewport().installEventFilter(self)
        self.fitted = True
        self.enlarged = None
        self.preview = QStackedLayout()
        self.placeholder = text_label(tr('select_pair'), 'metadata')
        self.placeholder.setAlignment(Qt.AlignCenter)
        self.placeholder.setMinimumHeight(160)
        self.placeholder.setMaximumHeight(160)
        self.preview.addWidget(self.placeholder)
        self.preview.addWidget(self.view)
        layout.addLayout(self.preview, 1)
        controls_host = ContextToolbar()
        controls = controls_host.actions
        layout.addWidget(controls_host)
        self.preview_buttons = []
        for key, callback, shortcut in (('zoom_in', lambda: self.zoom(1.25), '+'),
                                        ('zoom_out', lambda: self.zoom(.8), '-'), ('fit', self.fit, 'F')):
            control = button(key, callback, controls)
            set_text(control, tr(key), 'setToolTip')
            set_text(control, '+' if key == 'zoom_in' else '−' if key == 'zoom_out' else tr('fit_short'))
            self.preview_buttons.append(control)
            binding = QShortcut(QKeySequence(shortcut), self)
            binding.setContext(Qt.WidgetWithChildrenShortcut)
            binding.activated.connect(callback)
        self.zoom_label = with_text(QLabel(), '100%')
        self.zoom_label.setProperty('role', 'small')
        controls.addWidget(self.zoom_label)
        self.enlarge = button('enlarge_preview', self.show_enlarged, controls)
        set_text(self.enlarge, tr('enlarge_preview'), 'setToolTip')
        self.keep_photo = button('keep_photo', lambda: None, layout)
        self.keep_photo.setCheckable(True)
        self.keep_photo.setProperty('choice', True)
        set_text(self.keep_photo, tr('keep_description'), 'setAccessibleDescription')
        self.details = CollapsibleSection('photo_details')
        self.details.content.setContentsMargins(8, 8, 8, 8)
        self.full_metadata = path_label('', 'small')
        self.full_metadata.setFocusPolicy(Qt.StrongFocus)
        self.details.body_layout.addWidget(self.full_metadata)
        self.details.body_layout.addWidget(text_label(tr('preview_note'), 'small'))
        self.details.body_layout.addWidget(text_label(tr('heuristic'), 'small'))
        self.details.body_layout.addWidget(text_label(tr('xmp_possible'), 'small'))
        self.error_details = TechnicalDetails()
        self.details.body_layout.addWidget(self.error_details)
        layout.addWidget(self.details)
        self.reset()

    def show_state(self, key: str, *args: str) -> None:
        if self.enlarged:
            self.enlarged.close()
        self.scene.clear()
        self.state = key
        message = tr(key, *args)
        set_text(self.placeholder, message, 'setToolTip')
        set_text(self.placeholder, message)
        set_text(self.placeholder, message, 'setAccessibleName')
        self.preview.setCurrentWidget(self.placeholder)
        set_text(self.zoom_label, '—')
        for control in self.preview_buttons:
            control.setEnabled(False)
        self.enlarge.setEnabled(False)

    def reset(self) -> None:
        set_text(self.metadata, tr('select_pair'))
        self.keep_photo.setChecked(False)
        set_text(self.keep_photo, tr('keep_photo'))
        set_text(self.keep_photo, tr('keep_photo'), 'setAccessibleName')
        set_text(self.full_metadata, '')
        self.error_details.set_detail('')
        self.details.set_expanded(False)
        self.show_state('select_pair')

    def set_photo(self, photo: Photo) -> None:
        self.error_details.set_detail('')
        self.show_state('preview_loading')
        self.photo = photo
        self.update_summary()
        set_text(self.metadata, photo.path, 'setToolTip')
        set_text(self.keep_photo, tr('keep_named_photo', photo.path), 'setAccessibleName')
        set_text(self.full_metadata, tr('metadata', photo.path, photo.image_format or photo.ext,
            photo.width, photo.height, photo.size, photo.sha256, tr('yes' if photo.is_raw else 'no')))
        self.details.set_expanded(False)

    def update_summary(self) -> None:
        from pathlib import Path
        from app.ui.qt.dashboard_scan import size_text
        photo = self.photo
        name = self.metadata.fontMetrics().elidedText(Path(photo.path).name, Qt.ElideMiddle,
                                                     max(80, self.metadata.width()))
        set_text(self.metadata, tr('photo_summary', name, photo.image_format or photo.ext,
                                photo.width, photo.height, size_text(photo.size)))

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        if hasattr(self, 'photo') and self.state != 'select_pair':
            self.update_summary()

    def set_image(self, image: QImage | None, error: str) -> None:
        self.scene.clear()
        self.error_details.set_detail(error if image is None or image.isNull() else '')
        if image is None or image.isNull():
            self.show_state('preview_error')
        else:
            self.state = 'preview_ready'
            self.scene.addPixmap(QPixmap.fromImage(image))
            self.preview.setCurrentWidget(self.view)
            self.enlarge.setEnabled(True)
            for control in self.preview_buttons:
                control.setEnabled(True)
        self.scene.setSceneRect(self.scene.itemsBoundingRect())
        self.fit()

    def fit(self) -> None:
        self.fitted = True
        if not self.scene.items():
            return
        self.view.fitInView(self.scene.sceneRect(), Qt.KeepAspectRatio)
        set_text(self.zoom_label, f'{self.view.transform().m11() * 100:.0f}%')

    def zoom(self, factor: float) -> None:
        if self.state != 'preview_ready':
            return
        scale = self.view.transform().m11() * factor
        if .01 <= scale <= 32:
            self.fitted = False
            self.view.scale(factor, factor)
            set_text(self.zoom_label, f'{scale * 100:.0f}%')

    def eventFilter(self, watched, event) -> bool:
        if event.type() == QEvent.Resize and self.fitted:
            QTimer.singleShot(0, self.fit)
        return super().eventFilter(watched, event)

    def show_enlarged(self) -> None:
        if self.state != 'preview_ready':
            return
        if self.enlarged:
            self.enlarged.raise_()
            self.enlarged.activateWindow()
            return
        dialog = QDialog(self)
        dialog.setAttribute(Qt.WA_DeleteOnClose)
        set_text(dialog, tr('enlarge_preview'), 'setWindowTitle')
        dialog.resize(1000, 760)
        layout = QVBoxLayout(dialog)
        scene = QGraphicsScene(dialog)
        scene.addPixmap(self.scene.items()[0].pixmap())
        view = QGraphicsView(scene)
        view.setDragMode(QGraphicsView.ScrollHandDrag)
        set_text(view, text_of(self.view, 'setAccessibleName'), 'setAccessibleName')
        layout.addWidget(view)
        layout.addWidget(text_label(tr('preview_note'), 'small'))
        actions_host = ContextToolbar()
        actions = actions_host.actions
        layout.addWidget(actions_host)
        button('zoom_in', lambda: view.scale(1.25, 1.25), actions)
        button('zoom_out', lambda: view.scale(.8, .8), actions)
        button('fit', lambda: view.fitInView(scene.itemsBoundingRect(), Qt.KeepAspectRatio), actions)
        button('close_preview', dialog.reject, actions)
        def finished() -> None:
            self.enlarged = None
            QTimer.singleShot(0, self.restore_enlarge_focus)
        dialog.finished.connect(finished)
        self.enlarged = dialog
        dialog.show()
        dialog.activateWindow()
        view.setFocus(Qt.OtherFocusReason)
        view.fitInView(scene.itemsBoundingRect(), Qt.KeepAspectRatio)

    def restore_enlarge_focus(self) -> None:
        if self.enlarge.isVisible() and self.enlarge.isEnabled():
            self.window().activateWindow()
            self.enlarge.setFocus(Qt.OtherFocusReason)


class PlanDialog(QDialog):
    """No Approval exists until the explicit button validates every extra consent."""
    def __init__(self, plan: Plan, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.plan = plan
        self.approval = None
        set_text(self, tr('plan'), 'setWindowTitle')
        self.resize(900, 620)
        screen = self.screen().availableGeometry()
        self.resize(min(900, int(screen.width() * .94)), min(620, int(screen.height() * .94)))
        layout = QVBoxLayout(self)
        layout.addWidget(text_label(tr('plan_summary', len(plan.moves)), 'section'))
        layout.addWidget(text_label(tr('plan_reversible'), 'metadata'))
        summary = QPlainTextEdit()
        summary.setReadOnly(True)
        summary.setTabChangesFocus(True)
        set_text(summary, tr('plan_paths'), 'setAccessibleName')
        descriptions = []
        for move in plan.moves:
            descriptions.append(tr('move_summary', move.source, move.destination,
                move.keeper.path if move.keeper else tr('restore_original')))
        set_text(summary, join_text(descriptions, '\n\n'), 'setPlainText')
        layout.addWidget(summary, 1)
        warnings = []
        text = QPlainTextEdit()
        text.setReadOnly(True)
        text.setTabChangesFocus(True)
        set_text(text, tr('technical_details'), 'setAccessibleName')
        lines = [tr('plan_count', plan.id, len(plan.moves))]
        for move in plan.moves:
            if move.kind != Kind.EXACT:
                warnings.append(tr('visual_warning'))
            if move.keeper and move.keeper.root != move.root:
                warnings.append(tr('cross_roots'))
            if move.raw or move.keeper and move.keeper.is_raw:
                warnings.append(tr('raw_warning'))
            if move.xmp:
                warnings.append(tr('xmp_warning'))
                lines.extend(move.xmp)
            if move.legacy:
                warnings.append(tr('legacy_warning'))
            lines.extend([tr('heuristic'), tr('plan_move', move.action, move.kind.value, move.source,
                move.destination, move.expected.sha256, move.expected.identity)])
            if move.keeper:
                lines.append(tr('plan_keeper', move.keeper.path, move.keeper.sha256))
            lines.append('')
        set_text(text, join_text(lines), 'setPlainText')
        self.warnings = text_label(join_text(dict.fromkeys(warnings)), 'metadata')
        set_text(self.warnings, tr('plan_warnings'), 'setAccessibleName')
        layout.addWidget(self.warnings)
        self.details = CollapsibleSection('technical_details')
        self.details.body_layout.addWidget(text)
        layout.addWidget(self.details)
        self.raw = QLineEdit()
        set_text(self.raw, tr('raw_prompt'), 'setPlaceholderText')
        set_text(self.raw, tr('raw_prompt'), 'setAccessibleName')
        self.raw.setVisible(any(m.raw for m in plan.moves))
        layout.addWidget(self.raw)
        self.legacy = with_text(QCheckBox(), tr('legacy_confirm'))
        self.legacy.setVisible(any(m.legacy for m in plan.moves))
        layout.addWidget(self.legacy)
        # A plain row keeps both actions in the Tab chain. QDialogButtonBox can
        # reset a non-auto-default accept button's focus policy during relayout.
        buttons = QHBoxLayout()
        buttons.addStretch()
        self.confirm = with_text(QPushButton(), tr('approve'))
        buttons.addWidget(self.confirm)
        style_button(self.confirm, 'danger')
        self.confirm.setAutoDefault(False)
        self.cancel = cancel = with_text(QPushButton(), tr('cancel'))
        buttons.addWidget(cancel)
        style_button(cancel)
        cancel.setDefault(True)
        cancel.setFocus()
        cancel.clicked.connect(self.reject)
        self.confirm.clicked.connect(self.approve)
        self.raw.textChanged.connect(self.validate)
        self.legacy.toggled.connect(self.validate)
        layout.addLayout(buttons)
        chain = [summary, self.details.toggle, text, self.raw, self.legacy, self.confirm, cancel]
        for first, second in zip(chain, chain[1:]):
            QWidget.setTabOrder(first, second)
        self.validate()

    def showEvent(self, event) -> None:
        super().showEvent(event)
        # Initial focus assignment in __init__ can be replaced by Qt on open().
        # Queue it after the modal window is shown; Cancel remains the safe entry.
        QTimer.singleShot(0, self.focus_cancel)

    def focus_cancel(self) -> None:
        if self.isVisible():
            self.activateWindow()
            self.cancel.setFocus(Qt.OtherFocusReason)

    def keyPressEvent(self, event) -> None:
        # Enter is never consent, even when the danger button has focus.
        if event.key() in (Qt.Key_Return, Qt.Key_Enter):
            event.accept()
            return
        super().keyPressEvent(event)

    def validate(self) -> None:
        self.confirm.setEnabled((not any(m.raw for m in self.plan.moves) or self.raw.text() == 'RAW')
            and (not any(m.legacy for m in self.plan.moves) or self.legacy.isChecked()))

    def approve(self) -> None:
        self.validate()
        if self.confirm.isEnabled() and self.plan.moves:
            self.approval = Approval(self.plan, raw=any(m.raw for m in self.plan.moves),
                                     legacy=any(m.legacy for m in self.plan.moves))
            self.accept()
