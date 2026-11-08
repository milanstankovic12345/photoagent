from dataclasses import replace
import os
from pathlib import Path

import pytest

from app.core.models import Approval, Identity, Kind, SafetyError
from app.safety.operations import make_plan


def test_identity_replacement_same_bytes_rejected(scanned, operations):
    plan = make_plan(list(scanned.pairs))
    path = Path(plan.moves[0].source)
    st = path.stat()
    replacement = path.with_name("new.png")
    replacement.write_bytes(path.read_bytes())
    os.utime(replacement, ns=(st.st_atime_ns, st.st_mtime_ns))
    os.replace(replacement, path)
    with pytest.raises(SafetyError, match="source_changed"):
        operations.execute(plan, Approval(plan))
    assert path.exists()


def test_root_replacement_blocks(scanned, operations):
    plan = make_plan(list(scanned.pairs))
    move = replace(plan.moves[0], root_identity=Identity(-1, -1))
    plan = replace(plan, moves=(move,))
    with pytest.raises(SafetyError, match="root_or_volume_changed"):
        operations.execute(plan, Approval(plan))


@pytest.mark.parametrize("action", ["quarantine", "restore"])
def test_late_destination_conflict_preserves_both_files(scanned, operations, monkeypatch, action):
    plan = make_plan(list(scanned.pairs))
    if action == "restore":
        operations.execute(plan, Approval(plan))
        plan = operations.restore_plan()
    move = plan.moves[0]
    source_bytes = Path(move.source).read_bytes()
    begin = operations.journal.begin

    def conflict(m):
        begin(m)
        # Create a destination after every user/path check and durable intent.
        Path(m.destination).write_bytes(b"late arrival: must survive")

    monkeypatch.setattr(operations.journal, "begin", conflict)
    with pytest.raises(OSError):
        operations.execute(plan, Approval(plan))
    assert Path(move.source).read_bytes() == source_bytes
    assert Path(move.destination).read_bytes() == b"late arrival: must survive"
    assert operations.recover()  # Both paths remain ambiguous, no automated move.


def test_quarantined_bytes_changed_refuses_restore(scanned, operations):
    plan = make_plan(list(scanned.pairs))
    operations.execute(plan, Approval(plan))
    Path(plan.moves[0].destination).write_bytes(b"changed quarantine")
    with pytest.raises(SafetyError, match="quarantine_content_changed"):
        operations.restore_plan()


def test_sidecar_added_after_approval_blocks_bulk(scanned, operations):
    plan = make_plan(list(scanned.pairs), bulk=True)
    xmp = Path(plan.moves[0].source).with_suffix(".XMP")
    xmp.write_bytes(b"editing history")
    with pytest.raises(SafetyError, match="sidecars_changed"):
        operations.execute(plan, Approval(plan))
    assert xmp.read_bytes() == b"editing history"


def test_individual_sidecar_never_moved(scanned, operations):
    xmp = Path(scanned.pairs[0].dup.path).with_suffix(".xmp")
    xmp.write_bytes(b"editing history")
    plan = make_plan(list(scanned.pairs))
    operations.execute(plan, Approval(plan))
    assert xmp.read_bytes() == b"editing history"


def test_raw_requires_typed_confirmation(scanned, operations):
    pair = replace(scanned.pairs[0], dup=replace(scanned.pairs[0].dup, is_raw=True))
    plan = make_plan([pair])
    with pytest.raises(SafetyError, match="raw_confirmation_required"):
        operations.execute(plan, Approval(plan))
    assert Path(pair.dup.path).exists()


def test_visual_same_size_mtime_edit_blocked_by_full_digest(scanned, operations):
    pair = replace(scanned.pairs[0], kind=Kind.VISUAL)
    plan = make_plan([pair])
    path = Path(pair.dup.path)
    st = path.stat()
    path.write_bytes(b"z" * st.st_size)
    os.utime(path, ns=(st.st_atime_ns, st.st_mtime_ns))
    with pytest.raises(SafetyError, match="source_changed"):
        operations.execute(plan, Approval(plan))


def test_path_escape_and_symlink_destination(scanned, operations, tmp_path):
    plan = make_plan(list(scanned.pairs))
    outside = tmp_path / "outside"
    outside.mkdir()
    bad = replace(plan, moves=(replace(plan.moves[0], destination=str(outside / "escape.png")),))
    with pytest.raises(SafetyError, match="outside_root"):
        operations.execute(bad, Approval(bad))
    q = Path(scanned.pairs[0].dup.root) / ".photo_agent_quarantine"
    try:
        q.symlink_to(outside, target_is_directory=True)
    except OSError as exc:
        pytest.skip(f"symlink privilege unavailable: {exc}")
    with pytest.raises(SafetyError, match="redirected_path"):
        operations.execute(plan, Approval(plan))
    assert not list(outside.iterdir())


@pytest.mark.linux_only
@pytest.mark.skipif(not os.sys.platform.startswith("linux"), reason="Native Linux execution unavailable on Windows")
def test_linux_no_replace(scanned, operations):
    plan = make_plan(list(scanned.pairs))
    operations.execute(plan, Approval(plan))
    assert Path(plan.moves[0].destination).exists()
