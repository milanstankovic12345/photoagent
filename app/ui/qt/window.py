from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import Any

from PySide6.QtCore import QModelIndex, QTimer, Qt, QUrl
from PySide6.QtGui import QCloseEvent, QDesktopServices, QIcon, QKeySequence, QShortcut
from PySide6.QtWidgets import (QApplication, QDialog, QFileDialog, QHBoxLayout,
    QMainWindow, QMessageBox, QStackedWidget, QTextEdit, QVBoxLayout, QWidget)

from app.core.models import Kind, Match, Plan
from app.core.queries import MatchQuery, MatchRow, ScanProgress
from app.ui.qt.components import PageHeader, PlanDialog
from app.ui.qt.controller import Controller
from app.ui.qt.navigation import Route, Sidebar
from app.ui.qt.screens import (CompareScreen, DashboardScreen, DuplicatesFlow, DuplicatesScreen,
                               HistoryScreen, ScanScreen, SettingsScreen, scroll_page)
from app.ui.qt.localization import set_text, text_of, language_manager
from app.ui.qt.strings import error_text, tr, join_text
from app.ui.qt.themes import ThemeManager
from app.ui.qt import resources_rc  # Registers bundled local resources.


class MainWindow(QMainWindow):
    def __init__(self, home: Path | None = None) -> None:
        super().__init__()
        set_text(self, tr('title'), 'setWindowTitle')
        self.setWindowIcon(QIcon(':/photoagent/photoagent.svg'))
        self.home = home or Path.home()
        self.controller = Controller(self.home, self)
        self.theme = ThemeManager(QApplication.instance())
        self.theme.apply('dark')
        self.settings = {}
        self.roots = []
        self.session = ''
        self.status = ''
        self.query = MatchQuery(limit=24)
        self.choice_context = None
        self.retained = {}
        self.reviewed_photos = {}
        self.visual_choice = None
        self.executing_plan = None
        self.restore_id = None
        self.open_group = False
        self.listing_context = None
        self.group_offset = self.history_offset = self.error_offset = 0
        self.total = self.group_total = self.history_total = self.error_total = 0
        self.history_rows = ()
        self.group_rows = ()
        self.selected_id = None
        self.plan_dialog = None
        self.plan_focus = None
        self.finished = False
        self.pending_prepare = False
        self.operation_epoch = 0
        self.prepare_epoch = 0
        self.writable = False
        self.scan_active = False
        self.waiting_sources = False
        self.root_states = {}
        self.search_timer = QTimer(self)
        self.search_timer.setSingleShot(True)
        self.search_timer.setInterval(250)
        self.search_timer.timeout.connect(self.filter_changed)
        self._build()
        self.controller.result.connect(self.result)
        self.controller.error.connect(self.error)
        self.controller.progress.connect(self.progress)
        self.controller.preview_ready.connect(self.preview_ready)
        self.controller.thumbnails_ready.connect(self.dashboard.set_thumbnails)
        self.controller.thumbnails_ready.connect(self.duplicates.groups.set_thumbnails)
        self.controller.busy_changed.connect(self.busy_changed)
        self.controller.closed.connect(self.safe_closed)
        area = QApplication.primaryScreen().availableGeometry()
        self.resize(min(1440, int(area.width() * .92)), min(960, int(area.height() * .9)))
        QTimer.singleShot(0, lambda: self.controller.request('initialize'))

    def _build(self) -> None:
        central = QWidget()
        layout = QHBoxLayout(central)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(16)
        self.navigation = Sidebar()
        layout.addWidget(self.navigation)
        content = QVBoxLayout()
        layout.addLayout(content, 1)
        self.header = PageHeader('dashboard', 'dashboard_purpose')
        content.addWidget(self.header)
        self.toolbar = QVBoxLayout()
        self.toolbar.setContentsMargins(0, 0, 0, 0)
        content.addLayout(self.toolbar)
        self.stack = QStackedWidget()
        content.addWidget(self.stack, 1)
        self.dashboard = DashboardScreen(self.refresh, lambda: self.navigate(Route.SCAN),
            self.review_results, lambda: self.navigate(Route.SETTINGS), self.set_theme,
            self.controller.thumbnails)
        self.scan = ScanScreen(self.add_root, self.remove_root, self.reorder_root, self.start_scan,
            self.cancel, lambda: self.controller.request('reports'), self.errors_page,
            lambda: self.review_results(None))
        self.duplicates = DuplicatesScreen(self.query_edited, self.sort,
            self.change_page, self.selected, self.compare, self.prepare_selected, self.prepare_bulk,
            self.group_changed, self.groups_page, self.controller.thumbnails)
        self.comparison = CompareScreen(self.prepare_selected, self.back_to_duplicates, self.keep_both, self.change_page)
        self.comparison.members.setModel(self.duplicates.model)
        self.comparison.members.setSelectionModel(self.duplicates.table.selectionModel())
        self.comparison.left.keep_photo.clicked.connect(lambda checked: self.choose_keeper(False, checked))
        self.comparison.right.keep_photo.clicked.connect(lambda checked: self.choose_keeper(True, checked))
        self.comparison.context_restore.clicked.connect(self.restore_context)
        self.duplicates.groups.activated.connect(self.activate_group)
        self.history = HistoryScreen(self.restore, self.history_page, self.open_quarantine_folder)
        self.history.selection_changed.connect(self.history_selected)
        self.preferences = SettingsScreen(self.save_settings, self.theme_changed,
            lambda: self.navigate(Route.SCAN), self.language_changed)
        self.duplicates_flow = DuplicatesFlow(self.duplicates, self.comparison)
        self.screens = {Route.DASHBOARD: self.dashboard, Route.SCAN: self.scan,
                        Route.DUPLICATES: self.duplicates, Route.QUARANTINE: self.history,
                        Route.SETTINGS: self.preferences}
        self.pages = {route: self.duplicates_flow if route == Route.DUPLICATES else scroll_page(screen)
                      for route, screen in self.screens.items()}
        self.dashboard.bind_scroll(self.pages[Route.DASHBOARD])
        for page in self.pages.values():
            self.stack.addWidget(page)
        self.toolbars = [screen.toolbar for screen in (*self.screens.values(), self.comparison)]
        for toolbar in self.toolbars:
            self.toolbar.addWidget(toolbar)
            toolbar.hide()
        self.navigation.activated.connect(self.navigate)
        self.route = Route.DASHBOARD
        self.update_shell()
        self.back_shortcut = QShortcut(QKeySequence('Alt+Left'), self)
        self.back_shortcut.activated.connect(self.back_to_duplicates)
        self.setCentralWidget(central)
        set_text(self.statusBar(), tr('ready'), 'showMessage')

    def navigate(self, route: Route) -> None:
        if self.controller.closing:
            return
        route = Route(route)
        if route != self.route:
            self.open_group = False
            self.invalidate_plan()
        self.route = route
        self.stack.setCurrentWidget(self.pages[route])
        self.navigation.select(route)
        self.update_shell()
        # Keep keyboard navigation in the sidebar; Tab enters the current toolbar.
        self.navigation.buttons[route].setFocus(Qt.OtherFocusReason)

    def update_shell(self) -> None:
        comparing = self.route == Route.DUPLICATES and self.duplicates_flow.comparing
        key = 'compare' if comparing else self.route.value
        self.header.set_page('dashboard_title' if self.route == Route.DASHBOARD else
            'scan_photos' if self.route == Route.SCAN else 'duplicate_photos' if key == 'duplicates' else key, key + '_purpose')
        current = self.comparison if comparing else self.screens[self.route]
        for toolbar in self.toolbars:
            toolbar.setVisible(toolbar is current.toolbar)
        self.navigation.select(self.route)
        # Toolbars are reparented into the shared shell. Define the visual Tab
        # order explicitly instead of inheriting Qt's widget-creation order.
        controls = [current.toolbar.actions.itemAt(i).widget()
                    for i in range(current.toolbar.actions.count())]
        chain = [self.navigation.toggle, *self.navigation.buttons.values(), *controls]
        for first, second in zip(chain, chain[1:]):
            QWidget.setTabOrder(first, second)
        target = (self.comparison.left.view if comparing else {
            Route.DASHBOARD: None, Route.SCAN: self.scan.roots,
            Route.DUPLICATES: self.duplicates.search, Route.QUARANTINE: self.history.table,
            Route.SETTINGS: self.preferences.theme,
        }[self.route])
        if target is not None:
            QWidget.setTabOrder(controls[-1], target)
        if comparing:
            body = []
            for photo in (self.comparison.left, self.comparison.right):
                body.extend([photo.view, *photo.preview_buttons, photo.enlarge, photo.keep_photo,
                    photo.details.toggle, photo.full_metadata, photo.error_details.toggle, photo.error_details.text])
            body.extend([self.comparison.both, self.comparison.prepare, self.comparison.context_restore,
                self.comparison.member_section.toggle, self.comparison.previous,
                self.comparison.next, self.comparison.members])
        else:
            body = {
                Route.DASHBOARD: [],  # Dynamic candidate actions retain their native order.
                Route.SCAN: [self.scan.roots, *self.scan.remove_buttons, self.scan.add,
                    self.scan.advanced.toggle, self.scan.up, self.scan.down,
                    self.scan.error_section.toggle, self.scan.errors,
                    self.scan.error_previous, self.scan.error_next],
                Route.DUPLICATES: [self.duplicates.search, self.duplicates.kind,
                    self.duplicates.sort_order, self.duplicates.direction, self.duplicates.mode,
                    self.duplicates.all_groups, self.duplicates.groups, self.duplicates.group_previous,
                    self.duplicates.group_next, self.duplicates.table, self.duplicates.previous,
                    self.duplicates.next, self.duplicates.error_details.toggle, self.duplicates.error_details.text],
                Route.QUARANTINE: [self.history.table, self.history.previous, self.history.next,
                    self.history.error_details.toggle, self.history.error_details.text],
                Route.SETTINGS: [self.preferences.theme, self.preferences.language, self.preferences.edit_sources,
                    self.preferences.preset, self.preferences.advanced.toggle,
                    self.preferences.phash, self.preferences.dhash,
                    self.preferences.error_details.toggle, self.preferences.error_details.text],
            }[self.route]
        chain = [*chain, *body]
        for first, second in zip(chain, chain[1:]):
            QWidget.setTabOrder(first, second)

    def request_matches(self) -> None:
        if self.session:
            self.duplicates.set_state(tr('query_loading'), bool(self.total or self.group_total))
            # Once a group is selected, its member pager includes every direct
            # link. The gallery's session-wide search remains intact for Back.
            query = replace(self.query, text='') if self.query.keeper_id is not None else self.query
            self.controller.request('matches', (self.session, query))

    def refresh(self) -> None:
        self.controller.request('sources', tuple(self.roots))
        self.controller.request('dashboard', self.session or None)
        self.controller.request('history', MatchQuery(sort='time', descending=True, offset=self.history_offset))
        self.controller.request('storage')
        if self.session:
            self.request_matches()
            self.request_groups()

    def request_groups(self) -> None:
        self.controller.request('groups', (self.session, replace(self.query, keeper_id=None,
            kind=self.duplicates.kind.currentData(), offset=self.group_offset, limit=min(24, self.query.limit))))

    def result(self, action: str, value: Any) -> None:
        if action == 'initialize':
            self.settings, issues, self.writable, detail = value
            self.apply_language(self.settings['language'])
            self.roots = list(self.settings['roots'])
            self.render_roots()
            for combo in (self.preferences.theme, self.dashboard.theme):
                combo.blockSignals(True)
                combo.setCurrentIndex(combo.findData(self.settings['theme']))
                combo.blockSignals(False)
            self.theme.apply(self.settings['theme'])
            self.preferences.load_matching(self.settings['phash_max'], self.settings['dhash_max'])
            self.refresh()
            if issues or detail:
                self.error(action, '\n'.join([*issues, detail]))
        elif action == 'dashboard':
            self.dashboard.set_summary(value)
            if self.scan_active:
                self.dashboard.loading_enabled = False
                self.dashboard.pause_previews()
            set_text(self.duplicates.warning, text_of(self.dashboard.warning))
            self.duplicates.warning.setVisible(bool(self.dashboard.warning.text()))
            if not value.session_id:
                self.duplicates.set_state(tr('no_session'), False)
            elif not value.exact and not value.visual:
                set_text(self.duplicates.empty, tr('no_matches'))
            if not self.scan_active:
                # A failed attempt may precede creation of a new session. Keep
                # that failure visible instead of rendering the older successful
                # session as the result of the attempted scan.
                if not self.scan.failure_detail or value.status == 'failed':
                    self.scan.finish(value)
                self.error_total = value.errors
                if value.session_id and (not self.scan.failure_detail or value.status == 'failed'):
                    self.controller.request('errors', (value.session_id, self.error_offset))
            if value.session_id != self.session:
                self.listing_context = None
                self.session = self.controller.session = value.session_id
                self.invalidate_selection()
                self.query = replace(self.query, offset=0, keeper_id=None)
                self.group_offset = 0
                self.duplicates.groups.groups_model.review.clear()
                self.request_matches()
                self.request_groups()
            if not self.scan_active:
                self.status = 'failed' if self.scan.failure_detail else value.status
        elif action == 'sources':
            self.root_states = dict(value)
            self.scan.source_states(value)
            if self.waiting_sources:
                self.waiting_sources = False
                if any(self.root_states.get(root) == 'available' for root in self.roots):
                    self.controller.request('scan', self.roots.copy())
                else:
                    self.scan_active = False
                    self.scan.fail(tr('unavailable_source'))
                    self.status = 'failed'
        elif action == 'scan':
            summary, report, report_error, _, _, warning = value
            self.scan_active = False
            self.scan.timer.stop()
            self.session = self.controller.session = summary.session_id
            self.status = summary.status
            self.query = replace(self.query, offset=0, keeper_id=None)
            self.group_offset = self.error_offset = 0
            self.error_total = summary.error_count
            report_text = []
            if report:
                report_text.append(tr('report_saved', report))
            if report_error:
                report_text.append(tr('report_error'))
                self.scan.report_failure_detail = report_error
                set_text(self.scan.errors, report_error, 'setPlainText')
            set_text(self.scan.report, join_text(report_text))
            self.refresh()
        elif action == 'matches':
            self.total = value.total
            selected_id = self.selected_id
            selection = self.duplicates.table.selectionModel()
            selection.blockSignals(True)
            self.duplicates.model.replace(value.items)
            selection.blockSignals(False)
            set_text(self.duplicates.page, tr('page', value.offset + bool(value.items), value.offset + len(value.items), value.total))
            set_text(self.comparison.member_page, text_of(self.duplicates.page))
            set_text(self.comparison.member_section.toggle, tr('member_count', value.total + 1)
                if self.query.keeper_id is not None else tr('direct_members'))
            set_text(self.comparison.member_section.toggle, text_of(self.comparison.member_section.toggle), 'setAccessibleName')
            self.duplicates.set_state('' if value.items else tr('empty') if self.query.text or self.query.kind
                else tr('no_matches') if self.status == 'complete' else tr('scan_review_only'),
                bool(value.items or self.group_total))
            index = next((i for i, r in enumerate(value.items) if r.id == selected_id), None)
            if index is not None:
                self.duplicates.table.selectRow(index)
            else:
                if not (self.duplicates_flow.comparing and self.controller.selection is not None):
                    self.invalidate_selection(preserve_choices=True)
            if self.open_group:
                self.open_group = False
                if value.items:
                    self.duplicates.table.selectRow(0)
                    self.compare()
        elif action == 'groups':
            self.group_rows = value.items
            self.group_total = value.total
            widget = self.duplicates.groups
            selection = widget.selectionModel()
            selection.blockSignals(True)
            widget.replace(value.items)
            chosen = next((i + 1 for i, r in enumerate(value.items) if r.keeper_id == self.query.keeper_id and r.kind == self.query.kind), 0)
            widget.setCurrentRow(chosen)
            selection.blockSignals(False)
            set_text(self.duplicates.group_page, tr('page', value.offset + bool(value.items),
                value.offset + len(value.items), value.total))
            self.duplicates.set_state(text_of(self.duplicates.empty), bool(value.items or self.total))
        elif action == 'history':
            self.history_rows = value.items
            self.history_total = value.total
            self.history.show_page(value)
        elif action == 'history_preview':
            self.history.show_preview(*value)
        elif action == 'quarantine_folder':
            entry = self.history.selected_entry
            if entry and entry.id == value[0]:
                if not QDesktopServices.openUrl(QUrl.fromLocalFile(value[1])):
                    self.error(action, 'folder_open_failed')
        elif action == 'storage':
            self.preferences.show_storage(value)
        elif action == 'errors':
            set_text(self.scan.errors, join_text(filter(None,
                (self.scan.failure_detail, self.scan.report_failure_detail, *value))), 'setPlainText')
        elif action in ('prepare', 'bulk', 'restore'):
            self.pending_prepare = False
            if self.prepare_epoch == self.operation_epoch:
                self.confirm(value)
        elif action == 'execute':
            self.listing_context = None
            self.history_offset = 0
            self.operation_epoch += 1
            self.controller.preview(None)
            self.invalidate_selection()
            set_text(self.statusBar(), tr('operation_count', len(value)), 'showMessage')
            plan = self.executing_plan
            self.restore_id = (plan.moves[0].id if plan and len(plan.moves) == 1
                and plan.moves[0].action == 'quarantine' and value else None)
            self.executing_plan = None
            self.refresh()
        elif action == 'language_saved':
            self.settings = value
        elif action == 'language':
            self.settings = value
            self.apply_language(value['language'])
            set_text(self.statusBar(), tr('saved'), 'showMessage')
        elif action == 'settings':
            self.settings = value
            self.theme.apply(value['theme'])
            for combo in (self.preferences.theme, self.dashboard.theme):
                combo.blockSignals(True)
                combo.setCurrentIndex(combo.findData(value['theme']))
                combo.blockSignals(False)
            self.controller.request('sources', tuple(self.roots))
            self.preferences.show_roots(self.roots)
            set_text(self.statusBar(), tr('saved'), 'showMessage')
        elif action == 'cancelled':
            self.pending_prepare = False
            set_text(self.statusBar(), tr('action_cancelled'), 'showMessage')
            if value == 'execute':
                self.refresh()
        self.busy_changed(self.controller.busy)

    def error(self, action: str, detail: str) -> None:
        if action == 'language':
            self.apply_language(self.settings['language'])
            set_text(self.statusBar(), tr('language_save_failed'), 'showMessage')
            self.show_error('language_save_failed: ' + detail)
            return
        if action == 'history_preview':
            self.history.thumbnail.clear()
            set_text(self.history.thumbnail, tr('thumbnail_unavailable'))
            set_text(self.history.thumbnail, tr('thumbnail_unavailable'), 'setAccessibleName')
            set_text(self.history.thumbnail, error_text(detail), 'setToolTip')
            self.history.error_details.set_detail(detail)
            return
        if action == 'storage':
            set_text(self.preferences.index, tr('storage_failed'))
            self.preferences.error_details.set_detail(detail)
            return
        self.pending_prepare = False
        if action == 'scan' or action == 'sources' and self.waiting_sources:
            self.scan_active = self.waiting_sources = False
            self.scan.fail(detail)
            self.status = 'failed'
            # The failed session may have been committed before the worker raised.
            self.session = self.controller.session = ''
            self.error_offset = 0
            self.controller.request('dashboard', None)
            self.busy_changed(self.controller.busy)
            return
        if action in ('execute', 'prepare', 'restore', 'bulk'):
            self.restore_id = None
            self.comparison.context_restore.hide()
            self.executing_plan = None
            self.refresh()
        if action in ('matches', 'groups'):
            self.open_group = False
            self.duplicates.set_state(tr('query_error'), False)
            self.duplicates.error_details.set_detail(detail)
            self.invalidate_selection()
        if action == 'history':
            self.history_rows = ()
            self.history_total = 0
            self.history.fail(detail)
            return
        if action in ('restore', 'execute'):
            set_text(self.history.message, error_text(detail))
            self.history.error_details.set_detail(detail)
            self.history.message.show()
        self.show_error(detail)

    def show_error(self, detail: str) -> None:
        box = QMessageBox(self)
        box.setAttribute(Qt.WA_DeleteOnClose)
        set_text(box, tr('title'), 'setWindowTitle')
        box.setIcon(QMessageBox.Warning)
        box.setTextFormat(Qt.PlainText)
        set_text(box, tr('error'))
        set_text(box, error_text(detail), 'setInformativeText')
        box.setStandardButtons(QMessageBox.Close)
        set_text(box.button(QMessageBox.Close), tr('close'))
        box.setDetailedText(detail)
        for control in box.buttons():
            if box.buttonRole(control) == QMessageBox.ActionRole:
                def update_details_label(checked=False, button=control) -> None:
                    key = 'hide_details' if any(editor.isVisible() for editor in box.findChildren(QTextEdit)) else 'technical_details'
                    set_text(button, tr(key))
                    set_text(button, tr(key), 'setAccessibleName')
                set_text(control, tr('technical_details'))
                set_text(control, tr('technical_details'), 'setAccessibleName')
                control.clicked.connect(update_details_label)
        box.open()

    def progress(self, value: ScanProgress) -> None:
        if self.scan_active and not self.controller.closing:
            self.scan.update_progress(value)

    def busy_changed(self, busy: bool) -> None:
        available = not busy and not self.controller.closing and not self.scan_active
        self.scan.start.setEnabled(available and any(self.root_states.get(root) == 'available' for root in self.roots))
        self.scan.cancel.setEnabled(self.scan_active and not self.controller.closing)
        for control in (self.scan.add, self.scan.up, self.scan.down, *self.scan.remove_buttons):
            control.setEnabled(available)
        self.dashboard.scan.setEnabled(not self.controller.closing)
        if self.scan_active:
            self.scan.progress.setRange(0, 0)
        self.duplicates.compare.setEnabled(self.controller.selection is not None and not self.controller.closing)
        allowed = available and self.writable and self.status == 'complete'
        self.comparison.prepare.setEnabled(allowed and self.controller.selection is not None and bool(self.pending_pairs()))
        self.duplicates.bulk.setEnabled(allowed and bool(self.session))
        entry = self.history.selected_entry
        self.history.restore.setEnabled(available and self.writable and entry is not None and entry.restorable)
        self.history.open_folder.setEnabled(available and entry is not None)
        self.preferences.save.setEnabled(available and self.writable)
        eligible = self.restore_id and any(row.id == self.restore_id and row.restorable for row in self.history_rows)
        self.comparison.context_restore.setVisible(bool(eligible))
        self.comparison.context_restore.setEnabled(allowed and bool(eligible))
        if not self.controller.closing and self.statusBar().currentMessage() in (tr('ready'), tr('busy')):
            set_text(self.statusBar(), tr('busy' if busy else 'ready'), 'showMessage')

    def render_roots(self) -> None:
        self.scan.set_sources(self.roots, self.root_states)
        self.preferences.show_roots(self.roots)
        self.update_shell()
        self.busy_changed(self.controller.busy)

    def add_root(self) -> None:
        dialog = QFileDialog(self)
        dialog.setAttribute(Qt.WA_DeleteOnClose)
        dialog.setOptions(QFileDialog.DontUseNativeDialog | QFileDialog.ReadOnly)
        dialog.setFileMode(QFileDialog.Directory)
        dialog.setDirectory(self.roots[0] if self.roots else str(self.home))
        dialog.setWindowModality(Qt.WindowModal)
        set_text(dialog, tr('add'), 'setWindowTitle')
        dialog.fileSelected.connect(self.add_selected_root)
        dialog.open()

    def add_selected_root(self, path: str) -> None:
        if path and path not in self.roots:
            self.invalidate_selection()
            self.roots.append(path)
            self.render_roots()
            self.controller.request('settings', {'roots': self.roots.copy()})

    def remove_root(self) -> None:
        row = self.scan.roots.currentRow()
        if row >= 0:
            self.invalidate_selection()
            self.roots.pop(row)
            self.render_roots()
            if self.roots:
                self.scan.roots.setCurrentRow(min(row, len(self.roots) - 1))
                self.scan.roots.setFocus(Qt.OtherFocusReason)
            else:
                self.scan.add.setFocus(Qt.OtherFocusReason)
            self.controller.request('settings', {'roots': self.roots.copy()})

    def reorder_root(self, direction: int) -> None:
        row = self.scan.roots.currentRow()
        target = row + direction
        if row >= 0 and 0 <= target < len(self.roots):
            self.invalidate_selection()
            self.roots[row], self.roots[target] = self.roots[target], self.roots[row]
            self.render_roots()
            self.scan.roots.setCurrentRow(target)
            self.controller.request('settings', {'roots': self.roots.copy()})

    def start_scan(self) -> None:
        if self.controller.busy or not self.roots:
            return
        self.invalidate_selection()
        self.listing_context = None
        self.open_group = False
        for action in ('matches', 'groups'):
            self.controller.latest.pop(action, None)
        self.duplicates.groups.groups_model.review.clear()
        self.search_timer.stop()
        self.scan_active = self.waiting_sources = True
        self.status = 'running'
        self.dashboard.loading_enabled = False
        self.dashboard.pause_previews()
        self.scan.begin()
        self.pages[Route.SCAN].verticalScrollBar().setValue(0)
        self.controller.request('sources', tuple(self.roots))

    def cancel(self) -> None:
        self.invalidate_selection()
        self.controller.cancel()
        if self.waiting_sources:
            self.waiting_sources = self.scan_active = False
            self.status = 'cancelled'
            self.scan.timer.stop()
            set_text(self.scan.status, tr('state_cancelled'))
            self.scan.progress.setRange(0, 1)
            self.dashboard.loading_enabled = True
            self.dashboard.visible_timer.start()
        self.busy_changed(self.controller.busy)

    def invalidate_plan(self) -> None:
        self.operation_epoch += 1
        self.pending_prepare = False
        if self.plan_dialog:
            self.plan_dialog.reject()

    def invalidate_selection(self, *, preserve_choices: bool = False) -> None:
        self.invalidate_plan()
        self.controller.preview(None)
        self.selected_id = None
        if not preserve_choices:
            self.choice_context = None
            self.retained.clear()
            self.reviewed_photos.clear()
            self.visual_choice = None
            self.duplicates.model.set_choices(set(), set())
        set_text(self.comparison.decision, tr('choose_keeper'))
        for view in (self.comparison.left, self.comparison.right):
            view.keep_photo.setChecked(False)
        # Clear Qt's current row as well, so the same pair can be selected again
        # after cancellation/root changes. Block the invalid-index signal here
        # to avoid re-entering this method through selected().
        selection = self.duplicates.table.selectionModel()
        blocked = selection.blockSignals(True)
        selection.clear()
        selection.blockSignals(blocked)
        self.comparison.left.reset()
        self.comparison.right.reset()

    def filter_changed(self) -> None:
        self.listing_context = None
        self.invalidate_selection()
        self.group_offset = 0
        self.query = replace(self.query, text=self.duplicates.search.text(), kind=self.duplicates.kind.currentData(),
                             keeper_id=None, offset=0)
        self.request_matches()
        if self.session:
            self.request_groups()

    def query_edited(self, *_: Any) -> None:
        self.open_group = False
        self.invalidate_plan()
        # An old query/prepare response cannot become actionable during debounce.
        for action in ('matches', 'groups', 'prepare', 'bulk'):
            self.controller.latest.pop(action, None)
        self.search_timer.start()

    def sort(self, column: int) -> None:
        self.open_group = False
        self.listing_context = None
        self.invalidate_selection()
        name = self.duplicates.model.columns[column]
        self.query = replace(self.query, sort=name, descending=self.query.sort == name and not self.query.descending, offset=0)
        self.duplicates.sort_order.blockSignals(True)
        self.duplicates.sort_order.setCurrentIndex(column)
        self.duplicates.sort_order.blockSignals(False)
        set_text(self.duplicates.direction, tr('sort_desc' if self.query.descending else 'sort_asc'))
        set_text(self.duplicates.direction, text_of(self.duplicates.direction), 'setAccessibleName')
        self.duplicates.table.horizontalHeader().setSortIndicator(column, Qt.DescendingOrder if self.query.descending else Qt.AscendingOrder)
        self.duplicates.table.horizontalHeader().setSortIndicatorShown(True)
        self.request_matches()
        self.group_offset = 0
        self.request_groups()

    def change_page(self, direction: int) -> None:
        target = self.query.offset + direction * self.query.limit
        if 0 <= target < self.total:
            self.open_group = False
            self.invalidate_selection(preserve_choices=True)
            self.query = replace(self.query, offset=target)
            self.request_matches()
            if self.duplicates_flow.comparing:
                self.comparison.member_section.set_expanded(True)

    def groups_page(self, direction: int) -> None:
        target = self.group_offset + direction * min(24, self.query.limit)
        if 0 <= target < self.group_total:
            self.open_group = False
            self.group_offset = target
            self.request_groups()

    def group_changed(self, row: int) -> None:
        if row < 0:
            return
        self.open_group = False
        self.invalidate_selection()
        if row <= 0:
            self.query = replace(self.query, keeper_id=None, kind=self.duplicates.kind.currentData(), offset=0)
        else:
            group = self.group_rows[row - 1]
            self.query = replace(self.query, keeper_id=group.keeper_id, kind=group.kind, offset=0)
        self.request_matches()

    def activate_group(self, index: QModelIndex) -> None:
        if index.row() > 0:
            self.group_changed(index.row())
            self.open_group = True

    def selected(self, current: QModelIndex, previous: QModelIndex) -> None:
        if not current.isValid():
            self.invalidate_selection()
            self.busy_changed(self.controller.busy)
            return
        row = self.duplicates.model.rows[current.row()]
        self.open_group = False
        self.invalidate_plan()
        self.selected_id = row.id
        context = (self.session, row.keeper_id, row.match.kind)
        if context != self.choice_context:
            self.choice_context = context
            self.retained.clear()
            self.reviewed_photos.clear()
        self.visual_choice = None
        self.controller.preview(row)
        pair = row.match
        self.comparison.left.set_photo(pair.keep)
        self.comparison.right.set_photo(pair.dup)
        warnings = [tr('review_advice')]
        if pair.keep.root != pair.dup.root:
            warnings.append(tr('cross_roots'))
        if pair.keep.is_raw or pair.dup.is_raw:
            warnings.append(tr('raw_warning'))
        if pair.kind.value == 'VISUAL':
            warnings.append(tr('visual_warning'))
        set_text(self.comparison.warning, join_text(warnings))
        self.update_choice()
        self.busy_changed(self.controller.busy)

    def preview_ready(self, value: tuple) -> None:
        for view, (image, error) in zip((self.comparison.left, self.comparison.right), value):
            view.set_image(image, error)

    def compare(self, *_: Any) -> None:
        if self.controller.selection is None or self.controller.closing:
            return
        self.invalidate_plan()
        if not self.duplicates_flow.comparing:
            self.listing_context = (self.query, self.total, self.duplicates.model.rows, self.selected_id)
        self.duplicates_flow.show_comparison(True)
        self.navigate(Route.DUPLICATES)
        self.comparison.back.setFocus(Qt.OtherFocusReason)
        row = self.controller.selection
        if self.query.keeper_id != row.keeper_id or self.query.kind != row.match.kind.value:
            self.query = replace(self.query, keeper_id=row.keeper_id, kind=row.match.kind.value, offset=0)
            group = next((g for g in self.group_rows if g.keeper_id == row.keeper_id and g.kind == row.match.kind.value), None)
            complete_page = (group and group.members - 1 == len(self.duplicates.model.rows)
                and all(r.keeper_id == row.keeper_id and r.match.kind == row.match.kind for r in self.duplicates.model.rows))
            if not complete_page:
                self.request_matches()
            else:
                set_text(self.comparison.member_section.toggle, tr('member_count', group.members))

    def back_to_duplicates(self) -> None:
        if self.route != Route.DUPLICATES or not self.duplicates_flow.comparing or self.controller.closing:
            return
        self.invalidate_plan()
        self.duplicates_flow.show_comparison(False)
        if self.listing_context:
            query, total, rows, selected_id = self.listing_context
            self.controller.latest.pop('matches', None)
            self.query, self.total = query, total
            if self.duplicates.model.rows != rows:
                selection = self.duplicates.table.selectionModel()
                selection.blockSignals(True)
                self.duplicates.model.replace(rows)
                index = next((i for i, row in enumerate(rows) if row.id == selected_id), None)
                if index is not None:
                    self.duplicates.table.selectRow(index)
                selection.blockSignals(False)
                if index is not None and (self.controller.selection is None or self.controller.selection.id != selected_id):
                    self.selected(self.duplicates.model.index(index, 0), QModelIndex())
                self.selected_id = selected_id
            set_text(self.duplicates.page, tr('page', query.offset + bool(rows), query.offset + len(rows), total))
            self.listing_context = None
        self.update_shell()
        self.duplicates.table.setFocus(Qt.OtherFocusReason)
        self.duplicates_flow.restore_listing_scroll()

    def prepare_selected(self) -> None:
        row = self.controller.selection
        if not row or self.controller.busy or self.status != 'complete':
            return
        pairs = self.pending_pairs()
        if pairs:
            self.prepare('prepare', (pairs, self.session))

    def choose_keeper(self, right: bool, checked: bool = True) -> None:
        row = self.controller.selection
        if row is None:
            return
        self.invalidate_plan()
        pair = row.match
        keep, other = (pair.dup, pair.keep) if right else (pair.keep, pair.dup)
        if pair.kind == Kind.EXACT:
            if len(set(self.reviewed_photos) | {pair.keep.path, pair.dup.path}) > 200:
                set_text(self.comparison.decision, tr('selection_limit'))
                return
            self.reviewed_photos.update({p.path: p for p in (pair.keep, pair.dup)})
            if checked:
                self.retained[keep.path] = keep
            else:
                self.retained.pop(keep.path, None)
        else:
            self.visual_choice = Match(pair.kind, keep, other, pair.ph_distance, pair.dh_distance) if checked else None
        self.duplicates.groups.groups_model.review.setdefault((row.keeper_id, pair.kind.value), set()).add(row.id)
        self.update_choice()
        self.duplicates.groups.viewport().update()
        self.busy_changed(self.controller.busy)

    def pending_pairs(self) -> tuple[Match, ...]:
        if self.choice_context is None:
            return ()
        if self.choice_context[2] != Kind.EXACT:
            return (self.visual_choice,) if self.visual_choice else ()
        if not self.retained:
            return ()
        keeper = next(iter(self.retained.values()))
        return tuple(Match(Kind.EXACT, keeper, photo) for path, photo in self.reviewed_photos.items()
                     if path not in self.retained and photo.sha256 == keeper.sha256)

    def update_choice(self) -> None:
        row = self.controller.selection
        for view, photo in ((self.comparison.left, row.match.keep if row else None),
                            (self.comparison.right, row.match.dup if row else None)):
            view.keep_photo.setChecked(bool(photo and (photo.path in self.retained if row.match.kind == Kind.EXACT
                else self.visual_choice and photo == self.visual_choice.keep)))
            set_text(view.keep_photo, tr('keep_chosen' if view.keep_photo.isChecked() else 'keep_photo'))
            set_text(view.keep_photo, tr('keep_named_photo', photo.path) if photo else text_of(view.keep_photo), 'setAccessibleName')
        set_text(self.comparison.decision, tr('selection_summary', len(self.pending_pairs()),
            len(self.retained) if row and row.match.kind == Kind.EXACT else int(bool(self.visual_choice))))
        self.duplicates.model.set_choices(set(self.retained) if row and row.match.kind == Kind.EXACT else
            {self.visual_choice.keep.path} if self.visual_choice else set(),
            {pair.dup.path for pair in self.pending_pairs()})

    def keep_both(self) -> None:
        row = self.controller.selection
        if not row:
            return
        self.invalidate_plan()
        self.retained.clear()
        self.reviewed_photos.clear()
        self.visual_choice = None
        if row.match.kind == Kind.EXACT:
            self.retained.update({p.path: p for p in (row.match.keep, row.match.dup)})
        self.duplicates.groups.groups_model.review.setdefault((row.keeper_id, row.match.kind.value), set()).add(row.id)
        self.update_choice()
        set_text(self.comparison.decision, tr('both_kept'))
        self.duplicates.groups.viewport().update()
        self.busy_changed(self.controller.busy)

    def prepare_bulk(self) -> None:
        if self.session and not self.controller.busy:
            self.prepare('bulk', self.session)

    def prepare(self, action: str, payload: Any) -> None:
        self.plan_focus = QApplication.focusWidget()
        self.prepare_epoch = self.operation_epoch
        self.pending_prepare = True
        self.controller.request(action, payload)

    def confirm(self, plan: Plan) -> None:
        if not plan.moves:
            box = QMessageBox(QMessageBox.Information, '', '', QMessageBox.Close, self)
            set_text(box, tr('plan'), 'setWindowTitle')
            set_text(box, tr('no_plan'))
            box.setAttribute(Qt.WA_DeleteOnClose)
            box.setTextFormat(Qt.PlainText)
            set_text(box.button(QMessageBox.Close), tr('close'))
            box.open()
            return
        self.plan_dialog = PlanDialog(plan, self)
        epoch = self.operation_epoch
        # Nonblocking modal dialog; normal event processing and closing continue.
        self.plan_dialog.setWindowModality(Qt.WindowModal)
        self.plan_dialog.finished.connect(lambda code: self.plan_finished(code, epoch))
        self.plan_dialog.open()

    def plan_finished(self, code: int, epoch: int) -> None:
        dialog = self.plan_dialog
        self.plan_dialog = None
        if dialog and code == QDialog.Accepted and dialog.approval and epoch == self.operation_epoch and not self.controller.closing:
            self.executing_plan = dialog.approval.plan
            self.controller.request('execute', dialog.approval)
        if dialog:
            dialog.deleteLater()
        if not self.controller.closing and epoch == self.operation_epoch:
            # Let Qt finish hiding the modal window before restoring its invoker.
            # Epoch guards prevent this queued focus from overriding navigation.
            self.activateWindow()
            target = self.plan_focus
            QTimer.singleShot(0, lambda: self.restore_plan_focus(target, epoch))

    def restore_plan_focus(self, target: QWidget | None, epoch: int) -> None:
        if self.controller.closing or epoch != self.operation_epoch:
            return
        if target is None or not target.isVisible() or not target.isEnabled():
            target = self.navigation.buttons[self.route]
        target.setFocus(Qt.OtherFocusReason)

    def restore(self) -> None:
        entry = self.history.selected_entry
        if not self.controller.busy and self.writable and entry and entry.restorable:
            self.prepare('restore', entry.id)

    def history_selected(self) -> None:
        self.invalidate_plan()
        self.controller.invalidate_history_preview()
        self.controller.latest.pop('quarantine_folder', None)
        self.history.selection_details()
        entry = self.history.selected_entry
        if entry and entry.restorable:
            self.controller.request('history_preview', entry.id)
        self.busy_changed(self.controller.busy)

    def open_quarantine_folder(self) -> None:
        entry = self.history.selected_entry
        if not self.controller.busy and entry:
            self.controller.request('quarantine_folder', entry.id)

    def restore_context(self) -> None:
        if not self.controller.busy and self.restore_id and any(
                row.id == self.restore_id and row.restorable for row in self.history_rows):
            self.prepare('restore', self.restore_id)

    def history_page(self, direction: int) -> None:
        target = self.history_offset + direction * 200
        if 0 <= target < self.history_total:
            self.history.clear_selection()
            self.history_offset = target
            self.controller.request('history', MatchQuery(sort='time', descending=True, offset=target))

    def errors_page(self, direction: int) -> None:
        target = self.error_offset + direction * 200
        if self.session and 0 <= target < self.error_total:
            self.error_offset = target
            self.controller.request('errors', (self.session, target))

    def theme_changed(self, *_: Any) -> None:
        self.set_theme(self.preferences.theme.currentData())

    def apply_language(self, language: str) -> None:
        self.preferences.language.blockSignals(True)
        self.preferences.language.setCurrentIndex(self.preferences.language.findData(language))
        self.preferences.language.blockSignals(False)
        language_manager().set_language(language)

    def language_changed(self, *_: Any) -> None:
        language = self.preferences.language.currentData()
        if self.settings and language != language_manager().language and not self.controller.closing:
            # Presentation changes immediately even while the service is scanning.
            # Persistence runs on the existing service thread after queued work.
            self.apply_language(language)
            self.controller.request('language', {'language': language})

    def set_theme(self, theme: str) -> None:
        self.theme.apply(theme)
        if self.settings:
            self.controller.request('settings', {'theme': theme})

    def review_results(self, row: MatchRow | None = None) -> None:
        self.search_timer.stop()
        self.invalidate_selection()
        self.duplicates_flow.show_comparison(False)
        self.duplicates.search.blockSignals(True)
        self.duplicates.search.clear()
        self.duplicates.search.blockSignals(False)
        self.duplicates.kind.blockSignals(True)
        self.duplicates.kind.setCurrentIndex(self.duplicates.kind.findData(row.match.kind.value) if row else 0)
        self.duplicates.kind.blockSignals(False)
        self.query = MatchQuery(limit=24, keeper_id=row.keeper_id if row else None,
            kind=row.match.kind.value if row else '')
        self.group_offset = 0
        self.selected_id = row.id if row else None
        self.navigate(Route.DUPLICATES)
        self.request_matches()
        self.request_groups()

    def save_settings(self) -> None:
        self.controller.request('settings', {'theme': self.preferences.theme.currentData(),
            'language': self.preferences.language.currentData(),
            'phash_max': self.preferences.phash.value(), 'dhash_max': self.preferences.dhash.value()})

    def closeEvent(self, event: QCloseEvent) -> None:
        if self.finished:
            event.accept()
            return
        event.ignore()
        self.search_timer.stop()
        self.scan.timer.stop()
        self.dashboard.pause_previews()
        self.operation_epoch += 1
        if self.plan_dialog:
            self.plan_dialog.reject()
        self.setEnabled(False)
        set_text(self.statusBar(), tr('closing'), 'showMessage')
        self.controller.close()

    def safe_closed(self) -> None:
        self.finished = True
        self.close()
