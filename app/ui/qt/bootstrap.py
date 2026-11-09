from pathlib import Path
import sys
from PySide6.QtWidgets import QApplication
from app.ui.qt.window import MainWindow


def run(home: Path | None = None) -> int:
    application = QApplication(sys.argv[:1])
    application.setApplicationName('PhotoAgent')
    application.setOrganizationName('PhotoAgent')
    application.setStyle('Fusion')
    window = MainWindow(home)
    window.show()
    return application.exec()
