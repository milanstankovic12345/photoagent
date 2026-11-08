from dataclasses import FrozenInstanceError, replace
import os
from pathlib import Path
from queue import Queue
import shutil
from threading import Event

from PIL import Image
import pytest

from app.core.models import Cancelled, Kind, SafetyError
from app.matching.matcher import match
from app.safety.paths import QUARANTINE, check_path, snapshot
from app.scanning.scanner import inspect, roots_for_scan, scan


def run(*roots):
    return scan([str(r) for r in roots], Queue(), Event())


def test_three_copies_overlapping_roots_stable_keeper(collection):
    sub = collection / "sub"
    sub.mkdir()
    shutil.copy2(collection / "a.png", sub / "c.png")
    result = run(collection, sub, collection)
    assert result.complete, result.errors
    assert len(result.photos) == 3
    assert len(result.pairs) == 2
    assert {p.keep.path for p in result.pairs} == {str(collection / "a.png")}
    assert all(p.kind == Kind.EXACT and len(p.dup.sha256) == 64 for p in result.pairs)
    with pytest.raises(FrozenInstanceError):
        result.pairs[0].dup.path = "changed"


def test_root_selection_priority(collection, tmp_path):
    other = tmp_path / "first"
    other.mkdir()
    shutil.copy2(collection / "a.png", other / "z.png")
    result = run(other, collection)
    assert len(result.pairs) == 2
    assert all(p.keep.root == str(other) for p in result.pairs)


def test_hardlinks_deduplicated(collection):
    try:
        os.link(collection / "a.png", collection / "alias.png")
    except OSError as exc:
        pytest.skip(f"hardlinks unavailable: {exc}")
    result = run(collection)
    assert len(result.photos) == 2
    assert len(result.pairs) == 1
    assert result.pairs[0].keep.snapshot.identity != result.pairs[0].dup.snapshot.identity


def test_missing_root_incomplete(collection, tmp_path):
    result = run(collection, tmp_path / "offline")
    assert not result.complete
    assert len(result.photos) == 2 and result.errors


def test_quarantine_ancestors_excluded(collection):
    q = collection / QUARANTINE / "date" / "sub"
    q.mkdir(parents=True)
    shutil.copy2(collection / "a.png", q / "hidden.png")
    result = run(collection, q)
    assert len(result.photos) == 2
    assert not result.complete
    assert not roots_for_scan([str(q)])


def test_symlink_root_and_ancestor_rejected(collection, tmp_path):
    link = tmp_path / "link"
    try:
        link.symlink_to(collection, target_is_directory=True)
    except OSError as exc:
        pytest.skip(f"symlink privilege unavailable: {exc}")
    result = run(link)
    assert not result.photos and not result.complete
    with pytest.raises(SafetyError, match="redirected_path"):
        check_path(link / "a.png")


@pytest.mark.windows_only
@pytest.mark.skipif(os.name != "nt", reason="Windows junctions")
def test_junction_rejected(collection, tmp_path):
    import subprocess
    link = tmp_path / "junction"
    created = subprocess.run(["cmd", "/c", "mklink", "/J", str(link), str(collection)], capture_output=True)
    if created.returncode:
        pytest.skip("junction creation unavailable")
    try:
        assert not run(link).complete
        with pytest.raises(SafetyError, match="redirected_path"):
            check_path(link / "a.png")
    finally:
        # rmdir removes only the junction, never recursively touches its target.
        link.rmdir()


def test_parent_traversal_rejected(collection):
    with pytest.raises(SafetyError, match="parent_traversal"):
        check_path(collection / ".." / collection.name / "a.png")


def test_cancel_before_and_during_hash(collection, monkeypatch):
    cancel = Event()
    cancel.set()
    result = scan([str(collection)], Queue(), cancel)
    assert result.cancelled and not result.pairs and not result.complete
    cancel.clear()
    import app.safety.paths as paths
    real = paths.cancelled
    checks = []

    def stop(event):
        checks.append(True)
        if len(checks) == 2:
            cancel.set()
        real(event)

    monkeypatch.setattr(paths, "CHUNK", 10)
    monkeypatch.setattr(paths, "cancelled", stop)
    with pytest.raises(Cancelled):
        snapshot(collection / "a.png", cancel)
    assert len(checks) == 2


def test_corrupt_raw_and_images_have_binary_matches(tmp_path):
    root = tmp_path / "corrupt"
    root.mkdir()
    (root / "a.nef").write_bytes(b"not a raw")
    (root / "b.nef").write_bytes(b"not a raw")
    (root / "bad.jpg").write_bytes(b"bad jpg")
    result = run(root)
    assert not result.complete and len(result.photos) == 3
    assert len(result.pairs) == 1 and result.pairs[0].kind == Kind.EXACT
    from app.safety.operations import make_plan
    assert not make_plan(list(result.pairs), bulk=True).moves


def test_png_jpeg_webp_variants(collection):
    with Image.open(collection / "a.png") as image:
        image.save(collection / "render.jpg", quality=95)
        with image.resize((64, 48)) as small:
            small.save(collection / "small.webp", quality=85)
    result = run(collection)
    assert result.complete, result.errors
    assert sum(p.kind == Kind.EXACT for p in result.pairs) == 1
    assert sum(p.kind == Kind.VISUAL for p in result.pairs) == 2
    assert all(p.keep.sha256 and p.dup.sha256 for p in result.pairs)


def test_different_solid_colors_never_exact(tmp_path):
    for color in ("red", "blue"):
        with Image.new("RGB", (32, 32), color) as image:
            image.save(tmp_path / f"{color}.png")
    result = run(tmp_path)
    assert len(result.pairs) == 1
    assert result.pairs[0].kind == Kind.VISUAL
    from app.safety.operations import make_plan
    assert not make_plan(list(result.pairs), bulk=True).moves


def test_visual_chain_is_not_transitive(scanned):
    base = scanned.photos[0]
    # A~B (4 bits), B~C (4), A!~C (8). Same quality fixes order A,B,C.
    a = replace(base, path="z-A", phash="0000000000000000", dhash="0000000000000000")
    b = replace(base, path="y-B", phash="000000000000000f", dhash="000000000000000f",
                snapshot=replace(base.snapshot, sha256="1" * 64))
    c = replace(base, path="x-C", phash="00000000000000ff", dhash="00000000000000ff",
                snapshot=replace(base.snapshot, sha256="2" * 64))
    pairs = match([a, b, c], [base.root])
    assert [(p.keep.path, p.dup.path) for p in pairs] == [(a.path, b.path)]


def test_permission_failure_reported(collection, monkeypatch):
    import app.scanning.scanner as scanner
    original = scanner.inspect

    def deny(path, root, cancel):
        if path.name == "b.png":
            raise PermissionError("synthetic access denied")
        return original(path, root, cancel)

    monkeypatch.setattr(scanner, "inspect", deny)
    result = run(collection)
    assert not result.complete and len(result.photos) == 1
    assert "synthetic access denied" in "\n".join(result.errors)
