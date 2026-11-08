"""Metadata extraction tied to stable full-content snapshots."""
from __future__ import annotations

from pathlib import Path
from threading import Event

from app.core.models import Photo, SafetyError, Snapshot
from app.safety.paths import absolute, identity, snapshot
from app.scanning.decoder import RAWS, decode


def extract(path: Path, root: Path, before: Snapshot, cancel: Event | None = None) -> Photo:
    root_id = identity(root)
    error, data = "", {}
    try:
        data = decode(path, cancel, preview=False)
    except (OSError, SafetyError, ValueError) as exc:
        error = str(exc)
    after = snapshot(path, cancel)
    if before != after or identity(root) != root_id:
        raise SafetyError("changed_during_inspection")
    return Photo(str(absolute(path)), str(root), after, root_id,
                 data.get("width", 0), data.get("height", 0), data.get("phash", ""),
                 data.get("dhash", ""), path.suffix.lower() in RAWS,
                 path.suffix.lower(), error, data.get("image_format", ""))
