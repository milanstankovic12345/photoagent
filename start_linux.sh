#!/usr/bin/env bash
set -e

cd "$(dirname "$0")"

if [ ! -x ".venv/bin/python" ]; then
    python3 -m venv .venv
fi

if ! .venv/bin/python -c "import PIL, imagehash, rawpy"; then
    .venv/bin/python -m pip install -r requirements.txt
fi

.venv/bin/python photo_agent.py