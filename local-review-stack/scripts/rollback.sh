#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TARGET="${ANKI_CONNECT_TARGET:-$HOME/Library/Application Support/Anki2/addons21/2055492159}"
CONFIG="${CODEX_CONFIG:-$HOME/.codex/config.toml}"
SKILL_TARGET="${CHAT_REVIEW_SKILL_TARGET:-$HOME/.codex/skills/chat-anki-review}"

if [[ "${1:-}" != "--apply" ]]; then
  echo "Dry run. Run $0 --apply after quitting Anki and Codex MCP processes."
  exit 0
fi
if pgrep -x anki >/dev/null 2>&1 || pgrep -x Anki >/dev/null 2>&1 || pgrep -f 'AnkiProgramFiles/.venv/bin/python -c import aqt' >/dev/null 2>&1; then
  echo "Quit Anki before rollback." >&2
  exit 1
fi

anki_backup="${ANKI_CONNECT_BACKUP:-$(find "$ROOT/backups/anki-connect" -mindepth 1 -maxdepth 1 -type d 2>/dev/null | sort | head -n 1)}"
codex_backup="${CODEX_BACKUP:-$(find "$ROOT/backups/codex" -mindepth 1 -maxdepth 1 -type d 2>/dev/null | sort | head -n 1)}"
test -n "$anki_backup" && test -f "$anki_backup/__init__.py"
test -n "$codex_backup" && test -f "$codex_backup/config.toml"

failed="$ROOT/backups/failed-install-$(date -u +%Y%m%dT%H%M%SZ)"
if [[ -d "$TARGET" ]]; then mv "$TARGET" "$failed"; fi
cp -R "$anki_backup" "$TARGET"
cp "$codex_backup/config.toml" "$CONFIG"
python3 "$ROOT/scripts/update_codex_config.py" "$CONFIG" "$ROOT/anki-mcp-server/dist/main-stdio.js"
if [[ -d "$codex_backup/chat-anki-review" ]]; then
  rm -rf "$SKILL_TARGET"
  cp -R "$codex_backup/chat-anki-review" "$SKILL_TARGET"
fi

echo "Rollback restored the previous AnkiConnect, Codex config, and skill."
echo "Restart Anki and Codex, then run a disposable verification."
