"""Executed only by tests, always confined to an explicit synthetic sandbox."""
from dataclasses import replace
import json
import os
from pathlib import Path
import sys

from app.core.models import Approval, Plan
from app.safety.journal import Journal, move_from
from app.safety.operations import Operations


def main():
    sandbox, journal_path, plan_path = map(Path, sys.argv[1:4])
    assert journal_path.is_relative_to(sandbox) and plan_path.is_relative_to(sandbox)
    import app.safety.paths as paths
    original = paths.absolute

    def confined(path):
        result = original(path)
        assert result.is_relative_to(sandbox), result
        return result

    paths.absolute = confined
    journal = Journal(journal_path)
    if sys.argv[4] == "probe":
        print(json.dumps({"writable": journal.writable}))
        journal.close()
        return
    data = json.loads(plan_path.read_text(encoding="utf-8"))
    plan = Plan(data["id"], tuple(move_from(m) for m in data["moves"]), data["bulk"])
    stage = sys.argv[4]
    real_begin = journal.begin
    real_transition = journal.transition

    def begin(move):
        if stage == "before_intent":
            os._exit(73)
        real_begin(move)
        if stage == "after_intent":
            os._exit(73)

    def transition(operation_id, state, detail=""):
        if stage == "after_rename":
            os._exit(73)
        real_transition(operation_id, state, detail)
        if stage == "after_complete":
            os._exit(73)

    journal.begin = begin
    journal.transition = transition
    Operations(journal).execute(plan, Approval(plan))
    raise AssertionError("Expected a process boundary exit")


if __name__ == "__main__":
    main()
