#!/bin/sh
# The interface tests as the CI runs them (Linux, Playwright's image), from any computer with Docker; the reference
# screenshots are made here: sh e2e/linux.sh --update-snapshots (from ui/). Other arguments go to Playwright.
# UI_DIST: the interface build to test (default ui/dist; build one with npx vite build --outDir <dir>).
set -e
cd "$(dirname "$0")/../.."
repo="$(pwd -W 2>/dev/null || pwd)"
dist="${UI_DIST:-$repo/ui/dist}"
MSYS_NO_PATHCONV=1 docker run --rm --ipc=host \
  -v "$repo:/repo" -v "$dist:/dist:ro" -e FE_MAKER_UI_DIST=/dist -e CI=1 -w /repo/ui \
  mcr.microsoft.com/playwright:v1.59.1-noble sh -c '
    apt-get -qq update >/dev/null && apt-get -qq install -y python3-venv >/dev/null &&
    python3 -m venv /venv && /venv/bin/pip -q install fastapi uvicorn python-multipart pillow numpy certifi &&
    FE_MAKER_PYTHON=/venv/bin/python PYTHONPATH=/repo/server \
      npx playwright test --output /repo/ui/test-results --reporter=line "$@"' playwright "$@"
