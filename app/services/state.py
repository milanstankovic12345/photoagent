from __future__ import annotations

import json
import os
from pathlib import Path

from app.core.models import SafetyError
from app.safety.journal import atomic_json
from app.safety.paths import check_path


def load_state(path: Path) -> dict:
    if not os.path.lexists(path):
        return {"roots": [], "moves": []}
    value = json.loads(check_path(path).read_text(encoding="utf-8"))
    if (not isinstance(value, dict) or not isinstance(value.get("roots", []), list)
            or not all(isinstance(r, str) for r in value.get("roots", []))
            or not isinstance(value.get("moves", []), list)):
        raise SafetyError("invalid_settings_or_history")
    return {"roots": value.get("roots", []), "moves": value.get("moves", [])}


def save_state(path: Path, value: dict) -> None:
    atomic_json(path, value)
