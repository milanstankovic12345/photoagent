from __future__ import annotations

from dataclasses import replace
from datetime import datetime
from pathlib import Path
from typing import Any

from PySide6.QtCore import QModelIndex, QTimer, Qt
from PySide6.QtGui import QCloseEvent, QIcon
from PySide6.QtWidgets import (QApplication, QDialog, QFileDialog, QHBoxLayout, QListWidget,
    QMainWindow, QMessageBox, QScrollArea, QStackedWidget, QTableWidgetItem, QWidget)

from app.core.models import Match, Plan
from app.core.queries import MatchQuery, ScanProgress
from app.ui.qt.components import PlanDialog
from app.ui.qt.controller import Controller
from app.ui.qt.screens import (CompareScreen, DashboardScreen, DuplicatesScreen,
                               HistoryScreen, ScanScreen, SettingsScreen)
from app.ui.qt.strings import tr
from app.ui.qt.themes import ThemeManager
from app.ui.qt import resources_rc  # Registers bundled local resources.


class MainWindow(QMainWindow):
    def __init__(self, home: Path | None = None) -> None:
        super().__init__()
        self.setWindowTitle(tr('title'))
        self.setWindowIcon(QIcon(':/photoagent/photoagent.svg'))
        self.home = home or Path.home()
        self.controller = Controller(self.home, self)
        self.theme = ThemeManager(QApplication.instance())
        self.theme.apply('dark')
        self.settings = {}
        self.roots = []
        self.session = ''
        self.status = ''
        self.query = MatchQuery()
        self.group_offset = self.history_offset = self.error_offset = 0
        self.total = self.group_total = self.history_total = self.error_total = 0
        self.history_rows = ()
        self.group_rows = ()
        self.selected_id = None
        self.plan_dialog = None
        self.finished = False
        self.pending_prepare = False
        self.operation_epoch = 0
        self.prepare_epoch = 0
        self.writable = False
        self.search_timer = QTimer(self)
        self.search_timer.setSingleShot(True)
        self.search_timer.setInterval(250)
        self.search_timer.timeout.connect(self.filter_changed)
        self._build()
        self.controller.result.connect(self.result)
        self.controller.error.connect(self.error)
        self.controller.progress.connect(self.progress)
        self.controller.preview_ready.connect(self.preview_ready)
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
        self.navigation = QListWidget()
        self.navigation.setMaximumWidth(224)
        self.navigation.setAccessibleName(tr('title'))
        layout.addWidget(self.navigation)
        self.stack = QStackedWidget()
        layout.addWidget(self.stack, 1)
        self.dashboard = DashboardScreen(self.refresh)
        self.scan = ScanScreen(self.add_root, self.remove_root, self.reorder_root, self.start_scan,
            self.cancel, lambda: self.controller.request('reports'), self.errors_page)
        self.duplicates = DuplicatesScreen(lambda *_: self.search_timer.start(), self.sort,
            self.change_page, self.selected, self.compare, self.prepare_selected, self.prepare_bulk,
            self.group_changed, self.groups_page)
        self.comparison = CompareScreen(self.prepare_selected)
        self.comparison.keep.currentIndexChanged.connect(self.keeper_changed)
        self.history = HistoryScreen(self.restore, self.history_page)
        self.preferences = SettingsScreen(self.save_settings, self.theme_changed)
        for key, screen in zip(('dashboard', 'scan', 'duplicates', 'compare', 'history', 'settings'),
                (self.dashboard, self.scan, self.duplicates, self.comparison, self.history, self.preferences)):
            self.navigation.addItem(tr(key))
            self.navigation.item(self.navigation.count() - 1).setIcon(QIcon(':/photoagent/photoagent.svg'))
            # Scroll areas keep every action reachable on small/high-DPI screens.
            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            scroll.setWidget(screen)
            self.stack.addWidget(scroll)
        self.navigation.currentRowChanged.connect(self.stack.setCurrentIndex)
        self.navigation.setCurrentRow(0)
        self.setCentralWidget(central)
        self.statusBar().showMessage(tr('ready'))

    def request_matches(self) -> None:
        if self.session:
            self.controller.request('matches', (self.session, self.query))

    def refresh(self) -> None:
        self.controller.request('sources', tuple(self.roots))
        self.controller.request('dashboard', self.session or None)
        self.controller.request('history', MatchQuery(sort='time', descending=True, offset=self.history_offset))
        if self.session:
            self.request_matches()
            self.request_groups()

    def request_groups(self) -> None:
        self.controller.request('groups', (self.session, replace(self.query, keeper_id=None, offset=self.group_offset)))

    def result(self, action: str, value: Any) -> None:
        if action == 'initialize':
            self.settings, issues, self.writable, detail = value
            self.roots = list(self.settings['roots'])
            self.render_roots()
            self.preferences.theme.blockSignals(True)
            self.preferences.theme.setCurrentIndex(self.preferences.theme.findData(self.settings['theme']))
            self.preferences.theme.blockSignals(False)
            self.theme.apply(self.settings['theme'])
            self.preferences.phash.setValue(self.settings['phash_max'])
            self.preferences.dhash.setValue(self.settings['dhash_max'])
            self.preferences.index.setText(tr('index_info', self.home / '.photo_agent_index.sqlite3'))
            self.refresh()
            if issues or detail:
                self.error(action, '\n'.join([*issues, detail]))
        elif action == 'dashboard':
            self.dashboard.counts.setText(tr('dashboard_counts', value.indexed, value.exact, value.visual, value.potential_bytes))
            self.dashboard.session.setText(tr('last_scan', value.session_id, tr('state_' + value.status),
                datetime.fromtimestamp(value.started).astimezone().isoformat(timespec='seconds'), value.errors)
                if value.session_id else tr('no_session'))
            self.dashboard.roots.setText('\n'.join(f'{p} · {tr("state_" + s)}' for p, s in value.roots))
            self.dashboard.warning.setText('\n'.join(tr(w) for w in value.warnings))
            self.duplicates.warning.setText(self.dashboard.warning.text())
            if not self.session and value.session_id:
                self.session = self.controller.session = value.session_id
                self.status = value.status
                self.request_matches()
                self.request_groups()
        elif action == 'sources':
            for i, root in enumerate(self.roots):
                status = dict(value).get(root, 'unavailable')
                self.scan.roots.item(i).setText(f'{root} · {tr(status)}')
        elif action == 'scan':
            summary, report, report_error, _, _, warning = value
            self.session = self.controller.session = summary.session_id
            self.status = summary.status
            self.query = replace(self.query, offset=0, keeper_id=None)
            self.group_offset = self.error_offset = 0
            self.error_total = summary.error_count
            self.scan.status.setText(tr('scan_done', tr('state_' + summary.status), summary.photo_count, summary.pair_count, summary.error_count))
            if report:
                self.scan.status.setText(self.scan.status.text() + '\n' + tr('report_saved', report))
            if report_error:
                self.scan.status.setText(self.scan.status.text() + '\n' + tr('report_error', report_error))
            self.controller.request('errors', (self.session, 0))
            self.refresh()
        elif action == 'matches':
            self.total = value.total
            self.duplicates.model.replace(value.items)
            self.duplicates.page.setText(tr('page', value.offset + bool(value.items), value.offset + len(value.items), value.total))
            self.duplicates.empty.setText(tr('unimplemented') if self.query.kind in ('DERIVATIVE', 'SIMILAR_CAPTURE')
                else '' if value.items else tr('empty'))
            index = next((i for i, r in enumerate(value.items) if r.id == self.selected_id), None)
            if index is not None:
                self.duplicates.table.selectRow(index)
            else:
                self.selected_id = None
                self.controller.preview(None)
                self.comparison.left.reset()
                self.comparison.right.reset()
        elif action == 'groups':
            self.group_rows = value.items
            self.group_total = value.total
            widget = self.duplicates.groups
            widget.blockSignals(True)
            widget.clear()
            widget.addItem(tr('all_groups'))
            for row in value.items:
                widget.addItem(tr('group', row.kind, row.members, row.keeper_path))
            chosen = next((i + 1 for i, r in enumerate(value.items) if r.keeper_id == self.query.keeper_id and r.kind == self.query.kind), 0)
            widget.setCurrentRow(chosen)
            widget.blockSignals(False)
        elif action == 'history':
            self.history_rows = value.items
            self.history_total = value.total
            table = self.history.table
            table.setRowCount(len(value.items))
            for i, entry in enumerate(value.items):
                for j, item in enumerate((entry.at, entry.source, entry.destination, tr('state_' + entry.state), entry.error,
                                         tr('yes' if entry.restorable else 'no'))):
                    table.setItem(i, j, QTableWidgetItem(str(item)))
            self.history.page.setText(tr('page', value.offset + bool(value.items), value.offset + len(value.items), value.total))
        elif action == 'errors':
            self.scan.errors.setPlainText('\n'.join(value))
        elif action in ('prepare', 'bulk', 'restore'):
            self.pending_prepare = False
            if self.prepare_epoch == self.operation_epoch:
                self.confirm(value)
        elif action == 'execute':
            self.operation_epoch += 1
            self.controller.preview(None)
            self.statusBar().showMessage(tr('operation_done'))
            self.refresh()
        elif action == 'settings':
            self.settings = value
            self.theme.apply(value['theme'])
            self.statusBar().showMessage(tr('saved'))
        elif action == 'cancelled':
            self.pending_prepare = False
            self.statusBar().showMessage(tr('action_cancelled'))
            if value == 'execute':
                self.refresh()
        self.busy_changed(self.controller.busy)

    def error(self, action: str, detail: str) -> None:
        self.pending_prepare = False
        if action in ('execute', 'prepare', 'restore', 'bulk'):
            self.refresh()
        box = QMessageBox(self)
        box.setWindowTitle(tr('title'))
        box.setIcon(QMessageBox.Warning)
        box.setText(tr('error'))
        box.setInformativeText(tr(detail.split(':')[0]))
        box.setDetailedText(detail)
        box.open()

    def progress(self, value: ScanProgress) -> None:
        self.scan.status.setText(tr('progress', tr('phase_' + value.phase), value.discovered,
            value.processed, value.skipped, value.failed))
        for path, state in value.roots:
            for i, root in enumerate(self.roots):
                if Path(root) == Path(path):
                    self.scan.roots.item(i).setText(f'{root} · {tr("state_" + state)}')

    def busy_changed(self, busy: bool) -> None:
        available = not busy and not self.controller.closing
        self.scan.start.setEnabled(available and bool(self.roots))
        self.scan.cancel.setEnabled(busy)
        self.scan.progress.setRange(0, 0 if busy else 1)
        allowed = available and self.writable and self.status == 'complete'
        self.duplicates.prepare.setEnabled(allowed and self.controller.selection is not None)
        self.comparison.prepare.setEnabled(allowed and self.controller.selection is not None)
        self.duplicates.bulk.setEnabled(allowed and bool(self.session))
        self.history.restore.setEnabled(available and self.writable)

    def render_roots(self) -> None:
        self.scan.roots.clear()
        self.scan.roots.addItems(self.roots)
        self.busy_changed(self.controller.busy)

    def add_root(self) -> None:
        path = QFileDialog.getExistingDirectory(self, tr('add'), options=QFileDialog.DontUseNativeDialog)
        if path and path not in self.roots:
            self.roots.append(path)
            self.render_roots()
            self.controller.request('settings', {'roots': self.roots.copy()})

    def remove_root(self) -> None:
        row = self.scan.roots.currentRow()
        if row >= 0:
            self.roots.pop(row)
            self.render_roots()
            self.controller.request('settings', {'roots': self.roots.copy()})

    def reorder_root(self, direction: int) -> None:
        row = self.scan.roots.currentRow()
        target = row + direction
        if row >= 0 and 0 <= target < len(self.roots):
            self.roots[row], self.roots[target] = self.roots[target], self.roots[row]
            self.render_roots()
            self.scan.roots.setCurrentRow(target)
            self.controller.request('settings', {'roots': self.roots.copy()})

    def start_scan(self) -> None:
        if self.controller.busy or not self.roots:
            return
        self.invalidate_selection()
        self.scan.errors.clear()
        self.controller.request('scan', self.roots.copy())

    def cancel(self) -> None:
        self.operation_epoch += 1
        self.pending_prepare = False
        self.controller.cancel()
        if self.plan_dialog:
            self.plan_dialog.reject()

    def invalidate_selection(self) -> None:
        self.operation_epoch += 1
        self.controller.preview(None)
        self.selected_id = None
        self.comparison.left.reset()
        self.comparison.right.reset()

    def filter_changed(self) -> None:
        self.invalidate_selection()
        self.group_offset = 0
        self.query = replace(self.query, text=self.duplicates.search.text(), kind=self.duplicates.kind.currentData(),
                             keeper_id=None, offset=0)
        self.request_matches()
        if self.session:
            self.request_groups()

    def sort(self, column: int) -> None:
        name = self.duplicates.model.columns[column]
        self.query = replace(self.query, sort=name, descending=self.query.sort == name and not self.query.descending, offset=0)
        self.duplicates.table.horizontalHeader().setSortIndicator(column, Qt.DescendingOrder if self.query.descending else Qt.AscendingOrder)
        self.duplicates.table.horizontalHeader().setSortIndicatorShown(True)
        self.request_matches()

    def change_page(self, direction: int) -> None:
        target = self.query.offset + direction * 200
        if 0 <= target < self.total:
            self.query = replace(self.query, offset=target)
            self.request_matches()

    def groups_page(self, direction: int) -> None:
        target = self.group_offset + direction * 200
        if 0 <= target < self.group_total:
            self.group_offset = target
            self.request_groups()

    def group_changed(self, row: int) -> None:
        self.invalidate_selection()
        if row <= 0:
            self.query = replace(self.query, keeper_id=None, kind=self.duplicates.kind.currentData(), offset=0)
        else:
            group = self.group_rows[row - 1]
            self.query = replace(self.query, keeper_id=group.keeper_id, kind=group.kind, offset=0)
        self.request_matches()

    def selected(self, current: QModelIndex, previous: QModelIndex) -> None:
        if not current.isValid():
            return
        row = self.duplicates.model.rows[current.row()]
        self.operation_epoch += 1
        self.selected_id = row.id
        self.comparison.keep.setCurrentIndex(0)
        self.controller.preview(row)
        pair = row.match
        self.comparison.left.set_photo(pair.keep)
        self.comparison.right.set_photo(pair.dup)
        warnings = [tr('heuristic'), tr('xmp_possible')]
        if pair.keep.root != pair.dup.root:
            warnings.append(tr('cross_roots'))
        if pair.keep.is_raw or pair.dup.is_raw:
            warnings.append(tr('raw_warning'))
        if pair.kind.value == 'VISUAL':
            warnings.append(tr('visual_warning'))
        self.comparison.warning.setText('\n'.join(warnings))
        self.busy_changed(self.controller.busy)

    def preview_ready(self, value: tuple) -> None:
        for view, (image, error) in zip((self.comparison.left, self.comparison.right), value):
            view.set_image(image, error)

    def compare(self, *_: Any) -> None:
        self.navigation.setCurrentRow(3)

    def prepare_selected(self) -> None:
        row = self.controller.selection
        if not row or self.controller.busy or self.status != 'complete':
            return
        pair = row.match
        if self.comparison.keep.currentData():
            pair = Match(pair.kind, pair.dup, pair.keep, pair.ph_distance, pair.dh_distance)
        self.prepare('prepare', (pair, self.session))

    def keeper_changed(self, *_: Any) -> None:
        self.operation_epoch += 1
        if self.plan_dialog:
            self.plan_dialog.reject()

    def prepare_bulk(self) -> None:
        if self.session and not self.controller.busy:
            self.prepare('bulk', self.session)

    def prepare(self, action: str, payload: Any) -> None:
        self.prepare_epoch = self.operation_epoch
        self.pending_prepare = True
        self.controller.request(action, payload)

    def confirm(self, plan: Plan) -> None:
        if not plan.moves:
            QMessageBox.information(self, tr('plan'), tr('no_plan'))
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
            self.controller.request('execute', dialog.approval)
        if dialog:
            dialog.deleteLater()

    def restore(self) -> None:
        row = self.history.table.currentRow()
        if not self.controller.busy and 0 <= row < len(self.history_rows) and self.history_rows[row].restorable:
            self.prepare('restore', self.history_rows[row].id)

    def history_page(self, direction: int) -> None:
        target = self.history_offset + direction * 200
        if 0 <= target < self.history_total:
            self.history_offset = target
            self.controller.request('history', MatchQuery(sort='time', descending=True, offset=target))

    def errors_page(self, direction: int) -> None:
        target = self.error_offset + direction * 200
        if self.session and 0 <= target < self.error_total:
            self.error_offset = target
            self.controller.request('errors', (self.session, target))

    def theme_changed(self, *_: Any) -> None:
        self.theme.apply(self.preferences.theme.currentData())
        if self.settings:
            self.controller.request('settings', {'theme': self.preferences.theme.currentData()})

    def save_settings(self) -> None:
        self.controller.request('settings', {'theme': self.preferences.theme.currentData(),
            'phash_max': self.preferences.phash.value(), 'dhash_max': self.preferences.dhash.value()})

    def closeEvent(self, event: QCloseEvent) -> None:
        if self.finished:
            event.accept()
            return
        event.ignore()
        self.operation_epoch += 1
        if self.plan_dialog:
            self.plan_dialog.reject()
        self.setEnabled(False)
        self.statusBar().showMessage(tr('closing'))
        self.controller.close()

    def safe_closed(self) -> None:
        self.finished = True
        self.close()
