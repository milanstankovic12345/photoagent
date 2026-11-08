from __future__ import annotations

import os
from pathlib import Path
from queue import Queue
from threading import Event

from app.core.models import Cancelled, Photo, ScanResult, SafetyError
from app.matching.matcher import match
from app.safety.paths import QUARANTINE, absolute, cancelled, check_path, identity, snapshot
from app.scanning.discovery import discover
from app.scanning.inspection import extract


def roots_for_scan(folders: list[str], errors: list[str] | None = None) -> list[Path]:
    roots = []
    for folder in folders:
        try:
            root = check_path(folder)
            if any(part.casefold() == QUARANTINE for part in root.parts):
                raise SafetyError("quarantine_root")
            if not root.is_dir():
                raise SafetyError("unavailable_root")
            identity(root)
            if root not in roots:
                roots.append(root)
        except (OSError, SafetyError) as exc:
            if errors is not None:
                errors.append(f"{folder}: {exc}")
    # Preserve selection order, even for overlapping roots. Physical dedup below
    # assigns each file to the first selected root that actually yielded it.
    return roots


def inspect(path: Path, root: Path, cancel: Event | None = None) -> Photo:
    return extract(path, root, snapshot(path, cancel), cancel)


def scan(folders: list[str], updates: Queue, cancel: Event) -> ScanResult:
    found, errors, seen, physical = [], [], set(), set()
    roots = roots_for_scan(folders, errors)
    try:
        for root in roots:
            root_id = identity(root)

            for path in discover(root, cancel, lambda name, exc: errors.append(f"{name}: {exc}")):
                try:
                    key = os.path.normcase(str(absolute(path)))
                    file_id = identity(path)
                    if key in seen or file_id in physical:
                        continue
                    seen.add(key)
                    physical.add(file_id)
                    photo = inspect(path, root, cancel)
                    if photo.root_identity != root_id:
                        raise SafetyError("root_replaced")
                    found.append(photo)
                    if photo.decode_error:
                        errors.append(f"{path}: {photo.decode_error}")
                except (OSError, SafetyError, ValueError) as exc:
                    errors.append(f"{path}: {exc}")
                updates.put(("status", ("scan_progress", len(found))))
            if identity(root) != root_id:
                raise SafetyError("root_replaced")
        pairs = match(found, [str(r) for r in roots], cancel)
        return ScanResult(tuple(found), pairs, tuple(errors), not errors)
    except Cancelled:
        return ScanResult(tuple(found), (), tuple(errors), False, True)
    except (OSError, SafetyError) as exc:
        errors.append(str(exc))
        return ScanResult(tuple(found), (), tuple(errors), False)
