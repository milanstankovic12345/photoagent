from __future__ import annotations

import os
import stat
from pathlib import Path
from threading import Event
from typing import BinaryIO

from app.core.models import Cancelled, Identity, SafetyError, Snapshot
from app.core.hashing import sha256_stream

QUARANTINE = ".photo_agent_quarantine"
CHUNK = 1024 * 1024


def absolute(path: str | Path) -> Path:
    # Inspect the original spelling before normpath can erase a symlink/../ hop.
    p = Path(path).expanduser()
    if ".." in p.parts:
        raise SafetyError("parent_traversal")
    return Path(os.path.abspath(p))


def check_path(path: str | Path, *, allow_missing: bool = False) -> Path:
    p = absolute(path)
    for component in (*reversed(p.parents), p):
        try:
            info = component.lstat()
        except FileNotFoundError:
            if allow_missing:
                continue
            raise
        if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & 0x400:
            raise SafetyError(f"redirected_path: {component}")
    return p


def contained(path: str | Path, root: str | Path, *, missing: bool = False) -> Path:
    r = check_path(root)
    p = check_path(path, allow_missing=missing)
    if p == r or not p.is_relative_to(r):
        raise SafetyError("outside_root")
    return p


def identity(path: str | Path) -> Identity:
    st = check_path(path).stat()
    if not st.st_ino:
        raise SafetyError("identity_unavailable")
    return Identity(st.st_dev, st.st_ino)


def cancelled(cancel: Event | None) -> None:
    if cancel is not None and cancel.is_set():
        raise Cancelled()


def snapshot_stream(stream: BinaryIO, cancel: Event | None = None) -> Snapshot:
    before = os.fstat(stream.fileno())
    if not stat.S_ISREG(before.st_mode) or not before.st_ino:
        raise SafetyError("not_regular_file")
    digest = sha256_stream(stream, lambda: cancelled(cancel), chunk_size=CHUNK)
    after = os.fstat(stream.fileno())
    fields = ("st_dev", "st_ino", "st_size", "st_mtime_ns", "st_ctime_ns")
    if any(getattr(before, f) != getattr(after, f) for f in fields):
        raise SafetyError("unstable_read")
    return Snapshot(Identity(after.st_dev, after.st_ino), after.st_size,
                    after.st_mtime_ns, after.st_ctime_ns, digest)


def snapshot(path: str | Path, cancel: Event | None = None) -> Snapshot:
    p = check_path(path)
    before = p.stat()
    with p.open("rb") as stream:
        result = snapshot_stream(stream, cancel)
    after = check_path(p).stat()
    if (result.identity != Identity(before.st_dev, before.st_ino)
            or result.identity != Identity(after.st_dev, after.st_ino)
            or result.size != before.st_size or result.mtime_ns != before.st_mtime_ns
            or result.size != after.st_size or result.mtime_ns != after.st_mtime_ns):
        raise SafetyError("replaced_during_read")
    # On Windows/Python 3.12 stat(path).st_ctime may be creation time while
    # fstat(handle).st_ctime is change time. Never compare these two meanings.
    # Snapshot ctime always comes from fstat and is checked around every read.
    return result


def same_content(actual: Snapshot, expected: Snapshot) -> bool:
    # Rename may change ctime; identity, mtime, size and full bytes must survive.
    return (actual.identity == expected.identity and actual.size == expected.size
            and actual.mtime_ns == expected.mtime_ns and actual.sha256 == expected.sha256)


def sidecars(path: str | Path) -> tuple[str, ...]:
    p = Path(path)
    names = {(p.stem + ".xmp").casefold(), (p.name + ".xmp").casefold()}
    return tuple(sorted(str(c) for c in p.parent.iterdir() if c.name.casefold() in names))
