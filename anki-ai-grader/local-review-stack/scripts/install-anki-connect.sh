#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SOURCE="$ROOT/anki-connect/plugin"
TARGET="${ANKI_CONNECT_TARGET:-$HOME/Library/Application Support/Anki2/addons21/2055492159}"
BACKUP_ROOT="$ROOT/backups/anki-connect"

if [[ "${1:-}" != "--apply" ]]; then
  echo "Dry run. Would back up $TARGET and install $SOURCE"
  echo "Run $0 --apply to install. Quit Anki first."
  exit 0
fi

if pgrep -x anki >/dev/null 2>&1 || pgrep -x Anki >/dev/null 2>&1 || pgrep -f 'AnkiProgramFiles/.venv/bin/python -c import aqt' >/dev/null 2>&1; then
  echo "Refusing to install while Anki is running. Quit Anki and retry." >&2
  exit 1
fi

timestamp="$(date -u +%Y%m%dT%H%M%SZ)"
backup="$BACKUP_ROOT/$timestamp"
mkdir -p "$BACKUP_ROOT" "$(dirname "$TARGET")"

if [[ -e "$TARGET" ]]; then
  mv "$TARGET" "$backup"
  if [[ ! -f "$backup/__init__.py" ]]; then
    echo "Backup verification failed; restoring previous add-on." >&2
    mv "$backup" "$TARGET"
    exit 1
  fi
fi

if ! cp -R "$SOURCE" "$TARGET"; then
  rm -rf "$TARGET"
  if [[ -d "$backup" ]]; then
    mv "$backup" "$TARGET"
  fi
  echo "Install failed; previous add-on restored." >&2
  exit 1
fi

test -f "$TARGET/__init__.py"
test -f "$TARGET/chat_review_compat.json"
echo "Installed maintained AnkiConnect at $TARGET"
if [[ -d "$backup" ]]; then
  echo "Backup: $backup"
fi
echo "Restart Anki before capability verification."
