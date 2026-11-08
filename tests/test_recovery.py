from dataclasses import asdict, replace
import json
import os
from pathlib import Path

import pytest

from app.core.models import Approval, Identity, SafetyError
from app.safety.journal import Journal
from app.safety.operations import Operations, make_plan


def test_intent_write_failure_never_moves(scanned, operations, monkeypatch):
    plan = make_plan(list(scanned.pairs))

    def fail(record):
        raise OSError("synthetic disk full")

    monkeypatch.setattr(operations.journal, "_save", fail)
    with pytest.raises(OSError, match="disk full"):
        operations.execute(plan, Approval(plan))
    assert Path(plan.moves[0].source).exists()
    assert not Path(plan.moves[0].destination).exists()


def test_final_write_failure_reconciles_without_rollback(scanned, operations, monkeypatch):
    plan = make_plan(list(scanned.pairs))
    original = operations.journal.transition
    monkeypatch.setattr(operations.journal, "transition", lambda *a: (_ for _ in ()).throw(OSError("final write")))
    with pytest.raises(OSError, match="final write"):
        operations.execute(plan, Approval(plan))
    assert not Path(plan.moves[0].source).exists()
    assert Path(plan.moves[0].destination).exists()
    assert operations.journal.records()[0]["state"] == "intent"
    monkeypatch.setattr(operations.journal, "transition", original)
    assert operations.recover() == []
    assert operations.recover() == []
    assert operations.journal.records()[0]["state"] == "complete"


def test_rename_failure_recovers_not_moved(scanned, operations, monkeypatch):
    import app.safety.operations as service
    real = service.rename_verified

    def fail(source, dest, keeper, verify, expected):
        # Verification + durable intent happen normally, then the adapter fails.
        def verified(a, b):
            verify(a, b)
            raise OSError("synthetic rename failure")
        real(source, dest, keeper, verified, expected)

    monkeypatch.setattr(service, "rename_verified", fail)
    plan = make_plan(list(scanned.pairs))
    with pytest.raises(OSError):
        operations.execute(plan, Approval(plan))
    assert operations.recover() == []
    assert operations.journal.records()[0]["state"] == "not_moved"
    assert Path(plan.moves[0].source).exists()


@pytest.mark.parametrize("scenario", ["both", "neither", "changed", "wrong_disk"])
def test_ambiguous_recovery_blocks_preserves_evidence(scanned, operations, scenario):
    plan = make_plan(list(scanned.pairs))
    move = plan.moves[0]
    if scenario == "wrong_disk":
        move = replace(move, root_identity=Identity(-1, -1))
    operations.journal.begin(move)
    if scenario == "both":
        Path(move.destination).parent.mkdir(parents=True)
        Path(move.destination).write_bytes(Path(move.source).read_bytes())
    elif scenario == "neither":
        Path(move.source).unlink()  # Synthetic fixture only.
    elif scenario == "changed":
        Path(move.source).write_bytes(b"different")
    assert operations.recover()
    assert operations.journal.records()[0]["state"] == "blocked"
    assert operations.recover()
    assert len(operations.journal.records()[0]["transitions"]) == 3
    with pytest.raises(SafetyError, match="recovery_required"):
        operations.execute(plan, Approval(plan))


def test_single_writer_and_corrupt_manifest(tmp_path):
    directory = tmp_path / "journal"
    first = Journal(directory)
    second = Journal(directory)
    try:
        assert first.writable and not second.writable
        with pytest.raises(SafetyError):
            second.require_writer()
    finally:
        first.close()
        second.close()
    bad = directory / ("a" * 32 + ".json")
    bad.write_text("broken", encoding="utf-8")
    third = Journal(directory)
    try:
        assert not third.writable and third.error
        assert bad.read_text() == "broken"
    finally:
        third.close()


def test_legacy_backup_import_confirmation_and_retained_history(scanned, operations, tmp_path):
    pair = scanned.pairs[0]
    dest = Path(pair.dup.root) / ".photo_agent_quarantine" / "old" / "copy.png"
    dest.parent.mkdir(parents=True)
    # Emulate the historical program with synthetic bytes, without moving originals.
    dest.write_bytes(Path(pair.dup.path).read_bytes())
    origin = Path(pair.dup.root) / "restored_legacy.png"
    state = tmp_path / "legacy.json"
    raw = json.dumps({"roots": [pair.dup.root], "moves": [{"origin": str(origin), "dest": str(dest)}]}).encode()
    state.write_bytes(raw)
    operations.journal.import_legacy(state)
    operations.journal.import_legacy(state)
    assert len(operations.journal.records()) == 1
    backups = list(tmp_path.glob("legacy.json.legacy-*.bak"))
    assert len(backups) == 1 and backups[0].read_bytes() == raw
    plan = operations.restore_plan()
    assert plan.moves[0].legacy
    with pytest.raises(SafetyError, match="legacy_confirmation_required"):
        operations.execute(plan, Approval(plan))
    operations.execute(plan, Approval(plan, legacy=True))
    assert origin.read_bytes() == Path(pair.keep.path).read_bytes()
    assert state.read_bytes() == raw
    assert len(operations.journal.records()) == 2


def test_corrupt_legacy_never_empty(tmp_path, operations):
    from app.services.state import load_state
    path = tmp_path / "state.json"
    path.write_text("{bad json", encoding="utf-8")
    with pytest.raises(ValueError):
        load_state(path)
    with pytest.raises(ValueError):
        operations.journal.import_legacy(path)
    assert path.read_text() == "{bad json"
