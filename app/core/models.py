from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class Kind(StrEnum):
    EXACT = "EXACT"
    VISUAL = "VISUAL"
    DERIVATIVE = "DERIVATIVE"
    SIMILAR_CAPTURE = "SIMILAR_CAPTURE"


class SafetyError(Exception):
    """Stable technical error codes; the UI supplies the surrounding message."""


class Cancelled(Exception):
    pass


@dataclass(frozen=True)
class Identity:
    device: int
    inode: int


@dataclass(frozen=True)
class Snapshot:
    identity: Identity
    size: int
    mtime_ns: int
    ctime_ns: int
    sha256: str


@dataclass(frozen=True)
class Photo:
    path: str
    root: str
    snapshot: Snapshot
    root_identity: Identity
    width: int = 0
    height: int = 0
    phash: str = ""
    dhash: str = ""
    is_raw: bool = False
    ext: str = ""
    decode_error: str = ""
    image_format: str = ""

    @property
    def size(self) -> int:
        return self.snapshot.size

    @property
    def sha256(self) -> str:
        return self.snapshot.sha256


@dataclass(frozen=True)
class Match:
    kind: Kind
    keep: Photo
    dup: Photo
    ph_distance: int = 0
    dh_distance: int = 0


@dataclass(frozen=True)
class ScanResult:
    photos: tuple[Photo, ...]
    pairs: tuple[Match, ...]
    errors: tuple[str, ...]
    complete: bool
    cancelled: bool = False


@dataclass(frozen=True)
class ScanSummary:
    session_id: str
    status: str
    photo_count: int
    pair_count: int
    exact_count: int
    error_count: int
    cache_hits: int = 0
    decodes: int = 0
    hash_reads: int = 0
    hash_bytes: int = 0
    scan_seconds: float = 0.0
    match_seconds: float = 0.0

    @property
    def complete(self) -> bool:
        return self.status == "complete"

    @property
    def cancelled(self) -> bool:
        return self.status == "cancelled"


@dataclass(frozen=True)
class Move:
    id: str
    source: str
    destination: str
    root: str
    root_identity: Identity
    expected: Snapshot
    keeper: Photo | None
    kind: Kind
    action: str = "quarantine"
    restores: str = ""
    xmp: tuple[str, ...] = ()
    raw: bool = False
    legacy: bool = False
    decoded: bool = False


@dataclass(frozen=True)
class Plan:
    id: str
    moves: tuple[Move, ...]
    bulk: bool = False


@dataclass(frozen=True)
class Approval:
    """Created by the controller only after displaying this exact frozen plan."""
    plan: Plan
    raw: bool = False
    legacy: bool = False
