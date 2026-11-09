#!/usr/bin/env bash
set -eu
cd -- "$(dirname -- "$0")"
if [ ! -x .runtime/bin/python ]; then
    echo 'Run the matching Python install_offline.py first. No network installation is attempted.' >&2
    exit 1
fi
exec .runtime/bin/python -X utf8 -E -s -B photo_agent.py "$@"
