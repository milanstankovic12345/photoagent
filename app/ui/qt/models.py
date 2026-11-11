from pathlib import Path
from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt
from app.ui.qt.strings import tr
from app.ui.qt.localization import language_manager


class MatchModel(QAbstractTableModel):
    columns = ('name', 'kind', 'format', 'size', 'dimensions', 'path')

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.rows = ()
        self.retained_paths: set[str] = set()
        self.moving_paths: set[str] = set()
        language_manager().changed.connect(self.retranslate)

    def retranslate(self) -> None:
        self.headerDataChanged.emit(Qt.Horizontal, 0, len(self.columns) - 1)
        if self.rows:
            self.dataChanged.emit(self.index(0, 0), self.index(len(self.rows) - 1, len(self.columns) - 1))

    def set_choices(self, retained: set[str], moving: set[str]) -> None:
        self.retained_paths = retained
        self.moving_paths = moving
        if self.rows:
            self.dataChanged.emit(self.index(0, 0), self.index(len(self.rows) - 1, len(self.columns) - 1))

    def replace(self, rows: tuple) -> None:
        self.beginResetModel()
        self.rows = rows
        self.endResetModel()

    def rowCount(self, parent=QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self.rows)

    def columnCount(self, parent=QModelIndex()) -> int:
        return len(self.columns)

    def headerData(self, section: int, orientation: Qt.Orientation, role: int = Qt.DisplayRole) -> str | None:
        if role == Qt.DisplayRole and orientation == Qt.Horizontal:
            return tr(self.columns[section])

    def data(self, index: QModelIndex, role: int = Qt.DisplayRole) -> str | int | None:
        if not index.isValid():
            return None
        pair = self.rows[index.row()].match
        p = pair.dup
        if role == Qt.ToolTipRole:
            return p.path
        if role in (Qt.DisplayRole, Qt.AccessibleTextRole):
            status = tr('photo_retained') if p.path in self.retained_paths else tr('photo_proposed') if p.path in self.moving_paths else ''
            name = Path(p.path).name + (' · ' + status if status else '')
            kind = pair.kind.value
            return (name, tr(('filter_' if kind in ('EXACT', 'VISUAL') else 'classification_') + kind), p.image_format or p.ext,
                    p.size, f'{p.width} × {p.height}', p.path)[index.column()]
