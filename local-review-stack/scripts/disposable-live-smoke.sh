#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source "$ROOT/versions.env"
ANKI_BIN="${ANKI_LAUNCHER:-$HOME/Library/Application Support/AnkiProgramFiles/.venv/bin/anki}"
INSTALLED="${ANKI_CONNECT_TARGET:-$HOME/Library/Application Support/Anki2/addons21/2055492159}"
BASE="$(mktemp -d "${TMPDIR:-/tmp}/anki-chat-review-live.XXXXXX")"
PORT="${ANKI_SMOKE_PORT:-18765}"
ANKI_RUNNER="$ROOT/scripts/run-anki-python.sh"

cleanup() {
  if [[ -n "${ANKI_PID:-}" ]]; then
    kill "$ANKI_PID" >/dev/null 2>&1 || true
    wait "$ANKI_PID" >/dev/null 2>&1 || true
  fi
  rm -rf "$BASE"
}
trap cleanup EXIT

mkdir -p "$BASE/addons21"
cp -R "$INSTALLED" "$BASE/addons21/2055492159"
python3 -c 'import json,sys; p=sys.argv[1]; port=int(sys.argv[2]); d=json.load(open(p)); d["webBindPort"]=port; json.dump(d,open(p,"w"),indent=4)' "$BASE/addons21/2055492159/config.json" "$PORT"
"$ANKI_RUNNER" -c 'from pathlib import Path; import sys; from aqt.profiles import ProfileManager; pm=ProfileManager(Path(sys.argv[1])); pm.setupMeta(); pm.create("Disposable"); pm.db.close()' "$BASE"

"$ANKI_BIN" -b "$BASE" -p Disposable -l en >"$BASE/anki.log" 2>&1 &
ANKI_PID=$!
for _ in $(seq 1 120); do
  if curl -fsS -X POST -H 'Content-Type: application/json' -d '{"action":"chatReviewCapabilities","version":6}' "http://127.0.0.1:$PORT" >/dev/null 2>&1; then
    break
  fi
  sleep 0.5
done

python3 "$ROOT/scripts/live_smoke.py" --url "http://127.0.0.1:$PORT"
echo "Disposable Anki base: $BASE (removed on exit)"
