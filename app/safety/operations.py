from __future__ import annotations

from datetime import date
import logging
import os
from pathlib import Path
from threading import Event
from typing import BinaryIO
import uuid

from app.core.models import Approval, Kind, Match, Move, Plan, SafetyError
from app.safety.journal import Journal, move_from
from app.safety.native import ensure_directory, rename_verified
from app.safety.paths import (QUARANTINE, cancelled, check_path, contained, identity,
                              same_content, sidecars, snapshot, snapshot_stream)
from app.scanning.decoder import IMAGES, RAWS

log = logging.getLogger(__name__)


def make_plan(pairs: list[Match], *, bulk: bool = False, cancel: Event | None = None) -> Plan:
    moves, seen = [], set()
    for pair in pairs:
        cancelled(cancel)
        src, keeper = pair.dup, pair.keep
        contained(src.path, src.root)
        contained(keeper.path, keeper.root)
        if src.snapshot.identity == keeper.snapshot.identity:
            raise SafetyError("self_comparison")
        xmp = tuple(sorted(set(sidecars(src.path) + sidecars(keeper.path))))
        if bulk and (pair.kind != Kind.EXACT or src.is_raw or keeper.is_raw
                     or not src.phash or not keeper.phash or src.decode_error or keeper.decode_error
                     or src.root != keeper.root or xmp):
            continue
        if pair.kind == Kind.EXACT and src.sha256 != keeper.sha256:
            raise SafetyError("exact_digest_mismatch")
        if src.snapshot.identity in seen:
            continue
        seen.add(src.snapshot.identity)
        target = Path(src.root) / QUARANTINE / date.today().isoformat() / f"{uuid.uuid4().hex}_{Path(src.path).name}"
        contained(target, src.root, missing=True)
        moves.append(Move(uuid.uuid4().hex, src.path, str(target), src.root, src.root_identity,
                          src.snapshot, keeper, pair.kind, xmp=xmp, raw=src.is_raw,
                          decoded=bool(src.phash and not src.decode_error)))
    moving = {m.expected.identity for m in moves}
    if any(m.keeper.snapshot.identity in moving for m in moves):
        raise SafetyError("keeper_dependency")
    return Plan(uuid.uuid4().hex, tuple(moves), bulk)


def validate_plan(plan: Plan) -> None:
    if not plan.moves:
        raise SafetyError("empty_plan")
    ids, sources, destinations = set(), set(), set()
    for move in plan.moves:
        if move.id in ids or move.expected.identity in sources or move.destination in destinations:
            raise SafetyError("repeated_operation")
        ids.add(move.id)
        sources.add(move.expected.identity)
        destinations.add(move.destination)
    if any(m.keeper and m.keeper.snapshot.identity in sources for m in plan.moves):
        raise SafetyError("keeper_dependency")
    if plan.bulk:
        for move in plan.moves:
            k = move.keeper
            if (move.action != "quarantine" or move.kind != Kind.EXACT or not k or move.raw or k.is_raw
                    or move.xmp or k.root != move.root or not k.phash or k.decode_error or not move.decoded):
                raise SafetyError("bulk_ineligible")


class Operations:
    def __init__(self, journal: Journal) -> None:
        self.journal = journal

    @staticmethod
    def _paths(move: Move) -> tuple[Path, Path]:
        if identity(move.root) != move.root_identity:
            raise SafetyError("root_or_volume_changed")
        src = contained(move.source, move.root)
        dest = contained(move.destination, move.root, missing=True)
        if src.suffix.lower() not in IMAGES | RAWS or dest.suffix.lower() not in IMAGES | RAWS:
            raise SafetyError("not_a_photo_operation")
        src_quarantine = QUARANTINE in [p.casefold() for p in src.relative_to(move.root).parts]
        dest_parts = dest.relative_to(move.root).parts
        if move.action == "quarantine":
            if src_quarantine or not dest_parts or dest_parts[0].casefold() != QUARANTINE or not move.keeper:
                raise SafetyError("invalid_quarantine_paths")
        elif move.action == "restore":
            if not src_quarantine or QUARANTINE in [p.casefold() for p in dest_parts]:
                raise SafetyError("invalid_restore_paths")
        else:
            raise SafetyError("invalid_action")
        if os.path.lexists(dest):
            raise SafetyError("destination_occupied")
        if move.keeper:
            k = move.keeper
            contained(k.path, k.root)
            if identity(k.root) != k.root_identity or k.snapshot.identity == move.expected.identity:
                raise SafetyError("keeper_or_root_changed")
        return src, dest

    def execute(self, plan: Plan, approval: Approval, cancel: Event | None = None) -> tuple[str, ...]:
        if approval.plan != plan:
            raise SafetyError("approval_plan_mismatch")
        validate_plan(plan)
        if any(m.raw for m in plan.moves) and not approval.raw:
            raise SafetyError("raw_confirmation_required")
        if any(m.legacy for m in plan.moves) and not approval.legacy:
            raise SafetyError("legacy_confirmation_required")
        self.journal.require_writer()
        moved = []
        # Serialize the whole plan, not just individual JSON writes.
        with self.journal._guard:
            if any(r["state"] in {"intent", "blocked"} for r in self.journal.records()):
                raise SafetyError("recovery_required")
            for move in plan.moves:
                cancelled(cancel)
                # Errors leave the intent intact for reconciliation. Never roll back
                # with an unverified ordinary rename after a final-write failure.
                src, dest = self._paths(move)
                current_sidecars = tuple(sorted(set(sidecars(src) + (sidecars(move.keeper.path) if move.keeper else ()))))
                if move.action == "quarantine" and current_sidecars != move.xmp:
                    raise SafetyError("sidecars_changed_review_again")
                if plan.bulk and current_sidecars:
                    raise SafetyError("bulk_sidecar")
                ensure_directory(Path(move.root), dest.parent)
                self._paths(move)

                def verify(source_stream: BinaryIO, keeper_stream: BinaryIO | None) -> None:
                    self._paths(move)
                    if snapshot_stream(source_stream, cancel) != move.expected:
                        raise SafetyError("source_changed")
                    if move.keeper:
                        if snapshot_stream(keeper_stream, cancel) != move.keeper.snapshot:
                            raise SafetyError("keeper_changed")
                        if move.kind == Kind.EXACT and move.expected.sha256 != move.keeper.sha256:
                            raise SafetyError("exact_digest_mismatch")
                    if move.action == "quarantine":
                        xmp_now = tuple(sorted(set(sidecars(src) + sidecars(move.keeper.path))))
                        if xmp_now != move.xmp:
                            raise SafetyError("sidecars_changed_review_again")
                    # No cancellation after durable intent until the operation has
                    # either completed or left a recoverable record.
                    cancelled(cancel)
                    self.journal.begin(move)

                try:
                    rename_verified(src, dest, Path(move.keeper.path) if move.keeper else None,
                                    verify, move.expected)
                    if os.path.lexists(src) or not same_content(snapshot(dest), move.expected):
                        raise SafetyError("post_move_verification_failed")
                    self.journal.transition(move.id, "complete")
                    moved.append(move.source)
                except Exception as exc:
                    log.exception("operation_failed", extra={"operation_id": move.id, "source": move.source})
                    try:
                        if any(r["id"] == move.id and r["state"] == "intent" for r in self.journal.records()):
                            self.journal.transition(move.id, "blocked", f"{type(exc).__name__}: {exc}")
                    except (OSError, SafetyError, ValueError, KeyError, TypeError):
                        # A failed history write must leave the durable intent in
                        # place; do not replace the original operation error.
                        log.exception("failure_record_unavailable", extra={"operation_id": move.id})
                    raise
        return tuple(moved)

    def recover(self, cancel: Event | None = None) -> list[str]:
        self.journal.require_writer()
        issues = []
        with self.journal._guard:
            for record in self.journal.records():
                cancelled(cancel)
                if record["state"] not in {"intent", "blocked"}:
                    continue
                move = move_from(record["move"])
                try:
                    if identity(move.root) != move.root_identity:
                        raise SafetyError("root_or_volume_changed")
                    src = contained(move.source, move.root, missing=True)
                    dest = contained(move.destination, move.root, missing=True)
                    a, b = os.path.lexists(src), os.path.lexists(dest)
                    if a == b:
                        raise SafetyError("ambiguous_recovery_paths")
                    if not same_content(snapshot(src if a else dest, cancel), move.expected):
                        raise SafetyError("recovery_content_mismatch")
                    self.journal.transition(move.id, "not_moved" if a else "complete", "reconciled")
                except (OSError, SafetyError) as exc:
                    issues.append(f"{move.id}: {exc}")
                    self.journal.transition(move.id, "blocked", str(exc))
        return issues

    def restore_plan(self, cancel: Event | None = None) -> Plan:
        cancelled(cancel)
        records = self.journal.records()
        restored = {r["move"]["restores"] for r in records if "move" in r
                    and r["move"]["action"] == "restore" and r["state"] in {"intent", "blocked", "complete"}}
        candidates = [r for r in records if r["id"] not in restored and
                      (r["state"] == "legacy" or r["state"] == "complete" and r["move"]["action"] == "quarantine")]
        if not candidates:
            raise SafetyError("no_restore_candidates")
        # Never silently skip an inaccessible latest entry.
        record = max(candidates, key=lambda r: (r["transitions"][-1]["at"], r["id"]))
        legacy = record["state"] == "legacy"
        if legacy:
            origin = check_path(record["entry"]["origin"], allow_missing=True)
            dest = check_path(record["entry"]["dest"])
            roots = [p.parent for p in dest.parents if p.name.casefold() == QUARANTINE]
            if len(roots) != 1:
                raise SafetyError("invalid_legacy_quarantine")
            root = roots[0]
            contained(origin, root, missing=True)
            root_id = identity(root)
            expected = snapshot(dest, cancel)
        else:
            original = move_from(record["move"])
            origin, dest, root, root_id = Path(original.source), Path(original.destination), Path(original.root), original.root_identity
            if identity(root) != root_id:
                raise SafetyError("root_or_volume_changed")
            expected = snapshot(dest, cancel)
            if not same_content(expected, original.expected):
                raise SafetyError("quarantine_content_changed")
        if os.path.lexists(origin):
            raise SafetyError("destination_occupied")
        move = Move(uuid.uuid4().hex, str(dest), str(origin), str(root), root_id, expected,
                    None, Kind.EXACT, action="restore", restores=record["id"],
                    raw=origin.suffix.lower() in RAWS, legacy=legacy)
        self._paths(move)
        return Plan(uuid.uuid4().hex, (move,))
