from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
import json
import logging
import os
from pathlib import Path
import threading
import uuid

from app.core.models import Identity, Kind, Move, Photo, SafetyError, Snapshot
from app.safety.paths import check_path

log = logging.getLogger(__name__)
VERSION = 1


def valid_id(value: str) -> bool:
    return isinstance(value, str) and len(value) == 32 and all(c in "0123456789abcdef" for c in value)


def sync_directory(path: Path) -> None:
    if os.name != "nt":
        fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)


def atomic_json(path: Path, value: dict) -> None:
    check_path(path, allow_missing=True)
    tmp = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    try:
        with tmp.open("x", encoding="utf-8") as stream:
            json.dump(value, stream, ensure_ascii=False, indent=2)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(tmp, path)
        sync_directory(path.parent)
    finally:
        if tmp.exists():
            tmp.unlink()


def snapshot_from(data: dict) -> Snapshot:
    result = Snapshot(Identity(**data["identity"]), data["size"], data["mtime_ns"],
                      data["ctime_ns"], data["sha256"])
    if len(result.sha256) != 64 or any(c not in "0123456789abcdef" for c in result.sha256):
        raise SafetyError("invalid_digest")
    return result


def photo_from(data: dict) -> Photo:
    return Photo(**{**data, "snapshot": snapshot_from(data["snapshot"]),
                    "root_identity": Identity(**data["root_identity"])})


def move_from(data: dict) -> Move:
    return Move(**{**data, "root_identity": Identity(**data["root_identity"]),
                   "expected": snapshot_from(data["expected"]),
                   "keeper": photo_from(data["keeper"]) if data["keeper"] else None,
                   "kind": Kind(data["kind"]), "xmp": tuple(data["xmp"])})


class Journal:
    """One OS-locked writer, immutable operation IDs, retained transitions."""

    def __init__(self, directory: Path) -> None:
        self.directory = check_path(directory, allow_missing=True)
        self.directory.mkdir(parents=True, exist_ok=True)
        check_path(self.directory)
        self._guard = threading.RLock()
        lock_path = check_path(self.directory / "writer.lock", allow_missing=True)
        self._lock = lock_path.open("a+b")
        self.writable = False
        self.error = ""
        try:
            if self._lock.seek(0, os.SEEK_END) == 0:
                self._lock.write(b"0")
                self._lock.flush()
            self._lock.seek(0)
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(self._lock.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(self._lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            self.writable = True
            self.records()  # Corrupt history disables writes, never becomes empty.
        except (OSError, ValueError, TypeError, KeyError, SafetyError) as exc:
            self.error = f"history_unavailable: {exc}"
            self.writable = False

    def close(self) -> None:
        self.writable = False
        self._lock.close()

    def require_writer(self) -> None:
        if not self.writable:
            raise SafetyError(self.error or "history_locked_by_another_instance")

    def records(self) -> list[dict]:
        result = []
        for path in sorted(self.directory.glob("*.json")):
            check_path(path)
            record = json.loads(path.read_text(encoding="utf-8"))
            if record["version"] != VERSION or not record["transitions"]:
                raise SafetyError(f"invalid_manifest: {path}")
            if path.stem != record["id"] or not valid_id(path.stem):
                raise SafetyError("invalid_manifest_id")
            if record["transitions"][-1]["state"] != record["state"]:
                raise SafetyError("invalid_manifest_transition")
            if record["state"] == "legacy":
                if not isinstance(record["entry"]["origin"], str) or not isinstance(record["entry"]["dest"], str):
                    raise SafetyError("invalid_legacy_entry")
            else:
                move = move_from(record["move"])
                if move.id != record["id"] or record["state"] not in {"intent", "complete", "not_moved", "blocked"}:
                    raise SafetyError("invalid_manifest")
            result.append(record)
        return result

    def _save(self, record: dict) -> None:
        self.require_writer()
        if not valid_id(record["id"]):
            raise SafetyError("invalid_manifest_id")
        atomic_json(self.directory / f"{record['id']}.json", record)

    def begin(self, move: Move) -> None:
        with self._guard:
            if not valid_id(move.id):
                raise SafetyError("invalid_manifest_id")
            if (self.directory / f"{move.id}.json").exists():
                raise SafetyError("operation_already_recorded")
            move_data = asdict(move)
            if move_data['keeper'] is not None:
                # Index-only metadata must not change the version-1 recovery format.
                move_data['keeper'].pop('image_format', None)
            record = {"version": VERSION, "id": move.id, "move": move_data,
                      "state": "intent", "transitions": [self._event("intent")]}
            self._save(record)
            log.info("operation_intent", extra={"operation_id": move.id, "source": move.source})

    @staticmethod
    def _event(state: str, detail: str = "") -> dict:
        return {"state": state, "detail": detail, "at": datetime.now(timezone.utc).isoformat()}

    def transition(self, operation_id: str, state: str, detail: str = "") -> None:
        with self._guard:
            record = next(r for r in self.records() if r["id"] == operation_id)
            record["state"] = state
            record["transitions"].append(self._event(state, detail))
            self._save(record)
            log.info("operation_transition", extra={"operation_id": operation_id, "state": state, "detail": detail})

    def import_legacy(self, state_path: Path) -> None:
        self.require_writer()
        if not os.path.lexists(state_path):
            return
        raw = check_path(state_path).read_bytes()
        state = json.loads(raw)
        if not isinstance(state, dict):
            raise SafetyError("invalid_legacy_history")
        entries = state.get("moves", [])
        if not isinstance(entries, list):
            raise SafetyError("invalid_legacy_history")
        if not entries:
            return
        for entry in entries:
            if not isinstance(entry, dict) or not all(isinstance(entry.get(k), str) for k in ("origin", "dest")):
                raise SafetyError("invalid_legacy_history")
        backup = state_path.with_name(f"{state_path.name}.legacy-{hashlib.sha256(raw).hexdigest()}.bak")
        if not backup.exists():
            with backup.open("xb") as stream:
                stream.write(raw)
                stream.flush()
                os.fsync(stream.fileno())
            sync_directory(backup.parent)
        elif backup.read_bytes() != raw:
            raise SafetyError("legacy_backup_conflict")
        existing = {r["id"] for r in self.records()}
        for entry in entries:
            operation_id = uuid.uuid5(uuid.NAMESPACE_URL, json.dumps(entry, sort_keys=True)).hex
            if operation_id not in existing:
                self._save({"version": VERSION, "id": operation_id, "entry": entry,
                            "state": "legacy", "transitions": [self._event("legacy")]})
                existing.add(operation_id)
