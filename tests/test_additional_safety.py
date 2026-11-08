from dataclasses import replace
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from threading import Event, Timer

import pytest

from app.core.models import Approval, Cancelled, SafetyError
from app.safety.journal import Journal
from app.safety.operations import make_plan
from app.scanning.scanner import inspect


def test_cancel_after_intent_completes_active_move(scanned, operations, monkeypatch):
    pair = scanned.pairs[0]
    c = Path(pair.dup.root) / "c.png"
    shutil.copy2(pair.dup.path, c)
    third = inspect(c, Path(pair.dup.root))
    plan = make_plan([pair, replace(pair, dup=third)], bulk=True)
    cancel = Event()
    begin = operations.journal.begin

    def stop_after_intent(move):
        begin(move)
        cancel.set()

    monkeypatch.setattr(operations.journal, "begin", stop_after_intent)
    with pytest.raises(Cancelled):
        operations.execute(plan, Approval(plan), cancel)
    assert not Path(pair.dup.path).exists()
    assert c.exists()
    assert operations.journal.records()[0]["state"] == "complete"


def test_decoder_cancel_kills_active_child(collection, monkeypatch):
    import app.scanning.decoder as decoder
    real_popen = decoder.subprocess.Popen
    children = []
    cancel = Event()

    def slow(args, **kwargs):
        child = real_popen([sys.executable, "-B", "-c", "import time; time.sleep(30)"], **kwargs)
        children.append(child)
        cancel.set()
        return child

    monkeypatch.setattr(decoder.subprocess, "Popen", slow)
    with pytest.raises(Cancelled):
        decoder.decode(collection / "a.png", cancel)
    assert children and children[0].poll() is not None


@pytest.mark.parametrize("value", [[], {"roots": "bad"}, {"moves": "bad"}, {"roots": [42]}])
def test_invalid_settings_never_silently_empty(tmp_path, value):
    from app.services.state import load_state
    path = tmp_path / "state.json"
    path.write_text(json.dumps(value), encoding="utf-8")
    with pytest.raises(SafetyError):
        load_state(path)
    assert json.loads(path.read_text()) == value


def test_disconnected_drive_pending_then_reconnect(scanned, operations):
    plan = make_plan(list(scanned.pairs))
    operations.journal.begin(plan.moves[0])
    root = Path(plan.moves[0].root)
    detached = root.with_name("disconnected")
    root.rename(detached)  # Synthetic simulation, not a real removable drive.
    try:
        assert operations.recover()
        assert operations.journal.records()[0]["state"] == "blocked"
    finally:
        detached.rename(root)
    assert operations.recover() == []
    assert operations.journal.records()[0]["state"] == "not_moved"


@pytest.mark.windows_only
@pytest.mark.skipif(sys.platform != "win32", reason="Windows handle sharing semantics")
def test_windows_handles_pin_source_keeper_and_parents(scanned, operations, monkeypatch):
    plan = make_plan(list(scanned.pairs))
    begin = operations.journal.begin
    blocked = []

    def attempt_replacement(move):
        begin(move)
        for p in (Path(move.source), Path(move.keeper.path), Path(move.source).parent):
            try:
                p.rename(p.with_name(p.name + ".replaced"))
            except PermissionError:
                blocked.append(p)
            else:
                pytest.fail(f"Unpinned path: {p}")

    monkeypatch.setattr(operations.journal, "begin", attempt_replacement)
    operations.execute(plan, Approval(plan))
    assert len(blocked) == 3


def test_legacy_restore_cannot_escape_root(scanned, operations, tmp_path):
    pair = scanned.pairs[0]
    dest = Path(pair.dup.root) / ".photo_agent_quarantine" / "old.png"
    dest.parent.mkdir()
    dest.write_bytes(Path(pair.dup.path).read_bytes())
    state = tmp_path / "legacy.json"
    state.write_text(json.dumps({"moves": [{"origin": str(tmp_path / "outside.png"), "dest": str(dest)}]}))
    operations.journal.import_legacy(state)
    with pytest.raises(SafetyError, match="outside_root"):
        operations.restore_plan()
    assert dest.exists() and not (tmp_path / "outside.png").exists()


def test_unsupported_platform_fails_without_moving(scanned, operations, monkeypatch):
    import app.safety.native as native
    plan = make_plan(list(scanned.pairs))
    monkeypatch.setattr(native.sys, "platform", "unsupported")
    with pytest.raises(SafetyError, match="platform_unsupported"):
        operations.execute(plan, Approval(plan))
    assert Path(plan.moves[0].source).exists()
    assert not operations.journal.records()


def test_preflight_rejects_old_python(monkeypatch):
    import app.services.preflight as preflight
    monkeypatch.setattr(preflight.sys, "version_info", (3, 11))
    with pytest.raises(RuntimeError, match="Python >= 3.12"):
        preflight.check()


def test_cross_device_move_fails_without_copy_delete(scanned, operations, monkeypatch):
    plan = make_plan(list(scanned.pairs))
    destination_parent = Path(plan.moves[0].destination).parent
    original = Path.stat

    class OtherDevice:
        def __init__(self, st):
            self.stat = st
            self.st_dev = st.st_dev + 1

        def __getattr__(self, name):
            return getattr(self.stat, name)

    def stat(path, *args, **kwargs):
        value = original(path, *args, **kwargs)
        return OtherDevice(value) if path == destination_parent else value

    monkeypatch.setattr(Path, "stat", stat)
    with pytest.raises(SafetyError, match="cross_device_move"):
        operations.execute(plan, Approval(plan))
    assert Path(plan.moves[0].source).exists()
    assert not Path(plan.moves[0].destination).exists()
    assert not operations.journal.records()


def test_core_and_safety_import_without_tkinter():
    result = subprocess.run([sys.executable, "-B", "-c",
                             "import sys; import app.core.models, app.safety.operations, app.scanning.scanner; assert 'tkinter' not in sys.modules"],
                            capture_output=True, timeout=30)
    assert result.returncode == 0, result.stderr.decode(errors="replace")
