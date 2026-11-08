from dataclasses import asdict
import json
from pathlib import Path
import subprocess
import sys

import pytest

from app.safety.journal import Journal, atomic_json
from app.safety.operations import Operations, make_plan


@pytest.mark.parametrize("stage", ["before_intent", "after_intent", "after_rename", "after_complete"])
def test_real_process_exit_and_restart(scanned, tmp_path, stage):
    plan = make_plan(list(scanned.pairs))
    plan_path = tmp_path / "plan.json"
    atomic_json(plan_path, asdict(plan))
    journal_path = tmp_path / "journal"
    result = subprocess.run([sys.executable, "-B", "-m", "tests.crash_worker", str(tmp_path),
                             str(journal_path), str(plan_path), stage], capture_output=True, timeout=30)
    assert result.returncode == 73, result.stderr.decode(errors="replace")
    journal = Journal(journal_path)
    try:
        assert journal.writable, journal.error
        operations = Operations(journal)
        assert operations.recover() == []
        assert operations.recover() == []
        moved = stage in {"after_rename", "after_complete"}
        assert Path(plan.moves[0].source).exists() != moved
        assert Path(plan.moves[0].destination).exists() == moved
        records = journal.records()
        if stage == "before_intent":
            assert not records
        else:
            assert records[0]["state"] == ("complete" if moved else "not_moved")
        if moved:
            restore = operations.restore_plan()
            from app.core.models import Approval
            operations.execute(restore, Approval(restore))
            assert Path(plan.moves[0].source).exists()
    finally:
        journal.close()


def test_os_lock_excludes_other_process(tmp_path):
    journal_path = tmp_path / "journal"
    journal = Journal(journal_path)
    try:
        result = subprocess.run([sys.executable, "-B", "-m", "tests.crash_worker", str(tmp_path),
                                 str(journal_path), str(tmp_path / "unused.json"), "probe"],
                                capture_output=True, timeout=30)
        assert result.returncode == 0, result.stderr.decode(errors="replace")
        assert json.loads(result.stdout) == {"writable": False}
    finally:
        journal.close()
