#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source "$ROOT/versions.env"
ANKI_PYTHON="${ANKI_PYTHON:-$HOME/Library/Application Support/AnkiProgramFiles/.venv/bin/python}"
ANKI_RUNNER="$ROOT/scripts/run-anki-python.sh"
INSTALLED="${ANKI_CONNECT_TARGET:-$HOME/Library/Application Support/Anki2/addons21/2055492159}"
CONFIG="${CODEX_CONFIG:-$HOME/.codex/config.toml}"
SKILL="${CHAT_REVIEW_SKILL_TARGET:-$HOME/.codex/skills/chat-anki-review}"

test -f "$ROOT/anki-mcp-server/dist/main-stdio.js"
grep -q 'chatReviewAnswer' "$ROOT/anki-mcp-server/dist/mcp/primitives/essential/tools/rate-card-and-get-next.tool.js"
"$ANKI_RUNNER" -m py_compile "$ROOT/anki-connect/plugin/__init__.py"
python3 "$ROOT/scripts/render_compat_manifest.py" --check
"$ANKI_RUNNER" "$ROOT/anki-connect/tests/chat_review_protocol_headless.py"
"$ANKI_RUNNER" "$ROOT/anki-connect/tests/chat_review_scheduler_spike.py"
"$ROOT/scripts/disposable-fsrs-gate.sh"

if [[ -f "$INSTALLED/__init__.py" ]]; then
  cmp "$ROOT/anki-connect/plugin/__init__.py" "$INSTALLED/__init__.py"
  cmp "$ROOT/anki-connect/plugin/chat_review_compat.json" "$INSTALLED/chat_review_compat.json"
fi
grep -Fq "$ROOT/anki-mcp-server/dist/main-stdio.js" "$CONFIG"
cmp "$ROOT/chat-anki-review-skill/SKILL.md" "$SKILL/SKILL.md"

if [[ "${1:-}" == "--live" ]]; then
  "$ROOT/scripts/disposable-live-smoke.sh"
fi

echo "Verification passed for Anki $ANKI_VERSION and $TICKET_PROTOCOL"
