#!/usr/bin/env bash
# Build the Cyclia installer on macOS (.dmg) or Linux (.AppImage and .deb). Needs Python 3.10-3.13 and Node.js 20+.
set -euo pipefail
cd "$(dirname "$0")"
PY=$(command -v python3.12 || command -v python3.11 || command -v python3 || true)
[ -z "$PY" ] && { echo "Install Python 3.12 (python.org or your package manager) and run again."; exit 1; }
command -v npm >/dev/null || { echo "Install Node.js LTS from nodejs.org and run again."; exit 1; }
[ -x .buildenv/bin/python ] || "$PY" -m venv .buildenv
.buildenv/bin/python -m pip install --upgrade pip >/dev/null
.buildenv/bin/python engine/build-engine.py
.buildenv/bin/python engine/tools/apply_credits.py
.buildenv/bin/python engine/tools/fetch_world.py || true
cd app
npm install
if [[ "$(uname)" == "Darwin" ]]; then npm run dist:mac; else npm run dist:linux; fi
echo "Done. Installers are in app/dist"
