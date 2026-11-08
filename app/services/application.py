"""Application use cases. The desktop adapter owns dialogs, never storage."""
from __future__ import annotations

from functools import lru_cache
import logging
import os
from pathlib import Path
from queue import Queue
import sqlite3
from tempfile import TemporaryDirectory
from threading import Event
from typing import Callable, Iterable

from app.core.models import Approval, Cancelled, Match, Plan, SafetyError, ScanSummary
from app.safety.journal import Journal
from app.safety.operations import Operations, make_plan
from app.safety.paths import check_path, snapshot
from app.scanning.decoder import decode
from app.scanning.inspection import extract
from app.services.indexing import indexed_scan
from app.services.reports import make_report
from app.services.state import load_state, save_state
from app.storage.index import Index, PAGE_SIZE

log = logging.getLogger(__name__)


class Application:
    def __init__(self, home: Path, *, index_path: Path | None = None) -> None:
        self.home = home
        self.index_path = index_path or home / '.photo_agent_index.sqlite3'
        self.index: Index | None = None
        self.journal: Journal | None = None
        self.operations: Operations | None = None
        self.temporary: TemporaryDirectory | None = None
        self.index_warning = ''

    def initialize(self) -> tuple[Journal, dict, list[str]]:
        self.index_warning = ''
        self.journal = Journal(self.home / '.photo_agent_operations')
        self.operations = Operations(self.journal)
        issues = []
        try:
            state = load_state(self.home / '.photo_agent_state.json')
            if self.journal.writable:
                self.journal.import_legacy(self.home / '.photo_agent_state.json')
                issues = self.operations.recover()
        except (OSError, ValueError, TypeError, KeyError, SafetyError) as exc:
            self.journal.error = str(exc)
            self.journal.writable = False
            state = {'roots': [], 'moves': []}
            issues.append(str(exc))
        try:
            self.index = Index(self.index_path)
        except (sqlite3.Error, OSError, SafetyError) as exc:
            self.index_warning = f'index_temporary: {exc}'
            log.warning('index_fallback', extra={'reason': str(exc)})
            # Keep the original DB and sidecars untouched. Only this temp index is disposable.
            self.temporary = TemporaryDirectory(prefix='.photoagent-index-', dir=self.home)
            self.index = Index(Path(self.temporary.name) / 'index.sqlite3')
        self._sync_history()
        return self.journal, state, issues

    def _sync_history(self) -> None:
        if self.index is None or not self.journal.writable:
            return
        try:
            self.index.project_history(iter(self.journal.records()))
        except (sqlite3.Error, OSError, ValueError, SafetyError) as exc:
            # Projection failure must not reinterpret an already committed operation.
            self.index_warning = f'index_history_projection: {exc}'
            log.exception('index_history_projection_failed')

    def save_settings(self, value: dict) -> None:
        with self.journal._guard:
            self.journal.require_writer()
            save_state(self.home / '.photo_agent_state.json', value)

    def scan(self, folders: list[str], updates: Queue, cancel: Event) -> ScanSummary:
        return indexed_scan(self.index, folders, updates, cancel)

    def scan_with_report(self, folders: list[str], updates: Queue, cancel: Event,
                         report_writer: Callable = make_report) -> tuple:
        result = self.scan(folders, updates, cancel)
        report, error = None, ''
        try:
            report = report_writer(self.index.iter_pairs(result.session_id), self.index.iter_errors(result.session_id),
                                   self.home / 'PhotoAgentReports')
        except OSError as exc:
            error = str(exc)
        return result, report, error, self.page(result.session_id, 0), self.index.errors(result.session_id), self.index_warning

    def page(self, session: str, offset: int) -> tuple[list, list, int]:
        return (self.index.pairs(session, offset), self.index.photos(session, offset),
                self.index.db.execute('SELECT count(*) FROM match_results WHERE session_id=?', (session,)).fetchone()[0])

    def previews(self, pair: Match, cancel: Event) -> list[tuple[dict | None, str]]:
        result = []
        for photo in (pair.keep, pair.dup):
            try:
                result.append((decode(photo.path, cancel), ''))
            except (SafetyError, OSError, Cancelled) as exc:
                result.append((None, str(exc)))
        return result

    def recover(self, cancel: Event) -> None:
        issues = self.operations.recover(cancel)
        self._sync_history()
        if issues:
            raise SafetyError('recovery_blocked: ' + '\n'.join(issues))

    def prepare(self, pairs: Iterable[Match], cancel: Event, *, bulk: bool = False,
                session: str | None = None) -> Plan:
        if session is not None:
            row = self.index.db.execute('SELECT state FROM scan_sessions WHERE id=?', (session,)).fetchone()
            if row is None or row[0] != 'complete':
                raise SafetyError('incomplete_scan')
        self.recover(cancel)

        @lru_cache(maxsize=64)
        def fresh(photo):
            path, root = check_path(photo.path), check_path(photo.root)
            before = snapshot(path, cancel)
            if before != photo.snapshot:
                raise SafetyError('candidate_changed_review_again')
            actual = extract(path, root, before, cancel)
            if actual.root_identity != photo.root_identity:
                raise SafetyError('root_replaced')
            return actual

        def verified():
            for pair in pairs:
                # Derive RAW/decoded flags and hashes from files, not cache eligibility.
                yield Match(pair.kind, fresh(pair.keep), fresh(pair.dup), pair.ph_distance, pair.dh_distance)
        return make_plan(verified(), bulk=bulk, cancel=cancel)

    def prepare_session(self, session: str, cancel: Event) -> Plan:
        row = self.index.db.execute('SELECT state FROM scan_sessions WHERE id=?', (session,)).fetchone()
        if row is None or row[0] != 'complete':
            raise SafetyError('incomplete_scan')
        return self.prepare(self.index.iter_pairs(session, exact=True), cancel, bulk=True, session=session)

    def restore_plan(self, cancel: Event) -> Plan:
        self.recover(cancel)
        return self.operations.restore_plan(cancel)

    def execute(self, plan: Plan, approval: Approval, cancel: Event) -> tuple[str, ...]:
        try:
            return self.operations.execute(plan, approval, cancel)
        finally:
            # Even a partial native/journal failure invalidates affected dependencies.
            try:
                self.index.invalidate({p for m in plan.moves for p in (m.source, m.destination)})
            except (sqlite3.Error, OSError) as exc:
                self.index_warning = f'index_invalidation: {exc}'
                log.exception('index_invalidation_failed')
            self._sync_history()

    def open_reports(self) -> None:
        import subprocess
        import sys
        directory = check_path(self.home / 'PhotoAgentReports', allow_missing=True)
        directory.mkdir(parents=True, exist_ok=True)
        if sys.platform == 'win32':
            os.startfile(str(directory))
        else:
            subprocess.Popen(['xdg-open', str(directory)])

    def close(self) -> None:
        if self.index:
            self.index.close()
        if self.journal:
            self.journal.close()
        if self.temporary:
            self.temporary.cleanup()
            self.temporary = None
