"""Read-only runtime checks shared by both launchers."""
from __future__ import annotations

import importlib
from importlib.metadata import version
import sys

REQUIRED = {"Pillow": ("PIL", 11, 14), "ImageHash": ("imagehash", 4, 5),
            "rawpy": ("rawpy", 0, 1), "pillow-heif": ("pillow_heif", 1, 2)}


def check(ui: str = 'qt') -> None:
    if sys.version_info < (3, 12):
        raise RuntimeError("Python >= 3.12 required")
    if ui not in ('qt', 'tk'):
        raise ValueError('invalid_ui')
    if ui == 'tk':
        importlib.import_module("tkinter")
    else:
        importlib.import_module('PySide6.QtWidgets')
        if not (6, 8) <= tuple(int(p) for p in version('PySide6').split('.')[:2]) < (7, 0):
            raise RuntimeError('PySide6 >= 6.8, < 7 required')
    for name, (module, low, high) in REQUIRED.items():
        importlib.import_module(module)
        parts = tuple(int(p) for p in version(name).split(".")[:2])
        if not low <= parts[0] < high:
            raise RuntimeError(f"Unsupported dependency: {name}")
        if name == "rawpy" and not (0, 25) <= parts < (0, 29):
            raise RuntimeError("rawpy >= 0.25, < 0.29 required")
        if name == "ImageHash" and parts < (4, 3):
            raise RuntimeError("ImageHash >= 4.3 required")


if __name__ == "__main__":
    try:
        import argparse
        parser = argparse.ArgumentParser()
        parser.add_argument('--ui', choices=('qt', 'tk'), default='qt')
        check(parser.parse_args().ui)
    except (ImportError, RuntimeError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(1)
