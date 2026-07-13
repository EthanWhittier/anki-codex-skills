#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CONFIG="${CODEX_CONFIG:-$HOME/.codex/config.toml}"
MCP_PATH="$ROOT/anki-mcp-server/dist/main-stdio.js"
SKILL_TARGET="${CHAT_REVIEW_SKILL_TARGET:-$HOME/.codex/skills/chat-anki-review}"
BACKUP_ROOT="$ROOT/backups/codex"

if [[ "${1:-}" != "--apply" ]]; then
  printf '[mcp_servers.anki-mcp]\ncommand = "node"\nargs = ["%s"]\n' "$MCP_PATH"
  echo "Dry run. Run $0 --apply to back up and update Codex config and the chat-review skill."
  exit 0
fi

test -f "$MCP_PATH"
timestamp="$(date -u +%Y%m%dT%H%M%SZ)"
backup="$BACKUP_ROOT/$timestamp"
mkdir -p "$backup"
cp "$CONFIG" "$backup/config.toml"
if [[ -d "$SKILL_TARGET" ]]; then
  cp -R "$SKILL_TARGET" "$backup/chat-anki-review"
fi

python3 "$ROOT/scripts/update_codex_config.py" "$CONFIG" "$MCP_PATH"
mkdir -p "$(dirname "$SKILL_TARGET")"
rm -rf "$SKILL_TARGET"
cp -R "$ROOT/chat-anki-review-skill" "$SKILL_TARGET"

echo "Updated $CONFIG"
echo "Installed chat-review skill at $SKILL_TARGET"
echo "Backup: $backup"
echo "Restart Codex now so it loads the consolidated MCP path and updated skill."
