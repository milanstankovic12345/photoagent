from __future__ import annotations

import json
import os
from pathlib import Path

from app.core.models import SafetyError
from app.safety.journal import atomic_json
from app.safety.paths import check_path


def load_state(path: Path) -> dict:
    if not os.path.lexists(path):
        # Only true absence is a fresh installation. An existing legacy file
        # without language keeps Serbian through validated_settings below.
        return {"roots": [], "moves": [], "language": "en"}
    value = json.loads(check_path(path).read_text(encoding="utf-8"))
    if (not isinstance(value, dict) or not isinstance(value.get("roots", []), list)
            or not all(isinstance(r, str) for r in value.get("roots", []))
            or not isinstance(value.get("moves", []), list)):
        raise SafetyError("invalid_settings_or_history")
    return {**value, "roots": value.get("roots", []), "moves": value.get("moves", [])}


def validated_settings(value: dict) -> tuple[dict, list[str]]:
    result = dict(value)
    warnings = []
    defaults = {'theme': 'dark', 'language': 'sr_Latn', 'phash_max': 4, 'dhash_max': 6}
    for key, default in defaults.items():
        item = result.get(key, default)
        valid = (item in ('dark', 'light', 'system') if key == 'theme' else
                 item in ('en', 'sr_Latn') if key == 'language' else
                 type(item) is int and 0 <= item <= 64)
        if not valid:
            warnings.append('invalid_setting:' + key)
            item = 'en' if key == 'language' else default
        result[key] = item
    return result, warnings


def save_state(path: Path, value: dict) -> None:
    atomic_json(path, value)
