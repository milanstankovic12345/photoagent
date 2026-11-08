from __future__ import annotations

from contextlib import contextmanager
from dataclasses import asdict
import hashlib
import json
import logging
import os
from pathlib import Path
import sqlite3
from threading import Event
import time
from typing import Iterator
import uuid

from app.core.models import Identity, Kind, Match, Photo, SafetyError
from app.safety.journal import photo_from
from app.safety.paths import cancelled, check_path, identity

SCHEMA_VERSION = 1
PAGE_SIZE = 200
log = logging.getLogger(__name__)
SQL = (
    """CREATE TABLE scan_roots (
        id INTEGER PRIMARY KEY, path TEXT NOT NULL, path_key TEXT NOT NULL,
        device TEXT NOT NULL, inode TEXT NOT NULL, state TEXT NOT NULL,
        UNIQUE(path_key,device,inode))""",
    """CREATE TABLE scan_sessions (
        id TEXT PRIMARY KEY, state TEXT NOT NULL CHECK(state IN
        ('running','complete','incomplete','cancelled','interrupted','invalidated','failed')),
        started REAL NOT NULL, finished REAL, metrics TEXT NOT NULL DEFAULT '{}')""",
    """CREATE TABLE scan_session_roots (
        session_id TEXT NOT NULL REFERENCES scan_sessions(id), position INTEGER NOT NULL,
        root_id INTEGER REFERENCES scan_roots(id), path TEXT NOT NULL,
        state TEXT NOT NULL, PRIMARY KEY(session_id,position))""",
    """CREATE TABLE photo_files (
        id INTEGER PRIMARY KEY, root_id INTEGER NOT NULL REFERENCES scan_roots(id),
        path TEXT NOT NULL, path_key TEXT NOT NULL, device TEXT NOT NULL, inode TEXT NOT NULL,
        size INTEGER NOT NULL CHECK(size>=0), mtime_ns INTEGER NOT NULL, ctime_ns INTEGER NOT NULL,
        sha256 TEXT NOT NULL CHECK(length(sha256)=64), snapshot TEXT NOT NULL,
        state TEXT NOT NULL CHECK(state IN ('present','missing','moved','error','stale')),
        error TEXT NOT NULL, last_seen TEXT NOT NULL REFERENCES scan_sessions(id),
        UNIQUE(root_id,path_key))""",
    "CREATE INDEX files_identity ON photo_files(root_id,device,inode,sha256)",
    "CREATE INDEX files_seen ON photo_files(root_id,last_seen,state)",
    """CREATE TABLE image_fingerprints (
        file_id INTEGER PRIMARY KEY REFERENCES photo_files(id), pipeline TEXT NOT NULL,
        payload TEXT NOT NULL, checksum TEXT NOT NULL CHECK(length(checksum)=64))""",
    """CREATE TABLE scan_entries (
        id INTEGER PRIMARY KEY, session_id TEXT NOT NULL REFERENCES scan_sessions(id),
        file_id INTEGER REFERENCES photo_files(id), path TEXT NOT NULL, path_key TEXT NOT NULL,
        device TEXT, inode TEXT, photo TEXT, error TEXT NOT NULL DEFAULT '',
        rank INTEGER NOT NULL DEFAULT 0, size INTEGER, sha256 TEXT,
        folded TEXT NOT NULL, phash TEXT NOT NULL DEFAULT '', raw INTEGER NOT NULL DEFAULT 0,
        pixels INTEGER NOT NULL DEFAULT 0, format_rank INTEGER NOT NULL DEFAULT 0,
        UNIQUE(session_id,path_key))""",
    "CREATE UNIQUE INDEX entries_identity ON scan_entries(session_id,device,inode) WHERE photo IS NOT NULL",
    "CREATE INDEX entries_exact ON scan_entries(session_id,size,sha256,rank,folded,path)",
    "CREATE INDEX entries_quality ON scan_entries(session_id,raw DESC,pixels DESC,format_rank DESC,size DESC,rank,folded DESC)",
    """CREATE TABLE match_results (
        id INTEGER PRIMARY KEY, session_id TEXT NOT NULL REFERENCES scan_sessions(id),
        keeper INTEGER NOT NULL REFERENCES scan_entries(id),
        duplicate INTEGER NOT NULL REFERENCES scan_entries(id),
        kind TEXT NOT NULL CHECK(kind IN ('EXACT','VISUAL')), pd INTEGER NOT NULL, dd INTEGER NOT NULL,
        UNIQUE(session_id,duplicate), CHECK(keeper<>duplicate))""",
    "CREATE INDEX matches_session ON match_results(session_id,kind,duplicate)",
    """CREATE TABLE quarantine_operations (
        id TEXT PRIMARY KEY, state TEXT NOT NULL, manifest TEXT NOT NULL)""",
)
MIGRATIONS = {1: SQL}


def migrate(connection: sqlite3.Connection, path: Path) -> None:
    version = connection.execute("PRAGMA user_version").fetchone()[0]
    if version > SCHEMA_VERSION:
        raise SafetyError("index_newer_schema")
    if version == SCHEMA_VERSION:
        return
    # Never reinterpret an unrelated/unversioned database as an empty index.
    if version == 0 and connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'").fetchone():
        raise SafetyError("index_unknown_schema")
    if version:
        backup_path = path.with_name(f"{path.name}.v{version}.{uuid.uuid4().hex}.bak")
        backup = sqlite3.connect(backup_path)
        try:
            connection.backup(backup)
        finally:
            backup.close()
    connection.execute("BEGIN IMMEDIATE")
    try:
        for target in range(version + 1, SCHEMA_VERSION + 1):
            for statement in MIGRATIONS[target]:
                connection.execute(statement)
        connection.execute(f"PRAGMA user_version={SCHEMA_VERSION}")
        connection.commit()
    except BaseException:
        connection.rollback()
        raise


def encode(photo: Photo) -> str:
    return json.dumps(asdict(photo), sort_keys=True, separators=(',', ':'))


def decode_photo(payload: str) -> Photo:
    p = photo_from(json.loads(payload))
    if (not isinstance(p.width, int) or not isinstance(p.height, int)
            or p.width < 0 or p.height < 0 or p.width * p.height > 100_000_000
            or not isinstance(p.is_raw, bool) or not isinstance(p.decode_error, str)):
        raise ValueError("invalid_cached_metadata")
    for value in (p.phash, p.dhash):
        if value and (len(value) != 16 or any(c not in '0123456789abcdef' for c in value)):
            raise ValueError("invalid_cached_hash")
    if not p.decode_error and (not p.width or not p.height or not p.phash or not p.dhash):
        raise ValueError("incomplete_cached_metadata")
    return p


class Index:
    """Thread-confined connection and an independent OS writer lease.

    The lease is held for the lifetime of the service connection, including scans.
    It never shares the operation-journal lock or authorizes photo operations.
    """
    def __init__(self, path: Path, cancel: Event | None = None) -> None:
        self.path = check_path(path, allow_missing=True)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.cancel = cancel
        self._lock = None
        self.db = None
        self._acquire()
        try:
            self.db = sqlite3.connect(self.path, timeout=0, isolation_level=None)
            self.db.row_factory = sqlite3.Row
            if self.db.execute("PRAGMA quick_check").fetchone()[0] != 'ok':
                raise SafetyError("index_corrupt")
            # Check schema BEFORE changing journal mode on an unsupported database.
            migrate(self.db, self.path)
            self.db.execute("PRAGMA foreign_keys=ON")
            self.db.execute("PRAGMA journal_mode=WAL")
            self.db.execute("PRAGMA synchronous=FULL")
            self.db.execute("PRAGMA cache_size=-8192")
            self.db.execute("PRAGMA temp_store=FILE")
            with self.transaction():
                self.db.execute("UPDATE scan_sessions SET state='interrupted',finished=? WHERE state='running'", (time.time(),))
        except BaseException:
            self.close()
            raise

    def _acquire(self) -> None:
        lock = check_path(self.path.with_suffix(self.path.suffix + '.lock'), allow_missing=True)
        self._lock = lock.open('a+b')
        if self._lock.seek(0, os.SEEK_END) == 0:
            self._lock.write(b'0')
            self._lock.flush()
        self._lock.seek(0)
        try:
            if os.name == 'nt':
                import msvcrt
                msvcrt.locking(self._lock.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(self._lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            self._lock.close()
            self._lock = None
            raise SafetyError('index_busy') from exc

    def close(self) -> None:
        if self.db is not None:
            self.db.close()
            self.db = None
        if self._lock is not None:
            self._lock.close()
            self._lock = None

    @contextmanager
    def transaction(self) -> Iterator[None]:
        deadline = time.monotonic() + 5
        while True:
            cancelled(self.cancel)
            try:
                self.db.execute('BEGIN IMMEDIATE')
                break
            except sqlite3.OperationalError as exc:
                if exc.sqlite_errorcode not in (sqlite3.SQLITE_BUSY, sqlite3.SQLITE_LOCKED) or time.monotonic() >= deadline:
                    raise
                if self.cancel is not None:
                    self.cancel.wait(0.05)
                else:
                    time.sleep(0.05)
        try:
            yield
            self.db.commit()
        except BaseException:
            self.db.rollback()
            raise

    def root(self, path: str, root_id: Identity) -> int:
        args = (os.path.normcase(path), str(root_id.device), str(root_id.inode))
        with self.transaction():
            self.db.execute("UPDATE scan_roots SET state='replaced' WHERE path_key=? AND (device<>? OR inode<>?)", args)
            self.db.execute("INSERT INTO scan_roots(path,path_key,device,inode,state) VALUES(?,?,?,?,'online') "
                            "ON CONFLICT(path_key,device,inode) DO UPDATE SET state='online'", (path, *args))
        return self.db.execute('SELECT id FROM scan_roots WHERE path_key=? AND device=? AND inode=?', args).fetchone()[0]

    def cached(self, root_id: int, path: str, snapshot, pipeline: str) -> Photo | None:
        row = self.db.execute('''SELECT f.payload,f.checksum FROM photo_files p
            JOIN image_fingerprints f ON f.file_id=p.id
            WHERE p.root_id=? AND p.path_key=? AND p.state='present' AND f.pipeline=?''',
            (root_id, os.path.normcase(path), pipeline)).fetchone()
        if row is None or hashlib.sha256(row['payload'].encode()).hexdigest() != row['checksum']:
            return None
        try:
            photo = decode_photo(row['payload'])
            if photo.path != path or photo.snapshot != snapshot or photo.decode_error:
                return None
            return photo
        except (ValueError, TypeError, KeyError, SafetyError, AttributeError):
            return None

    def seen(self, session: str, path: str, file_id: Identity) -> bool:
        # Separate indexed lookups avoid an OR causing a full session scan per file.
        return (self.db.execute('SELECT 1 FROM scan_entries WHERE session_id=? AND path_key=?',
                               (session, os.path.normcase(path))).fetchone() is not None or
                self.db.execute('SELECT 1 FROM scan_entries WHERE session_id=? AND device=? AND inode=? AND photo IS NOT NULL',
                                (session, str(file_id.device), str(file_id.inode))).fetchone() is not None)

    def save_photo(self, session: str, root_id: int, rank: int, photo: Photo, pipeline: str) -> None:
        from app.matching.quality import quality
        payload = encode(photo)
        snap = photo.snapshot
        key = os.path.normcase(photo.path)
        # A surviving hardlink alias is not a rename. Prove old-name absence on the
        # same available root, outside a write transaction, before marking moved.
        previous = self.db.execute("SELECT id,path FROM photo_files WHERE root_id=? AND device=? AND inode=? "
                                   "AND sha256=? AND path_key<>? AND last_seen<>? AND state IN ('present','error')",
                                   (root_id, str(snap.identity.device), str(snap.identity.inode), snap.sha256, key, session))
        for old in previous:
            try:
                check_path(old['path'], allow_missing=True).lstat()
            except FileNotFoundError:
                if identity(photo.root) == photo.root_identity:
                    with self.transaction():
                        self.db.execute("UPDATE photo_files SET state='moved' WHERE id=?", (old['id'],))
            except (OSError, SafetyError) as exc:
                # Unreadable/redirected names are not evidence of absence.
                log.warning('index_alias_unverified', extra={'path': old['path'], 'reason': str(exc)})
        with self.transaction():
            self.db.execute('''INSERT INTO photo_files(root_id,path,path_key,device,inode,size,mtime_ns,ctime_ns,
                sha256,snapshot,state,error,last_seen) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT(root_id,path_key) DO UPDATE SET path=excluded.path,device=excluded.device,
                inode=excluded.inode,size=excluded.size,mtime_ns=excluded.mtime_ns,ctime_ns=excluded.ctime_ns,
                sha256=excluded.sha256,snapshot=excluded.snapshot,state=excluded.state,error=excluded.error,last_seen=excluded.last_seen''',
                (root_id, photo.path, key, str(snap.identity.device), str(snap.identity.inode), snap.size,
                 snap.mtime_ns, snap.ctime_ns, snap.sha256, json.dumps(asdict(snap)),
                 'error' if photo.decode_error else 'present', photo.decode_error, session))
            file_id = self.db.execute('SELECT id FROM photo_files WHERE root_id=? AND path_key=?', (root_id, key)).fetchone()[0]
            self.db.execute('INSERT OR REPLACE INTO image_fingerprints VALUES(?,?,?,?)',
                            (file_id, pipeline, payload, hashlib.sha256(payload.encode()).hexdigest()))
            q = quality(photo)
            self.db.execute('''INSERT INTO scan_entries(session_id,file_id,path,path_key,device,inode,photo,error,
                rank,size,sha256,folded,phash,raw,pixels,format_rank) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',
                (session, file_id, photo.path, key, str(snap.identity.device), str(snap.identity.inode), payload,
                 photo.decode_error, rank, snap.size, snap.sha256, photo.path.casefold(), photo.phash, q[0], q[1], q[2]))

    def error(self, session: str, path: str, error: str) -> None:
        with self.transaction():
            self.db.execute('INSERT INTO scan_entries(session_id,path,path_key,error,folded) VALUES(?,?,?,?,?) '
                            'ON CONFLICT(session_id,path_key) DO UPDATE SET error=excluded.error',
                            (session, path, os.path.normcase(path), error, path.casefold()))

    def errors(self, session: str, offset: int = 0, limit: int = PAGE_SIZE) -> list[str]:
        return [f"{r['path']}: {r['error']}" for r in self.db.execute(
            "SELECT path,error FROM scan_entries WHERE session_id=? AND error<>'' ORDER BY id LIMIT ? OFFSET ?",
            (session, min(PAGE_SIZE, limit), offset))]

    def photos(self, session: str, offset: int = 0, limit: int = PAGE_SIZE) -> list[Photo]:
        return [decode_photo(r[0]) for r in self.db.execute(
            'SELECT photo FROM scan_entries WHERE session_id=? AND photo IS NOT NULL ORDER BY id LIMIT ? OFFSET ?',
            (session, min(PAGE_SIZE, limit), offset))]

    def pairs(self, session: str, offset: int = 0, limit: int = PAGE_SIZE, *, exact: bool = False) -> list[Match]:
        rows = self.db.execute('''SELECT k.photo AS kept,d.photo AS dup,m.kind,m.pd,m.dd
            FROM match_results m JOIN scan_entries k ON k.id=m.keeper JOIN scan_entries d ON d.id=m.duplicate
            JOIN scan_sessions s ON s.id=m.session_id WHERE m.session_id=? AND s.state IN ('complete','incomplete') '''
            + ("AND m.kind='EXACT' " if exact else '') +
            "ORDER BY m.kind<>'EXACT',d.folded,d.id LIMIT ? OFFSET ?", (session, min(PAGE_SIZE, limit), offset))
        return [Match(Kind(r['kind']), decode_photo(r['kept']), decode_photo(r['dup']), r['pd'], r['dd']) for r in rows]

    def iter_pairs(self, session: str, *, exact: bool = False) -> Iterator[Match]:
        rows = self.db.execute('''SELECT k.photo AS kept,d.photo AS dup,m.kind,m.pd,m.dd
            FROM match_results m JOIN scan_entries k ON k.id=m.keeper JOIN scan_entries d ON d.id=m.duplicate
            JOIN scan_sessions s ON s.id=m.session_id WHERE m.session_id=? AND s.state IN ('complete','incomplete') '''
            + ("AND m.kind='EXACT' " if exact else '') +
            "ORDER BY m.kind<>'EXACT',d.folded,d.id", (session,))
        while page := rows.fetchmany(PAGE_SIZE):
            for r in page:
                yield Match(Kind(r['kind']), decode_photo(r['kept']), decode_photo(r['dup']), r['pd'], r['dd'])

    def iter_errors(self, session: str) -> Iterator[str]:
        rows = self.db.execute("SELECT path,error FROM scan_entries WHERE session_id=? AND error<>'' ORDER BY id", (session,))
        while page := rows.fetchmany(PAGE_SIZE):
            for r in page:
                yield f"{r['path']}: {r['error']}"

    def invalidate(self, paths: set[str]) -> None:
        with self.transaction():
            for path in paths:
                key = os.path.normcase(path)
                self.db.execute("UPDATE photo_files SET state='stale' WHERE path_key=?", (key,))
                self.db.execute('''DELETE FROM match_results WHERE keeper IN
                    (SELECT id FROM scan_entries WHERE path_key=?) OR duplicate IN
                    (SELECT id FROM scan_entries WHERE path_key=?)''', (key, key))

    def project_history(self, records: Iterator[dict]) -> None:
        # Each projection is independently replaceable; the JSON manifest is authoritative.
        for record in records:
            with self.transaction():
                self.db.execute('INSERT OR REPLACE INTO quarantine_operations VALUES(?,?,?)',
                                (record['id'], record['state'], json.dumps(record, sort_keys=True)))
                move = record.get('move')
                if move:
                    for path in (move['source'], move['destination']):
                        self.db.execute("UPDATE photo_files SET state='stale' WHERE path_key=?", (os.path.normcase(path),))
