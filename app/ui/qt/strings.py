"""Qt adapter for the shared EN/SR catalogs and live text bindings."""
from collections.abc import Iterable
from app.i18n import Message, STRINGS, joined
from app.ui.qt.localization import current_language

SR = STRINGS['sr_Latn']


def tr(key: str, *args: object) -> Message:
    return Message(key, args, current_language())


def join_text(parts: Iterable[str], separator: str = '\n') -> Message:
    return joined(parts, current_language(), separator)


def error_text(detail: str) -> Message:
    key = detail.split(':', 1)[0]
    return tr(key if key in STRINGS['en'] else 'error')
