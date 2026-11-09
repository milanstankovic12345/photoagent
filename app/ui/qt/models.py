from pathlib import Path
from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt
from app.ui.qt.strings import tr


class MatchModel(QAbstractTableModel):
    columns = ('name', 'kind', 'format', 'size', 'dimensions', 'path')

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.rows = ()

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
        if role in (Qt.DisplayRole, Qt.ToolTipRole):
            return (Path(p.path).name, pair.kind.value, p.image_format or p.ext,
                    p.size, f'{p.width} × {p.height}', p.path)[index.column()]
