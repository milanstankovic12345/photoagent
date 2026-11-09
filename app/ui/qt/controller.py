from __future__ import annotations

from threading import Event
from pathlib import Path
from typing import Any
from PySide6.QtCore import QObject, QThread, Signal, Slot
from app.core.queries import MatchRow
from app.ui.qt.workers import ServiceWorker, PreviewWorker


class Controller(QObject):
    dispatch = Signal(int, str, object, object)
    preview_dispatch = Signal(int, object, object)
    stop_service = Signal()
    stop_preview = Signal()
    result = Signal(str, object)
    error = Signal(str, str)
    preview_ready = Signal(object)
    progress = Signal(object)
    busy_changed = Signal(bool)
    closed = Signal()

    def __init__(self, home: Path, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.sequence = 0
        self.latest = {}
        self.pending = set()
        self.busy = False
        self.closing = False
        self.cancel_event = Event()
        self.preview_cancel = Event()
        self.preview_id = 0
        self.session = ''
        self.selection = None
        self.threads = []
        self.worker = ServiceWorker(home)
        self.preview_worker = PreviewWorker()
        for worker, stop in ((self.worker, self.stop_service), (self.preview_worker, self.stop_preview)):
            thread = QThread(self)
            worker.moveToThread(thread)
            stop.connect(worker.close)
            worker.stopped.connect(thread.quit)
            worker.stopped.connect(worker.deleteLater)
            thread.finished.connect(self._finished)
            self.threads.append(thread)
            thread.start()
        self.dispatch.connect(self.worker.run)
        self.preview_dispatch.connect(self.preview_worker.run)
        self.worker.result.connect(self._result)
        self.worker.error.connect(self._error)
        self.worker.cancelled.connect(self._cancelled)
        self.worker.progress.connect(self.progress)
        self.preview_worker.result.connect(self._preview)

    def request(self, action: str, payload: Any = None) -> None:
        if self.closing:
            return
        self.sequence += 1
        self.latest[action] = self.sequence
        self.pending.add(self.sequence)
        if not self.busy:
            self.cancel_event = Event()
            self.busy = True
            self.busy_changed.emit(True)
        self.dispatch.emit(self.sequence, action, payload, self.cancel_event)

    def cancel(self) -> None:
        self.cancel_event.set()
        self.preview_cancel.set()

    def preview(self, row: MatchRow | None) -> None:
        self.preview_cancel.set()
        self.preview_cancel = Event()
        self.preview_id += 1
        self.selection = row
        if row:
            self.preview_dispatch.emit(self.preview_id, row.match, self.preview_cancel)

    def _settle(self, request: int) -> None:
        self.pending.discard(request)
        if not self.pending:
            self.busy = False
            self.busy_changed.emit(False)

    @Slot(int, str, object)
    def _result(self, request: int, action: str, value: Any) -> None:
        self._settle(request)
        if not self.closing and self.latest.get(action) == request:
            self.result.emit(action, value)

    @Slot(int, str, str)
    def _error(self, request: int, action: str, detail: str) -> None:
        self._settle(request)
        if not self.closing and self.latest.get(action) == request:
            self.error.emit(action, detail)

    @Slot(int, str)
    def _cancelled(self, request: int, action: str) -> None:
        self._settle(request)
        if not self.closing and self.latest.get(action) == request:
            self.result.emit('cancelled', action)

    @Slot(int, object)
    def _preview(self, request: int, value: Any) -> None:
        if request == self.preview_id and not self.closing:
            self.preview_ready.emit(value)

    def close(self) -> None:
        if self.closing:
            return
        self.closing = True
        self.cancel()
        self.preview_id += 1
        self.stop_service.emit()
        self.stop_preview.emit()

    @Slot()
    def _finished(self) -> None:
        if all(not t.isRunning() for t in self.threads):
            self.closed.emit()
