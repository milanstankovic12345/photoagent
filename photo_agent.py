"""PhotoAgent desktop entry point; domain services live in app/."""
from __future__ import annotations

import logging
import multiprocessing
import argparse

from app.services.preflight import check


def main() -> None:
    parser = argparse.ArgumentParser(description='PhotoAgent offline desktop')
    parser.add_argument('--ui', choices=('qt', 'tk'), default='qt')
    args = parser.parse_args()
    check(args.ui)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    if args.ui == 'qt':
        from app.ui.qt.bootstrap import run
        raise SystemExit(run())
    import tkinter as tk
    from app.ui.tk_app import PhotoApp

    root = tk.Tk()
    PhotoApp(root)
    root.mainloop()


if __name__ == "__main__":
    multiprocessing.freeze_support()
    main()
