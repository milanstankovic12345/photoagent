#!/usr/bin/env bash
set -e

cd "$(dirname "$0")"

python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3, 12) else "Python >= 3.12 required")'

if [ ! -x ".venv/bin/python" ]; then
    python3 -m venv .venv
fi

if ! .venv/bin/python -B -m app.services.preflight "$@"; then
    .venv/bin/python -m pip install -r requirements.txt
fi

.venv/bin/python -B -m app.services.preflight "$@"
.venv/bin/python -B photo_agent.py "$@"
