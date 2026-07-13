#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MCP="$ROOT/anki-mcp-server"
ANKI_CONNECT="$ROOT/anki-connect"

python3 "$ROOT/scripts/render_compat_manifest.py"

if [[ ! -d "$MCP/node_modules" ]]; then
  (cd "$MCP" && npm ci)
fi
(cd "$MCP" && npm run type-check && npm run build)

mkdir -p "$ROOT/dist"
rm -f "$ROOT/dist/AnkiConnect-chat-review.zip"
(cd "$ANKI_CONNECT" && python3 -m zipfile -c "$ROOT/dist/AnkiConnect-chat-review.zip" plugin/*)

echo "Built MCP: $MCP/dist/main-stdio.js"
echo "Built AnkiConnect: $ROOT/dist/AnkiConnect-chat-review.zip"
