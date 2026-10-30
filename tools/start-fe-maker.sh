#!/bin/sh
# FE Maker: first launch installs what it needs in .venv (Python 3.10 or later required), then starts.
cd "$(dirname "$0")" || exit 1
if [ ! -x .venv/bin/python ]; then
    python3 -m venv .venv || exit 1
    .venv/bin/python -m pip install --quiet -e ./server || exit 1
fi
exec .venv/bin/python -m fe_maker
