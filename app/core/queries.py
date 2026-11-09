"""Immutable service contracts shared by desktop adapters."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Generic, TypeVar

from app.core.models import Match

T = TypeVar('T')


@dataclass(frozen=True)
class MatchingOptions:
    phash_max: int = 4
    dhash_max: int = 6

    def __post_init__(self) -> None:
        if any(type(v) is not int or not 0 <= v <= 64 for v in (self.phash_max, self.dhash_max)):
            raise ValueError('invalid_matching_options')


@dataclass(frozen=True)
class MatchQuery:
    text: str = ''
    kind: str = ''
    sort: str = 'name'
    descending: bool = False
    offset: int = 0
    limit: int = 200
    keeper_id: int | None = None

    def __post_init__(self) -> None:
        if self.kind not in ('', 'EXACT', 'VISUAL', 'DERIVATIVE', 'SIMILAR_CAPTURE'):
            raise ValueError('invalid_kind')
        if self.sort not in ('name', 'kind', 'format', 'size', 'dimensions', 'path', 'time'):
            raise ValueError('invalid_sort')
        if self.offset < 0 or not 1 <= self.limit <= 200:
            raise ValueError('invalid_page')


@dataclass(frozen=True)
class PageResult(Generic[T]):
    items: tuple[T, ...]
    total: int
    offset: int = 0


@dataclass(frozen=True)
class MatchRow:
    id: int
    keeper_id: int
    match: Match


@dataclass(frozen=True)
class GroupRow:
    keeper_id: int
    kind: str
    keeper_path: str
    members: int


@dataclass(frozen=True)
class DashboardSummary:
    indexed: int
    session_id: str = ''
    status: str = ''
    started: float = 0
    exact: int = 0
    visual: int = 0
    potential_bytes: int = 0
    errors: int = 0
    roots: tuple[tuple[str, str], ...] = ()
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True)
class HistoryEntry:
    id: str
    at: str
    source: str
    destination: str
    state: str
    error: str
    restorable: bool


@dataclass(frozen=True)
class ScanProgress:
    phase: str
    discovered: int = 0
    processed: int = 0
    skipped: int = 0
    failed: int = 0
    roots: tuple[tuple[str, str], ...] = ()
