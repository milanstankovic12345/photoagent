"""Windowed entry point for the installed application."""
import ctypes
import os
from pathlib import Path
import traceback


if __name__ == "__main__":
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.CreateMutexW.restype = ctypes.c_void_p
    mutex = kernel.CreateMutexW(None, False, "PhotoAgent.Installed.Running")
    try:
        if not mutex:
            raise ctypes.WinError(ctypes.get_last_error())
        from photo_agent import main
        main()
    except Exception:
        detail = traceback.format_exc()
        try:
            path = Path(os.environ["LOCALAPPDATA"]) / "PhotoAgent" / "startup.log"
            path.parent.mkdir(exist_ok=True, parents=True)
            path.write_text(detail, encoding="utf-8")
            detail = str(path)
        except OSError:
            pass
        ctypes.windll.user32.MessageBoxW(None, "PhotoAgent startup error / Greška pri pokretanju\n" + detail,
                                         "PhotoAgent", 16)
        raise SystemExit(1)
