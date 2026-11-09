"""Read-only manifest views. These never authorize a restore or repair history."""
from __future__ import annotations

from pathlib import Path
from threading import Event

from app.core.models import Photo, SafetyError
from app.safety.journal import Journal, move_from
from app.safety.paths import QUARANTINE, cancelled, contained, identity, same_content, snapshot


def _record(journal: Journal, operation_id: str) -> dict:
    return next((r for r in journal.records() if r['id'] == operation_id), {})


def quarantine_folder(journal: Journal, operation_id: str) -> Path:
    record = _record(journal, operation_id)
    if not record:
        raise SafetyError('no_restore_candidates')
    if record['state'] == 'legacy':
        path = Path(record['entry']['dest'])
        roots = [p.parent for p in path.parents if p.name.casefold() == QUARANTINE]
        if len(roots) != 1:
            raise SafetyError('invalid_legacy_quarantine')
        root = roots[0]
    else:
        move = move_from(record['move'])
        root = Path(move.root)
        if identity(root) != move.root_identity:
            raise SafetyError('root_or_volume_changed')
        path = Path(move.destination if move.action == 'quarantine' else move.source)
    # The file may already be restored, but never create a replacement folder.
    checked = contained(path, root, missing=True)
    if checked.relative_to(root).parts[0].casefold() != QUARANTINE:
        raise SafetyError('invalid_quarantine_paths')
    folder = contained(checked.parent, root)
    if not folder.is_dir():
        raise SafetyError('quarantine_folder_unavailable')
    return folder


def quarantine_photo(journal: Journal, operation_id: str, cancel: Event) -> Photo:
    cancelled(cancel)
    records = journal.records()
    record = next((r for r in records if r['id'] == operation_id), None)
    if (not record or record['state'] != 'complete'
            or record.get('move', {}).get('action') != 'quarantine'
            or any(r.get('move', {}).get('restores') == operation_id
                   and r['state'] in ('intent', 'blocked', 'complete') for r in records)):
        raise SafetyError('quarantine_preview_unavailable')
    move = move_from(record['move'])
    if identity(move.root) != move.root_identity:
        raise SafetyError('root_or_volume_changed')
    path = contained(move.destination, move.root)
    if path.relative_to(move.root).parts[0].casefold() != QUARANTINE:
        raise SafetyError('invalid_quarantine_paths')
    actual = snapshot(path, cancel)
    if not same_content(actual, move.expected):
        raise SafetyError('quarantine_content_changed')
    # Rename changes ctime. Use the fresh snapshot after verifying all surviving
    # identity/content fields, then let PreviewService validate again around decode.
    return Photo(str(path), move.root, actual, move.root_identity,
                 is_raw=move.raw, ext=path.suffix.lower())
