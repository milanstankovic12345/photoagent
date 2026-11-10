"""Task014 audit replay; reuse existing synthetic drivers without changing the app.

Run from the repository root:
  .venv/Scripts/python.exe -B docs/design/verification/task014-20261110/capture.py
The evidence destination must be new. All state and operations are disposable.
"""
from __future__ import annotations

import os
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT))
os.environ['QT_QPA_PLATFORM'] = 'offscreen'
os.environ['QT_SCALE_FACTOR'] = '1'

from tools.capture_task011 import run
from tools.capture_task012 import isolated_framework_settings


if __name__ == '__main__':
    with tempfile.TemporaryDirectory(prefix='photoagent-task014-qt-') as private:
        with isolated_framework_settings(Path(private)):
            run(Path(__file__).parent / 'baseline', scenarios=True)
