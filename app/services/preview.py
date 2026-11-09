"""Preview preparation without SQLite, with fresh content validation on every request."""
from __future__ import annotations

from collections import OrderedDict
from threading import Event
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from PySide6.QtGui import QImage

from app.core.models import Photo, SafetyError
from app.safety.paths import snapshot
from app.scanning.decoder import decode
from app.services.indexing import pipeline_version


class PreviewService:
    def __init__(self, limit: int = 64 * 1024 * 1024) -> None:
        self.limit = limit
        self.cache = OrderedDict()
        self.bytes = 0

    def get(self, photo: Photo, cancel: Event, size: int = 2048) -> QImage:
        # QImage is reentrant; decoding PNG here keeps GUI event processing bounded.
        import base64
        from PySide6.QtGui import QImage
        before = snapshot(photo.path, cancel)
        if before != photo.snapshot:
            raise SafetyError('candidate_changed_review_again')
        key = (photo.path, before, size, 'preview-oriented-v1', pipeline_version())
        if key in self.cache:
            image = self.cache[key]
            if snapshot(photo.path, cancel) != before:
                del self.cache[key]
                self.bytes -= image.sizeInBytes()
                raise SafetyError('candidate_changed_review_again')
            self.cache.move_to_end(key)
            return image
        data = decode(photo.path, cancel, preview_size=size)
        image = QImage.fromData(base64.b64decode(data['preview']), 'PNG')
        if image.isNull():
            raise SafetyError('decoder_invalid_response')
        if snapshot(photo.path, cancel) != before:
            raise SafetyError('candidate_changed_review_again')
        cost = image.sizeInBytes()
        while self.cache and self.bytes + cost > self.limit:
            _, old = self.cache.popitem(last=False)
            self.bytes -= old.sizeInBytes()
        if cost <= self.limit:
            self.cache[key] = image
            self.bytes += cost
        return image
