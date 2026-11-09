"""Bindings update presentation only, without rebuilding widgets or domain plans."""
from __future__ import annotations

from typing import TypeVar

from PySide6.QtCore import QLocale, QObject, QSignalBlocker, Signal, Slot
from PySide6.QtWidgets import QApplication, QComboBox, QWidget

from app.i18n import LANGUAGES, Message, render
from app.ui.qt.qt_translations import FrameworkTranslator

Widget = TypeVar('Widget', bound=QWidget)


class LanguageManager(QObject):
    changed = Signal()

    def __init__(self, parent: QObject) -> None:
        super().__init__(parent)
        self.language = 'en'
        self.apply_locale()
        self.framework = FrameworkTranslator(self)
        QApplication.installTranslator(self.framework)

    def set_language(self, language: str) -> None:
        language = language if language in LANGUAGES else 'en'
        if language != self.language:
            self.language = language
            self.apply_locale()
            # Qt sends LanguageChange to open standard dialogs and context menus.
            QApplication.removeTranslator(self.framework)
            QApplication.installTranslator(self.framework)
            self.changed.emit()

    def apply_locale(self) -> None:
        locale = QLocale('sr_Latn_RS' if self.language == 'sr_Latn' else 'en_US')
        QLocale.setDefault(locale)
        for window in QApplication.topLevelWidgets():
            window.setLocale(locale)


def language_manager() -> LanguageManager:
    application = QApplication.instance()
    if application is None:
        raise RuntimeError('QApplication is required for Qt localization')
    if not hasattr(application, '_photoagent_languages'):
        application._photoagent_languages = LanguageManager(application)
    return application._photoagent_languages


def current_language() -> str:
    return language_manager().language if QApplication.instance() else 'en'


class TextBindings(QObject):
    def __init__(self, target: QObject) -> None:
        super().__init__(target)
        self.target = target
        self.values: dict[tuple[str, tuple], object] = {}
        language_manager().changed.connect(self.refresh)

    @Slot()
    def refresh(self) -> None:
        with QSignalBlocker(self.target):
            for (setter, prefix), value in self.values.items():
                bars = (self.target.horizontalScrollBar(), self.target.verticalScrollBar()) if setter == 'setPlainText' else ()
                positions = [bar.value() for bar in bars]
                getattr(self.target, setter)(*prefix, render(value, language_manager().language))
                for bar, position in zip(bars, positions):
                    bar.setValue(position)


def set_text(target: QObject, value: str | list[str], setter: str = 'setText', *prefix: object) -> None:
    """Assign a string/list and retain its recipe until replaced or cleared."""
    binding = getattr(target, '_photoagent_texts', None)
    translated = isinstance(value, Message) or isinstance(value, (list, tuple)) and any(isinstance(v, Message) for v in value)
    if binding is None and translated:
        binding = target._photoagent_texts = TextBindings(target)
    if binding:
        if translated:
            binding.values[(setter, prefix)] = value
        else:
            binding.values.pop((setter, prefix), None)
    getattr(target, setter)(*prefix, render(value, language_manager().language))


def text_of(target: QObject, setter: str = 'setText') -> str:
    binding = getattr(target, '_photoagent_texts', None)
    if binding and (setter, ()) in binding.values:
        return binding.values[(setter, ())]
    return target.text()


def add_item(combo: QComboBox, text: Message, data: object = None) -> None:
    index = combo.count()
    combo.addItem(str(text), data)
    set_text(combo, text, 'setItemText', index)


def with_text(widget: Widget, text: str) -> Widget:
    set_text(widget, text)
    return widget
