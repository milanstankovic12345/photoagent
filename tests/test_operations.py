from dataclasses import replace
import os
from pathlib import Path

import pytest

from app.core.models import Approval, Kind, SafetyError
from app.safety.operations import make_plan


def test_quarantine_restore_restart(scanned, operations):
    pair = scanned.pairs[0]
    original = Path(pair.dup.path).read_bytes()
    plan = make_plan([pair], bulk=True)
    assert len(plan.moves) == 1
    operations.execute(plan, Approval(plan))
    assert not Path(pair.dup.path).exists()
    assert Path(pair.keep.path).read_bytes() == original
    assert operations.recover() == []
    restore = operations.restore_plan()
    operations.execute(restore, Approval(restore))
    assert Path(pair.dup.path).read_bytes() == original
    assert len(operations.journal.records()) == 2
    assert all(r["state"] == "complete" for r in operations.journal.records())


@pytest.mark.parametrize("which", ["keep", "dup"])
def test_same_size_mtime_changes_blocked(scanned, operations, which):
    pair = scanned.pairs[0]
    plan = make_plan([pair])
    path = Path(getattr(pair, which).path)
    st = path.stat()
    path.write_bytes(b"x" * st.st_size)
    os.utime(path, ns=(st.st_atime_ns, st.st_mtime_ns))
    with pytest.raises((SafetyError, OSError)):
        operations.execute(plan, Approval(plan))
    assert Path(pair.dup.path).exists()
    assert operations.journal.records() == []


def test_no_approval_and_plan_changed(scanned, operations):
    plan = make_plan(list(scanned.pairs))
    with pytest.raises(SafetyError, match="approval_plan_mismatch"):
        operations.execute(plan, Approval(replace(plan, id="different")))
    assert Path(plan.moves[0].source).exists()


def test_bulk_visual_raw_cross_root_sidecar(scanned, tmp_path):
    pair = scanned.pairs[0]
    assert not make_plan([replace(pair, kind=Kind.VISUAL)], bulk=True).moves
    assert not make_plan([replace(pair, keep=replace(pair.keep, is_raw=True))], bulk=True).moves
    assert not make_plan([replace(pair, dup=replace(pair.dup, is_raw=True))], bulk=True).moves
    other = tmp_path / "other"
    other.mkdir()
    import shutil
    p = other / "a.png"
    shutil.copy2(pair.keep.path, p)
    from app.scanning.scanner import inspect
    assert not make_plan([replace(pair, keep=inspect(p, other))], bulk=True).moves
    xmp = Path(pair.dup.path).with_suffix(".xmp")
    xmp.write_bytes(b"metadata")
    assert not make_plan([pair], bulk=True).moves
    assert make_plan([pair]).moves[0].xmp == (str(xmp),)


def test_self_and_dependency(scanned):
    pair = scanned.pairs[0]
    with pytest.raises(SafetyError, match="self_comparison"):
        make_plan([replace(pair, dup=pair.keep)])
    reverse = replace(pair, keep=pair.dup, dup=pair.keep)
    with pytest.raises(SafetyError, match="keeper_dependency"):
        make_plan([pair, reverse])
    assert len(make_plan([pair, pair]).moves) == 1


def test_destination_conflict_and_restore_conflict(scanned, operations):
    plan = make_plan(list(scanned.pairs))
    dest = Path(plan.moves[0].destination)
    dest.parent.mkdir(parents=True)
    dest.write_bytes(b"occupied")
    with pytest.raises(SafetyError, match="destination_occupied"):
        operations.execute(plan, Approval(plan))
    assert dest.read_bytes() == b"occupied"
    plan = make_plan(list(scanned.pairs))
    operations.execute(plan, Approval(plan))
    restore = operations.restore_plan()
    Path(restore.moves[0].destination).write_bytes(b"new original")
    with pytest.raises(SafetyError, match="destination_occupied"):
        operations.execute(restore, Approval(restore))
    assert Path(restore.moves[0].destination).read_bytes() == b"new original"
