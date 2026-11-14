"""The only Qt photo launch boundary. Never interpret a path as a command/URL."""
import logging

from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices

log = logging.getLogger(__name__)


class DesktopViewer:
    def open_photo(self, path: str) -> bool:
        # True means the OS accepted the request, not that an image was shown.
        try:
            accepted = QDesktopServices.openUrl(QUrl.fromLocalFile(path))
        except (OSError, RuntimeError, ValueError):
            log.exception('photo_launch_failed', extra={'path': path})
            raise
        if accepted:
            log.info('photo_launch_requested', extra={'path': path})
        else:
            log.warning('photo_launch_rejected', extra={'path': path})
        return accepted
