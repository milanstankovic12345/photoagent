"""Qt adapter for the shared EN/SR catalogs and live text bindings."""
from collections.abc import Iterable
from PySide6.QtWidgets import QApplication
from app.i18n import Message, STRINGS, joined, translate
from app.ui.qt.localization import current_language, language_manager

SR = STRINGS['sr_Latn']


class QtMessage(Message):
    """Use compiled Qt catalogs, retaining the shared non-Qt fallback/grammar."""

    @staticmethod
    def _translate(key: str, args: tuple[object, ...], language: str) -> str:
        return translate(key, args, language,
                         lookup=language_manager().lookup if QApplication.instance() else None)


def tr(key: str, *args: object) -> Message:
    return QtMessage(key, args, current_language())


def join_text(parts: Iterable[str], separator: str = '\n') -> Message:
    return joined(parts, current_language(), separator)


def error_text(detail: str) -> Message:
    key = detail.split(':', 1)[0]
    return tr(key if key in STRINGS['en'] else 'error')
