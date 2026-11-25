"""Validate the installed payload before activating its shortcut."""
import hashlib
import json
import sys
from pathlib import Path


def main() -> None:
    root = Path(__file__).resolve().parent
    if Path(sys.executable).parent != root / ".runtime" or not sys.flags.isolated:
        raise RuntimeError("Expected isolated private interpreter")
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    for name, expected in manifest["files"].items():
        with (root / name).open("rb") as stream:
            if hashlib.file_digest(stream, "sha256").hexdigest() != expected:
                raise ValueError(f"Incorrect installed file: {name}")
    from app.services.preflight import check
    from PySide6.QtWidgets import QApplication
    import tkinter
    check()
    qt = QApplication([])
    if qt.platformName() != "windows":
        raise RuntimeError("Native Windows Qt platform required")
    tk = tkinter.Tk()
    tk.withdraw()
    tk.destroy()


if __name__ == "__main__":
    main()
