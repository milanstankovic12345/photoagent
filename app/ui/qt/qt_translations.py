"""Qt framework source strings mapped into the same catalog as application text.

PySide6 does not ship a Serbian Latin qtbase catalog in the tested distribution.
This small QTranslator covers the framework controls used by PhotoAgent; it does
not maintain a second .ts/.qm copy of application messages.
"""
from __future__ import annotations

from typing import TYPE_CHECKING
from PySide6.QtCore import QTranslator
from app.i18n import translate

if TYPE_CHECKING:
    from app.ui.qt.localization import LanguageManager

QT_KEYS = {
    'QFileDialog': {
        '&Choose': 'file_choose', '&Look in:': 'file_look_in', '&Open': 'qt_open',
        'File &name:': 'file_name', 'Directory:': 'file_name', 'Files of &type:': 'file_type',
        'Back': 'file_back', 'Go back': 'file_back', 'Forward': 'file_forward', 'Go forward': 'file_forward',
        'Parent Directory': 'file_parent', 'Go to the parent directory': 'file_parent',
        '&New Folder': 'file_new_folder', 'Create New Folder': 'file_new_folder',
        'Create a New Folder': 'file_new_folder',
        'List View': 'file_list', 'Change to list view mode': 'file_list',
        'Detail View': 'file_detail', 'Change to detail view mode': 'file_detail',
        'All Files (*)': 'qt_all_files', 'Directories': 'qt_directories', 'Files': 'qt_files',
        'Show ': 'qt_show', 'Show &hidden files': 'qt_hidden', 'Sidebar': 'qt_sidebar',
        'List of places and bookmarks': 'qt_places', '&Rename': 'qt_rename', '&Delete': 'qt_delete',
        'New Folder': 'file_new_folder', 'Find Directory': 'file_choose',
        'Directory not found.\nPlease verify the correct directory name was given.': 'qt_directory_missing',
        '%1\nDirectory not found.\nPlease verify the correct directory name was given.': 'qt_directory_missing_named',
        'File not found.\nPlease verify the correct file name was given.': 'qt_file_missing',
    },
    'QFileSystemModel': {
        'Name': 'name', 'Size': 'file_size', 'Type': 'file_type_header',
        'Date Modified': 'file_date', 'My Computer': 'file_computer', 'Computer': 'file_computer',
        '%1 bytes': 'qt_bytes', '%1 KB': 'qt_kb', '%1 MB': 'qt_mb', '%1 GB': 'qt_gb', '%1 TB': 'qt_tb',
    },
    'QAbstractFileIconProvider': {'Drive': 'qt_drive', 'File Folder': 'file_folder', 'File': 'qt_file', 'Shortcut': 'qt_shortcut'},
    'QPlatformTheme': {
        'Cancel': 'cancel', 'Close': 'close', 'OK': 'qt_ok', 'Open': 'qt_open',
        'Yes': 'yes', 'No': 'no', 'Save': 'qt_save', 'Restore Defaults': 'qt_defaults',
    },
    'QWidgetTextControl': {
        '&Undo': 'qt_undo', '&Redo': 'qt_redo', 'Cu&t': 'qt_cut', '&Copy': 'qt_copy',
        '&Paste': 'qt_paste', 'Delete': 'qt_delete', 'Select All': 'qt_select_all',
        'Copy &Link Location': 'qt_copy_link',
    },
    'QLineEdit': {
        '&Undo': 'qt_undo', '&Redo': 'qt_redo', 'Cu&t': 'qt_cut', '&Copy': 'qt_copy',
        '&Paste': 'qt_paste', 'Delete': 'qt_delete', 'Select All': 'qt_select_all',
    },
    'QAbstractSpinBox': {'&Step up': 'qt_step_up', 'Step &down': 'qt_step_down', '&Select All': 'qt_select_all'},
    'QMessageBox': {'Show Details...': 'technical_details', 'Hide Details...': 'hide_details'},
}


class FrameworkTranslator(QTranslator):
    def __init__(self, manager: LanguageManager) -> None:
        super().__init__(manager)
        self.manager = manager

    def isEmpty(self) -> bool:
        return False

    def translate(self, context: str, source: str, disambiguation: str | None = None, n: int = -1) -> str:
        key = QT_KEYS.get(context, {}).get(source)
        return translate(key, language=self.manager.language) if key else ''
