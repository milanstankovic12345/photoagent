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
                                  button, path_label, text_label, style_button)
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
        self.scan_active = False
        self.summary = DashboardSummary(0)
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
        self.stats.setSpacing(12)
        self.stat_cards = [StatCard(title, detail_key=detail) for title, detail in (
            ('indexed_photos', 'whole_index'), ('exact_candidates', 'last_session_candidates'),
            ('visual_links', 'last_session_links'), ('exact_groups_stat', 'last_scan_groups'))]
        self.arrange_stats()
        self.activity = text_label(tr('scan_next_running'), 'section')
        self.activity.hide()
        layout.addWidget(self.activity)
        self.empty = EmptyState('no_session', 'first_scan_detail')
        layout.addWidget(self.empty)
        self.recent = Card()
        layout.addWidget(self.recent)
        self.recent.content.addWidget(text_label(tr('recent_scan'), 'section'))
        self.session = text_label('', 'body')
        self.recent.content.addWidget(self.session)
        self.next_step = text_label('', 'metadata')
        self.recent.content.addWidget(self.next_step)
        self.scan_details = CollapsibleSection('scan_details')
        self.recent.content.addWidget(self.scan_details)
        self.roots = path_label('', 'small')
        self.scan_details.body_layout.addWidget(self.roots)
        layout.addLayout(self.stats)
        self.warning = text_label('', 'metadata')
        layout.addWidget(self.warning)
        self.warning_details = TechnicalDetails()
        layout.addWidget(self.warning_details)
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
        self.summary = value
        for card, measurement in zip(self.stat_cards, (number_text(value.indexed), number_text(value.exact),
                number_text(value.visual), number_text(value.exact_groups))):
            set_text(card.value, measurement)
        has_session = bool(value.session_id)
        if not has_session:
            for card in self.stat_cards[1:]:
                set_text(card.value, '—')
        self.update_actions()
        self.empty.setVisible(not has_session)
        self.recent.setVisible(has_session)
        set_text(self.session, tr('recent_scan_summary',
            date_text(value.started),
            tr('state_' + value.status), value.photo_count, value.exact, value.visual, value.errors)
            if has_session else '')
        set_text(self.roots, join_text(tr('root_status', p, tr('state_' + s)) for p, s in value.roots))
        set_text(self.warning, join_text(error_text(w) for w in value.warnings))
        self.warning_details.set_detail('\n'.join(w for w in value.warnings if ':' in w))
        self.warning.setVisible(bool(value.warnings))
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

    def can_review(self) -> bool:
        return (not self.scan_active and self.summary.status in ('complete', 'incomplete')
                and bool(self.summary.exact or self.summary.visual))

    def set_scan_active(self, active: bool) -> None:
        self.scan_active = active
        self.update_actions()

    def update_actions(self) -> None:
        review = self.can_review()
        self.activity.setVisible(self.scan_active)
        set_text(self.next_step, tr('scan_next_running' if self.scan_active else
            'scan_next_partial' if self.summary.status == 'incomplete' else
            'scan_next_cancelled' if self.summary.status == 'cancelled' else
            'scan_next_review' if review else
            'scan_next_clear' if self.summary.status == 'complete' else 'scan_next_retry'))
        self.review.setEnabled(review)
        style_button(self.review, 'primary' if review else 'secondary')
        style_button(self.scan, 'secondary' if review else 'primary')
        for control in (self.scan, self.review):
            control.style().unpolish(control)
            control.style().polish(control)
        set_text(self.scan, tr('scan_photos' if self.summary.session_id else 'first_scan'))
        set_text(self.scan, text_of(self.scan), 'setAccessibleName')

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
        self.add = button('add_folder', add, self.toolbar.actions)
        self.start = button('start', start, self.toolbar.actions)
        self.cancel = button('cancel', cancel, self.toolbar.actions)
        self.cancel.setEnabled(False)
        self.review = button('review_results', review, self.toolbar.actions)
        self.review.setEnabled(False)
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
        self.source_warning = text_label('', 'metadata')
        self.source_warning.hide()
        self.remove_callback = remove
        self.remove_buttons = []
        self.source_labels: dict[str, QLabel] = {}
        self.advanced = CollapsibleSection('advanced_sources')
        self.advanced.body_layout.addWidget(text_label(tr('source_priority'), 'metadata'))
        priority = QHBoxLayout()
        self.advanced.body_layout.addLayout(priority)
        self.up = button('up', lambda: reorder(-1), priority)
        self.down = button('down', lambda: reorder(1), priority)
        self.progress_card = progress_card = Card()
        layout.addWidget(progress_card)
        self.status = text_label(tr('scan_ready'), 'section')
        progress_card.content.addWidget(self.status)
        progress_card.content.addWidget(self.source_warning)
        self.progress = QProgressBar()
        set_text(self.progress, tr('scan_progress_name'), 'setAccessibleName')
        self.progress.setTextVisible(False)
        self.progress.setRange(0, 1)
        progress_card.content.addWidget(self.progress)
        self.elapsed = text_label('', 'metadata')
        progress_card.content.addWidget(self.elapsed)
        self.report_warning = text_label(tr('report_error'), 'metadata')
        self.report_warning.hide()
        progress_card.content.addWidget(self.report_warning)
        self.guidance = text_label(tr('scan_next_ready'), 'metadata')
        progress_card.content.addWidget(self.guidance)
        layout.addWidget(self.advanced)
        self.details = CollapsibleSection('scan_details')
        layout.addWidget(self.details)
        self.progress_detail = text_label('', 'small')
        self.details.body_layout.addWidget(self.progress_detail)
        self.report = path_label('', 'small')
        self.details.body_layout.addWidget(self.report)
        self.reports = button('reports', reports, self.details.body_layout)
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
        self.state = 'ready'
        self.current_source_states: dict[str, str] = {}
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
        self.current_source_states = {path: states.get(path, 'checking_source') for path in roots}
        self.update_source_warning()
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
            set_text(remove, tr('remove_source_help'), 'setToolTip')
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
                self.current_source_states[path] = state
                key = state if state in ('available', 'unavailable') else 'state_' + state
                set_text(self.source_labels[path], tr(key))
                for i in range(self.roots.count()):
                    item = self.roots.item(i)
                    if item.toolTip() == path:
                        item.setData(Qt.AccessibleTextRole, path + '\n' + tr(key))
        self.update_source_warning()

    def update_source_warning(self) -> None:
        count = sum(state in ('unavailable', 'incomplete', 'failed')
                    for state in self.current_source_states.values())
        set_text(self.source_warning, tr('scan_sources_warning', count) if count else '')
        self.source_warning.setVisible(bool(count))

    def set_review_action(self, enabled: bool) -> None:
        self.review.setEnabled(enabled)
        for control, primary in ((self.review, enabled), (self.start, not enabled)):
            style_button(control, 'primary' if primary else 'secondary')
            control.style().unpolish(control)
            control.style().polish(control)

    def begin(self) -> None:
        self.state = 'running'
        self.show_activity()
        self.started = time.monotonic()
        set_text(self.status, tr('checking_sources'))
        set_text(self.errors, '', 'setPlainText')
        self.failure_detail = ''
        self.report_failure_detail = ''
        self.report_warning.hide()
        set_text(self.error_summary, tr('no_scan_errors'))
        self.error_section.set_expanded(False)
        set_text(self.report, '')
        set_text(self.progress_detail, '')
        set_text(self.guidance, tr('scan_next_running'))
        self.set_review_action(False)
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
        set_text(self.status, tr('scan_progress_summary', tr('phase_' + value.phase), value.processed))
        set_text(self.progress_detail, tr('progress', tr('phase_' + value.phase), value.discovered,
            value.processed, value.skipped, value.failed))
        set_text(self.error_summary, tr('scan_error_count', value.failed) if value.failed else tr('no_scan_errors'))
        self.source_states(value.roots)

    def finish(self, value: DashboardSummary) -> None:
        self.timer.stop()
        self.progress.setRange(0, 1)
        self.progress.setValue(1 if value.status == 'complete' else 0)
        if not value.session_id:
            return
        self.state = value.status
        self.report_warning.setVisible(bool(self.report_failure_detail))
        self.show_activity()
        set_text(self.status, tr('scan_result_summary', tr('state_' + value.status),
            value.photo_count, value.exact_groups, value.visual, value.errors))
        set_text(self.elapsed, tr('elapsed', max(0, int(value.finished - value.started))) if value.finished else '')
        set_text(self.error_summary, tr('scan_error_count', value.errors) if value.errors else tr('no_scan_errors'))
        if value.status == 'failed':
            set_text(self.error_summary, tr('scan_failure_help'))
        review = value.status in ('complete', 'incomplete') and bool(value.exact or value.visual)
        self.set_review_action(review)
        set_text(self.guidance, tr('scan_next_partial' if value.status == 'incomplete' else
            'scan_next_cancelled' if value.status == 'cancelled' else
            'scan_next_retry' if value.status == 'failed' else
            'scan_next_review' if review else 'scan_next_clear'))
        # Dashboard roots are availability-checked by the service. A successful
        # historical root scan describes an available source, not its live phase.
        self.source_states(tuple((path, 'available' if state == 'complete' else state)
                                 for path, state in value.roots))

    def cancelled(self) -> None:
        self.state = 'cancelled'
        self.timer.stop()
        self.progress.setRange(0, 1)
        self.progress.setValue(0)
        set_text(self.status, tr('state_cancelled'))
        set_text(self.guidance, tr('scan_next_cancelled'))
        self.set_review_action(False)

    def fail(self, detail: str) -> None:
        self.state = 'failed'
        self.show_activity()
        self.failure_detail = detail
        self.timer.stop()
        self.progress.setRange(0, 1)
        self.progress.setValue(0)
        set_text(self.status, tr('scan_failed'))
        set_text(self.error_summary, tr('scan_failure_help'))
        set_text(self.errors, detail, 'setPlainText')
        set_text(self.guidance, tr('scan_next_retry'))
        self.set_review_action(False)
