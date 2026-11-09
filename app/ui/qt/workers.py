"""Services and SQLite are constructed, used and closed on one worker thread."""
from __future__ import annotations

import logging
from pathlib import Path
from threading import Event
from types import MappingProxyType
from typing import Any

from PySide6.QtCore import QObject, Signal, Slot

from app.services.application import Application
from app.services.preview import PreviewService
from app.core.models import Cancelled, Match

log = logging.getLogger(__name__)


def frozen(value: Any) -> Any:
    """Transfer immutable container snapshots; service objects never cross threads."""
    if isinstance(value, dict):
        return MappingProxyType({k: frozen(v) for k, v in value.items()})
    if isinstance(value, (list, tuple)):
        return tuple(frozen(v) for v in value)
    return value


class ServiceWorker(QObject):
    result = Signal(int, str, object)
    error = Signal(int, str, str)
    cancelled = Signal(int, str)
    progress = Signal(object)
    stopped = Signal()

    def __init__(self, home: Path) -> None:
        super().__init__()
        self.home = home
        self.service = None

    @Slot(int, str, object, object)
    def run(self, request: int, action: str, payload: Any, cancel: Event) -> None:
        try:
            if action == 'initialize':
                self.service = Application(self.home)
                journal, settings, issues = self.service.initialize()
                value = (settings, tuple(issues), journal.writable, journal.error)
            elif action == 'scan':
                value = self.service.scan_with_report(payload, None, cancel, progress=self.progress.emit)
            elif action == 'prepare':
                pair, session = payload
                value = self.service.prepare([pair], cancel, session=session)
            elif action == 'bulk':
                value = self.service.prepare_session(payload, cancel)
            elif action == 'restore':
                value = self.service.restore_plan(cancel, operation_id=payload)
            elif action == 'execute':
                value = self.service.execute(payload.plan, payload, cancel)
            elif action == 'matches':
                value = self.service.query_matches(*payload)
            elif action == 'groups':
                value = self.service.query_groups(*payload)
            elif action == 'settings':
                value = self.service.update_settings(payload)
            elif action == 'sources':
                value = self.service.sources(payload)
            elif action == 'errors':
                session, offset = payload
                value = tuple(self.service.index.errors(session, offset))
            elif action == 'reports':
                value = self.service.open_reports()
            elif action == 'dashboard':
                value = self.service.dashboard(payload)
            elif action == 'history':
                value = self.service.history(payload)
            else:
                raise ValueError('unknown_action')
            self.result.emit(request, action, frozen(value))
        except Cancelled:
            self.cancelled.emit(request, action)
        except Exception as exc:
            log.exception('qt_service_failure', extra={'action': action})
            self.error.emit(request, action, str(exc))

    @Slot()
    def close(self) -> None:
        try:
            if self.service:
                self.service.close()
        finally:
            self.stopped.emit()


class PreviewWorker(QObject):
    result = Signal(int, object)
    stopped = Signal()

    def __init__(self) -> None:
        super().__init__()
        self.service = PreviewService()

    @Slot(int, object, object)
    def run(self, request: int, pair: Match, cancel: Event) -> None:
        images = []
        for photo in (pair.keep, pair.dup):
            if cancel.is_set():
                return
            try:
                images.append((self.service.get(photo, cancel), ''))
            except Cancelled:
                return
            except Exception as exc:
                log.warning('qt_preview_failed', extra={'path': photo.path, 'reason': str(exc)})
                images.append((None, str(exc)))
        if not cancel.is_set():
            self.result.emit(request, tuple(images))

    @Slot()
    def close(self) -> None:
        self.service.cache.clear()
        self.stopped.emit()
