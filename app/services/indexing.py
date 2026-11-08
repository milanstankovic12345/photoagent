"""Incremental scanning independent of GUI, history and presentation."""
from __future__ import annotations

from dataclasses import asdict
import importlib.metadata
import json
import os
from pathlib import Path
from queue import Queue
import sqlite3
from threading import Event
import time
import uuid

from app.core.models import Cancelled, ScanSummary, SafetyError
from app.matching.indexed import match_index
from app.safety.paths import QUARANTINE, absolute, cancelled, check_path, identity, snapshot
from app.scanning.discovery import discover
from app.scanning.inspection import extract
from app.storage.index import Index


def pipeline_version() -> str:
    return 'oriented-rgb-880-320-phash8-dhash8-v1:' + ':'.join(
        importlib.metadata.version(n) for n in ('Pillow', 'ImageHash', 'rawpy', 'pillow-heif', 'numpy', 'scipy'))


def indexed_scan(index: Index, folders: list[str], updates: Queue, cancel: Event) -> ScanSummary:
    session = uuid.uuid4().hex
    db = index.db
    pipeline = pipeline_version()
    hits = decodes = hash_reads = hash_bytes = 0
    scan_seconds = match_seconds = 0.0
    start = time.perf_counter()
    state = 'complete'
    # Do not attach an already-set cancellation flag until intent is recorded.
    index.cancel = None
    with index.transaction():
        db.execute("INSERT INTO scan_sessions(id,state,started) VALUES(?,'running',?)", (session, time.time()))
    index.cancel = cancel
    db.set_progress_handler(lambda: int(cancel.is_set()), 1000)
    try:
        for rank, folder in enumerate(dict.fromkeys(folders)):
            cancelled(cancel)
            root_id = None
            path = str(folder)
            traversal_ok = True
            try:
                root = check_path(folder, allow_missing=True)
                path = str(root)
                if any(part.casefold() == QUARANTINE for part in root.parts):
                    raise SafetyError('quarantine_root')
                if not root.is_dir():
                    raise SafetyError('unavailable_root')
                original_id = identity(root)
                root_id = index.root(path, original_id)
                with index.transaction():
                    db.execute('INSERT INTO scan_session_roots VALUES(?,?,?,?,?)', (session, rank, root_id, path, 'running'))

                def error(name: str, exc: Exception) -> None:
                    nonlocal traversal_ok
                    traversal_ok = False
                    index.error(session, name, str(exc))

                for file in discover(root, cancel, error, spool=db):
                    cancelled(cancel)
                    try:
                        fid = identity(file)
                        file_path = str(absolute(file))
                        if index.seen(session, file_path, fid):
                            # A physically deduplicated file was still observed in this root.
                            with index.transaction():
                                db.execute('UPDATE photo_files SET last_seen=? WHERE root_id=? AND path_key=?',
                                           (session, root_id, os.path.normcase(file_path)))
                            continue
                        before = snapshot(file, cancel)
                        hash_reads += 1
                        hash_bytes += before.size
                        photo = index.cached(root_id, file_path, before, pipeline)
                        if photo is not None and photo.root_identity == original_id:
                            hits += 1
                        else:
                            photo = extract(file, root, before, cancel)
                            decodes += 1
                            hash_reads += 1
                            hash_bytes += photo.size
                        if identity(root) != original_id or photo.root_identity != original_id:
                            raise SafetyError('root_replaced')
                        index.save_photo(session, root_id, rank, photo, pipeline)
                    except (OSError, SafetyError, ValueError) as exc:
                        error(str(file), exc)
                    # Coalesce progress at the producer; UI is not an unbounded per-file queue.
                    if time.perf_counter() - getattr(index, '_last_progress', 0) >= .15:
                        count = db.execute('SELECT count(*) FROM scan_entries WHERE session_id=? AND photo IS NOT NULL', (session,)).fetchone()[0]
                        updates.put(('status', ('scan_progress', count)))
                        index._last_progress = time.perf_counter()
                if identity(root) != original_id:
                    raise SafetyError('root_replaced')
                with index.transaction():
                    db.execute('UPDATE scan_session_roots SET state=? WHERE session_id=? AND position=?',
                               ('complete' if traversal_ok else 'incomplete', session, rank))
                    if traversal_ok:
                        db.execute("UPDATE photo_files SET state='missing' WHERE root_id=? AND last_seen<>? AND state<>'moved'",
                                   (root_id, session))
            except (OSError, SafetyError) as exc:
                traversal_ok = False
                index.error(session, path, str(exc))
                with index.transaction():
                    db.execute('INSERT OR REPLACE INTO scan_session_roots VALUES(?,?,?,?,?)', (session, rank, root_id, path, 'unavailable'))
                    db.execute("UPDATE scan_roots SET state='unavailable' WHERE path_key=?", (os.path.normcase(path),))
            if not traversal_ok:
                state = 'incomplete'
        scan_seconds = time.perf_counter() - start
        if db.execute("SELECT 1 FROM scan_entries WHERE session_id=? AND error<>'' LIMIT 1", (session,)).fetchone():
            state = 'incomplete'
        cancelled(cancel)
        if state in ('complete', 'incomplete'):
            match_start = time.perf_counter()
            match_index(index, session, cancel)
            match_seconds = time.perf_counter() - match_start
        cancelled(cancel)
    except Cancelled:
        state = 'cancelled'
    except (sqlite3.Error, OSError, SafetyError):
        # Keep committed cache rows but never expose partial matching after failure.
        index.cancel = None
        db.set_progress_handler(None, 0)
        if cancel.is_set():
            state = 'cancelled'
        else:
            with index.transaction():
                db.execute("UPDATE scan_sessions SET state='failed',finished=? WHERE id=?", (time.time(), session))
                db.execute('DELETE FROM match_results WHERE session_id=?', (session,))
            raise
    finally:
        index.cancel = None
        db.set_progress_handler(None, 0)
    with index.transaction():
        if state not in ('complete', 'incomplete'):
            db.execute('DELETE FROM match_results WHERE session_id=?', (session,))
        db.execute("UPDATE scan_session_roots SET state=? WHERE session_id=? AND state='running'", (state, session))
        db.execute('UPDATE scan_sessions SET state=?,finished=? WHERE id=?', (state, time.time(), session))
    counts = db.execute("SELECT count(photo),sum(error<>'') FROM scan_entries WHERE session_id=?", (session,)).fetchone()
    pairs = db.execute("SELECT count(*),coalesce(sum(kind='EXACT'),0) FROM match_results WHERE session_id=?", (session,)).fetchone()
    summary = ScanSummary(session, state, counts[0], pairs[0], pairs[1], counts[1] or 0,
                          hits, decodes, hash_reads, hash_bytes, scan_seconds or time.perf_counter() - start, match_seconds)
    with index.transaction():
        db.execute('UPDATE scan_sessions SET metrics=? WHERE id=?', (json.dumps(asdict(summary)), session))
    return summary
