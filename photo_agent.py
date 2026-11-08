"""PhotoAgent desktop entry point; domain services live in app/."""
from __future__ import annotations

import logging
import multiprocessing

from app.services.preflight import check


def main() -> None:
    check()
    import tkinter as tk
    from app.ui.tk_app import PhotoApp

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    root = tk.Tk()
    PhotoApp(root)
    root.mainloop()


if __name__ == "__main__":
    multiprocessing.freeze_support()
    main()
