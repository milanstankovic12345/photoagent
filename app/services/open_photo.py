"""Resolve one immutable photo target; never decode, move or repair files here."""
from __future__ import annotations

from threading import Event

from app.core.models import Photo, SafetyError
from app.safety.journal import Journal
from app.safety.paths import QUARANTINE, cancelled, contained, identity, snapshot
from app.services.quarantine import quarantine_photo


def resolve_photo(journal: Journal, target: Photo | str, cancel: Event) -> str:
    """Strings are operation IDs, never user paths or URLs.

    Restored/legacy/ambiguous history entries fail closed through the existing
    manifest resolver. A scan result never follows a file into quarantine.
    """
    cancelled(cancel)
    if isinstance(target, str):
        photo = quarantine_photo(journal, target, cancel)
        path = photo.path  # Already checked against the authoritative manifest.
    elif isinstance(target, Photo):
        if identity(target.root) != target.root_identity:
            raise SafetyError('root_or_volume_changed')
        path = contained(target.path, target.root)
        if any(part.casefold() == QUARANTINE for part in path.relative_to(target.root).parts):
            raise SafetyError('invalid_quarantine_paths')
        if snapshot(path, cancel) != target.snapshot:
            raise SafetyError('candidate_changed_review_again')
    else:
        raise TypeError('invalid_photo_target')
    cancelled(cancel)
    return str(path)
