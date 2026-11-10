"""Dashboard and scan presentation. Services supply every filesystem measurement."""
from __future__ import annotations

from pathlib import Path
import time
from typing import Callable

from PySide6.QtCore import QEvent, QSize, QTimer, Qt
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import (QGridLayout, QHBoxLayout, QLabel, QListWidget,
    QListWidgetItem, QPlainTextEdit, QProgressBar, QScrollArea, QVBoxLayout, QWidget)

from app.core.queries import DashboardSummary, MatchRow, ScanProgress
from app.ui.qt.components import (Card, CollapsibleSection, ContextToolbar, ElidedPathLabel, EmptyState,
                                  StatCard, StatusBadge, TechnicalDetails, ThemeSelector,
                                  button, path_label, text_label)
from app.ui.qt.localization import set_text, text_of, language_manager
from app.ui.qt.icons import IconLabel
from app.ui.qt.strings import tr, join_text, error_text
from app.ui.qt.formatting import date_text, number_text, size_text


class CandidateCard(Card):
    def __init__(self, row: MatchRow, review: Callable) -> None:
        super().__init__()
        self.row = row
        self.loaded = False
        photo = row.match.dup
        content = QHBoxLayout()
        self.content.addLayout(content)
        self.image = text_label(tr('preview_loading'), 'small')
        self.image.setFixedSize(128, 96)
        self.image.setAlignment(Qt.AlignCenter)
        content.addWidget(self.image)
        metadata = QVBoxLayout()
        content.addLayout(metadata, 1)
        name = path_label(Path(photo.path).name, 'section')
        set_text(name, photo.path, 'setToolTip')
        metadata.addWidget(name)
        metadata.addWidget(text_label(tr('candidate_metadata', photo.image_format or photo.ext,
            photo.width, photo.height), 'metadata'))
        metadata.addWidget(StatusBadge('classification_' + row.match.kind.value))
        button('review_candidate', lambda: review(row), metadata)
        self.error_details = TechnicalDetails()
        self.content.addWidget(self.error_details)

    def set_image(self, image: QImage | None, error: str) -> None:
        self.loaded = True
        self.error_details.set_detail(error if image is None or image.isNull() else '')
        if image is None or image.isNull():
            set_text(self.image, tr('thumbnail_unavailable'))
            set_text(self.image, tr('preview_error'), 'setToolTip')
        else:
            set_text(self.image, '')
            self.image.setPixmap(QPixmap.fromImage(image).scaled(self.image.size(),
                Qt.KeepAspectRatio, Qt.SmoothTransformation))
        set_text(self.image, tr('thumbnail_for', Path(self.row.match.dup.path).name), 'setAccessibleName')


class DashboardScreen(QWidget):
    def __init__(self, refresh: Callable, scan: Callable, review: Callable,
                 settings: Callable, theme_changed: Callable, thumbnails: Callable) -> None:
        super().__init__()
        self.thumbnails = thumbnails
        self.cards: list[CandidateCard] = []
        self.viewport = None
        self.requested = ()
        self.loading_enabled = True
        self.visible_timer = QTimer(self)
        self.visible_timer.setSingleShot(True)
        self.visible_timer.setInterval(50)
        self.visible_timer.timeout.connect(self.load_visible)
        self.toolbar = ContextToolbar()
        self.scan = button('first_scan', scan, self.toolbar.actions, variant='primary')
        self.review = button('review_duplicates', lambda: review(None), self.toolbar.actions)
        self.review.setEnabled(False)
        self.theme = ThemeSelector()
        self.theme.currentIndexChanged.connect(lambda: theme_changed(self.theme.currentData()))
        self.toolbar.actions.addWidget(self.theme)
        button('settings', settings, self.toolbar.actions)
        self.refresh = button('refresh', refresh, self.toolbar.actions)
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        self.stats = QGridLayout()
        layout.addLayout(self.stats)
        self.stat_cards = [StatCard(title, detail_key=detail) for title, detail in (
            ('indexed_photos', 'whole_index'), ('exact_candidates', 'last_session_candidates'),
            ('visual_links', 'last_session_links'), ('estimated_space', 'exact_space_detail'))]
        self.arrange_stats()
        self.empty = EmptyState('no_session', 'first_scan_detail')
        layout.addWidget(self.empty)
        self.recent = Card()
        layout.addWidget(self.recent)
        self.recent.content.addWidget(text_label(tr('recent_scan'), 'section'))
        self.session = text_label('', 'body')
        self.recent.content.addWidget(self.session)
        self.roots = path_label('', 'small')
        self.recent.content.addWidget(self.roots)
        self.warning = text_label('', 'metadata')
        layout.addWidget(self.warning)
        self.warning_details = TechnicalDetails()
        layout.addWidget(self.warning_details)
        self.estimate = text_label(tr('estimate'), 'small')
        layout.addWidget(self.estimate)
        self.candidates_panel = QWidget()
        self.candidate_layout = QVBoxLayout(self.candidates_panel)
        self.candidate_layout.setContentsMargins(0, 0, 0, 0)
        self.candidate_layout.addWidget(text_label(tr('recent_candidates'), 'section'))
        layout.addWidget(self.candidates_panel)
        self.no_matches = EmptyState('no_matches', 'no_matches_detail')
        layout.addWidget(self.no_matches)
        layout.addStretch()
        self.review_callback = review
        self.set_summary(DashboardSummary(0))

    def arrange_stats(self) -> None:
        columns = 4 if self.width() >= 900 else 2
        for i, card in enumerate(self.stat_cards):
            self.stats.addWidget(card, i // columns, i % columns)

    def set_summary(self, value: DashboardSummary) -> None:
        for card, measurement in zip(self.stat_cards, (number_text(value.indexed), number_text(value.exact),
                number_text(value.visual), size_text(value.potential_bytes))):
            set_text(card.value, measurement)
        has_session = bool(value.session_id)
        set_text(self.scan, tr('scan_photos' if has_session else 'first_scan'))
        set_text(self.scan, text_of(self.scan), 'setAccessibleName')
        self.empty.setVisible(not has_session)
        self.recent.setVisible(has_session)
        self.estimate.setVisible(has_session)
        set_text(self.session, tr('recent_scan_summary',
            date_text(value.started),
            tr('state_' + value.status), value.photo_count, value.exact, value.visual, value.errors)
            if has_session else '')
        set_text(self.roots, join_text(tr('root_status', p, tr('state_' + s)) for p, s in value.roots))
        set_text(self.warning, join_text(error_text(w) for w in value.warnings))
        self.warning_details.set_detail('\n'.join(w for w in value.warnings if ':' in w))
        self.warning.setVisible(bool(value.warnings))
        self.review.setEnabled(bool(value.candidates))
        self.no_matches.setVisible(has_session and value.status == 'complete' and not (value.exact or value.visual))
        self.candidates_panel.setVisible(bool(value.candidates))
        if self.requested:
            self.thumbnails(())  # Supersede only this view's batch before replacing cards.
        self.requested = ()
        for card in self.cards:
            self.candidate_layout.removeWidget(card)
            card.deleteLater()
        self.cards = [CandidateCard(row, self.review_callback) for row in value.candidates[:3]]
        for card in self.cards:
            self.candidate_layout.addWidget(card)
        self.loading_enabled = True
        self.visible_timer.start()

    def bind_scroll(self, scroll: QScrollArea) -> None:
        self.viewport = scroll.viewport()
        self.viewport.installEventFilter(self)
        for bar in (scroll.verticalScrollBar(), scroll.horizontalScrollBar()):
            bar.valueChanged.connect(lambda: self.visible_timer.start())

    def eventFilter(self, obj, event) -> bool:
        if event.type() in (QEvent.Resize, QEvent.Show):
            self.visible_timer.start()
        return super().eventFilter(obj, event)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self.arrange_stats()
        self.visible_timer.start()

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self.visible_timer.start()

    def hideEvent(self, event) -> None:
        self.pause_previews()
        super().hideEvent(event)

    def pause_previews(self) -> None:
        self.visible_timer.stop()
        if self.requested:
            self.thumbnails(())
        self.requested = ()

    def load_visible(self) -> None:
        if not self.isVisible() or self.viewport is None or not self.loading_enabled:
            return
        visible = tuple(card.row.match.dup for card in self.cards if not card.loaded
            and self.viewport.rect().intersects(card.rect().translated(card.mapTo(self.viewport, card.rect().topLeft()))))
        if visible != self.requested:
            self.requested = visible
            self.thumbnails(visible)

    def set_thumbnails(self, results: tuple) -> None:
        for photo, image, error in results:
            for card in self.cards:
                if card.row.match.dup == photo:
                    card.set_image(image, error)


class ScanScreen(QWidget):
    def __init__(self, add: Callable, remove: Callable, reorder: Callable, start: Callable,
                 cancel: Callable, reports: Callable, errors_page: Callable, review: Callable) -> None:
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        self.toolbar = ContextToolbar()
        self.start = button('start', start, self.toolbar.actions)
        self.cancel = button('cancel', cancel, self.toolbar.actions)
        self.cancel.setEnabled(False)
        self.review = button('review_results', review, self.toolbar.actions)
        self.review.setEnabled(False)
        button('reports', reports, self.toolbar.actions)
        sources = Card()
        layout.addWidget(sources)
        sources.content.addWidget(text_label(tr('scan_sources'), 'section'))
        sources.content.addWidget(text_label(tr('source_description'), 'metadata'))
        self.empty_sources = text_label(tr('empty_sources'), 'body')
        sources.content.addWidget(self.empty_sources)
        self.roots = QListWidget()
        self.roots.setProperty('embedded', True)
        set_text(self.roots, tr('source'), 'setAccessibleName')
        set_text(self.roots, tr('keyboard_sources'), 'setAccessibleDescription')
        self.roots.setMinimumHeight(100)
        self.roots.setMaximumHeight(230)
        sources.content.addWidget(self.roots)
        self.add = button('add', add, sources.content)
        self.remove_callback = remove
        self.remove_buttons = []
        self.source_labels: dict[str, QLabel] = {}
        self.advanced = CollapsibleSection('advanced_sources')
        layout.addWidget(self.advanced)
        self.advanced.body_layout.addWidget(text_label(tr('source_priority'), 'metadata'))
        priority = QHBoxLayout()
        self.advanced.body_layout.addLayout(priority)
        self.up = button('up', lambda: reorder(-1), priority)
        self.down = button('down', lambda: reorder(1), priority)
        self.progress_card = progress_card = Card()
        layout.addWidget(progress_card)
        self.status = text_label(tr('scan_ready'), 'section')
        progress_card.content.addWidget(self.status)
        self.progress = QProgressBar()
        set_text(self.progress, tr('scan_progress_name'), 'setAccessibleName')
        self.progress.setTextVisible(False)
        self.progress.setRange(0, 1)
        progress_card.content.addWidget(self.progress)
        self.elapsed = text_label('', 'metadata')
        progress_card.content.addWidget(self.elapsed)
        self.report = path_label('', 'small')
        progress_card.content.addWidget(self.report)
        self.error_section = CollapsibleSection('errors')
        layout.addWidget(self.error_section)
        self.error_summary = text_label(tr('no_scan_errors'), 'metadata')
        self.error_section.content.insertWidget(1, self.error_summary)
        self.errors = QPlainTextEdit()
        self.errors.setReadOnly(True)
        self.errors.setTabChangesFocus(True)
        set_text(self.errors, tr('technical_details'), 'setAccessibleName')
        self.errors.setMinimumHeight(100)
        self.errors.setMaximumHeight(200)
        self.error_section.body_layout.addWidget(self.errors)
        pages = QHBoxLayout()
        self.error_section.body_layout.addLayout(pages)
        self.error_previous = button('previous', lambda: errors_page(-1), pages)
        self.error_next = button('next', lambda: errors_page(1), pages)
        layout.addStretch()
        self.started = 0.0
        self.failure_detail = ''
        self.report_failure_detail = ''
        self.timer = QTimer(self)
        self.timer.setInterval(1000)
        self.timer.timeout.connect(self.tick)
        language_manager().changed.connect(self.retranslate_sources)

    def retranslate_sources(self) -> None:
        for i in range(self.roots.count()):
            item = self.roots.item(i)
            path = item.toolTip()
            message = text_of(self.source_labels[path])
            item.setData(Qt.AccessibleTextRole, tr('source_status', path, message))

    def set_sources(self, roots: list[str], states: dict[str, str]) -> None:
        selected = self.roots.currentRow()
        self.roots.clear()
        self.remove_buttons = []
        self.source_labels = {}
        self.empty_sources.setVisible(not roots)
        self.roots.setVisible(bool(roots))
        self.roots.setFixedHeight(min(230, max(100, len(roots) * 80)))
        for path in roots:
            item = QListWidgetItem(self.roots)
            row = QWidget()
            content = QHBoxLayout(row)
            content.addWidget(IconLabel('folder'))
            values = QVBoxLayout()
            content.addLayout(values, 1)
            values.addWidget(ElidedPathLabel(path))
            state_key = states.get(path, 'checking_source')
            status = text_label(tr(state_key if state_key in ('available', 'unavailable', 'checking_source')
                                   else 'state_' + state_key), 'small')
            values.addWidget(status)
            self.source_labels[path] = status
            remove = button('remove', lambda checked=False, target=item: self.remove_source(target), content)
            set_text(remove, tr('remove_source', path), 'setAccessibleName')
            self.remove_buttons.append(remove)
            item.setSizeHint(QSize(0, 76))
            item.setToolTip(path)
            item.setData(Qt.AccessibleTextRole, path + '\n' + status.text())
            self.roots.setItemWidget(item, row)
        if 0 <= selected < len(roots):
            self.roots.setCurrentRow(selected)

    def remove_source(self, item: QListWidgetItem) -> None:
        self.roots.setCurrentItem(item)
        self.remove_callback()

    def source_states(self, states: tuple) -> None:
        for path, state in states:
            if path in self.source_labels:
                key = state if state in ('available', 'unavailable') else 'state_' + state
                set_text(self.source_labels[path], tr(key))
                for i in range(self.roots.count()):
                    item = self.roots.item(i)
                    if item.toolTip() == path:
                        item.setData(Qt.AccessibleTextRole, path + '\n' + tr(key))

    def begin(self) -> None:
        self.show_activity()
        self.started = time.monotonic()
        set_text(self.status, tr('checking_sources'))
        set_text(self.errors, '', 'setPlainText')
        self.failure_detail = ''
        self.report_failure_detail = ''
        set_text(self.error_summary, tr('no_scan_errors'))
        self.error_section.set_expanded(False)
        set_text(self.report, '')
        self.review.setEnabled(False)
        self.progress.setRange(0, 0)
        self.timer.start()
        self.tick()

    def tick(self) -> None:
        set_text(self.elapsed, tr('elapsed', int(time.monotonic() - self.started)))

    def show_activity(self) -> None:
        # Keep progress/results above the source list on short windows, where
        # otherwise the phase and elapsed time would require scrolling.
        self.layout().removeWidget(self.progress_card)
        self.layout().insertWidget(0, self.progress_card)

    def update_progress(self, value: ScanProgress) -> None:
        set_text(self.status, tr('progress', tr('phase_' + value.phase), value.discovered,
            value.processed, value.skipped, value.failed))
        set_text(self.error_summary, tr('scan_error_count', value.failed) if value.failed else tr('no_scan_errors'))
        self.source_states(value.roots)

    def finish(self, value: DashboardSummary) -> None:
        self.timer.stop()
        self.progress.setRange(0, 1)
        self.progress.setValue(1 if value.status == 'complete' else 0)
        if not value.session_id:
            return
        self.show_activity()
        set_text(self.status, tr('scan_result_summary', tr('state_' + value.status),
            value.photo_count, value.exact_groups, value.visual, value.errors))
        set_text(self.elapsed, tr('elapsed', max(0, int(value.finished - value.started))) if value.finished else '')
        set_text(self.error_summary, tr('scan_error_count', value.errors) if value.errors else tr('no_scan_errors'))
        if value.status == 'failed':
            set_text(self.error_summary, tr('scan_failure_help'))
        self.review.setEnabled(value.status in ('complete', 'incomplete') and bool(value.exact or value.visual))

    def fail(self, detail: str) -> None:
        self.show_activity()
        self.failure_detail = detail
        self.timer.stop()
        self.progress.setRange(0, 1)
        self.progress.setValue(0)
        set_text(self.status, tr('scan_failed'))
        set_text(self.error_summary, tr('scan_failure_help'))
        set_text(self.errors, detail, 'setPlainText')
        self.review.setEnabled(False)
