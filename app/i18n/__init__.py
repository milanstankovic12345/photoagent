"""Local text catalogs. No Qt dependency; legacy Tk callers default to Serbian."""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Callable, Iterable

log = logging.getLogger(__name__)
LANGUAGES = ('en', 'sr_Latn')
STRINGS: dict[str, dict[str, str]] = {
    language: json.loads(Path(__file__).with_name(language + '.json').read_text(encoding='utf-8'))
    for language in LANGUAGES
}


def translate(key: str, args: tuple[object, ...] = (), language: str = 'en', *,
              lookup: Callable[[str, str], str] | None = None) -> str:
    """Unknown languages use English; missing keys/format errors stay readable."""
    catalog = STRINGS.get(language, STRINGS['en'])
    # Count-first group labels stay readable on small cards. Serbian needs the
    # 1 / 2–4 / other forms, including the 11–14 exception (21 / 22 / 25).
    if key == 'group_summary' and args and type(args[0]) is int:
        count = abs(args[0])
        if language == 'sr_Latn':
            form = ('one' if count % 10 == 1 and count % 100 != 11 else
                    'few' if 2 <= count % 10 <= 4 and not 12 <= count % 100 <= 14 else 'other')
        else:
            form = 'one' if count == 1 else 'other'
        key += '_' + form
    value = (lookup(key, language) if lookup else None) or catalog.get(key, STRINGS['en'].get(key))
    if value is None:
        log.warning('translation_missing', extra={'translation_key': key, 'language': language})
        return catalog.get('message_unavailable', STRINGS['en']['message_unavailable'])
    try:
        return value.format(*(render(arg, language) for arg in args))
    except (IndexError, KeyError, ValueError):
        log.warning('translation_format_failed', extra={'translation_key': key, 'language': language})
        return catalog.get('message_unavailable', STRINGS['en']['message_unavailable'])


def tr(key: str, *args: object, language: str = 'sr_Latn') -> str:
    return translate(key, args, language)


class Message(str):
    """Readable text plus a stable recipe for live Qt retranslation.

    Arguments are captured when displayed, never recovered by parsing translated
    text. Paths and hashes stay literal even when they resemble a catalog entry.
    """
    _translate = staticmethod(translate)

    def __new__(cls, key: str | None, args: tuple[object, ...], language: str,
                separator: str = '') -> Message:
        value = (cls._translate(key, args, language) if key is not None
                 else separator.join(str(render(part, language)) for part in args))
        instance = super().__new__(cls, value)
        instance.key, instance.args, instance.separator = key, args, separator
        return instance

    def translated(self, language: str) -> str:
        return (self._translate(self.key, self.args, language) if self.key is not None
                else self.separator.join(str(render(part, language)) for part in self.args))


def render(value: object, language: str) -> object:
    if isinstance(value, Message):
        return value.translated(language)
    if isinstance(value, (list, tuple)):
        return [render(item, language) for item in value]
    return value


def joined(parts: Iterable[str], language: str, separator: str = '\n') -> Message:
    return Message(None, tuple(parts), language, separator)
