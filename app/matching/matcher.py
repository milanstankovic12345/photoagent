from __future__ import annotations

from collections import defaultdict
from threading import Event
from typing import Iterator

from app.core.models import Kind, Match, Photo
from app.core.queries import MatchingOptions
from app.matching.quality import quality
from app.safety.paths import cancelled

PHASH_MAX, DHASH_MAX, ASPECT_MAX = 4, 6, 0.025


def aspect(p: Photo) -> float:
    return max(p.width, p.height) / max(1, min(p.width, p.height))


class BKTree:
    def __init__(self) -> None:
        self.node = None

    def add(self, h: int, photo: Photo) -> None:
        if self.node is None:
            self.node = [h, [photo], {}]
            return
        node = self.node
        while True:
            distance = (h ^ node[0]).bit_count()
            if distance == 0:
                node[1].append(photo)
                return
            if distance not in node[2]:
                node[2][distance] = [h, [photo], {}]
                return
            node = node[2][distance]

    def near(self, h: int, radius: int) -> Iterator[tuple[int, Photo]]:
        stack = [self.node] if self.node else []
        while stack:
            node = stack.pop()
            distance = (h ^ node[0]).bit_count()
            if distance <= radius:
                yield from ((distance, p) for p in node[1])
            stack.extend(child for edge, child in node[2].items()
                         if distance - radius <= edge <= distance + radius)


def match(photos: list[Photo], roots: list[str], cancel: Event | None = None,
          options: MatchingOptions = MatchingOptions()) -> tuple[Match, ...]:
    rank = {r: i for i, r in enumerate(roots)}
    groups = defaultdict(list)
    for photo in photos:
        cancelled(cancel)
        groups[(photo.size, photo.sha256)].append(photo)
    pairs, duplicates = [], set()
    for group in groups.values():
        cancelled(cancel)
        group.sort(key=lambda p: (rank[p.root], p.path.casefold(), p.path))
        for dup in group[1:]:
            pairs.append(Match(Kind.EXACT, group[0], dup))
            duplicates.add(dup.path)
    tree = BKTree()
    for photo in sorted((p for p in photos if p.path not in duplicates and p.phash),
                        key=lambda p: (*quality(p), -rank[p.root], p.path.casefold()), reverse=True):
        cancelled(cancel)
        candidates = []
        for pdist, keeper in tree.near(int(photo.phash, 16), options.phash_max):
            cancelled(cancel)
            ddist = (int(photo.dhash, 16) ^ int(keeper.dhash, 16)).bit_count()
            difference = abs(aspect(photo) - aspect(keeper)) / max(aspect(photo), aspect(keeper))
            if ddist <= options.dhash_max and difference <= ASPECT_MAX:
                candidates.append((pdist, ddist, keeper))
        if candidates:
            pdist, ddist, keeper = min(candidates, key=lambda c: (c[0], c[1], c[2].path))
            pairs.append(Match(Kind.VISUAL, keeper, photo, pdist, ddist))
        else:
            # Followers never enter the tree: A~B and B~C cannot imply A~C.
            tree.add(int(photo.phash, 16), photo)
    return tuple(sorted(pairs, key=lambda p: (p.kind != Kind.EXACT, p.dup.path.casefold())))
