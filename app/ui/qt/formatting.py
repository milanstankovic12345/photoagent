"""Locale-aware display values. Paths, hashes and stored measurements stay literal."""
from __future__ import annotations

from PySide6.QtCore import QDateTime, QLocale

from app.i18n import Message
from app.ui.qt.localization import current_language, locale_for


class FormattedText(Message):
    """Retain the original measurement so open bindings can reformat it on switch."""

    def __new__(cls, kind: str, value: int | float) -> FormattedText:
        instance = str.__new__(cls, cls.format_value(kind, value, current_language()))
        instance.kind, instance.value = kind, value
        return instance

    def translated(self, language: str) -> str:
        return self.format_value(self.kind, self.value, language)

    @staticmethod
    def format_value(kind: str, value: int | float, language: str) -> str:
        locale = locale_for(language)
        if kind == 'size':
            amount = float(value)
            for unit in ('B', 'KiB', 'MiB', 'GiB', 'TiB'):
                if amount < 1024 or unit == 'TiB':
                    return locale.toString(amount, 'f', 0 if unit == 'B' else 1) + ' ' + unit
                amount /= 1024
        if kind == 'date':
            date = QDateTime.fromMSecsSinceEpoch(round(float(value) * 1000))
            return locale.toString(date, QLocale.ShortFormat)
        if kind == 'utc_date':
            date = QDateTime.fromMSecsSinceEpoch(round(value * 1000)).toUTC()
            # Keep the recorded second and explicit UTC used by the history UI.
            return (locale.toString(date.date(), QLocale.ShortFormat) + ' '
                    + locale.toString(date.time(), 'HH:mm:ss') + ' UTC')
        return locale.toString(int(value))


def size_text(value: int | float) -> Message:
    return FormattedText('size', value)


def number_text(value: int) -> Message:
    return FormattedText('number', value)


def date_text(value: int | float) -> Message:
    return FormattedText('date', value)
