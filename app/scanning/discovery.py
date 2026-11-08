"""Safe deterministic traversal; errors prevent absence reconciliation."""
from __future__ import annotations

import os
from pathlib import Path
import sqlite3
from threading import Event
from typing import Callable, Iterator
from app.core.models import SafetyError

from app.safety.paths import QUARANTINE, cancelled, check_path
from app.scanning.decoder import IMAGES, RAWS

SKIP_DIRS = {QUARANTINE, "$recycle.bin", "system volume information", ".git", "__pycache__",
             "windows", "program files", "program files (x86)"}


def discover(root: Path, cancel: Event, error: Callable[[str, Exception], None], *,
             spool: sqlite3.Connection | None = None) -> Iterator[Path]:
    if spool is not None:
        yield from _disk_walk(root, cancel, error, spool)
        return
    for directory, dirs, files in os.walk(root, followlinks=False,
                                          onerror=lambda exc: error(str(root), exc)):
        cancelled(cancel)
        check_path(directory)
        safe_dirs = []
        for name in sorted(dirs):
            cancelled(cancel)
            if name.casefold() in SKIP_DIRS:
                continue
            path = Path(directory) / name
            try:
                check_path(path)
                safe_dirs.append(name)
            except (OSError, SafetyError) as exc:
                error(str(path), exc)
        dirs[:] = safe_dirs
        for name in sorted(files):
            cancelled(cancel)
            path = Path(directory) / name
            if path.suffix.lower() in IMAGES | RAWS:
                yield path


def _disk_walk(root: Path, cancel: Event, error: Callable[[str, Exception], None],
               db: sqlite3.Connection) -> Iterator[Path]:
    """Depth-first sorted walk without retaining a large directory listing in Python.

    The spool is SQLite TEMP storage, outside the selected photo roots. Directory
    entries are consumed with scandir; only the current path crosses the boundary.
    """
    db.execute('DROP TABLE IF EXISTS temp.walk_pending')
    db.execute('DROP TABLE IF EXISTS temp.walk_entries')
    db.execute('CREATE TEMP TABLE walk_pending(id INTEGER PRIMARY KEY AUTOINCREMENT,path TEXT NOT NULL)')
    db.execute('CREATE TEMP TABLE walk_entries(name TEXT PRIMARY KEY,directory INTEGER NOT NULL)')
    db.execute('INSERT INTO walk_pending(path) VALUES(?)', (str(root),))
    while row := db.execute('SELECT id,path FROM walk_pending ORDER BY id DESC LIMIT 1').fetchone():
        cancelled(cancel)
        directory = check_path(row['path'])
        db.execute('DELETE FROM walk_pending WHERE id=?', (row['id'],))
        db.execute('DELETE FROM walk_entries')
        try:
            with os.scandir(directory) as entries:
                for entry in entries:
                    cancelled(cancel)
                    try:
                        if entry.name.casefold() in SKIP_DIRS:
                            continue
                        path = check_path(entry.path)
                        is_dir = entry.is_dir(follow_symlinks=False)
                        if is_dir or path.suffix.lower() in IMAGES | RAWS:
                            db.execute('INSERT INTO walk_entries VALUES(?,?)', (entry.name, int(is_dir)))
                    except (OSError, SafetyError) as exc:
                        error(entry.path, exc)
        except OSError as exc:
            error(str(directory), exc)
            continue
        # Push in reverse order so the next pop matches os.walk's sorted DFS order.
        for child in db.execute('SELECT name FROM walk_entries WHERE directory=1 ORDER BY name DESC'):
            db.execute('INSERT INTO walk_pending(path) VALUES(?)', (str(directory / child[0]),))
        for file in db.execute('SELECT name FROM walk_entries WHERE directory=0 ORDER BY name'):
            cancelled(cancel)
            yield directory / file[0]
