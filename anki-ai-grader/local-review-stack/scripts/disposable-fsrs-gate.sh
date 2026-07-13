#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source "$ROOT/versions.env"
ANKI_PYTHON="${ANKI_PYTHON:-$HOME/Library/Application Support/AnkiProgramFiles/.venv/bin/python}"
ANKI_RUNNER="$ROOT/scripts/run-anki-python.sh"
BASE="$(mktemp -d "${TMPDIR:-/tmp}/anki-chat-review-sync.XXXXXX")"
PORT="${ANKI_FSRS_SYNC_PORT:-18766}"

cleanup() {
  if [[ -n "${SYNC_PID:-}" ]]; then
    kill "$SYNC_PID" >/dev/null 2>&1 || true
    wait "$SYNC_PID" >/dev/null 2>&1 || true
  fi
  rm -rf "$BASE"
}
trap cleanup EXIT

SYNC_USER1=gate:gatepass SYNC_BASE="$BASE/server" SYNC_PORT="$PORT" \
  "$ANKI_RUNNER" -m anki.syncserver >"$BASE/sync-server.log" 2>&1 &
SYNC_PID=$!
for _ in $(seq 1 100); do
  if nc -z 127.0.0.1 "$PORT" >/dev/null 2>&1; then
    break
  fi
  if ! kill -0 "$SYNC_PID" >/dev/null 2>&1; then
    cat "$BASE/sync-server.log" >&2
    exit 1
  fi
  sleep 0.1
done
nc -z 127.0.0.1 "$PORT" >/dev/null 2>&1 || {
  cat "$BASE/sync-server.log" >&2
  echo "Disposable Anki sync server did not start" >&2
  exit 1
}

args=(
  "$ROOT/anki-connect/tests/chat_review_fsrs_compat.py"
  --sync-endpoint "http://127.0.0.1:$PORT/"
)
if [[ -n "${ANKI_CANDIDATE_VERSION:-}" ]]; then
  args+=(--candidate-version "$ANKI_CANDIDATE_VERSION")
fi
"$ANKI_RUNNER" "${args[@]}"
echo "Disposable FSRS sync base: $BASE (removed on exit)"
