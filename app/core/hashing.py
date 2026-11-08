"""Exact byte hashing; callers supply identity checks and cancellation policy."""
from __future__ import annotations

import hashlib
from typing import BinaryIO, Callable


def sha256_stream(stream: BinaryIO, checkpoint: Callable[[], None], *, chunk_size: int) -> str:
    digest = hashlib.sha256()
    stream.seek(0)
    while True:
        checkpoint()
        data = stream.read(chunk_size)
        if not data:
            return digest.hexdigest()
        digest.update(data)
