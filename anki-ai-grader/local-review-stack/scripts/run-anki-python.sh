#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source "$ROOT/versions.env"
ANKI_PYTHON="${ANKI_PYTHON:-$HOME/Library/Application Support/AnkiProgramFiles/.venv/bin/python}"

if [[ -n "${ANKI_APP_RESOURCES:-}" ]]; then
  export ANKI_APP_RESOURCES
  exec "$ANKI_PYTHON" "$ROOT/scripts/anki_python_bootstrap.py" "$@"
else
  exec "$ANKI_PYTHON" "$@"
fi
